//! 中文大写金额 → 数字
//!
//! 例: "玖拾捌圆零壹分" -> 98.01
//! 例: "壹仟贰佰叁拾肆圆伍角陆分" -> 1234.56
//! 例: "壹佰零伍圆整" -> 105.00

use anyhow::{anyhow, Result};

/// 中文大写数字字符 -> 值
fn digit_value(ch: char) -> Option<u64> {
    match ch {
        '零' | '〇' => Some(0),
        '壹' => Some(1), '贰' => Some(2), '叁' => Some(3), '肆' => Some(4), '伍' => Some(5),
        '陆' => Some(6), '柒' => Some(7), '捌' => Some(8), '玖' => Some(9),
        _ => None,
    }
}

fn small_unit(ch: char) -> Option<u64> {
    match ch {
        '拾' | '十' => Some(10),
        '佰' | '百' => Some(100),
        '仟' | '千' => Some(1000),
        _ => None,
    }
}

fn big_unit(ch: char) -> Option<u64> {
    match ch {
        '万' => Some(10_000),
        '亿' => Some(100_000_000),
        _ => None,
    }
}

/// 中文大写金额合法字符集 (用于扫描 candidate)
pub fn is_amount_char(ch: char) -> bool {
    digit_value(ch).is_some()
        || small_unit(ch).is_some()
        || big_unit(ch).is_some()
        || matches!(ch, '圆' | '元' | '角' | '分' | '整')
}

/// 解析整数部分: 壹仟贰佰叁拾肆 -> 1234
fn parse_chinese_int(s: &str) -> u64 {
    let mut total: u64 = 0;
    let mut section: u64 = 0;
    let mut digit: u64 = 0;
    for ch in s.chars() {
        if let Some(d) = digit_value(ch) {
            digit = d;
        } else if let Some(u) = small_unit(ch) {
            let multiplier = if digit > 0 { digit } else { 1 };
            section += multiplier * u;
            digit = 0;
        } else if let Some(u) = big_unit(ch) {
            section += digit;
            if section == 0 {
                section = 1;
            }
            total += section * u;
            section = 0;
            digit = 0;
        }
    }
    section += digit;
    total + section
}

/// 中文大写金额 -> Decimal (返回 f64, 容差 0.005 比对足够)
pub fn chinese_amount_to_decimal(s: &str) -> Result<f64> {
    let s = s.trim();
    let yuan_idx = s
        .find('圆')
        .or_else(|| s.find('元'))
        .ok_or_else(|| anyhow!("中文大写金额缺少 圆/元: {:?}", s))?;

    let int_part = &s[..yuan_idx];
    // 跳过 圆 / 元 (UTF-8 长度 3)
    let frac_part = &s[yuan_idx + '圆'.len_utf8()..];

    let integer = parse_chinese_int(int_part);

    let mut jiao: u64 = 0;
    let mut fen: u64 = 0;
    let mut last_digit: u64 = 0;
    for ch in frac_part.chars() {
        if let Some(d) = digit_value(ch) {
            last_digit = d;
        } else if ch == '角' {
            jiao = last_digit;
            last_digit = 0;
        } else if ch == '分' {
            fen = last_digit;
            last_digit = 0;
        } // '整' 直接忽略
    }

    let value = integer as f64 + (jiao as f64) / 10.0 + (fen as f64) / 100.0;
    // 保留 2 位
    Ok((value * 100.0).round() / 100.0)
}

/// 从全文找出所有候选中文大写金额 (按 amount-char 字符段切分)
pub fn find_chinese_amounts(text: &str) -> Vec<String> {
    let mut candidates: Vec<String> = Vec::new();
    let mut buf = String::new();
    for ch in text.chars() {
        if is_amount_char(ch) {
            buf.push(ch);
        } else if !buf.is_empty() {
            candidates.push(std::mem::take(&mut buf));
        }
    }
    if !buf.is_empty() {
        candidates.push(buf);
    }
    candidates
        .into_iter()
        .filter(|c| {
            (c.contains('圆') || c.contains('元'))
                && c.chars().any(|ch| digit_value(ch).is_some())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx_eq(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-6
    }

    #[test]
    fn test_simple_yuan_jiao_fen() {
        assert!(approx_eq(chinese_amount_to_decimal("玖拾捌圆零壹分").unwrap(), 98.01));
        assert!(approx_eq(chinese_amount_to_decimal("壹仟贰佰叁拾肆圆伍角陆分").unwrap(), 1234.56));
    }

    #[test]
    fn test_zheng_full_yuan() {
        assert!(approx_eq(chinese_amount_to_decimal("壹佰零伍圆整").unwrap(), 105.00));
        assert!(approx_eq(chinese_amount_to_decimal("贰拾圆整").unwrap(), 20.00));
    }

    #[test]
    fn test_wan() {
        assert!(approx_eq(chinese_amount_to_decimal("壹万贰仟叁佰肆拾伍圆陆角柒分").unwrap(), 12345.67));
        assert!(approx_eq(chinese_amount_to_decimal("壹万圆整").unwrap(), 10000.00));
    }

    #[test]
    fn test_yi() {
        assert!(approx_eq(chinese_amount_to_decimal("壹亿圆整").unwrap(), 100_000_000.00));
    }

    #[test]
    fn test_only_jiao_or_fen() {
        assert!(approx_eq(chinese_amount_to_decimal("零圆叁角").unwrap(), 0.30));
        assert!(approx_eq(chinese_amount_to_decimal("零圆零陆分").unwrap(), 0.06));
    }

    #[test]
    fn test_yuan_only_no_zheng() {
        // 价税合计大写不带'整'但金额是整数的边界
        assert!(approx_eq(chinese_amount_to_decimal("壹拾陆圆陆角整").unwrap(), 16.60));
    }

    #[test]
    fn test_alternative_yuan_char() {
        assert!(approx_eq(chinese_amount_to_decimal("玖拾捌元零壹分").unwrap(), 98.01));
    }

    #[test]
    fn test_ling_in_middle() {
        assert!(approx_eq(chinese_amount_to_decimal("壹仟零壹圆整").unwrap(), 1001.00));
    }

    #[test]
    fn test_find_chinese_amounts_picks_yuan_only() {
        let text = "壹拾陆圆陆角整 ¥16.60 备注 项目";
        let v = find_chinese_amounts(text);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0], "壹拾陆圆陆角整");
    }

    #[test]
    fn test_find_filters_no_yuan_marker() {
        // 没有 圆/元 的字符串不应被认作金额
        let text = "拾佰仟万 单纯单位字符";
        let v = find_chinese_amounts(text);
        assert!(v.is_empty(), "got {:?}", v);
    }

    #[test]
    fn test_find_two_amounts_ok() {
        // 同一发票理论上只有一个大写金额, 但解析器允许多个
        let text = "壹圆整 一些其他字 贰圆整";
        let v = find_chinese_amounts(text);
        assert_eq!(v.len(), 2);
    }

    #[test]
    fn test_is_amount_char() {
        assert!(is_amount_char('壹'));
        assert!(is_amount_char('圆'));
        assert!(is_amount_char('整'));
        assert!(!is_amount_char('A'));
        assert!(!is_amount_char('1'));
    }

    #[test]
    fn test_decimal_two_places() {
        // 0.005 边界
        let v = chinese_amount_to_decimal("零圆贰角伍分").unwrap();
        assert!((v - 0.25).abs() < 1e-9);
    }

    #[test]
    fn test_only_fen() {
        let v = chinese_amount_to_decimal("零圆零分").unwrap();
        assert!(v.abs() < 1e-9);
    }
}
