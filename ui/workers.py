"""后台线程：扫描与删除。"""
import os
import shutil
from typing import Optional, List, Set
from PyQt5.QtCore import QThread, pyqtSignal

from scanner import scan_directory, LargeFileInfo


class ScanWorker(QThread):
    """后台扫描线程"""
    progress = pyqtSignal(str)
    file_found = pyqtSignal(object)  # LargeFileInfo
    finished_signal = pyqtSignal()

    def __init__(self, root: str, min_size_mb: float, aggregate_dir_names: Optional[Set[str]] = None, exclude_paths: Optional[Set[str]] = None):
        super().__init__()
        self.root = root
        self.min_size_mb = min_size_mb
        self.aggregate_dir_names = aggregate_dir_names
        self.exclude_paths = exclude_paths
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            for info in scan_directory(
                self.root,
                min_size_mb=self.min_size_mb,
                progress_callback=lambda p: self.progress.emit(p),
                cancel_check=lambda: self._cancel,
                aggregate_dir_names=self.aggregate_dir_names,
                exclude_paths=self.exclude_paths,
            ):
                self.file_found.emit(info)
        finally:
            self.finished_signal.emit()


class DeleteWorker(QThread):
    """后台删除线程：逐个删除文件/目录，避免阻塞界面。"""
    progress = pyqtSignal(int, int, str)  # current, total, current_path
    finished_with_result = pyqtSignal(list, list)  # deleted_paths, failed_list[(path, err)]

    def __init__(self, paths: List[str]):
        super().__init__()
        self.paths = paths
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        deleted = []
        failed = []
        n = len(self.paths)
        for i, path in enumerate(self.paths):
            if self._cancel:
                break
            self.progress.emit(i + 1, n, path)
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    deleted.append(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                    deleted.append(path)
                else:
                    failed.append((path, "不存在"))
            except OSError as e:
                failed.append((path, str(e)))
        self.finished_with_result.emit(deleted, failed)
