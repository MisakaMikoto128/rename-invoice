//! 右键多选场景的跨进程队列 + leader 锁.
//!
//! 两个 bin 都要用, 各自通过 `#[path = "queue.rs"] mod queue;` 引入.
//! 因此这里**只依赖 std + fs2**, 绝不碰 pdfium / slint / xlsx ——
//! rename-invoice-w.exe 必须保持"小而快", 原因见 shim.rs 顶部注释.
//!
//! 文件 (都放在 .exe 同目录):
//!   .queue.txt    待处理路径, 一行一条
//!   .queue.lock   保护 .queue.txt 读写
//!   .leader.lock  谁拿到谁负责排空队列; 拿不到说明已经有 worker 在跑
//!   .spawn.lock   保护"检查 worker 是否存在 -> 拉起 worker"这段临界区,
//!                 否则一次多选会拉起好几个重进程

// 两个 bin 各自只用到其中一部分函数, 另一半在对方那边用.
#![allow(dead_code)]

use fs2::FileExt;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::time::{Duration, Instant};

/// 拉起 worker 后, 最多等它多久去把 .leader.lock 抢到手.
/// 等这一下是为了让后续的 shim 能看到"已经有 worker 了", 不再重复拉起.
const WORKER_HANDOFF_TIMEOUT: Duration = Duration::from_millis(1000);
const WORKER_HANDOFF_POLL: Duration = Duration::from_millis(20);

fn lock_dir() -> PathBuf {
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."))
}

fn queue_file() -> PathBuf {
    lock_dir().join(".queue.txt")
}
fn queue_lock_file() -> PathBuf {
    lock_dir().join(".queue.lock")
}
fn leader_lock_file() -> PathBuf {
    lock_dir().join(".leader.lock")
}
fn spawn_lock_file() -> PathBuf {
    lock_dir().join(".spawn.lock")
}

fn open_lockfile(path: PathBuf) -> std::io::Result<File> {
    OpenOptions::new()
        .create(true)
        .read(true)
        .write(true)
        .open(path)
}

/// 把路径追加到队列. 必须在任何"要不要干活"的判断**之前**调用,
/// 否则被闸门挡掉的进程会把它那份文件弄丢.
pub fn append_to_queue(paths: &[PathBuf]) -> std::io::Result<()> {
    let lockfile = open_lockfile(queue_lock_file())?;
    lockfile.lock_exclusive()?;
    let result = (|| -> std::io::Result<()> {
        let mut qf = OpenOptions::new()
            .create(true)
            .append(true)
            .open(queue_file())?;
        for p in paths {
            writeln!(qf, "{}", p.display())?;
        }
        Ok(())
    })();
    let _ = FileExt::unlock(&lockfile);
    result
}

/// 读出队列全部内容并截断. 返回原始路径字符串.
pub fn drain_queue() -> Vec<String> {
    let lockfile = match open_lockfile(queue_lock_file()) {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };
    if lockfile.lock_exclusive().is_err() {
        return Vec::new();
    }
    let queue_path = queue_file();
    let mut lines: Vec<String> = Vec::new();
    if queue_path.exists() {
        if let Ok(f) = OpenOptions::new().read(true).open(&queue_path) {
            for line in BufReader::new(f).lines().map_while(Result::ok) {
                if !line.trim().is_empty() {
                    lines.push(line);
                }
            }
        }
        let _ = OpenOptions::new()
            .write(true)
            .truncate(true)
            .open(&queue_path);
    }
    let _ = FileExt::unlock(&lockfile);
    lines
}

/// 抢 leader 锁. 拿到就返回句柄 (**必须一直持有到干完活**), 拿不到返回 None.
pub fn try_become_leader() -> Option<File> {
    let f = open_lockfile(leader_lock_file()).ok()?;
    if f.try_lock_exclusive().is_ok() {
        Some(f)
    } else {
        None
    }
}

pub fn release_leader(f: &File) {
    let _ = FileExt::unlock(f);
}

/// 现在是否已经有 worker 在跑 (即 .leader.lock 被别人独占着).
/// 注意这是个瞬时快照, 只用来避免重复拉起重进程, 不用于正确性判断 ——
/// 正确性由"先入队, 再判断"的顺序保证.
fn worker_running() -> bool {
    match open_lockfile(leader_lock_file()) {
        Ok(f) => {
            if f.try_lock_exclusive().is_ok() {
                let _ = FileExt::unlock(&f);
                false
            } else {
                true
            }
        }
        // 打不开锁文件时保守认为没有 worker, 宁可多拉一个也不能一个都不拉
        Err(_) => false,
    }
}

/// 「没有 worker 就拉一个」的临界区版本. 返回是否真的拉起了新 worker.
///
/// .spawn.lock 用 **try_lock**: 抢不到说明已经有别的 shim 正在拉 worker,
/// 而我们的路径在调用本函数之前就已经入队了, 那个 worker 一定会捞到它 ——
/// 所以直接返回, 不要在这儿排队. 用阻塞锁的话, 一次多选 N 个文件会让 N-1 个
/// shim 全堵在锁上陪跑, 任务管理器里就是一排进程 (虽然每个只有 0.25 MB).
///
/// 拿到锁的那一个会一直握到新 worker 真的抢下 leader 锁 (或超时), 这样后面的
/// shim 看到的要么是"锁被占着", 要么是"worker 已经在跑", 都不会重复拉起重进程.
pub fn spawn_worker_if_needed<F>(spawn: F) -> std::io::Result<bool>
where
    F: FnOnce() -> std::io::Result<()>,
{
    let guard = open_lockfile(spawn_lock_file())?;
    if guard.try_lock_exclusive().is_err() {
        return Ok(false);
    }
    let result = (|| -> std::io::Result<bool> {
        if worker_running() {
            return Ok(false);
        }
        spawn()?;
        let deadline = Instant::now() + WORKER_HANDOFF_TIMEOUT;
        while Instant::now() < deadline {
            if worker_running() {
                break;
            }
            std::thread::sleep(WORKER_HANDOFF_POLL);
        }
        Ok(true)
    })();
    let _ = FileExt::unlock(&guard);
    result
}
