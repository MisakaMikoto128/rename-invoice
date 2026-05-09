//! 审计日志: rename_invoice.log (与 .exe 同目录)

use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

use chrono::Local;

pub fn log_path() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("rename-invoice.exe"));
    exe.parent()
        .map(|p| p.join("rename_invoice.log"))
        .unwrap_or_else(|| PathBuf::from("rename_invoice.log"))
}

pub fn log_line(line: &str) {
    let ts = Local::now().format("%Y-%m-%d %H:%M:%S");
    if let Ok(mut f) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path())
    {
        let _ = writeln!(f, "[{}] {}", ts, line);
    }
}
