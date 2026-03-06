"""主窗口：扫描设置、结果表格、筛选与删除。"""
import os
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QProgressBar,
    QProgressDialog,
    QSpinBox,
    QMessageBox,
    QMenu,
    QAbstractItemView,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from scanner import LargeFileInfo, DEFAULT_AGGREGATE_DIR_NAMES
from .widgets import SizeSortTableWidget
from .workers import ScanWorker, DeleteWorker
from utils import open_file_location


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("大文件清理助手")
        self.setMinimumSize(900, 560)
        self.resize(1000, 620)

        self.scan_worker: ScanWorker | None = None
        self.delete_worker: DeleteWorker | None = None
        self.results: list[LargeFileInfo] = []

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._build_scan_group(layout)
        self._build_table_section(layout)
        self.count_label = QLabel("共 0 个文件")
        layout.addWidget(self.count_label)
        self._update_count()

    def _build_scan_group(self, layout):
        group = QGroupBox("扫描设置")
        group_layout = QVBoxLayout(group)
        row = QHBoxLayout()
        row.addWidget(QLabel("扫描目录:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择要扫描的目录...")
        row.addWidget(self.path_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._on_browse)
        row.addWidget(browse_btn)
        group_layout.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("最小文件大小 (MB):"))
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(1, 100000)
        self.min_size_spin.setValue(10)
        row2.addWidget(self.min_size_spin)
        row2.addStretch()
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.clicked.connect(self._on_scan)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        row2.addWidget(self.scan_btn)
        row2.addWidget(self.stop_btn)
        group_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("汇总目录（不展开子文件）:"))
        self.aggregate_dirs_edit = QLineEdit()
        self.aggregate_dirs_edit.setPlaceholderText("逗号分隔的目录名，如: .git, node_modules, vendor")
        self.aggregate_dirs_edit.setText(", ".join(sorted(DEFAULT_AGGREGATE_DIR_NAMES)))
        row3.addWidget(self.aggregate_dirs_edit)
        group_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("排除目录（路径，逗号分隔）:"))
        self.exclude_paths_edit = QLineEdit()
        self.exclude_paths_edit.setPlaceholderText("例如: /proc, /sys, /dev")
        self.exclude_paths_edit.setText("/proc, /sys, /dev")
        row4.addWidget(self.exclude_paths_edit)
        group_layout.addLayout(row4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.status_label = QLabel("")
        group_layout.addWidget(self.status_label)
        group_layout.addWidget(self.progress_bar)
        layout.addWidget(group)

    def _build_table_section(self, layout):
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("大文件列表（按大小降序）:"))
        table_header.addStretch()
        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.clicked.connect(self._on_delete_selected)
        table_header.addWidget(self.delete_btn)
        layout.addLayout(table_header)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("正则筛选:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("按路径匹配，留空显示全部。例如: \\.iso$|\.mp4$")
        self.filter_edit.returnPressed.connect(self._apply_filter)
        filter_row.addWidget(self.filter_edit)
        self.filter_btn = QPushButton("应用筛选")
        self.filter_btn.clicked.connect(self._apply_filter)
        clear_filter_btn = QPushButton("清除")
        clear_filter_btn.clicked.connect(self._clear_filter)
        filter_row.addWidget(self.filter_btn)
        filter_row.addWidget(clear_filter_btn)
        layout.addLayout(filter_row)

        self.table = SizeSortTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["类型", "文件名", "大小", "路径", "所在目录"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择扫描目录")
        if path:
            self.path_edit.setText(path)

    def _on_scan(self):
        root = self.path_edit.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.warning(self, "提示", "请选择有效的扫描目录。")
            return
        self.filter_edit.clear()
        self.results.clear()
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)
        min_mb = self.min_size_spin.value()
        raw_agg = self.aggregate_dirs_edit.text().strip()
        agg_set = {s.strip() for s in raw_agg.split(",") if s.strip()} if raw_agg else None
        raw_exclude = self.exclude_paths_edit.text().strip()
        exclude_set = {s.strip() for s in raw_exclude.split(",") if s.strip()} if raw_exclude else None
        self.scan_worker = ScanWorker(root, float(min_mb), aggregate_dir_names=agg_set, exclude_paths=exclude_set)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.file_found.connect(self._on_file_found)
        self.scan_worker.finished_signal.connect(self._on_scan_finished)
        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在扫描...")
        self.scan_worker.start()

    def _on_scan_progress(self, path: str):
        self.status_label.setText(f"正在扫描: {path[:80]}...")

    def _on_file_found(self, info: LargeFileInfo):
        self.results.append(info)
        row = 0
        for i in range(self.table.rowCount()):
            size_item = self.table.item(i, 2)
            if size_item and (size_item.data(Qt.ItemDataRole.UserRole) or 0) < info.size:
                row = i
                break
        else:
            row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("目录" if info.is_aggregate_dir else "文件"))
        self.table.setItem(row, 1, QTableWidgetItem(info.name))
        size_item = QTableWidgetItem(info.size_human)
        size_item.setData(Qt.ItemDataRole.UserRole, info.size)
        self.table.setItem(row, 2, size_item)
        self.table.setItem(row, 3, QTableWidgetItem(info.path))
        self.table.setItem(row, 4, QTableWidgetItem(info.directory))
        self._update_count()

    def _on_scan_finished(self):
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("扫描完成。")
        self.table.setSortingEnabled(True)
        self.scan_worker = None

    def _on_stop(self):
        if self.scan_worker:
            self.scan_worker.cancel()

    def _update_count(self):
        total = self.table.rowCount()
        visible = sum(1 for i in range(total) if not self.table.isRowHidden(i))
        total_bytes = sum(self.table.item(i, 2).data(Qt.ItemDataRole.UserRole) or 0 for i in range(total))
        visible_bytes = sum(
            self.table.item(i, 2).data(Qt.ItemDataRole.UserRole) or 0
            for i in range(total) if not self.table.isRowHidden(i)
        )
        def fmt(b):
            s = b
            for u in ("B", "KB", "MB", "GB", "TB"):
                if s < 1024:
                    return f"{s:.1f} {u}"
                s /= 1024
            return f"{s:.1f} PB"
        if visible < total:
            self.count_label.setText(f"显示 {visible} / 共 {total} 项，当前显示约 {fmt(visible_bytes)}（全部约 {fmt(total_bytes)}）")
        else:
            self.count_label.setText(f"共 {total} 项，总大小约 {fmt(total_bytes)}")

    def _on_table_context_menu(self, pos):
        menu = QMenu(self)
        index = self.table.indexAt(pos)
        row = index.row() if index.isValid() else -1
        is_dir_row = row >= 0 and (t := self.table.item(row, 0)) and t.text() == "目录"
        open_dir = QAction("打开所在目录", self)
        open_dir.triggered.connect(self._open_selected_directory)
        menu.addAction(open_dir)
        if is_dir_row:
            continue_scan = QAction("继续在此目录查找大文件", self)
            continue_scan.triggered.connect(lambda checked=False, r=row: self._scan_from_row(r))
            menu.addAction(continue_scan)
        delete_action = QAction("删除选中", self)
        delete_action.triggered.connect(self._on_delete_selected)
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_selected_directory(self):
        row = self.table.currentRow()
        if row < 0:
            return
        path_item = self.table.item(row, 3)
        if not path_item:
            return
        path = path_item.text()
        if open_file_location(path):
            self.status_label.setText(f"已打开: {Path(path).parent}")
        else:
            QMessageBox.warning(self, "提示", "无法打开所在目录。")

    def _scan_from_row(self, row: int):
        if row < 0:
            return
        path_item = self.table.item(row, 3)
        if not path_item:
            return
        path = path_item.text().strip()
        if not path:
            return
        path = str(Path(path).expanduser().resolve())
        if not os.path.isdir(path):
            QMessageBox.warning(self, "提示", "该路径不是有效目录或已被删除：\n" + path)
            return
        self.path_edit.setText(path)
        self._on_scan()

    def _apply_filter(self):
        pattern = self.filter_edit.text().strip()
        total = self.table.rowCount()
        if not pattern:
            for i in range(total):
                self.table.setRowHidden(i, False)
            self._update_count()
            self.status_label.setText("已显示全部文件。")
            return
        try:
            rx = re.compile(pattern)
        except re.error as e:
            QMessageBox.warning(self, "正则错误", f"无效的正则表达式：\n{e}")
            return
        shown = 0
        for i in range(total):
            path_item = self.table.item(i, 3)
            path = path_item.text() if path_item else ""
            match = rx.search(path)
            self.table.setRowHidden(i, not match)
            if match:
                shown += 1
        self._update_count()
        self.status_label.setText(f"筛选后显示 {shown} 个文件。")

    def _clear_filter(self):
        self.filter_edit.clear()
        self._apply_filter()

    def _on_delete_selected(self):
        rows = set(index.row() for index in self.table.selectionModel().selectedRows())
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择要删除的项。")
            return
        paths = [self.table.item(r, 3).text() for r in rows if self.table.item(r, 3)]
        if not paths:
            return
        n = len(paths)
        msg = f"确定要删除选中的 {n} 项吗？\n\n删除目录将递归删除其下所有内容，此操作不可恢复。"
        if n <= 3:
            msg += "\n\n" + "\n".join(Path(p).name for p in paths)
        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.delete_btn.setEnabled(False)
        progress = QProgressDialog("正在准备删除...", "取消", 0, n, self)
        progress.setWindowTitle("删除中")
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(0)

        def on_progress(current: int, total: int, path: str):
            name = Path(path).name
            if len(name) > 40:
                name = name[:37] + "..."
            progress.setLabelText(f"正在删除 ({current}/{total}): {name}")
            progress.setValue(current)

        def on_cancel():
            if self.delete_worker:
                self.delete_worker.cancel()

        def on_finished(deleted_paths: list, failed_list: list):
            progress.close()
            self.delete_btn.setEnabled(True)
            self.delete_worker = None
            deleted_set = set(deleted_paths)
            path_to_row = {self.table.item(r, 3).text(): r for r in range(self.table.rowCount()) if self.table.item(r, 3)}
            for row in sorted((path_to_row[p] for p in deleted_set if p in path_to_row), reverse=True):
                self.table.removeRow(row)
            self.results = [r for r in self.results if r.path not in deleted_set]
            self._update_count()
            if failed_list:
                QMessageBox.warning(
                    self, "删除部分失败",
                    "以下项删除失败：\n\n" + "\n".join(f"{p}\n  {e}" for p, e in failed_list[:5])
                    + ("\n..." if len(failed_list) > 5 else ""),
                )
            else:
                self.status_label.setText(f"已删除 {len(deleted_paths)} 项。")

        progress.canceled.connect(on_cancel)
        self.delete_worker = DeleteWorker(paths)
        self.delete_worker.progress.connect(on_progress)
        self.delete_worker.finished_with_result.connect(on_finished)
        self.delete_worker.start()

    def closeEvent(self, event):
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.scan_worker.cancel()
            self.scan_worker.wait(5000)
        if self.delete_worker is not None and self.delete_worker.isRunning():
            self.delete_worker.cancel()
            self.delete_worker.wait(5000)
        event.accept()
