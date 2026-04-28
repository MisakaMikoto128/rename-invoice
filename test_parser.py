# -*- coding: utf-8 -*-
"""中文大写金额解析单元测试. 财务可靠性的最后一道防线."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from rename_invoice import chinese_amount_to_decimal, find_chinese_amounts

CASES = [
    ('玖拾捌圆零壹分', 98.01),
    ('壹佰柒拾柒圆整', 177.00),
    ('壹元整', 1.00),
    ('壹拾元整', 10.00),
    ('壹仟贰佰叁拾肆圆伍角陆分', 1234.56),
    ('壹万贰仟叁佰肆拾伍圆陆角柒分', 12345.67),
    ('壹佰零伍圆整', 105.00),
    ('壹仟零伍拾圆整', 1050.00),
    ('壹佰元零伍分', 100.05),
    ('贰拾元', 20.00),
    ('壹亿圆整', 100000000.00),
    ('贰仟万圆整', 20000000.00),
    ('玖佰玖拾玖元玖角玖分', 999.99),
    # 用 '元' 代替 '圆'
    ('玖拾捌元零壹分', 98.01),
]

failed = 0
for text, expected in CASES:
    try:
        actual = chinese_amount_to_decimal(text)
        ok = abs(actual - expected) < 0.005
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            failed += 1
        print(f'[{status}] {text!r:30s} -> {actual!r}  (expected {expected})')
    except Exception as e:
        failed += 1
        print(f'[FAIL] {text!r:30s} -> EXCEPTION: {e}')

# Test find_chinese_amounts
print('\n--- find_chinese_amounts ---')
sample_text = """
价税合计（大写）（小写）
玖拾捌圆零壹分
¥98.01
其他文字
"""
found = find_chinese_amounts(sample_text)
print(f'Found: {found}')
if found != ['玖拾捌圆零壹分']:
    print(f'[FAIL] expected [\'玖拾捌圆零壹分\'], got {found}')
    failed += 1
else:
    print('[PASS]')

print(f'\n=== {len(CASES) + 1 - failed} passed, {failed} failed ===')
sys.exit(1 if failed else 0)
