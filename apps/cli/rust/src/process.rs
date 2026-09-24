//! process_pdf 单文件处理 + 直接模式 (cmd 输出)

use crate::extract::{extract_metadata, InvoiceMetadata};
use crate::log_audit::log_line;
use crate::pdf::read_pdf;
use crate::xlsx;

use anyhow::Result;
use regex::Regex;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Renamed,
    Skipped,
    Failed,
}

#[derive(Debug, Clone)]
pub struct ProcessResult {
    pub status: Status,
    pub message: String,
    pub metadata: InvoiceMetadata,
    pub original_name: String,
    pub final_path: PathBuf,
}

fn already_prefixed_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^\d+(\.\d{1,2})?元-").unwrap())
}

fn safe_target_path(dir: &Path, name: &str) -> PathBuf {
    let target = dir.join(name);
    if !target.exists() {
        return target;
    }
    let stem;
    let ext;
    if let Some(dot) = name.rfind('.') {
        stem = &name[..dot];
        ext = &name[dot..];
    } else {
        stem = name;
        ext = "";
    }
    let mut n = 2u32;
    loop {
        let cand = dir.join(format!("{} ({}){}", stem, n, ext));
        if !cand.exists() {
            return cand;
        }
        n += 1;
    }
}

pub fn process_pdf(pdf_path: &Path) -> ProcessResult {
    let original_name = pdf_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("(unknown)")
        .to_string();

    if already_prefixed_re().is_match(&original_name) {
        // SKIP 也提取 metadata, 让 xlsx 仍能拿到字段
        let meta = match read_pdf(pdf_path) {
            Ok(doc) => extract_metadata(&doc),
            Err(_) => InvoiceMetadata::default(),
        };
        return ProcessResult {
            status: Status::Skipped,
            message: "已有价格前缀, 跳过".to_string(),
            metadata: meta,
            original_name,
            final_path: pdf_path.to_path_buf(),
        };
    }

    let doc = match read_pdf(pdf_path) {
        Ok(d) => d,
        Err(e) => {
            return ProcessResult {
                status: Status::Failed,
                message: format!("{}", e),
                metadata: InvoiceMetadata::default(),
                original_name,
                final_path: pdf_path.to_path_buf(),
            };
        }
    };
    let meta = extract_metadata(&doc);

    let amount = match &meta.amount {
        Some(a) => a.clone(),
        None => {
            let reason = meta
                .amount_reason
                .clone()
                .unwrap_or_else(|| "未知失败".to_string());
            return ProcessResult {
                status: Status::Failed,
                message: reason,
                metadata: meta,
                original_name,
                final_path: pdf_path.to_path_buf(),
            };
        }
    };

    let new_name = format!("{}元-{}", amount, original_name);
    let parent = pdf_path.parent().unwrap_or(Path::new("."));
    let target = safe_target_path(parent, &new_name);
    if let Err(e) = std::fs::rename(pdf_path, &target) {
        return ProcessResult {
            status: Status::Failed,
            message: format!("重命名失败: {}", e),
            metadata: meta,
            original_name,
            final_path: pdf_path.to_path_buf(),
        };
    }

    let final_name = target
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("")
        .to_string();
    log_line(&format!(
        "OK    {}  ->  {}  (金额={})",
        original_name, final_name, amount
    ));

    ProcessResult {
        status: Status::Renamed,
        message: final_name,
        metadata: meta,
        original_name,
        final_path: target,
    }
}

pub fn collect_pdfs(target: &Path) -> Vec<PathBuf> {
    if target.is_file() {
        if target.extension().and_then(|e| e.to_str()).map(|s| s.eq_ignore_ascii_case("pdf")) == Some(true) {
            return vec![target.to_path_buf()];
        }
        return vec![];
    }
    if target.is_dir() {
        let mut out: Vec<PathBuf> = Vec::new();
        if let Ok(rd) = std::fs::read_dir(target) {
            for entry in rd.flatten() {
                let p = entry.path();
                if p.is_file()
                    && p.extension().and_then(|e| e.to_str()).map(|s| s.eq_ignore_ascii_case("pdf")) == Some(true)
                {
                    out.push(p);
                }
            }
        }
        out.sort();
        return out;
    }
    vec![]
}

// ANSI 颜色 (Windows 10+ 终端支持)
fn c_red(s: &str) -> String { format!("\x1b[31m{}\x1b[0m", s) }
fn c_green(s: &str) -> String { format!("\x1b[32m{}\x1b[0m", s) }
fn c_yellow(s: &str) -> String { format!("\x1b[33m{}\x1b[0m", s) }
fn c_cyan(s: &str) -> String { format!("\x1b[36m{}\x1b[0m", s) }
fn c_gray(s: &str) -> String { format!("\x1b[90m{}\x1b[0m", s) }

pub fn direct_main(paths: &[PathBuf], want_xlsx: bool) -> Result<()> {
    let mut args: Vec<PathBuf> = paths.to_vec();
    if args.is_empty() {
        args.push(std::env::current_dir()?);
    }

    let mut targets: Vec<PathBuf> = Vec::new();
    for arg in &args {
        if !arg.exists() {
            println!("{}", c_red(&format!("[ERROR] 路径不存在: {}", arg.display())));
            continue;
        }
        targets.extend(collect_pdfs(arg));
    }

    if targets.is_empty() {
        println!("{}", c_yellow("[INFO] 没有找到 PDF 文件"));
        wait_keypress();
        return Ok(());
    }

    println!("{}", c_cyan(&format!("\n=== 发票重命名 (共 {} 个 PDF) ===\n", targets.len())));

    let mut counts = (0u32, 0u32, 0u32); // renamed, skipped, failed
    let mut failures: Vec<(String, String)> = Vec::new();
    let mut xlsx_results: Vec<ProcessResult> = Vec::new();

    for pdf in &targets {
        let r = process_pdf(pdf);
        match r.status {
            Status::Renamed => {
                counts.0 += 1;
                println!(
                    "{} {} {} {}",
                    c_green("[ OK ]"),
                    r.original_name,
                    c_gray("->"),
                    c_cyan(&r.message)
                );
            }
            Status::Skipped => {
                counts.1 += 1;
                println!(
                    "{} {} {}",
                    c_gray("[SKIP]"),
                    r.original_name,
                    c_gray(&format!("({})", r.message))
                );
            }
            Status::Failed => {
                counts.2 += 1;
                println!(
                    "{} {} {}",
                    c_red("[FAIL]"),
                    r.original_name,
                    c_red(&format!("-- {}", r.message))
                );
                failures.push((r.original_name.clone(), r.message.clone()));
                log_line(&format!("FAIL  {}  原因: {}", r.original_name, r.message));
            }
        }
        if matches!(r.status, Status::Renamed | Status::Skipped) && r.metadata.amount.is_some() {
            xlsx_results.push(r);
        }
    }

    println!();
    println!(
        "{}",
        c_cyan(&format!(
            "重命名: {}  跳过: {}  失败: {}",
            counts.0, counts.1, counts.2
        ))
    );

    if !failures.is_empty() {
        println!("{}", c_red("\n以下文件需手动处理:"));
        for (n, m) in &failures {
            println!("  - {}", n);
            println!("      原因: {}", m);
        }
    }

    if want_xlsx && !xlsx_results.is_empty() {
        let target_dir = resolve_xlsx_dir(&args, &xlsx_results);
        let xlsx_path = xlsx::output_path(&target_dir);
        match xlsx::write_summary(&xlsx_results, &xlsx_path) {
            Ok(()) => {
                log_line(&format!(
                    "XLSX  导出 -> {}  ({} 行)",
                    xlsx_path.display(),
                    xlsx_results.len()
                ));
                println!("{}", c_cyan(&format!("\n[XLSX] 已生成: {}", xlsx_path.display())));
            }
            Err(e) => {
                log_line(&format!("FAIL  导出 Excel 失败: {}", e));
                println!("{}", c_red(&format!("\n[XLSX] 失败: {}", e)));
            }
        }
    }

    wait_keypress();
    Ok(())
}

pub fn resolve_xlsx_dir(args: &[PathBuf], fallback_results: &[ProcessResult]) -> PathBuf {
    for a in args {
        if a.is_dir() {
            return a.clone();
        }
    }
    if let Some(first) = fallback_results.first() {
        if let Some(parent) = first.final_path.parent() {
            return parent.to_path_buf();
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

#[cfg(windows)]
fn wait_keypress() {
    // 拖放/双击场景 cmd 窗口会立刻关. 只有有 stdin (terminal attached) 时才等回车.
    use std::io::Read;
    if std::env::var("RENAME_INVOICE_NO_PAUSE").is_ok() {
        return;
    }
    println!("\n按回车键退出...");
    let _ = std::io::stdin().read(&mut [0u8; 1]);
}

#[cfg(not(windows))]
fn wait_keypress() {}
