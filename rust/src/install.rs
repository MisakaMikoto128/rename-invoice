//! Windows 右键菜单注册 / 卸载. 写到 HKCU, 不需要管理员.
//!
//! 三个挂载点:
//!   HKCU\Software\Classes\SystemFileAssociations\.pdf\shell\AddInvoicePrice
//!   HKCU\Software\Classes\Directory\shell\AddInvoicePrice
//!   HKCU\Software\Classes\Directory\Background\shell\AddInvoicePrice
//!
//! 命令: "<exe>" --silent [--summary] [--xlsx] "%1"  (background 用 %V)

#[cfg(windows)]
use anyhow::Context;
#[allow(unused_imports)]
use anyhow::{anyhow, Result};
#[cfg(windows)]
use std::path::PathBuf;

const KEY_NAME: &str = "AddInvoicePrice";
const MENU_TEXT: &str = "添加发票价格前缀";

#[cfg(windows)]
fn current_exe() -> Result<PathBuf> {
    std::env::current_exe().context("无法定位当前 .exe 路径")
}

#[cfg(windows)]
pub fn install(_summary: bool, _xlsx: bool) -> Result<()> {
    use std::io::{stdin, stdout, BufRead, Write};
    use winreg::enums::*;
    use winreg::RegKey;

    let exe = current_exe()?;
    let exe_str = exe.to_string_lossy().to_string();

    // 注册表右键 verb 用 rename-invoice-w.exe (windows 子系统, 0 cmd 闪窗)
    let exe_dir = exe
        .parent()
        .ok_or_else(|| anyhow!("无法定位 .exe 父目录"))?;
    let silent_exe = exe_dir.join("rename-invoice-w.exe");
    if !silent_exe.exists() {
        return Err(anyhow!(
            "找不到 rename-invoice-w.exe (静默执行用): {}\n\
             请确保 release zip 解压完整, 它应该和 rename-invoice.exe 在同一目录.",
            silent_exe.display()
        ));
    }
    let silent_exe_str = silent_exe.to_string_lossy().to_string();

    // 图标: 用 .exe 自身嵌入的 ICON RESOURCE, 索引 0 (两个 bin 都嵌了一样的图标)
    let icon_path = format!("{},0", silent_exe_str);

    println!("[INFO] 当前 .exe:    {}", exe_str);
    println!("[INFO] 静默版 .exe: {}", silent_exe_str);
    println!();

    // 两问交互 (与 Python v0.4.0 行为一致). 命令行已传 _summary/_xlsx 时跳过.
    let mut want_summary = _summary;
    let mut want_xlsx = _xlsx;
    let interactive = !_summary && !_xlsx && std::env::var("RENAME_INVOICE_NO_PROMPT").is_err();

    if interactive {
        println!("请回答两个独立问题 (回车=否, 都选否就是纯静默):");
        print!("  1) 处理完后弹出 汇总窗口? [y/N] ");
        let _ = stdout().flush();
        let mut buf = String::new();
        stdin().lock().read_line(&mut buf).ok();
        if buf.trim().eq_ignore_ascii_case("y") || buf.trim().eq_ignore_ascii_case("yes") {
            want_summary = true;
        }
        buf.clear();
        print!("  2) 处理完后在文件夹生成 Excel 汇总? [y/N] ");
        let _ = stdout().flush();
        stdin().lock().read_line(&mut buf).ok();
        if buf.trim().eq_ignore_ascii_case("y") || buf.trim().eq_ignore_ascii_case("yes") {
            want_xlsx = true;
        }
    }

    let mut extra_args: Vec<&str> = vec!["--silent"];
    if want_summary {
        extra_args.push("--summary");
    }
    if want_xlsx {
        extra_args.push("--xlsx");
    }
    let extra = extra_args.join(" ");

    let mode_desc = match (want_summary, want_xlsx) {
        (true, true) => "静默 + 汇总窗口 + Excel 汇总",
        (true, false) => "静默 + 汇总窗口",
        (false, true) => "静默 + Excel 汇总",
        (false, false) => "静默 (纯无窗口)",
    };
    println!("[INFO] 安装模式: {}", mode_desc);

    let cmd_file = format!("\"{}\" {} \"%1\"", silent_exe_str, extra);
    let cmd_bg = format!("\"{}\" {} \"%V\"", silent_exe_str, extra);

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let targets = [
        (
            format!("Software\\Classes\\SystemFileAssociations\\.pdf\\shell\\{}", KEY_NAME),
            &cmd_file,
            "PDF 文件右键",
        ),
        (
            format!("Software\\Classes\\Directory\\shell\\{}", KEY_NAME),
            &cmd_file,
            "文件夹右键",
        ),
        (
            format!("Software\\Classes\\Directory\\Background\\shell\\{}", KEY_NAME),
            &cmd_bg,
            "文件夹空白处右键",
        ),
    ];

    for (path, cmd, desc) in &targets {
        let (shell_key, _) = hkcu.create_subkey(path)?;
        shell_key.set_value("", &MENU_TEXT.to_string())?;
        shell_key.set_value("Icon", &icon_path)?;
        let (cmd_key, _) = hkcu.create_subkey(format!("{}\\command", path))?;
        cmd_key.set_value("", &cmd.to_string())?;
        println!("[OK] {}: HKCU\\{}", desc, path);
    }

    println!();
    println!("完成! 现在你可以:");
    println!("  - 在任意 PDF 上右键 -> '{}'", MENU_TEXT);
    println!("  - 在任意文件夹上右键 -> '{}'", MENU_TEXT);
    println!("  - 在文件夹空白处右键 -> '{}'", MENU_TEXT);
    println!();
    if want_summary {
        println!("(汇总窗口: 处理完后会弹一个 Slint 原生窗口列出全部结果)");
    }
    if want_xlsx {
        println!("(Excel 导出: 处理完后会在当前文件夹生成 发票汇总_<时间戳>.xlsx)");
    }
    if !want_summary && !want_xlsx {
        println!("(纯静默: 完全无窗口, 结果写入 rename_invoice.log)");
    }
    println!("(Win11 用户可能需要点'显示更多选项'才能看到自定义菜单)");

    pause_if_interactive();
    Ok(())
}

#[cfg(windows)]
pub fn uninstall() -> Result<()> {
    use winreg::enums::*;
    use winreg::RegKey;

    let hkcu = RegKey::predef(HKEY_CURRENT_USER);
    let paths = [
        format!("Software\\Classes\\SystemFileAssociations\\.pdf\\shell\\{}", KEY_NAME),
        format!("Software\\Classes\\Directory\\shell\\{}", KEY_NAME),
        format!("Software\\Classes\\Directory\\Background\\shell\\{}", KEY_NAME),
    ];
    for p in &paths {
        match hkcu.delete_subkey_all(p) {
            Ok(()) => println!("[已删除] HKCU\\{}", p),
            Err(_) => println!("[跳过] HKCU\\{} (不存在)", p),
        }
    }
    println!();
    println!("右键菜单已卸载完成.");
    pause_if_interactive();
    Ok(())
}

#[cfg(not(windows))]
pub fn install(_summary: bool, _xlsx: bool) -> Result<()> {
    Err(anyhow!("install 子命令仅支持 Windows"))
}

#[cfg(not(windows))]
pub fn uninstall() -> Result<()> {
    Err(anyhow!("uninstall 子命令仅支持 Windows"))
}

fn pause_if_interactive() {
    if std::env::var("RENAME_INVOICE_NO_PROMPT").is_ok() {
        return;
    }
    use std::io::Read;
    println!("\n按回车键退出...");
    let _ = std::io::stdin().read(&mut [0u8; 1]);
}
