//! 静默模式: 排空跨进程队列, 逐个处理.
//!
//! 队列/锁的实现在 queue.rs (与 shim 共用). 这里只关心"当上 leader 之后怎么干活".
//!
//! 两条进入路径:
//!   1. rename-invoice-w.exe (shim) 拉起  -> --from-queue, 路径已由 shim 入队
//!   2. 直接 `rename-invoice.exe --silent <paths>` -> 自己入队再抢 leader
//! 两种情况都要先入队再抢锁, 否则会跟正在退出的 leader 撞出"路径没人处理"的窗口.

use crate::log_audit::log_line;
use crate::process::{collect_pdfs, process_pdf, resolve_xlsx_dir, ProcessResult, Status};
use crate::queue;
use crate::summary;
use crate::xlsx;

use anyhow::Result;
use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

const DEBOUNCE: Duration = Duration::from_millis(250);
/// 队列空了之后继续待命多久, 见下面排空循环处的注释.
const LINGER: Duration = Duration::from_millis(800);
const LINGER_POLL: Duration = Duration::from_millis(50);

pub fn silent_main(
    paths: &[PathBuf],
    from_queue: bool,
    show_summary: bool,
    want_xlsx: bool,
) -> Result<()> {
    let mut args: Vec<PathBuf> = paths.to_vec();
    if !from_queue {
        // 直接调用: 命令行路径要自己入队. 没给路径就按 cwd 兜底.
        if args.is_empty() {
            args.push(std::env::current_dir()?);
        }
        queue::append_to_queue(&args)?;
    }

    // 抢 leader 锁 (非阻塞). 抢不到说明已经有 worker 在跑, 它会把队列排空.
    let leader_fp = match queue::try_become_leader() {
        Some(f) => f,
        None => return Ok(()),
    };

    // Leader 流程
    std::thread::sleep(DEBOUNCE);
    let mut all_results: Vec<ProcessResult> = Vec::new();
    let mut all_args_for_xlsx: Vec<PathBuf> = args.clone();
    let mut seen: HashSet<PathBuf> = HashSet::new();

    // 排空 + linger.
    //
    // Explorer 一次多选 N 个文件是**陆续**启动 N 个 shim 的 (实测 23 个铺开约 900 ms),
    // 而处理本身可能不到 1 s. 队列一空就退出的话, 晚到的 shim 会发现没有 worker,
    // 于是又拉起一个重进程 —— 结果不会错 (那条路径照样被处理), 但白白多一个 10 MB 进程.
    // 所以队列空了之后再空转 LINGER 这么久, 把整个启动波次吃完再收工.
    let mut idle_since = Instant::now();
    loop {
        let raw_paths = queue::drain_queue();
        if raw_paths.is_empty() {
            if idle_since.elapsed() >= LINGER {
                break;
            }
            std::thread::sleep(LINGER_POLL);
            continue;
        }
        for raw in &raw_paths {
            let p = PathBuf::from(raw);
            if !all_args_for_xlsx.contains(&p) {
                all_args_for_xlsx.push(p);
            }
        }
        let mut pdfs: Vec<PathBuf> = Vec::new();
        for raw in &raw_paths {
            let p = Path::new(raw);
            if !p.exists() {
                log_line(&format!("FAIL  (silent) 路径不存在: {}", raw));
                continue;
            }
            for pdf in collect_pdfs(p) {
                let key = pdf.canonicalize().unwrap_or_else(|_| pdf.clone());
                if seen.insert(key) {
                    pdfs.push(pdf);
                }
            }
        }
        for pdf in &pdfs {
            let r = process_pdf(pdf);
            match r.status {
                Status::Failed => log_line(&format!("FAIL  {}  原因: {}", r.original_name, r.message)),
                Status::Skipped => log_line(&format!("SKIP  {}  ({})", r.original_name, r.message)),
                _ => {}
            }
            all_results.push(r);
        }
        idle_since = Instant::now();
    }

    let mut xlsx_written: Option<PathBuf> = None;
    if want_xlsx {
        let xlsx_results: Vec<ProcessResult> = all_results
            .iter()
            .filter(|r| matches!(r.status, Status::Renamed | Status::Skipped))
            .filter(|r| r.metadata.amount.is_some())
            .cloned()
            .collect();
        if !xlsx_results.is_empty() {
            let target_dir = resolve_xlsx_dir(&all_args_for_xlsx, &xlsx_results);
            let xlsx_path = xlsx::output_path(&target_dir);
            match xlsx::write_summary(&xlsx_results, &xlsx_path) {
                Ok(()) => {
                    log_line(&format!(
                        "XLSX  导出 -> {}  ({} 行)",
                        xlsx_path.display(),
                        xlsx_results.len()
                    ));
                    xlsx_written = Some(xlsx_path);
                }
                Err(e) => log_line(&format!("FAIL  导出 Excel 失败: {}", e)),
            }
        }
    }

    // Slint 窗口阻塞期间继续握 leader 锁, 否则会被晚到的右键进程抢去当新 leader,
    // 表现为多个 Slint 窗口同时弹出.
    if show_summary {
        summary::show(&all_results, xlsx_written.as_deref());
    }

    queue::release_leader(&leader_fp);
    Ok(())
}
