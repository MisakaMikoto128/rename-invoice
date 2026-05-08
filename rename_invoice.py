# -*- coding: utf-8 -*-
"""
发票 PDF 重命名工具 —— 严格双重校验（小写数字 ↔ 中文大写）

用法:
  python rename_invoice.py <PDF文件 或 目录> [<PDF文件 或 目录> ...]
  无参数时, 扫描脚本所在目录

  --silent        静默模式 (右键菜单专用): 多次并发调用通过文件锁合并为一次处理,
                  不输出到控制台, 仅写入日志.
  --summary       与 --silent 配合: 处理完后弹出 Tk 汇总窗口 (默认不弹).

可靠性策略:
  1. 提取中文大写金额 (玖拾捌圆零壹分) 转为数字
  2. 提取所有 ¥X.XX 值
  3. 必须存在某个 ¥ 值精确等于中文大写转换后的数字
  4. 任一校验失败 -> 拒绝重命名, 保留原文件名
"""
import sys
import os
import re
import time
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
    try:
        input('按回车键退出...')
    except Exception:
        pass
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
LOG_PATH = SCRIPT_DIR / 'rename_invoice.log'
QUEUE_FILE = SCRIPT_DIR / '.queue.txt'
QUEUE_LOCK = SCRIPT_DIR / '.queue.lock'
LEADER_LOCK = SCRIPT_DIR / '.leader.lock'
DEBOUNCE_SECONDS = 0.25

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

    price_matches = PRICE_RE.findall(full_text)
    if not price_matches:
        return None, '未找到 ¥ 价格标记'
    prices = [round(float(p), 2) for p in price_matches]

    for cn_str, cn_val in chinese_decimals:
        for p in prices:
            if abs(p - cn_val) < 0.005:
                if cn_val + 0.005 < max(prices):
                    return None, (
                        f'中文大写金额 {cn_val} ({cn_str}) 不是最大 ¥ 值, '
                        f'最大 ¥ 值是 {max(prices)}, 异常'
                    )
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
        return 'skipped', '已有价格前缀, 跳过'

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


# ---------------------------------------------------------------------------
# 队列 + 文件锁: 让多次并发调用合并为一次处理
# ---------------------------------------------------------------------------

def _open_lockfile(path: Path):
    """Open / create a 1-byte lock file. Returns file handle (binary, r+b)."""
    if not path.exists():
        try:
            path.write_bytes(b'\0')
        except Exception:
            pass
    return open(path, 'r+b')


def _acquire_blocking(fh):
    import msvcrt
    fh.seek(0)
    deadline = time.time() + 5.0
    while True:
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if time.time() > deadline:
                return False
            time.sleep(0.02)


def _acquire_nonblocking(fh):
    import msvcrt
    fh.seek(0)
    try:
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _release(fh):
    import msvcrt
    fh.seek(0)
    try:
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def _append_to_queue(raw_args):
    """把原始路径参数(可能是文件夹/文件) append 到 queue, 由 leader 统一展开处理."""
    fh = _open_lockfile(QUEUE_LOCK)
    try:
        if not _acquire_blocking(fh):
            # 锁久占, 退化: 直接写, 接受微小竞态
            pass
        try:
            with open(QUEUE_FILE, 'a', encoding='utf-8') as qf:
                for p in raw_args:
                    qf.write(str(p) + '\n')
        finally:
            _release(fh)
    finally:
        fh.close()


def _drain_queue():
    """读出 queue 全部行并清空文件. 返回原始路径字符串列表."""
    fh = _open_lockfile(QUEUE_LOCK)
    try:
        if not _acquire_blocking(fh):
            return []
        try:
            if not QUEUE_FILE.exists():
                return []
            with open(QUEUE_FILE, 'r', encoding='utf-8') as qf:
                lines = qf.read().splitlines()
            with open(QUEUE_FILE, 'w', encoding='utf-8') as qf:
                pass
            return [ln for ln in lines if ln.strip()]
        finally:
            _release(fh)
    finally:
        fh.close()


def _show_summary_window(results):
    """results: list of (pdf_path, status, message). 弹一个 Tk 汇总窗口."""
    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except Exception:
        return  # tkinter 不可用时静默退化

    counts = {'renamed': 0, 'skipped': 0, 'failed': 0}
    for _, status, _ in results:
        counts[status] = counts.get(status, 0) + 1

    root = tk.Tk()
    root.title('发票重命名结果')
    root.geometry('760x420')

    icon_path = SCRIPT_DIR / 'assets' / 'icon.ico'
    if icon_path.exists():
        try:
            root.iconbitmap(str(icon_path))
        except Exception:
            pass

    header_text = (
        f'重命名: {counts["renamed"]}    '
        f'跳过: {counts["skipped"]}    '
        f'失败: {counts["failed"]}    '
        f'(总 {len(results)})'
    )
    header = tk.Label(root, text=header_text, font=('Microsoft YaHei', 12, 'bold'),
                      pady=8)
    header.pack(fill='x')

    txt = scrolledtext.ScrolledText(root, font=('Consolas', 10), wrap='none')
    txt.pack(fill='both', expand=True, padx=10, pady=4)
    txt.tag_config('ok', foreground='#1b8a3a')
    txt.tag_config('skip', foreground='#777777')
    txt.tag_config('fail', foreground='#c62828')

    if not results:
        txt.insert('end', '(没有任何 PDF 被处理)\n', 'skip')
    for pdf, status, msg in results:
        if status == 'renamed':
            txt.insert('end', f'[ OK ] {pdf.name}  ->  {msg}\n', 'ok')
        elif status == 'skipped':
            txt.insert('end', f'[SKIP] {pdf.name}  ({msg})\n', 'skip')
        else:
            txt.insert('end', f'[FAIL] {pdf.name}  -- {msg}\n', 'fail')
    txt.config(state='disabled')

    btn = tk.Button(root, text='关闭', command=root.destroy, width=12,
                    font=('Microsoft YaHei', 10))
    btn.pack(pady=8)

    root.attributes('-topmost', True)
    root.update()
    root.attributes('-topmost', False)
    root.mainloop()


def silent_main(args, show_summary):
    """静默 + leader 路径: 写队列, 抢锁, 抢到的当 leader 处理全部."""
    if not args:
        args = [os.getcwd()]
    _append_to_queue(args)

    leader_fh = _open_lockfile(LEADER_LOCK)
    try:
        if not _acquire_nonblocking(leader_fh):
            return  # 已有 leader, 静默退出
        try:
            time.sleep(DEBOUNCE_SECONDS)

            all_results = []
            while True:
                raw_paths = _drain_queue()
                if not raw_paths:
                    break
                pdfs = []
                seen = set()
                for raw in raw_paths:
                    p = Path(raw)
                    if not p.exists():
                        log_line(f'FAIL  (silent) 路径不存在: {raw}')
                        continue
                    for pdf in collect_pdfs(p):
                        key = str(pdf.resolve())
                        if key in seen:
                            continue
                        seen.add(key)
                        pdfs.append(pdf)
                for pdf in pdfs:
                    status, msg = process_pdf(pdf)
                    if status == 'failed':
                        log_line(f'FAIL  {pdf.name}  原因: {msg}')
                    elif status == 'skipped':
                        log_line(f'SKIP  {pdf.name}  ({msg})')
                    all_results.append((pdf, status, msg))

            if show_summary:
                _show_summary_window(all_results)
        finally:
            _release(leader_fh)
    finally:
        leader_fh.close()


# ---------------------------------------------------------------------------
# 直接模式: 老路径, 输出到 stdout (cmd 窗口可见)
# ---------------------------------------------------------------------------

def direct_main(args):
    if not args:
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
            print(c('[ OK ]', 'green'),
                  f'{pdf.name}',
                  c('->', 'gray'),
                  c(msg, 'cyan'))
        elif status == 'skipped':
            print(c('[SKIP]', 'gray'),
                  f'{pdf.name}',
                  c(f'({msg})', 'gray'))
        else:
            print(c('[FAIL]', 'red'),
                  f'{pdf.name}',
                  c(f'-- {msg}', 'red'))
            failures.append((pdf.name, msg))
            log_line(f'FAIL  {pdf.name}  原因: {msg}')

    print()
    print(c(
        f'重命名: {counts["renamed"]}  跳过: {counts["skipped"]}  失败: {counts["failed"]}',
        'cyan'))

    if failures:
        print(c('\n以下文件需手动处理:', 'red'))
        for n, m in failures:
            print(f'  - {n}')
            print(f'      原因: {m}')


def main():
    raw = sys.argv[1:]
    silent = False
    show_summary = False
    paths = []
    for a in raw:
        if a == '--silent':
            silent = True
        elif a == '--summary':
            show_summary = True
        else:
            paths.append(a)

    if silent:
        silent_main(paths, show_summary)
    else:
        direct_main(paths)


if __name__ == '__main__':
    main()
    try:
        if os.environ.get('RENAME_INVOICE_PAUSE') == '1':
            input('\n按回车键退出...')
    except (EOFError, KeyboardInterrupt):
        pass
