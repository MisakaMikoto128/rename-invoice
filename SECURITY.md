# 安全策略

## 数据隐私

本工具完全在本地运行，**不会上传任何数据**：

- ✅ 不联网（核心脚本零网络调用）
- ✅ 不收集任何用户信息或文件内容
- ✅ 不读取除指定 PDF 外的其他文件
- ✅ 仅修改：你指定的 PDF 文件名 + 工具目录下的 `rename_invoice.log`
- ✅ 注册表修改限于 `HKCU\Software\Classes\...` 三处，可用 `uninstall_context.bat` 完整移除

## 报告漏洞

如果你发现可能的安全问题——例如：

- 路径穿越（恶意文件名让脚本写入预期外的位置）
- 命令注入（特殊文件名让 cmd / PowerShell 执行额外命令）
- 注册表权限提升
- 财务可靠性绕过（构造能让校验过关但金额错误的 PDF）

**请不要**直接开 public issue。请通过以下方式联系我们：

- 邮件：`[在你的 GitHub 个人页公开邮箱]`
- 或者使用 GitHub 的 [Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)

我们会在 7 个工作日内回复。修复发布前，请先不要公开漏洞细节。

## 支持的版本

| 版本 | 状态 |
|------|------|
| 0.1.x | ✅ 当前版本，安全修复持续支持 |

## 用户须自行核对

⚠️ **重要免责**：

本工具尽最大努力保证金额提取准确（三层校验），但**不对因使用本工具产生的任何财务后果负责**。

- 报销/对账前请自行核对金额
- 工具检测到的"失败"文件**必须**人工处理
- 如果你的工作流对正确率要求 > 99.99%，请在批量处理后随机抽查
