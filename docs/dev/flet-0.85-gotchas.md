# Flet 0.85 踩坑日记 — 系统托盘 / 关闭确认 / 单实例 撤回记录

**日期**: 2026-05-12
**版本**: Flet 0.85.0 / Python 3.11 / Windows 11
**结论**: 系统托盘 + 第一次关闭弹框 + 单实例保护这一套「QQ/微信级别」常驻型行为, 在 Flet 0.85 上**做不出来**。撤回, 只保留开机自启。

后续维护者如果想再尝试这个特性, 看完下面这些坑再决定。

---

## 撤回了什么

- `accounting/tray.py` — pystray 守护线程封装
- `accounting/single_instance.py` — socket 占座 + IPC
- `accounting/window_manager.py` — close/minimize 状态机 + 关闭对话框路由
- `accounting/_win32_window.py` — Win32 ShowWindow 绕过 Flet
- `accounting/ui/app.py` 里的 tray 接线 + `prevent_close=True` + `--silent` flag
- `accounting/ui/dialogs.py` 里的 `show_close_confirm_dialog` + `show_about_dialog` + 设置页「关闭时」下拉
- `accounting/settings.py` 的 `KEY_CLOSE_ACTION` 常量
- `tests/test_single_instance.py` + `tests/test_window_manager.py`
- `requirements.txt` 的 `pystray` + `Pillow`

**保留**: `accounting/autostart.py` (winreg HKCU\\Run, 验证可工作) + 对应的 `tests/test_autostart.py` + 设置页里的「开机启动」开关。

设计文档 `docs/superpowers/specs/2026-05-11-tray-autostart-close-confirm-design.md` 和实施计划 `docs/superpowers/plans/2026-05-11-tray-autostart-close-confirm.md` 留作历史档案。

---

## 踩到的坑 (按发现顺序)

每一个都让前面的"修复"看起来对了, 但后面又冒出新问题。

### 1. `page.show_dialog(SnackBar)` 在已开的 AlertDialog 上面会弹掉父对话框

设置页里 `on_autostart_change` 报错时用 `page.show_dialog(ft.SnackBar(...))` 弹错误提示, SnackBar 自动消失时 Flet 内部的 `pop_dialog()` 会从对话框栈顶弹出, 把**底下的 settings 对话框**一起弹掉, 不是只弹掉 SnackBar。

**修复**: 用 `page.open(ft.SnackBar(...))` (overlay 机制, 独立于对话框栈)。

### 2. `page.window.destroy()` / `to_front()` 是 `async def`

源码 (`flet/controls/core/window.py:355` 之类):

```python
async def destroy(self):
    await self._invoke_method("destroy")
```

我们一开始 `WindowManager.quit()` 里直接 `self.page.window.destroy()` —— 返回一个 coroutine, 没人 `await` —— **窗口永远不会被销毁**。表现: ✕、对话框退出、托盘退出三条路径全失效。

**修复**: 用 `self.page.run_task(self.page.window.destroy)` 把 async 方法投到事件循环。

### 3. `page.run_thread(fn)` 不是把 `fn` 投到主事件循环线程, 而是投到 executor 线程池

Flet 0.85 文档没明确说这点。`page.run_thread` 内部走 `loop.call_soon_threadsafe(loop.run_in_executor, executor, fn)` —— 跑在子线程上, 不是事件循环线程。

后果: 我们的托盘菜单回调 `lambda: page.run_thread(tray_quit)` 在 executor 线程上调 `cleanup()` → `state.close()` → sqlite 连接关闭。sqlite 连接在主线程创建, 关闭时报 `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`。

**修复**: 包一层 `async def _wrap(): fn()` 然后 `page.run_task(_wrap)`。run_task 才是真的回主线程。

### 4. `page.window.visible` 是启动时标志, 运行时改它没效果

源码 docstring (`flet/controls/core/window.py:294`):

```python
visible: bool = True
"""
Whether to make the app window visible.

Can be of use when the app starts as hidden.   # ← 这句
"""
```

「Can be of use when the app **starts** as hidden」—— 暗示运行时 mutation 无效。实测: 运行时设 `page.window.visible = False` + `page.update()` 窗口不消失。

**没有有效修复方式 (Flet 层面)**。Window 类**没有** `hide()` / `show()` / `restore()` 方法 —— 只有 `destroy / close / center / to_front / start_dragging / start_resizing / wait_until_ready_to_show`。

### 5. `page.window.minimized = True` 单向能用, 反向不可靠

`minimized` 是运行时可读写的, 但是把 `minimized=True` + `skip_task_bar=True` 一起设, 后续设 `minimized=False` 想恢复, 窗口卡死在最小化状态, 没有 taskbar 入口, 不可达。

试过的所有变种都失败:
- 同时一次 `page.window.update()` —— 卡死
- 分两次 `update()` (先 `skip_task_bar=False` 后 `minimized=False`) —— 卡死
- 加 `page.run_task(page.window.to_front)` 兜底 —— 卡死

**结论**: Flet 0.85 的 Window 属性系统不能可靠地实现"隐藏到托盘 + 从托盘恢复"。

### 6. 试 Win32 `ShowWindow(SW_HIDE/SW_RESTORE)` 绕过 Flet —— 还是失败, 因为 hwnd 找不到

直接用 ctypes 调 user32 应该是金标。但 `EnumWindows` 按 `os.getpid()` 过滤, 0 个结果。原因:

> **Flet 0.85 desktop mode 把 Flutter 窗口跑在独立子进程 `flet.exe` 里**, OS 窗口 PID 是子进程 PID, 不是我们 Python 进程 PID。

诊断脚本验证:
```
python parent (pid=16376) → flet.exe child (pid=25080)
└─ HWND=0x49021C class=FLUTTER_RUNNER_WIN32_WINDOW
```

**(部分)修复**: 用 `kernel32.CreateToolhelp32Snapshot` 走进程树, 找类名 = `FLUTTER_RUNNER_WIN32_WINDOW` + PID 在我们子孙集合里的窗口。

### 7. `ft.run(main)` 何时返回, 行为不可预测

`ft.run(main)` 内部:
```python
fvp, pid_file = await open_flet_view_async(...)
with contextlib.suppress(Exception):
    await fvp.wait()
close_flet_view(pid_file)
```

`fvp` 是 `flet.exe` 子进程。`fvp.wait()` 等它退出。但 `flet.exe` 是 launcher 还是窗口本体, 不同环境表现不同 —— 实测 (Python 父进程视角):

- **简单 main (只 `page.add(Text)`)** : ft.run 阻塞到用户关闭窗口为止 ✓
- **main + `prevent_close=True`**: ft.run 阻塞 (用户必须 Ctrl+C 才退) ✓
- **main + `prevent_close=True` + `on_event` handler**: ft.run 阻塞 ✓
- **main + 完整 tray 接线**: 实测某些机器上 ft.run **立即返回**, 窗口变孤儿, prevent_close 卡死, 不可关闭

返回时机依赖 launcher 进程是否 detach。在测试机上一致阻塞, 在用户机器上立即返回 —— 没找到为什么。

另外 `close_flet_view(pid_file)` 末尾调 `os.kill(fvp_pid, signal.SIGKILL)` —— **`signal.SIGKILL` 在 Windows 上根本不存在**, AttributeError 被 try/except 吞掉, 孤儿窗口不会被清掉。

### 8. ★ **真正的根因 (其他 7 个坑都是症状/绕路)**: `WindowEvent` 字段是 `e.type` 不是 `e.data`

源码 (`flet/controls/core/window.py:106-114`):
```python
@dataclass
class WindowEvent(Event[EventControlType]):
    """Payload for `flet.Window.on_event` callbacks."""
    type: WindowEventType
    """Native event kind emitted by the desktop window backend."""
```

`e.type` 是 `WindowEventType` 枚举 (`.value` 取字符串)。**`e.data` 永远是 `None`**。

我们的 `WindowManager.on_window_event` 一路写:
```python
if e.data == "minimize": ...
elif e.data == "close": ...
```

**永远不命中**。所以 `prevent_close=True` 把关闭事件拦住后, handler 跑了但啥也不干, 窗口卡死打不开关不掉 —— 这看起来像「最小化卡死」、「Win32 hide 失败」、「Flutter window 找不到」, 但**全部都是同一个 bug**: 事件根本没被识别, hide_to_tray / _handle_close / show_from_tray **从来没被调用过**。

诊断脚本里加了 `print(e.data)` 打出来都是 `None` —— 这才是关键线索。

**修复**: `kind = getattr(getattr(e, "type", None), "value", None) or getattr(e, "data", None)`。

### 9. 撤回之后的尾巴: 残留的窗口几何 + 注册表项

撤回 tray 代码之后, 用户回报"主窗口仍然不显示"。代码层已经清干净, 实际是**数据残留**:

1. `%APPDATA%\rename-invoice\settings.json` 里被上一轮的 `minimized=True` 测试污染:
   ```json
   "window_width":  "157.0",
   "window_height": "35.5",
   "window_left":   "-16000.0",   ← 屏幕外
   "window_top":    "-16000.0"
   ```
   `(-32000, -32000)` 是 Windows 给最小化窗口记录的位置 (DPI scale 后变成 -16000)。每次启动 `app.py` 读这些值, 把窗口放到屏幕外 —— 看起来"主窗口不显示", 其实是被放到看不见的地方。

2. 注册表 `HKCU\...\Run\AccountManager` 里残留 `python.exe --silent` —— 因为 `autostart.enable()` 在 dev mode 下取 `sys.executable`, 写入的是 Python 解释器, 不是 AccountManager.exe。重启电脑触发这条 Run 项, python.exe 不认 `--silent`, 直接退出, 看似"开机启动失效"。

**修复**: 在 `app.py` 加几何 sanity check (拒绝 < 400x300 或 left/top < -1000), 在 `save_window_state()` 加同样的防御 (异常状态不存); `autostart.enable()` 拒绝非 .exe 或 python.exe 路径。

**教训**: 撤回失败特性时, 不光要回退**代码**, 还要清理那段代码留下的**状态** (settings.json, 注册表, 缓存等)。代码是无状态的, 这些副作用却是持久的。

### 10. 真正解决了 #8 之后, 仍然撤回, 因为信任已经崩了

修复 `e.type` 之后, 理论上整套应该能跑。但用户已经被反复"修好了 → 又坏了"折磨多轮, 决定撤回。

技术上不是没救, 但 Flet 0.85 这个版本上做"常驻型 + 托盘"的代价 (踩坑 + 验证回归) **远大于功能价值**。开机自启就够了。

---

## 通用经验教训

### a. Flet 0.85 的 Window API 是半成品

- 没有 `hide/show/restore` 方法
- `visible` 是启动专用
- `minimized` 反向恢复不可靠
- 事件字段在 `e.type` 不在 `e.data`, 但 docstring 里没把这点写清楚
- 子进程 + 异步方法 + 线程模型, 全部要看源码才知道

### b. Unit test 通过 ≠ 真能用

撤回的代码有 21 个单元测试全绿。但全部是 mock 出来的, 假设 `page.window.minimized = True` 真的会让窗口最小化、`page.run_thread(fn)` 真的会跑 `fn` —— 这些假设全部不成立。

集成测试和真机 smoke 才暴露了这些 bug。**Flet/GUI 这类代码, 单元测试只能验证逻辑分支, 不能替代真机走一遍**。

### c. 多个 bug 互相掩盖时, 修一个会让症状变形但不会消失

`e.type` 这个真正的根因, 在前 8 轮"修复"中始终没暴露 —— 因为:
- 我们改了 `destroy()` 调用方式, 用户继续报"无法关闭" → 误以为是窗口属性问题
- 改了 `visible` → `minimized`, 用户继续报"卡死" → 误以为是 Flet 属性 bug
- 加了 Win32 ShowWindow, 用户继续报"无法恢复" → 误以为是 hwnd 查找问题

实际上从一开始 `wm.on_window_event` 就没匹配过任何事件, `hide_to_tray` 从来没被调用 —— 所以所有 hide-path 修复都没在路径上。

**诊断脚本里 `e.data == None` 才是直接证据**。如果第一轮就让用户打印事件实参, 一天就能定位。

---

## 如果将来要再做

等 Flet 升 1.x 之后再考虑。建议:

1. 先验证 Flet 那个版本的 Window 提供 `hide()` / `show()` 显式方法
2. 验证 `WindowEvent` 的字段是否标准化
3. 验证 `ft.run` 阻塞行为是否一致
4. 用「真机 smoke checklist + 单元测试」组合, 不要只靠 mock

或者: 直接用 Tauri / Electron / pywebview, 这类成熟桌面框架对系统托盘有 first-class 支持, 不需要绕 Win32。
