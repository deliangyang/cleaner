"""系统相关工具：打开目录等。"""
import os
import platform
from pathlib import Path


def open_directory(path: str) -> bool:
    """在系统文件管理器中打开目录。返回是否成功。"""
    path = str(Path(path).resolve())
    if not os.path.isdir(path):
        path = str(Path(path).parent)
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
        return True
    except Exception:
        return False


def open_file_location(file_path: str) -> bool:
    """打开文件所在目录。"""
    dir_path = str(Path(file_path).parent)
    return open_directory(dir_path)
