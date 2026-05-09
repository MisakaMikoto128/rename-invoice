//! Excel 汇总输出 (rust_xlsxwriter).

use crate::process::ProcessResult;
use anyhow::Result;
use chrono::Local;
use rust_xlsxwriter::{Color, Format, FormatAlign, FormatBorder, Formula, Workbook};
use std::path::{Path, PathBuf};

const HEADERS: [&str; 7] = [
    "发票文件名称",
    "发票号码",
    "开票日期",
    "销售方名称",
    "备注名称",
    "淘宝单号",
    "金额",
];

/// Excel 标准 "货币" 格式 (人民币), 千分位 + 两位小数 + 负数红色
const RMB_FORMAT: &str = "\"¥\"#,##0.00;[Red]\"¥\"-#,##0.00";

pub fn output_path(target_dir: &Path) -> PathBuf {
    let ts = Local::now().format("%Y%m%d-%H%M%S");
    target_dir.join(format!("发票汇总_{}.xlsx", ts))
}

pub fn write_summary(results: &[ProcessResult], output_path: &Path) -> Result<()> {
    let mut wb = Workbook::new();
    let ws = wb.add_worksheet();
    ws.set_name("发票汇总")?;

    // 样式
    let header_fmt = Format::new()
        .set_bold()
        .set_font_color(Color::White)
        .set_background_color(Color::RGB(0x447CC4))
        .set_align(FormatAlign::Center)
        .set_align(FormatAlign::VerticalCenter)
        .set_border(FormatBorder::Thin);

    let cell_left = Format::new()
        .set_align(FormatAlign::Left)
        .set_align(FormatAlign::VerticalCenter)
        .set_border(FormatBorder::Thin);
    let cell_center = Format::new()
        .set_align(FormatAlign::Center)
        .set_align(FormatAlign::VerticalCenter)
        .set_border(FormatBorder::Thin);
    let cell_money = Format::new()
        .set_align(FormatAlign::Right)
        .set_align(FormatAlign::VerticalCenter)
        .set_border(FormatBorder::Thin)
        .set_num_format(RMB_FORMAT);

    let total_label = Format::new()
        .set_bold()
        .set_align(FormatAlign::Right)
        .set_align(FormatAlign::VerticalCenter)
        .set_background_color(Color::RGB(0xFFF2CC))
        .set_border(FormatBorder::Thin);
    let total_money = Format::new()
        .set_bold()
        .set_align(FormatAlign::Right)
        .set_align(FormatAlign::VerticalCenter)
        .set_background_color(Color::RGB(0xFFF2CC))
        .set_border(FormatBorder::Thin)
        .set_num_format(RMB_FORMAT);
    let total_blank = Format::new()
        .set_align(FormatAlign::Center)
        .set_align(FormatAlign::VerticalCenter)
        .set_background_color(Color::RGB(0xFFF2CC))
        .set_border(FormatBorder::Thin);

    // 表头
    for (i, h) in HEADERS.iter().enumerate() {
        ws.write_string_with_format(0, i as u16, *h, &header_fmt)?;
    }

    // 数据行
    for (idx, r) in results.iter().enumerate() {
        let row = (idx as u32) + 1;
        let final_name = r
            .final_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("");
        ws.write_string_with_format(row, 0, final_name, &cell_left)?;
        ws.write_string_with_format(row, 1, r.metadata.invoice_no.as_deref().unwrap_or(""), &cell_center)?;
        ws.write_string_with_format(row, 2, r.metadata.date.as_deref().unwrap_or(""), &cell_center)?;
        ws.write_string_with_format(row, 3, r.metadata.seller.as_deref().unwrap_or(""), &cell_left)?;
        ws.write_string_with_format(row, 4, "", &cell_left)?; // 备注名称
        ws.write_string_with_format(row, 5, "", &cell_left)?; // 淘宝单号
        match r.metadata.amount.as_deref().and_then(|s| s.parse::<f64>().ok()) {
            Some(v) => ws.write_number_with_format(row, 6, v, &cell_money)?,
            None => ws.write_string_with_format(row, 6, "", &cell_money)?,
        };
    }

    // 合计行
    let n = results.len() as u32;
    let last_data_row = n; // 1-indexed last data row inside excel = 1 + n; here 0-based = n
    let total_row = last_data_row + 1;
    for col in 0..5u16 {
        ws.write_string_with_format(total_row, col, "", &total_blank)?;
    }
    ws.write_string_with_format(total_row, 5, "合计", &total_label)?;
    if n > 0 {
        // SUM(G2:G{n+1})  注意 excel 是 1-indexed
        let formula = Formula::new(format!("=SUM(G2:G{})", n + 1));
        ws.write_formula_with_format(total_row, 6, formula, &total_money)?;
    } else {
        ws.write_number_with_format(total_row, 6, 0.0, &total_money)?;
    }

    // 列宽
    ws.set_column_width(0, 60.0)?;
    ws.set_column_width(1, 24.0)?;
    ws.set_column_width(2, 16.0)?;
    ws.set_column_width(3, 32.0)?;
    ws.set_column_width(4, 18.0)?;
    ws.set_column_width(5, 18.0)?;
    ws.set_column_width(6, 14.0)?;

    // 冻结首行
    ws.set_freeze_panes(1, 0)?;

    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    wb.save(output_path)?;
    Ok(())
}
