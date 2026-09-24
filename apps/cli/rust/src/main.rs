//! rename-invoice (Rust) — 发票 PDF 自动加价格前缀工具
//!
//! 两个 bin 分工 (子系统和体量都不同):
//!   rename-invoice.exe    — 本文件. console 子系统, 完整功能 (pdfium + slint + xlsx),
//!                           约 10 MB. install / uninstall / 直接模式 / 队列 worker.
//!   rename-invoice-w.exe  — src/shim.rs. windows 子系统, 只依赖 std + fs2, 几百 KB.
//!                           右键菜单注册到它: Explorer 会按选中文件数把它启动 N 次,
//!                           它入队后拉起 1 个本程序当 worker. 详见 src/shim.rs.
//!
//! 用法:
//!   rename-invoice [paths...]                    直接模式 (cmd 输出)
//!   rename-invoice --silent [paths...]           静默 + 队列锁
//!   rename-invoice --silent --from-queue         同上, 但路径全部来自队列 (shim 拉起时用)
//!   rename-invoice --silent --summary [paths]    + Slint 汇总窗口
//!   rename-invoice --silent --xlsx [paths]       + Excel 汇总
//!   rename-invoice install [--summary] [--xlsx]  注册右键菜单
//!   rename-invoice uninstall                     卸载右键菜单

mod amount;
mod pdf;
mod extract;
mod log_audit;
mod process;
mod queue;
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
    /// 由 rename-invoice-w.exe (shim) 拉起时带上: 路径已经被 shim 入队了,
    /// 本进程不要再入队, 也不要在没有路径参数时拿 cwd 兜底.
    from_queue: bool,
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
            "--from-queue" => a.from_queue = true,
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
                silent::silent_main(&args.paths, args.from_queue, args.summary, args.xlsx)
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
