//! Slint 汇总窗口: 处理完后弹一个原生窗口列出全部结果.

use crate::process::{ProcessResult, Status};
use std::path::Path;
use std::rc::Rc;

slint::include_modules!();

pub fn show(results: &[ProcessResult], xlsx_path: Option<&Path>) {
    let mut renamed = 0u32;
    let mut skipped = 0u32;
    let mut failed = 0u32;
    for r in results {
        match r.status {
            Status::Renamed => renamed += 1,
            Status::Skipped => skipped += 1,
            Status::Failed => failed += 1,
        }
    }
    let header = format!(
        "重命名: {}    跳过: {}    失败: {}    (总 {})",
        renamed,
        skipped,
        failed,
        results.len()
    );

    let rows: Vec<ResultRow> = results
        .iter()
        .map(|r| match r.status {
            Status::Renamed => ResultRow {
                status: " OK ".into(),
                name: format!("{}  ->  {}", r.original_name, r.message).into(),
                detail: "".into(),
                color_tag: 0,
            },
            Status::Skipped => ResultRow {
                status: "SKIP".into(),
                name: r.original_name.clone().into(),
                detail: format!("({})", r.message).into(),
                color_tag: 1,
            },
            Status::Failed => ResultRow {
                status: "FAIL".into(),
                name: r.original_name.clone().into(),
                detail: r.message.clone().into(),
                color_tag: 2,
            },
        })
        .collect();
    let model = Rc::new(slint::VecModel::from(rows));

    let xlsx_line = match xlsx_path {
        Some(p) => format!("[XLSX] 已生成: {}", p.display()),
        None => String::new(),
    };

    let window = match SummaryWindow::new() {
        Ok(w) => w,
        Err(e) => {
            eprintln!("[WARN] 汇总窗口启动失败: {}", e);
            return;
        }
    };
    window.set_header_text(header.into());
    window.set_rows(slint::ModelRc::from(model));
    window.set_xlsx_line(xlsx_line.into());

    let weak = window.as_weak();
    window.on_close_clicked(move || {
        if let Some(w) = weak.upgrade() {
            let _ = w.window().hide();
        }
    });

    let _ = window.run();
}
