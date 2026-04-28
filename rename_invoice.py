# -*- coding: utf-8 -*-
"""
发票 PDF 重命名工具 —— 严格双重校验（小写数字 ↔ 中文大写）

用法:
  python rename_invoice.py <PDF文件 或 目录> [<PDF文件 或 目录> ...]
  无参数时, 扫描脚本所在目录

可靠性策略:
  1. 提取中文大写金额 (玖拾捌圆零壹分) 转为数字
  2. 提取所有 ¥X.XX 值
  3. 必须存在某个 ¥ 值精确等于中文大写转换后的数字
  4. 任一校验失败 -> 拒绝重命名, 保留原文件名
"""
import sys
import os
import re
import glob
import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

try:
    import fitz  # PyMuPDF
except ImportError:
    print('[ERROR] 缺少依赖 PyMuPDF. 请运行: pip install pymupdf')
    input('按回车键退出...')
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
LOG_PATH = SCRIPT_DIR / 'rename_invoice.log'

CHINESE_DIGITS = {
    '零': 0, '〇': 0,
    '壹': 1, '贰': 2, '叁': 3, '肆': 4, '伍': 5,
    '陆': 6, '柒': 7, '捌': 8, '玖': 9,
}
SMALL_UNITS = {'拾': 10, '佰': 100, '仟': 1000, '十': 10, '百': 100, '千': 1000}
BIG_UNITS = {'万': 10000, '亿': 100000000}

CHINESE_AMOUNT_CHARS = set(CHINESE_DIGITS) | set(SMALL_UNITS) | set(BIG_UNITS) | set('圆元角分整')

ALREADY_PREFIXED_RE = re.compile(r'^\d+(\.\d{1,2})?元-')
PRICE_RE = re.compile(r'¥\s*(\d+(?:\.\d{1,2})?)')


def parse_chinese_int(s: str) -> int:
    """壹仟贰佰叁拾肆 -> 1234"""
    total = 0
    section = 0
    digit = 0
    for ch in s:
        if ch in CHINESE_DIGITS:
            digit = CHINESE_DIGITS[ch]
        elif ch in SMALL_UNITS:
            unit = SMALL_UNITS[ch]
            multiplier = digit if digit > 0 else 1
            section += multiplier * unit
            digit = 0
        elif ch in BIG_UNITS:
            section += digit
            if section == 0:
                section = 1
            total += section * BIG_UNITS[ch]
            section = 0
            digit = 0
    section += digit
    total += section
    return total


def chinese_amount_to_decimal(s: str) -> float:
    """玖拾捌圆零壹分 -> 98.01"""
    s = s.strip()
    yuan_idx = -1
    for marker in ('圆', '元'):
        idx = s.find(marker)
        if idx != -1:
            yuan_idx = idx
            break
    if yuan_idx == -1:
        raise ValueError(f'中文大写金额缺少 圆/元: {s!r}')

    int_part = s[:yuan_idx]
    frac_part = s[yuan_idx + 1:]

    integer = parse_chinese_int(int_part)

    jiao = 0
    fen = 0
    last_digit = 0
    for ch in frac_part:
        if ch in CHINESE_DIGITS:
            last_digit = CHINESE_DIGITS[ch]
        elif ch == '角':
            jiao = last_digit
            last_digit = 0
        elif ch == '分':
            fen = last_digit
            last_digit = 0
        elif ch == '整':
            pass

    return round(integer + jiao / 10 + fen / 100, 2)


def find_chinese_amounts(text: str):
    """从文本中找出所有候选中文大写金额."""
    candidates = []
    buf = []
    for ch in text:
        if ch in CHINESE_AMOUNT_CHARS:
            buf.append(ch)
        else:
            if buf:
                candidates.append(''.join(buf))
                buf = []
    if buf:
        candidates.append(''.join(buf))
    return [c for c in candidates if ('圆' in c or '元' in c) and any(d in c for d in CHINESE_DIGITS)]


def extract_total_from_pdf(pdf_path: Path):
    """
    返回 (amount_str, reason).
    成功: amount_str 形如 "98.01", reason 为 None.
    失败: amount_str 为 None, reason 说明原因.
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        return None, f'无法打开 PDF: {e}'

    full_text = ''
    try:
        for page in doc:
            full_text += page.get_text() + '\n'
    finally:
        doc.close()

    if not full_text.strip():
        return None, 'PDF 无文字层 (可能是扫描件), 不支持'

    # 1) 找中文大写金额
    chinese_candidates = find_chinese_amounts(full_text)
    if not chinese_candidates:
        return None, '未找到中文大写金额'

    chinese_decimals = []
    for c in chinese_candidates:
        try:
            chinese_decimals.append((c, chinese_amount_to_decimal(c)))
        except Exception:
            continue
    if not chinese_decimals:
        return None, f'中文大写金额无法解析: {chinese_candidates}'

    # 2) 找所有 ¥X.XX 值
    price_matches = PRICE_RE.findall(full_text)
    if not price_matches:
        return None, '未找到 ¥ 价格标记'
    prices = [round(float(p), 2) for p in price_matches]

    # 3) 校验: 中文大写金额必须等于某个 ¥ 值
    for cn_str, cn_val in chinese_decimals:
        for p in prices:
            if abs(p - cn_val) < 0.005:
                # 4) 加固: 中文金额必须是最大 ¥ 值 (价税合计 >= 金额, >= 税额)
                if cn_val + 0.005 < max(prices):
                    return None, (
                        f'中文大写金额 {cn_val} ({cn_str}) 不是最大 ¥ 值, '
                        f'最大 ¥ 值是 {max(prices)}, 异常'
                    )
                # 格式化为两位小数
                return f'{cn_val:.2f}', None

    return None, (
        f'中文大写金额与 ¥ 值不匹配. '
        f'中文: {[(s, v) for s, v in chinese_decimals]}, ¥ 值: {prices}'
    )


def safe_target_path(directory: Path, name: str) -> Path:
    """目标文件已存在时, 追加 (2), (3) ... 不覆盖."""
    target = directory / name
    if not target.exists():
        return target
    stem, ext = os.path.splitext(name)
    n = 2
    while True:
        candidate = directory / f'{stem} ({n}){ext}'
        if not candidate.exists():
            return candidate
        n += 1


def log_line(line: str):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] {line}\n')
    except Exception:
        pass


def process_pdf(pdf_path: Path):
    """
    返回 ('renamed' | 'skipped' | 'failed', message)
    """
    name = pdf_path.name

    if ALREADY_PREFIXED_RE.match(name):
        return 'skipped', f'已有价格前缀, 跳过'

    amount_str, reason = extract_total_from_pdf(pdf_path)
    if amount_str is None:
        return 'failed', reason

    new_name = f'{amount_str}元-{name}'
    target = safe_target_path(pdf_path.parent, new_name)
    try:
        pdf_path.rename(target)
    except Exception as e:
        return 'failed', f'重命名失败: {e}'

    log_line(f'OK  {name}  ->  {target.name}  (金额={amount_str})')
    return 'renamed', target.name


def collect_pdfs(target: Path):
    if target.is_file():
        if target.suffix.lower() == '.pdf':
            return [target]
        return []
    if target.is_dir():
        return sorted(target.glob('*.pdf'))
    return []


# ANSI color (Windows 10+ terminal supports it)
def c(text, color):
    codes = {'red': '31', 'green': '32', 'yellow': '33', 'cyan': '36', 'gray': '90'}
    return f'\033[{codes.get(color, "0")}m{text}\033[0m'


def main():
    args = sys.argv[1:]
    if not args:
        # 无参数 -> 扫描脚本所在目录? 不, 应该是当前工作目录
        # 但是双击 .bat 时 cwd 是 .bat 所在目录, 所以 cwd 即"当前目录"
        args = [os.getcwd()]

    targets = []
    for arg in args:
        p = Path(arg)
        if not p.exists():
            print(c(f'[ERROR] 路径不存在: {arg}', 'red'))
            continue
        targets.extend(collect_pdfs(p))

    if not targets:
        print(c('[INFO] 没有找到 PDF 文件', 'yellow'))
        return

    print(c(f'\n=== 发票重命名 (共 {len(targets)} 个 PDF) ===\n', 'cyan'))

    counts = {'renamed': 0, 'skipped': 0, 'failed': 0}
    failures = []

    for pdf in targets:
        status, msg = process_pdf(pdf)
        counts[status] += 1
        if status == 'renamed':
            print(c(f'[ OK ]', 'green'),
                  f'{pdf.name}',
                  c('->', 'gray'),
                  c(msg, 'cyan'))
        elif status == 'skipped':
            print(c(f'[SKIP]', 'gray'),
                  f'{pdf.name}',
                  c(f'({msg})', 'gray'))
        else:
            print(c(f'[FAIL]', 'red'),
                  f'{pdf.name}',
                  c(f'-- {msg}', 'red'))
            failures.append((pdf.name, msg))
            log_line(f'FAIL  {pdf.name}  原因: {msg}')

    print()
    print(c(f'重命名: {counts["renamed"]}  跳过: {counts["skipped"]}  失败: {counts["failed"]}', 'cyan'))

    if failures:
        print(c('\n以下文件需手动处理:', 'red'))
        for n, m in failures:
            print(f'  - {n}')
            print(f'      原因: {m}')


if __name__ == '__main__':
    main()
    # 双击运行/拖放时, 让窗口停留以便查看结果
    if sys.stdin.isatty() if hasattr(sys.stdin, 'isatty') else False:
        pass
    try:
        if os.environ.get('RENAME_INVOICE_PAUSE') == '1':
            input('\n按回车键退出...')
    except (EOFError, KeyboardInterrupt):
        pass
