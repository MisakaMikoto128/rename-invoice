//! 静默模式 + 队列 + 文件锁 leader 模式
//!
//! N 次右键并发触发的 .exe -> 每个进程把自己路径写到 .queue.txt;
//! 用 fs2 在 .leader.lock 上抢非阻塞独占锁; 抢到的当 leader, 其它直接 exit.
//! Leader 短暂 debounce 之后排空队列处理. 处理过程中新来的 append 也能在再循环里被消化.

use crate::log_audit::{log_line, log_path};
use crate::process::{collect_pdfs, process_pdf, resolve_xlsx_dir, ProcessResult, Status};
use crate::summary;
use crate::xlsx;

use anyhow::Result;
use fs2::FileExt;
use std::collections::HashSet;
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::time::Duration;

const DEBOUNCE: Duration = Duration::from_millis(250);

fn lock_dir() -> PathBuf {
    log_path()
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."))
}

fn queue_file() -> PathBuf {
    lock_dir().join(".queue.txt")
}
fn queue_lock_file() -> PathBuf {
    lock_dir().join(".queue.lock")
}
fn leader_lock_file() -> PathBuf {
    lock_dir().join(".leader.lock")
}

fn append_to_queue(args: &[PathBuf]) -> Result<()> {
    let qlock_path = queue_lock_file();
    let lockfile = OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(&qlock_path)?;
    lockfile.lock_exclusive()?;
    let result = (|| -> Result<()> {
        let mut qf = OpenOptions::new()
            .create(true)
            .append(true)
            .open(queue_file())?;
        for p in args {
            writeln!(qf, "{}", p.display())?;
        }
        Ok(())
    })();
    let _ = lockfile.unlock();
    result
}

fn drain_queue() -> Vec<String> {
    let qlock_path = queue_lock_file();
    let lockfile = match OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(&qlock_path)
    {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };
    if lockfile.lock_exclusive().is_err() {
        return Vec::new();
    }
    let queue_path = queue_file();
    let mut lines: Vec<String> = Vec::new();
    if queue_path.exists() {
        if let Ok(f) = OpenOptions::new().read(true).open(&queue_path) {
            let reader = BufReader::new(f);
            for line in reader.lines().map_while(Result::ok) {
                if !line.trim().is_empty() {
                    lines.push(line);
                }
            }
        }
        // 截断
        let _ = OpenOptions::new()
            .write(true)
            .truncate(true)
            .open(&queue_path);
    }
    let _ = lockfile.unlock();
    lines
}

pub fn silent_main(paths: &[PathBuf], show_summary: bool, want_xlsx: bool) -> Result<()> {
    let mut args: Vec<PathBuf> = paths.to_vec();
    if args.is_empty() {
        args.push(std::env::current_dir()?);
    }

    append_to_queue(&args)?;

    // 抢 leader 锁 (非阻塞)
    let leader_path = leader_lock_file();
    let leader_fp = OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(&leader_path)?;
    if leader_fp.try_lock_exclusive().is_err() {
        // 已有 leader 在干活, 我们的路径已经入队, 静默 exit
        return Ok(());
    }

    // Leader 流程
    std::thread::sleep(DEBOUNCE);
    let mut all_results: Vec<ProcessResult> = Vec::new();
    let mut all_args_for_xlsx: Vec<PathBuf> = args.clone();
    let mut seen: HashSet<PathBuf> = HashSet::new();

    loop {
        let raw_paths = drain_queue();
        if raw_paths.is_empty() {
            break;
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
                Status::Failed => {
                    log_line(&format!("FAIL  {}  原因: {}", r.original_name, r.message));
                }
                Status::Skipped => {
                    log_line(&format!("SKIP  {}  ({})", r.original_name, r.message));
                }
                _ => {}
            }
            all_results.push(r);
        }
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

    let _ = FileExt::unlock(&leader_fp);

    if show_summary {
        summary::show(&all_results, xlsx_written.as_deref());
    }

    Ok(())
}
