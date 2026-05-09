//! 三层校验 (中文大写 ↔ ¥ 值 ↔ 最大值) + 发票号/日期/销售方提取.

use crate::amount::{chinese_amount_to_decimal, find_chinese_amounts};
use crate::pdf::{PdfDoc, TextBlock};
use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Default, Clone)]
pub struct InvoiceMetadata {
    /// 已通过三层校验的金额 (字符串, 形如 "98.01"); 校验失败为 None
    pub amount: Option<String>,
    /// 失败原因 (amount=None 时填)
    pub amount_reason: Option<String>,
    pub invoice_no: Option<String>,
    pub date: Option<String>,
    pub seller: Option<String>,
}

fn price_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"¥\s*(\d+(?:\.\d{1,2})?)").unwrap())
}
fn invoice_no_label_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"发\s*票\s*号\s*码\s*[:：]\s*(\d{8,25})").unwrap())
}
fn invoice_no_standalone_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(?m)^\s*(\d{15,25})\s*$").unwrap())
}
fn invoice_date_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(\d{4}年\d{1,2}月\d{1,2}日)").unwrap())
}
fn name_prefix_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^\s*名\s*称\s*[:：]\s*").unwrap())
}
fn company_suffix_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(
            r"(?:有限公司|股份有限公司|股份公司|集团公司|集团|个体工商户|事务所|合伙企业|工作室|商行|经营部|分公司|店)$",
        )
        .unwrap()
    })
}

/// 三层校验 (从全文): 找中文大写 -> 找 ¥ 值 -> 取交集且必须是最大 ¥ 值
pub fn validate_amount(text: &str) -> (Option<String>, Option<String>) {
    let candidates = find_chinese_amounts(text);
    if candidates.is_empty() {
        return (None, Some("未找到中文大写金额".to_string()));
    }

    let mut decimals: Vec<(String, f64)> = Vec::new();
    for c in candidates.iter() {
        if let Ok(v) = chinese_amount_to_decimal(c) {
            decimals.push((c.clone(), v));
        }
    }
    if decimals.is_empty() {
        return (
            None,
            Some(format!("中文大写金额无法解析: {:?}", candidates)),
        );
    }

    let mut prices: Vec<f64> = Vec::new();
    for caps in price_re().captures_iter(text) {
        if let Some(m) = caps.get(1) {
            if let Ok(v) = m.as_str().parse::<f64>() {
                prices.push((v * 100.0).round() / 100.0);
            }
        }
    }
    if prices.is_empty() {
        return (None, Some("未找到 ¥ 价格标记".to_string()));
    }
    let max_price = prices.iter().cloned().fold(f64::MIN, f64::max);

    for (cn_str, cn_val) in &decimals {
        for p in &prices {
            if (p - cn_val).abs() < 0.005 {
                if *cn_val + 0.005 < max_price {
                    return (
                        None,
                        Some(format!(
                            "中文大写金额 {} ({}) 不是最大 ¥ 值, 最大 ¥ 值是 {}, 异常",
                            cn_val, cn_str, max_price
                        )),
                    );
                }
                return (Some(format!("{:.2}", cn_val)), None);
            }
        }
    }

    (
        None,
        Some(format!(
            "中文大写金额与 ¥ 值不匹配. 中文: {:?}, ¥ 值: {:?}",
            decimals, prices
        )),
    )
}

pub fn extract_invoice_no(text: &str) -> Option<String> {
    if let Some(c) = invoice_no_label_re().captures(text) {
        return Some(c[1].to_string());
    }
    invoice_no_standalone_re()
        .captures(text)
        .map(|c| c[1].to_string())
}

pub fn extract_invoice_date(text: &str) -> Option<String> {
    invoice_date_re().captures(text).map(|c| c[1].to_string())
}

fn strip_name_prefix(line: &str) -> String {
    name_prefix_re().replace(line, "").trim().to_string()
}

/// 销售方名称: 用首页坐标判断 —— 公司名水平中点 > 页面中线 = 销售方.
/// 退路: 文本顺序的第二个公司名 (旧版"label 在前 / value 在后"布局).
pub fn extract_seller(blocks: &[TextBlock], page_width: f32, full_text: &str) -> Option<String> {
    if !blocks.is_empty() && page_width > 0.0 {
        let center = page_width * 0.5;
        let mut right_candidates: Vec<(f32, String)> = Vec::new(); // (cy, text)
        let mut all_candidates: Vec<(f32, f32, String)> = Vec::new(); // (cy, cx, text)
        for b in blocks {
            for line in b.text.lines() {
                let clean = strip_name_prefix(line.trim());
                if clean.is_empty() || !company_suffix_re().is_match(&clean) {
                    continue;
                }
                let cx = b.cx();
                let cy = b.cy();
                all_candidates.push((cy, cx, clean.clone()));
                if cx > center {
                    right_candidates.push((cy, clean));
                }
            }
        }
        if !right_candidates.is_empty() {
            // 上方优先 (注意 PDF 坐标 y 朝上, 上方意味着 y 大)
            right_candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
            return Some(right_candidates[0].1.clone());
        }
        if !all_candidates.is_empty() {
            all_candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
            return Some(all_candidates[0].2.clone());
        }
    }

    // 文本退路
    let mut candidates: Vec<String> = Vec::new();
    for line in full_text.lines() {
        let clean = strip_name_prefix(line.trim());
        if !clean.is_empty() && company_suffix_re().is_match(&clean) {
            candidates.push(clean);
        }
    }
    if candidates.len() >= 2 {
        return Some(candidates.swap_remove(1));
    }
    candidates.into_iter().next()
}

pub fn extract_metadata(doc: &PdfDoc) -> InvoiceMetadata {
    let (amount, reason) = validate_amount(&doc.full_text);
    InvoiceMetadata {
        amount,
        amount_reason: reason,
        invoice_no: extract_invoice_no(&doc.full_text),
        date: extract_invoice_date(&doc.full_text),
        seller: extract_seller(&doc.first_page_blocks, doc.first_page_width, &doc.full_text),
    }
}
