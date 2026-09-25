# 托盘 / 开机启动 / 关闭确认 — 设计文档

**版本目标**：v1.0.2（暂定，v1.0.1 即将合并 main）
**分支**：在 `feat/v1.0.1-smaller-exe` 合并后新开 `feat/v1.0.2-tray-autostart`
**日期**：2026-05-11

## 1. 目标

把 AccountManager 从「普通桌面窗口程序」升级到「常驻型工具」体验，对齐 QQ / 微信 / Discord 这类常用工具的标准行为：

- **最小化** ─ → 隐藏到系统托盘（任务栏也不留按钮）。
- **关闭** ✕ → 首次询问，用户可选「隐藏到托盘」「退出」，并勾选「☑ 记住本次选择」持久化。
- **托盘图标** → 左键唤起主窗；右键菜单 = `显示主界面` / `设置...` / `关于` / `退出`。
- **开机启动** → 设置里开关，默认关；开启后静默启动到托盘（无主窗弹出）。
- **单实例** → 第二次启动唤起已有窗口，自己退出。
- 「关闭时」行为可在设置里随时改回「询问」，不需要手动改 settings.json。

## 2. 范围

**包含：**

- 4 个新模块（tray / single_instance / autostart / window_manager）。
- 现有 `dialogs.py` 扩展：设置页加两项 + 新增「关闭确认」对话框 + 新增「关于」对话框。
- `requirements.txt` 加 `pystray` + `Pillow`。
- `build.py` 打包 tray 图标资源 + hidden-imports 调整。

**明确不包含（YAGNI）：**

- 跨平台托盘支持（macOS / Linux）——本项目 Windows-only 分发。
- 托盘消息通知（NotifyIcon balloon）——一期不做，二期看需求。
- 全局快捷键（Ctrl+Shift+X 唤起）——一期不做。
- 单实例的「命令转发」（第二次启动带文件参数让一号打开）——一期只发 SHOW。
- 自启动时的延迟（"开机后 30 秒再起"）——直接由 Run 键拉起，不做调度。

## 3. 技术选型

| 维度 | 选型 | 理由 |
|---|---|---|
| 托盘库 | `pystray>=0.19` + `Pillow>=10` | 跨平台稳定、社区活跃；Win 后端走 Shell_NotifyIcon。打包后 exe 约 +5 MB。 |
| 单实例机制 | `127.0.0.1:47821` socket 占座 + 双用作命令通道 | 零新依赖、零残留文件、崩溃后 OS 自动回收端口。 |
| Flet ↔ 守护线程 | `page.run_thread(fn)` | Flet 0.85 官方机制，pystray / socket listener 的回调统一走它进主线程。 |
| 开机自启 | `winreg` 写 `HKCU\...\Run`，值 = `"...AccountManager.exe" --silent` | 标准库、无管理员权限、卸载干净；用户在「任务管理器→启动」能看到。 |
| 设置存储 | 沿用 `accounting/settings.py` 的 JSON | 已有完善的 get/set + 默认值机制，无需引入新表。 |
| 「静默启动」标志 | 命令行 `--silent`，**不**存 settings | 描述「本次启动方式」而非「用户偏好」，避免双数据源。 |

## 4. 架构

```
┌──────────────────────────────────────────────────────────┐
│ AccountManager.exe  (单实例,通过本地 socket 47821 占座)   │
│                                                          │
│   主线程 (Flet event loop)                               │
│   ├─ page.window.on_event  ──►  WindowManager            │
│   │                              ├─ hide_to_tray()       │
│   │                              ├─ show_from_tray()     │
│   │                              ├─ quit()               │
│   │                              └─ _handle_close()      │
│   │                                                      │
│   └─ render_main / render_project / ... (现有逻辑不变)   │
│                                                          │
│   守护线程 1: pystray.Icon.run() (TrayController 内部)   │
│       菜单回调 ── page.run_thread() ──► 主线程方法       │
│                                                          │
│   守护线程 2: single_instance socket listener            │
│       accept() → recv "SHOW" → page.run_thread(on_show)  │
└──────────────────────────────────────────────────────────┘

  启动序列:
    parse_args(--silent)
      ↓
    single_instance.acquire_or_signal_existing()
      ├─ 失败 (端口已被一号占) → connect+send "SHOW" → sys.exit(0)
      └─ 成功 (返回 listening sock)
            ↓
         ft.run(main):
            page.window.prevent_close = True   # ← 不可省略
            wm = WindowManager(page, on_real_quit=cleanup)
            tray = TrayController(on_show=wm.show_from_tray,
                                  on_settings=open_settings,
                                  on_about=show_about,
                                  on_quit=wm.quit)
            tray.start()
            serve_show_requests(sock, on_show=wm.show_from_tray)
            if silent_flag: wm.hide_to_tray()
            page.window.on_event = wm.on_window_event
```

## 5. 组件清单

### 5.1 `accounting/tray.py` (≈80 行,新增)

```python
class TrayController:
    def __init__(self,
                 on_show: Callable[[], None],
                 on_settings: Callable[[], None],
                 on_about: Callable[[], None],
                 on_quit: Callable[[], None]) -> None: ...

    def start(self) -> None:
        """起守护线程跑 pystray.Icon.run()。失败时 log warning,不抛。"""

    def stop(self) -> None:
        """icon.stop(); thread.join(timeout=2.0)。"""
```

- 图标：通过 `_resource_path()` 解析 `assets/icon-256.png`，兼容 `sys._MEIPASS`（onefile）和源码路径。打开失败 → PIL 生成 32×32 占位图（深色背景 + 大写 "A"），保证 tray 永远能起。
- 菜单（pystray Menu）：
  - `显示主界面` (default=True, 粗体显示)
  - `设置...`
  - `关于`
  - `─` (separator)
  - `退出`
- 左键单击托盘图标 = 触发默认项 = `on_show()`。pystray 的 `default=True` 自动绑定。
- 对 Flet 零依赖：4 个回调全部由调用方传入，便于单测。

### 5.2 `accounting/single_instance.py` (≈60 行,新增)

```python
PORT = 47821  # 本地回环固定端口

def acquire_or_signal_existing() -> Optional[socket.socket]:
    """
    返回:
      - 占座成功 → 返回已 bind 的 socket(调用方 listen + 启动 server 线程)
      - 占座失败 → 向已有实例发 b"SHOW\\n",返回 None
      - 端口被非本程序占用 (e.g. connect 失败) → log warning,返回新 socket
        bind 失败时退一步绑随机端口 → 单实例保护降级,但应用继续启动
    """

def serve_show_requests(sock: socket.socket,
                        on_show: Callable[[], None]) -> None:
    """spawn 守护线程: 循环 accept() → recv() → 含 b'SHOW' 即调 on_show()。"""
```

- 监听 `127.0.0.1` 不监听公网。
- 协议简单：行分隔，目前只识别 `SHOW`，未来要加命令（如 `OPEN <path>`）也兼容。
- recv buffer 上限 1024 字节，丢弃多余数据避免 DoS。

### 5.3 `accounting/autostart.py` (≈40 行,新增)

```python
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AccountManager"

def is_enabled() -> bool: ...

def enable(exe_path: Path) -> None:
    """winreg.SetValueEx(HKCU\\...\\Run, APP_NAME, REG_SZ,
       '"<exe_path>" --silent')。失败抛 OSError。"""

def disable() -> None:
    """winreg.DeleteValue。值不存在视为成功。"""

def current_exe_path() -> Path:
    """sys.executable 若是 onefile bundle → 用它;否则 (源码运行) 抛错。"""
```

- 全部 `HKEY_CURRENT_USER`，无需管理员。
- 路径每次 `enable()` 都重写，用户挪了 exe 重新开关一次即可。

### 5.4 `accounting/window_manager.py` (≈100 行,新增)

```python
class WindowManager:
    def __init__(self, page: ft.Page, on_real_quit: Callable[[], None]):
        self.page = page
        self.on_real_quit = on_real_quit
        self._closing = False  # 防止 quit() 期间又触发 close 事件

    def hide_to_tray(self) -> None:
        self.page.window.visible = False
        self.page.window.skip_task_bar = True
        self.page.update()

    def show_from_tray(self) -> None:
        self.page.window.skip_task_bar = False
        self.page.window.visible = True
        self.page.window.to_front()
        self.page.update()

    def quit(self) -> None:
        if self._closing: return
        self._closing = True
        self.on_real_quit()           # 保存窗口状态 + 关 db
        self.page.window.destroy()     # 真正销毁,触发进程退出

    def on_window_event(self, e):
        if e.data == "minimize":
            self.hide_to_tray()        # 用户决定: 最小化 = 隐藏到托盘
        elif e.data == "close":
            self._handle_close()

    def _handle_close(self):
        action = settings.get(KEY_CLOSE_ACTION, "ask")
        if action == "hide":  self.hide_to_tray(); return
        if action == "exit":  self.quit(); return
        self._show_close_dialog()      # action == "ask"

    def _show_close_dialog(self):
        # 三按钮: [隐藏到托盘] [退出] [取消]
        # + 复选框 [☑ 记住本次选择] (默认勾选)
        # 取消 = 关闭对话框,什么都不做(窗口保持原样)
        ...
```

**重点：Flet 0.85 必须先在 `main()` 设 `page.window.prevent_close = True`**，否则 ✕ 触发原生关闭，我们的 handler 跑了也白搭。

### 5.5 现有文件改动

#### `accounting/ui/app.py`

```python
def main(page: ft.Page):
    # 现有 page.title / window 尺寸恢复保持不变
    page.window.prevent_close = True             # ★ 新增

    # state 初始化保持不变
    state = AppState(...); state.init()

    def cleanup():                               # 替换原 on_close
        save_window_state()
        state.close()
        tray.stop()

    wm = WindowManager(page, on_real_quit=cleanup)

    def open_settings_from_tray():
        wm.show_from_tray()                      # 设置弹框必须主窗在
        open_settings()                          # 复用现有 open_settings()

    def show_about():
        wm.show_from_tray()
        show_about_dialog(page)                  # 新增 dialog

    tray = TrayController(
        on_show=wm.show_from_tray,
        on_settings=open_settings_from_tray,
        on_about=show_about,
        on_quit=wm.quit,
    )
    tray.start()

    serve_show_requests(_listener_sock,          # 由 entry point 传入
                        on_show=wm.show_from_tray)

    page.window.on_event = wm.on_window_event

    # silent flag 由 entry point 传入
    if silent_flag:
        wm.hide_to_tray()

    # 现有 render_main() / render_project() 全部保留
    ...

# entry point 改动:
if __name__ == "__main__":
    silent_flag = "--silent" in sys.argv
    sock = single_instance.acquire_or_signal_existing()
    if sock is None:
        sys.exit(0)                              # 二号实例,把唤起信号发出去就走
    # 把 sock 和 silent_flag 通过闭包 / 模块级变量传给 main
    ft.run(lambda p: main(p, sock, silent_flag))
```

#### `accounting/settings.py`

```python
# 新增常量
KEY_CLOSE_ACTION = "close_action"            # "ask" | "hide" | "exit"  默认 "ask"
KEY_AUTOSTART_ENABLED = "autostart_enabled"  # "0" | "1"  默认 "0"
```

#### `accounting/ui/dialogs.py`

`show_settings_dialog` 增补两块（在「外观」「项目存储根目录」之间插入新章节「行为」）：

- 「关闭时」`Dropdown`：选项 = `[询问 (默认), 隐藏到托盘, 直接退出]`，change 时 `settings.set_value(KEY_CLOSE_ACTION, ...)`。
- 「开机启动」`Switch`：change 时调 `autostart.enable/disable`，失败弹 SnackBar 并回退 Switch 状态。

新增 `show_close_confirm_dialog(page, on_hide, on_quit)`：
- 标题 `关闭 AccountManager`
- 正文 `关闭主窗口后,应用继续在系统托盘运行吗?`
- 复选框 `☑ 记住本次选择(可在设置中修改)`(默认勾选)
- 按钮：`隐藏到托盘`(主按钮) / `退出` / `取消`

新增 `show_about_dialog(page)`：
- 标题 `关于 AccountManager`
- 内容：版本号(从 `__version__` 或 git tag 读)、作者、项目主页(GitHub URL)、许可证。

#### `requirements.txt`

```
pystray>=0.19,<1.0
Pillow>=10.0,<12.0
```

#### `build.py`

- `--add-data "assets/icon-256.png;assets"` (pystray 运行时要的 PNG)。
- 检查 EXCLUDES 列表，确保 `Pillow` / `PIL` 不在里面。
- `--hidden-import pystray._win32`（pystray 后端按平台动态导入，PyInstaller 抓不到）。
- 更新打包脚本 docstring 里的预期大小（75 → ~80 MB）。

## 6. 数据流

### 6.1 启动流程（用户双击 exe）

```
sys.argv 解析 → silent_flag
single_instance.acquire_or_signal_existing()
  ├─ 占座失败 → 连 47821 发 "SHOW" → sys.exit(0)         # 二号实例
  └─ 占座成功 (sock listening)
        ↓
     ft.run(main(page, sock, silent_flag))
        ↓
     page.window.prevent_close = True
     wm = WindowManager(...)
     tray = TrayController(...); tray.start()
     serve_show_requests(sock, on_show=wm.show_from_tray)
     page.window.on_event = wm.on_window_event
     if silent_flag: wm.hide_to_tray()
     render_main()
```

### 6.2 关闭流程（用户点 ✕）

```
page.window.on_event(e=Close)
  → wm._handle_close()
     ↓
  settings.get("close_action", "ask")
  ├─ "ask"   → show_close_confirm_dialog(page, on_hide, on_quit)
  │              用户点 [隐藏到托盘] + 记住 → settings.set("close_action", "hide")
  │                                       → wm.hide_to_tray()
  │              用户点 [退出]       + 记住 → settings.set("close_action", "exit")
  │                                       → wm.quit()
  │              不勾「记住」                 → 只执行,不写 settings
  │              [取消] → page.pop_dialog(), 窗口保持原样
  ├─ "hide"  → wm.hide_to_tray()
  └─ "exit"  → wm.quit()
```

### 6.3 最小化流程（用户点 ─）

```
page.window.on_event(e=Minimize)
  → wm.hide_to_tray()       # 跟 close→hide 一致, 不再问
```

### 6.4 托盘菜单流程

```
pystray 守护线程 → 用户右键 → 选「显示主界面」→ on_show 回调
  → page.run_thread(wm.show_from_tray)   # marshal 回主线程
  → page.window.visible=True / skip_task_bar=False / to_front()
```

### 6.5 第二个实例流程

```
用户双击 exe(已有一号在跑)
  → single_instance.acquire_or_signal_existing()
      socket().bind(47821) → OSError [WinError 10048]
      → 创建新 socket → connect(127.0.0.1, 47821) → send b"SHOW\n"
      → 返回 None
  → sys.exit(0)

一号实例侧:
  socket.accept() → conn.recv(1024) → b"SHOW\n" 命中
  → page.run_thread(on_show=wm.show_from_tray)
  → 用户看到主窗弹出
```

## 7. 错误处理

| 故障点 | 处理 |
|---|---|
| pystray 导入失败 / 启动异常 | log warning,跳过托盘。WindowManager 仍工作,关闭 = 退出。「设置→开机启动」开关置灰并提示「托盘不可用」。 |
| `icon-256.png` 不在 bundle 里 | 用 PIL 生成 32×32 占位图(深色 + "A")作为兜底,tray 仍能起。 |
| 47821 端口被非本程序占用 | bind 失败 → 退绑随机端口 → 单实例保护降级(第二个实例正常起,不再唤起一号)。log warning 但继续启动。 |
| `autostart.enable()` 抛 `PermissionError` | 设置页 Switch 弹回原状 + SnackBar `开机启动设置失败,请重启应用后重试`。 |
| `settings.json` 损坏 | 已有 `_load()` 异常吞掉返回 `{}`,新 key 走默认 `"ask"` / `"0"`。 |
| `quit()` 期间又收到 close 事件 | `_closing` 标志位幂等,第二次直接 return。 |
| `--silent` 启动但 tray 起不来 | 降级:`visible=False` 仍设上,但 `skip_task_bar` 取决于 tray 是否在。tray 没起→不设 skip_task_bar,用户能从任务栏找回窗口。 |
| `show_from_tray()` 时窗口已 destroy | `_closing` 已是 True → 早 return。 |

**原则：托盘 / 自启都是加分项，启动失败 → 降级，不阻塞应用主功能。**

## 8. 测试

### 8.1 单元测试（pytest，新增 file）

- **`tests/test_single_instance.py`**
  - mock `socket.socket`：占座成功路径 / 占座失败发送 SHOW 路径 / 端口被占用降级路径。
  - 断言：返回值、send 调用参数、不抛异常。
- **`tests/test_autostart.py`**
  - monkeypatch `winreg.OpenKey / SetValueEx / QueryValueEx / DeleteValue`。
  - 断言：`enable()` 传给 `SetValueEx` 的值包含 `--silent` 和 exe 绝对路径；`disable()` 调用 `DeleteValue`；`is_enabled()` 读不到值时返回 False。
- **`tests/test_window_manager.py`**
  - mock `page`（含 `window.visible / skip_task_bar / update / destroy`）+ mock `settings.get`。
  - 断言 `_handle_close()` 三态分支：`"hide"` → 调 `hide_to_tray`；`"exit"` → 调 `quit`；`"ask"` → 调 `_show_close_dialog`。
  - 断言 `_closing` 幂等：连续两次 `quit()` 只调一次 `on_real_quit`。
- **`tests/test_settings.py`** (扩展)
  - 加两条 case：`close_action` 默认 `"ask"`，`autostart_enabled` 默认 `"0"`。

**不单测：**

- `tray.TrayController` — pystray 后端在测试环境(无 GUI session)启不起来；其逻辑很薄(转发回调)，留给手动 smoke。
- `accounting/ui/app.py` 的 main wire-up — 经典集成层，单测价值低。

### 8.2 手动 smoke checklist（写进 BUILD.md）

1. 双击 exe → 主窗出现 → 托盘有图标 ✓
2. 点 ─ → 主窗消失，任务栏按钮消失，托盘图标仍在 ✓
3. 左键托盘图标 → 主窗弹出回前台 ✓
4. 点 ✕ → 弹「关闭确认」对话框 ✓
5. 选「隐藏到托盘」+ 不勾「记住」→ 隐藏；下次再点 ✕ 还弹 ✓
6. 选「退出」+ 勾「记住」→ 进程退出；重启 exe 后再点 ✕ 不弹对话框，直接退出 ✓
7. 设置→关闭时下拉改回「询问」→ 下次点 ✕ 又弹对话框 ✓
8. 设置→开机启动开关 ON → 重启电脑 → 桌面无窗口，托盘有图标 ✓
9. 已在托盘运行时双击 exe → 主窗弹出，无第二个进程 ✓（`tasklist | findstr AccountManager` 只一个）
10. 设置→开机启动开关 OFF → 重启电脑 → 应用不启动 ✓

### 8.3 回归测试

- 现有 86 个 pytest 全绿。
- 源码模式 `python -m accounting.ui.app` 走主流程不报错（开发期）。
- 打包后 `release\v1.0.2\AccountManager.exe` 走 8.2 全清单。

## 9. 实施顺序（供 writing-plans 参考）

预估 4 个增量 PR / commit 序列：

1. **基础设施层** — `single_instance.py` + `autostart.py` + `window_manager.py` + 对应单测。改 `settings.py` 加常量。不动 UI 不动 app.py。
2. **托盘层** — `tray.py` + `assets` 资源路径解析。不接 app.py，先靠手动跑一个独立 main 验通。
3. **集成层** — 改 `app.py` 把 1+2 串起来，加 `--silent` 处理，加 `prevent_close`。
4. **UI 层** — `dialogs.py` 加「关闭确认」对话框、「关于」对话框、设置页加两项。同步改 `build.py` / `requirements.txt` / `BUILD.md`。

每步独立可跑、独立可测。

## 10. 不做的事 / 已知限制

- **macOS / Linux 不支持**：本项目分发 Windows-only；`autostart.py` 直接 `winreg` 调用，非 Win 平台会 `ImportError`，设置项在非 Win 平台需置灰。一期连置灰都不做（用户只在 Win 上跑）。
- **「关于」对话框**仅静态信息，不做更新检查 / 不联网。
- **托盘菜单不显示账目状态**（如未报销笔数）—— 一期不做，避免引入「主线程 → 托盘线程」反向数据流。
- **`prevent_close` 在 Flet 0.85 的 macOS 行为可能不同** —— 不在范围内，无需测试。

## 11. 风险

| 风险 | 缓解 |
|---|---|
| Flet 0.85 `page.run_thread` 在某些情况下不调度（GitHub 上有零星报告） | 集成测试覆盖；如确认有 bug，退化为 `threading.Event` + Flet 侧轮询。 |
| pystray + PyInstaller onefile 资源路径在 `_MEIPASS` 下解错 | `_resource_path()` 助手统一处理；smoke checklist 第 1 条直接验证。 |
| AV 把 winreg 写 Run 键当可疑行为标记 | 自签名证书已经覆盖；真出问题就在 BUILD.md 加说明，引导用户白名单。 |
| 用户禁用了「Microsoft Defender SmartScreen 信誉检查」但 47821 端口被防火墙拦 | bind 127.0.0.1 在大部分防火墙规则下放行；如出问题降级到随机端口。 |
