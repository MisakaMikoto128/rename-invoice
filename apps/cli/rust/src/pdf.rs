//! PDF 文本 + 块坐标提取 (PDFium 封装).
//!
//! 一次打开 PDF, 同时给出:
//!   - full_text: 全部页面文本顺序拼接 (用于正则提取发票号码/日期/金额)
//!   - first_page_blocks: 首页所有文本对象的 (文本, 边框) 列表
//!   - first_page_width: 用于"销售方在右半"的中线判断
//!
//! 加载 pdfium.dll 的策略:
//!   1. 与 .exe 同目录优先
//!   2. 兼容用户把 .exe 放别处 (回退到系统 PATH)

use anyhow::{anyhow, Context, Result};
use pdfium_render::prelude::*;
use std::cell::RefCell;
use std::path::Path;

#[derive(Debug, Clone)]
pub struct TextBlock {
    pub text: String,
    pub x0: f32,
    pub y0: f32,
    pub x1: f32,
    pub y1: f32,
}

impl TextBlock {
    pub fn cx(&self) -> f32 {
        (self.x0 + self.x1) * 0.5
    }
    pub fn cy(&self) -> f32 {
        (self.y0 + self.y1) * 0.5
    }
}

#[derive(Debug)]
pub struct PdfDoc {
    pub full_text: String,
    pub first_page_blocks: Vec<TextBlock>,
    pub first_page_width: f32,
}

// Pdfium 不是 Send/Sync, 用 thread_local 缓存 (每个线程内只初始化一次)
thread_local! {
    static PDFIUM_TLS: RefCell<Option<Pdfium>> = const { RefCell::new(None) };
}

fn init_pdfium() -> Result<Pdfium> {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()));

    let bindings = if let Some(dir) = exe_dir.as_ref() {
        let lib_name = Pdfium::pdfium_platform_library_name_at_path(dir);
        Pdfium::bind_to_library(&lib_name).or_else(|_| Pdfium::bind_to_system_library())
    } else {
        Pdfium::bind_to_system_library()
    }
    .context("找不到 pdfium.dll —— 请把 pdfium.dll 放在 rename-invoice.exe 同目录")?;

    Ok(Pdfium::new(bindings))
}

pub fn read_pdf(pdf_path: &Path) -> Result<PdfDoc> {
    PDFIUM_TLS.with(|cell| -> Result<PdfDoc> {
        let mut opt = cell.borrow_mut();
        if opt.is_none() {
            *opt = Some(init_pdfium()?);
        }
        let pdfium = opt.as_ref().unwrap();
        read_pdf_with(pdfium, pdf_path)
    })
}

fn read_pdf_with(pdfium: &Pdfium, pdf_path: &Path) -> Result<PdfDoc> {
    let doc = pdfium
        .load_pdf_from_file(
            pdf_path
                .to_str()
                .ok_or_else(|| anyhow!("路径含非 UTF-8 字符"))?,
            None,
        )
        .with_context(|| format!("无法打开 PDF: {}", pdf_path.display()))?;

    let mut full_text = String::new();
    let mut first_blocks: Vec<TextBlock> = Vec::new();
    let mut first_width: f32 = 0.0;

    for (page_idx, page) in doc.pages().iter().enumerate() {
        // 全文 (用 page text 的 all() 拼接)
        let page_text = page.text().with_context(|| format!("page {} text 提取失败", page_idx))?;
        full_text.push_str(&page_text.all());
        full_text.push('\n');

        if page_idx == 0 {
            first_width = page.width().value;
            // 收集首页所有文本对象的 bbox
            for obj in page.objects().iter() {
                if let Some(text_obj) = obj.as_text_object() {
                    let text = text_obj.text();
                    if text.trim().is_empty() {
                        continue;
                    }
                    if let Ok(bounds) = text_obj.bounds() {
                        first_blocks.push(TextBlock {
                            text,
                            x0: bounds.left().value,
                            y0: bounds.bottom().value,
                            x1: bounds.right().value,
                            y1: bounds.top().value,
                        });
                    }
                }
            }
        }
    }

    if full_text.trim().is_empty() {
        return Err(anyhow!("PDF 无文字层 (可能是扫描件), 不支持"));
    }

    Ok(PdfDoc {
        full_text,
        first_page_blocks: first_blocks,
        first_page_width: first_width,
    })
}
