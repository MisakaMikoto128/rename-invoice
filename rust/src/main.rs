//! rename-invoice (Rust) — 发票 PDF 自动加价格前缀工具
//!
//! 同源编译两个 bin (子系统不同), 解决 GUI/console 混用的 stdin/stdout 难题:
//!   rename-invoice.exe    — console 子系统: install / uninstall / 直接模式
//!                           (PowerShell / cmd 同步等它退, 交互输入正常)
//!   rename-invoice-w.exe  — windows 子系统: 右键菜单 --silent 路径专用, 0 cmd 闪窗
//!
//! 用法:
//!   rename-invoice [paths...]                    直接模式 (cmd 输出)
//!   rename-invoice --silent [paths...]           静默 + 队列锁
//!   rename-invoice --silent --summary [paths]    + Slint 汇总窗口
//!   rename-invoice --silent --xlsx [paths]       + Excel 汇总
//!   rename-invoice install [--summary] [--xlsx]  注册右键菜单
//!   rename-invoice uninstall                     卸载右键菜单
//!
//! install 注册到注册表的命令路径用 rename-invoice-w.exe (静默不闪窗).

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
