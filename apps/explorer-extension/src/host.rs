//! invoice-ext-host.exe — 稀疏 MSIX 包的占位可执行文件。
//!
//! AppxManifest 的 <Application> 要求包内有真实存在的 Executable;
//! 本扩展通过 AppListEntry="none" 隐藏应用条目, 这个 exe 永远不会被
//! 用户或系统启动。别往里加逻辑 — 真正的功能在 invoice_shext.dll。

fn main() {}
