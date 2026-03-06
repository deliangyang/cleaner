# 大文件清理助手

桌面端大文件扫描工具：选择目录后扫描并列出超过指定大小的文件，支持打开所在目录、按列排序等。

## 功能

- 选择任意目录进行递归扫描
- 设置最小文件大小（MB），只列出大于该值的文件
- 列表显示：文件名、大小、完整路径、所在目录
- 支持按列排序（点击表头）
- 右键或菜单：**打开所在目录**（在系统文件管理器中打开并定位）
- 扫描在后台线程进行，可随时停止

## 环境与运行

- Python 3.10+
- 依赖：`PyQt6`

```bash
pip install -r requirements.txt
python main.py
```

若使用 **PyQt6 6.5+** 且在 Linux 下出现 xcb 插件错误，请安装系统依赖后重试：

```bash
# Debian / Ubuntu
sudo apt install libxcb-cursor0

# Fedora
sudo dnf install libxcb-cursor

# Arch
sudo pacman -S libxcb-cursor
```

当前 `requirements.txt` 限定为 PyQt6 6.4.x，无需上述系统库即可运行。

## 项目结构

```
cleaner/
  main.py           # 程序入口（仅启动应用）
  scanner.py        # 目录扫描与大文件/汇总目录逻辑
  utils.py          # 系统工具（打开目录等）
  ui/
    __init__.py
    main_window.py  # 主窗口与扫描/筛选/删除逻辑
    widgets.py      # 自定义表格（大小列数值排序）
    workers.py      # 后台线程（ScanWorker、DeleteWorker）
  requirements.txt
```

## 使用说明

1. 点击「浏览」选择要扫描的根目录。
2. 设置「最小文件大小 (MB)」，例如 10 表示只显示 ≥10MB 的文件。
3. 点击「开始扫描」，等待或点击「停止」结束。
4. 在表格中查看结果，右键某行选择「打开所在目录」即可在文件管理器中打开该文件所在文件夹。
