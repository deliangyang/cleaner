"""
大文件清理助手 - 入口
"""
import os
import sys
import warnings

# 在导入 Qt 前设置
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*sipPyTypeDict.*")
if "QT_QPA_PLATFORM_THEME" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM_THEME", "qt")

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("大文件清理助手")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
