//! rename-invoice (Rust) — 发票 PDF 自动加价格前缀工具
//!
//! 用法 (单 .exe, 同目录放 pdfium.dll):
//!   rename-invoice [paths...]                   直接模式 (cmd 输出)
//!   rename-invoice --silent [paths...]          静默 + 队列锁 (右键菜单走这条)
//!   rename-invoice --silent --summary [paths]   + 处理完弹结果窗口 (TODO: 后续版本)
//!   rename-invoice --silent --xlsx [paths]      + 处理完导出 Excel 汇总
//!   rename-invoice install [--summary] [--xlsx] 注册右键菜单
//!   rename-invoice uninstall                    卸载右键菜单

mod amount;
mod pdf;
mod extract;
mod log_audit;
mod process;
mod silent;
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

fn main() -> ExitCode {
    let args = parse_args();

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
