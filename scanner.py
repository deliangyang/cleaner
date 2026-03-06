"""
大文件扫描器：在指定目录下递归扫描并收集超过阈值大小的文件信息。
支持将指定名称的目录（如 .git, node_modules）整体汇总显示，不展开子文件。
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, Callable, Optional, Set

# 默认作为汇总的目录名（不递归列出子文件，只显示该目录总大小）
DEFAULT_AGGREGATE_DIR_NAMES = {
    ".git", "node_modules", "vendor", "target",
    "__pycache__", "dist", "build", ".venv", "venv",
    "out", "bin", ".cache", ".next", ".nuxt",
}


def _get_dir_size(path: str, cancel_check: Optional[Callable[[], bool]] = None) -> int:
    """递归计算目录总大小（字节）。"""
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path, topdown=True):
            if cancel_check and cancel_check():
                return total
            for name in filenames:
                if cancel_check and cancel_check():
                    return total
                try:
                    full = os.path.join(dirpath, name)
                    total += os.path.getsize(full)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


@dataclass
class LargeFileInfo:
    """大文件/汇总目录信息"""
    path: str
    size: int
    name: str
    is_aggregate_dir: bool = False

    @property
    def size_human(self) -> str:
        """人类可读的文件大小（不修改原 size）"""
        s = self.size
        for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
            if s < 1024:
                return f"{s:.1f} {unit}"
            s /= 1024
        return f"{s:.1f} PB"

    @property
    def directory(self) -> str:
        """所在目录（父目录路径）"""
        return str(Path(self.path).parent)


def scan_directory(
    root: str,
    min_size_mb: float = 10.0,
    progress_callback: Optional[Callable[[str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    aggregate_dir_names: Optional[Set[str]] = None,
    exclude_paths: Optional[Set[str]] = None,
) -> Iterator[LargeFileInfo]:
    """
    递归扫描目录，yield 大于 min_size_mb MB 的文件；
    若目录名在 aggregate_dir_names 中，则只 yield 该目录的总大小一条记录，不展开子文件；
    exclude_paths 中的路径及其子目录不会进入扫描。

    :param root: 根目录路径
    :param min_size_mb: 最小大小（MB），文件或汇总目录达到该值才列出
    :param progress_callback: 当前扫描路径回调
    :param cancel_check: 返回 True 表示取消扫描
    :param aggregate_dir_names: 作为汇总的目录名集合，不递归进入，只统计总大小后输出一条
    :param exclude_paths: 要排除的绝对路径集合，这些目录及其子目录不会进入
    """
    root = os.path.abspath(root)
    min_bytes = int(min_size_mb * 1024 * 1024)
    agg = aggregate_dir_names if aggregate_dir_names is not None else DEFAULT_AGGREGATE_DIR_NAMES
    excluded = set()
    if exclude_paths:
        for p in exclude_paths:
            p = os.path.abspath(p.strip())
            if p:
                excluded.add(p)
    sep = os.sep

    def should_skip_dir(parent: str, dirname: str) -> bool:
        full = os.path.abspath(os.path.join(parent, dirname))
        if full in excluded:
            return True
        for ex in excluded:
            if full == ex or full.startswith(ex + sep):
                return True
        return False

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        if cancel_check and cancel_check():
            return
        if progress_callback:
            progress_callback(dirpath)

        # 排除指定路径：不进入这些目录及其子目录
        dirnames[:] = [d for d in dirnames if not should_skip_dir(dirpath, d)]

        # 先处理“汇总目录”：从 dirnames 中移除并统计总大小，不递归进入
        for d in list(dirnames):
            if d not in agg:
                continue
            dirnames.remove(d)
            full_path = os.path.join(dirpath, d)
            full_path = os.path.abspath(full_path)
            if cancel_check and cancel_check():
                return
            if progress_callback:
                progress_callback(full_path)
            try:
                if os.path.islink(full_path):
                    # 软链接：只取链接自身大小（指向路径的长度），不跟到目标
                    size = os.lstat(full_path).st_size
                else:
                    size = _get_dir_size(full_path, cancel_check=cancel_check)
                if size >= min_bytes:
                    yield LargeFileInfo(path=full_path, size=size, name=d, is_aggregate_dir=True)
            except (OSError, PermissionError):
                pass

        # 再处理当前目录下的普通文件
        for name in filenames:
            if cancel_check and cancel_check():
                return
            full_path = os.path.join(dirpath, name)
            full_path = os.path.abspath(full_path)
            try:
                # 使用 lstat：软链接显示自身大小（指向路径长度），不跟到目标文件
                st = os.lstat(full_path)
                if st.st_size >= min_bytes:
                    yield LargeFileInfo(path=full_path, size=st.st_size, name=name)
            except (OSError, PermissionError):
                continue
