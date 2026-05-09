//! rename-invoice (Rust) — 发票 PDF 自动加价格前缀工具
//!
//! 用法 (单 .exe, 同目录放 pdfium.dll):
//!   rename-invoice [paths...]                   直接模式 (cmd 输出)
//!   rename-invoice --silent [paths...]          静默 + 队列锁 (右键菜单走这条)
//!   rename-invoice --silent --summary [paths]   + 处理完弹结果窗口
//!   rename-invoice --silent --xlsx [paths]      + 处理完导出 Excel 汇总
//!   rename-invoice install [--summary] [--xlsx] 注册右键菜单
//!   rename-invoice uninstall                    卸载右键菜单
//!
//! 编译为 windows 子系统 (无控制台). 静默模式直接跑 -> 0 cmd 闪窗.
//! 直接模式 / install / uninstall 启动时 AttachConsole(parent) 否则 AllocConsole,
//! 然后 SetStdHandle 让 println / read_line 能用上 console 句柄.

#![cfg_attr(windows, windows_subsystem = "windows")]

mod amount;
mod pdf;
mod extract;
mod log_audit;
mod process;
mod silent;
mod summary;
mod xlsx;
mod install;

use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Debug, Default)]
struct Args {
    silent: bool,
    summary: bool,
    xlsx: bool,
    paths: Vec<PathBuf>,
    subcommand: Option<String>,
}

fn parse_args() -> Args {
    let mut a = Args::default();
    let mut iter = std::env::args().skip(1).peekable();
    if let Some(first) = iter.peek() {
        if first == "install" || first == "uninstall" {
            a.subcommand = Some(iter.next().unwrap());
        }
    }
    for arg in iter {
        match arg.as_str() {
            "--silent" => a.silent = true,
            "--summary" => a.summary = true,
            "--xlsx" => a.xlsx = true,
            _ => a.paths.push(PathBuf::from(arg)),
        }
    }
    a
}

#[cfg(windows)]
fn ensure_console() {
    use std::ptr::null_mut;
    use windows_sys::Win32::Foundation::{GENERIC_READ, GENERIC_WRITE, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::Storage::FileSystem::{
        CreateFileW, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
    };
    use windows_sys::Win32::System::Console::{
        AllocConsole, AttachConsole, GetConsoleWindow, SetStdHandle, ATTACH_PARENT_PROCESS,
        STD_ERROR_HANDLE, STD_INPUT_HANDLE, STD_OUTPUT_HANDLE,
    };

    unsafe {
        // 已经有 console (从 cmd 启动) 就不动它
        if !GetConsoleWindow().is_null() {
            return;
        }
        // 试 attach 父进程的 console (cmd 直接调 .exe 时)
        if AttachConsole(ATTACH_PARENT_PROCESS) == 0 {
            // 失败 -> 我们没有父 console (双击 / Explorer 启动), 自己开一个
            AllocConsole();
        }

        // 即使 attach/alloc 成功, Rust 的 std::io 句柄可能是 NULL,
        // 显式 CreateFileW + SetStdHandle 把 STD_*_HANDLE 接到 console 设备上.
        let conin: Vec<u16> = "CONIN$\0".encode_utf16().collect();
        let h_in = CreateFileW(
            conin.as_ptr(),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            null_mut(),
            OPEN_EXISTING,
            0,
            null_mut(),
        );
        if h_in != INVALID_HANDLE_VALUE && !h_in.is_null() {
            SetStdHandle(STD_INPUT_HANDLE, h_in);
        }

        let conout: Vec<u16> = "CONOUT$\0".encode_utf16().collect();
        let h_out = CreateFileW(
            conout.as_ptr(),
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            null_mut(),
            OPEN_EXISTING,
            0,
            null_mut(),
        );
        if h_out != INVALID_HANDLE_VALUE && !h_out.is_null() {
            SetStdHandle(STD_OUTPUT_HANDLE, h_out);
            SetStdHandle(STD_ERROR_HANDLE, h_out);
        }
    }
}

#[cfg(not(windows))]
fn ensure_console() {}

fn main() -> ExitCode {
    let args = parse_args();

    // 静默模式 (右键菜单走的): 不要 console -> 0 cmd 闪窗
    // 直接模式 / install / uninstall: 需要 console (彩色输出 / 交互问答)
    if !args.silent {
        ensure_console();
    }

    let result = match args.subcommand.as_deref() {
        Some("install") => install::install(args.summary, args.xlsx),
        Some("uninstall") => install::uninstall(),
        _ => {
            if args.silent {
                silent::silent_main(&args.paths, args.summary, args.xlsx)
            } else {
                process::direct_main(&args.paths, args.xlsx)
            }
        }
    };

    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("[ERROR] {:#}", e);
            ExitCode::FAILURE
        }
    }
}
