# 贡献指南

感谢你考虑为 rename-invoice 贡献代码！本项目的核心价值是**财务可靠性**，所以贡献流程会比一般工具项目更严格一些。

## 我可以贡献什么？

我们尤其欢迎以下贡献：

- 🐛 **Bug 报告**：发票样本无法正确识别的实际案例
- 💡 **新发票格式支持**：新版票据格式、其他类型的发票（火车票、机票等）
- ✅ **测试用例**：增加 `test_parser.py` 的边界覆盖
- 📝 **文档改进**：使用说明、故障排查
- 🌐 **国际化**：英文文档、其他财务格式（如港澳台、海外）

## 开发环境

```bash
git clone <你的 fork 地址> rename_invoice
cd rename_invoice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 代码改动前必读

### 1. 财务可靠性优先

这个工具一旦把金额提取错（比如 980.10 当成 98.01），用户会真的损失钱。所以：

- **绝不允许"试一下能不能猜对"的代码**
- 任何提取逻辑必须能解释"为什么这一步是可靠的"
- 校验失败时**保留原文件名**永远比"尝试改名"安全
- 加新的提取规则时，必须同时加单元测试

### 2. 单元测试是底线

```bash
python test_parser.py
```

必须看到 `15 passed, 0 failed`（或更多）。

提交涉及金额解析的 PR **必须**：
- 加新测试用例覆盖你的改动
- 不能让现有测试失败

### 3. 跨平台编码注意事项

本项目踩过不少 Windows 编码坑，请务必遵守：

| 文件类型 | 编码 | 行尾 | 备注 |
|---------|------|------|------|
| `*.py`   | UTF-8 | LF | Python 3 默认 |
| `*.bat`  | ASCII（不允许中文） | CRLF | cmd 对中文注释解析有 bug，用 `::` 不要用 `rem` |
| `*.ps1`  | **UTF-8 with BOM** | CRLF | PowerShell 5.1 无 BOM 时按 ANSI 误读，**这一条破坏会导致脚本报语法错误** |
| `*.reg`  | UTF-16 LE | CRLF | Windows 注册表编辑器要求 |

`.gitattributes` 已经为你锁定行尾，但 BOM 需要你提交前自己确认：

```bash
python -c "import sys; p=sys.argv[1]; print('BOM' if open(p,'rb').read(3)==b'\xef\xbb\xbf' else 'NO BOM')" install_context.ps1
```

### 4. YAGNI 原则

工具的成功靠**不做什么**。请不要提交：

- ❌ GUI（已决定不做，命令行 + 右键菜单足够）
- ❌ OCR 集成（OCR 会破坏可靠性保证）
- ❌ 撤销功能（重命名已可逆，且日志够用）
- ❌ 配置文件、命令行参数 5+ 个（会膨胀）
- ❌ 对你"觉得可能要"但还没用户明确需求的功能

如果不确定，先开 issue 讨论。

## 提交 PR 流程

1. **先开 issue**（除非是显而易见的小修小补）
2. **基于 main 创建特性分支**：`feat/xxx` / `fix/xxx` / `docs/xxx`
3. **运行单元测试**确保通过
4. **更新 `CHANGELOG.md` 的 `[Unreleased]` 区段**
5. 提交时使用[约定式提交](https://www.conventionalcommits.org/zh-hans/v1.0.0/)：
   ```
   fix: 修复 12345.67 元的中文大写解析
   feat: 支持火车票电子发票
   docs: 补充 Windows 11 右键菜单截图
   test: 增加百万级金额边界用例
   ```
6. 提 PR，描述改动 + 关联 issue

## Bug 报告须知

提交无法识别的发票样本时：

⚠️ **务必脱敏**：把发票号码、公司名、纳税人识别号涂黑。**金额字段保留原样**，否则我们没法复现。

最好附上：
- 错误信息（控制台输出截图）
- `rename_invoice.log` 中对应的失败记录
- 你预期的金额是多少
