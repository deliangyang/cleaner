"""自定义表格控件：大小列按数值排序。"""
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import Qt


class SizeSortTableWidget(QTableWidget):
    """表格：点击「大小」列时按数值排序，其余列按默认文本排序。"""
    def sortItems(self, column, order):
        if column != 2:
            super().sortItems(column, order)
            return
        # 按「大小」列的数值（UserRole）排序（列索引 2）
        rows_data = []
        for row in range(self.rowCount()):
            size_item = self.item(row, 2)
            size_val = size_item.data(Qt.ItemDataRole.UserRole) if size_item else 0
            if size_val is None:
                size_val = 0
            hidden = self.isRowHidden(row)
            row_items = [self.takeItem(row, c) for c in range(self.columnCount())]
            rows_data.append((size_val, hidden, row_items))
        ascending = order == Qt.SortOrder.AscendingOrder
        rows_data.sort(key=lambda x: x[0], reverse=not ascending)
        self.setSortingEnabled(False)
        for row, (_, hidden, row_items) in enumerate(rows_data):
            for col, item in enumerate(row_items):
                if item is not None:
                    self.setItem(row, col, item)
            self.setRowHidden(row, hidden)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicator(column, order)
