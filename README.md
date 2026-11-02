# 视频码率计算器 · Windows

离线 Python/Tkinter 桌面工具。按最终成片时长、上传大小上限、目标体积、音频和封装余量计算视频平均码率，并生成 H.264 / H.265 / AV1 / VP9 设置文本。它计算码率预算，不执行视频压缩，也不是比较两个文件压缩率的工具。

## 安装与使用

在本仓库 [Releases](../../releases) 下载 Windows ZIP，完整解压后启动 `VideoBitrateCalculator.exe`；无需 Python。源码下载不含 EXE。源码版安装含 tkinter 的 Python 3.10+ 后运行：

```powershell
py -3 bitrate_gui.pyw
```

输入 `9:38`、180 MB 上限、170 MB 目标、128 Kbps 音频、1.5% 预留，示例为 2189 Kbps。选择编码格式可复制设置或导出 TXT；去实际转码软件中填写平均码率，再检查最终大小和画质。完整中文说明和计算公式见 [README_使用说明.txt](README_使用说明.txt)。默认不包含 ffprobe；选择视频时内置解析器尝试读取 MP4/MOV/MKV 等元数据，失败可手填时长。不会扫描个人视频或上传文件。

## 测试与构建

```powershell
py -3 -m unittest -v test_bitrate_core
py -3 tools/gui_smoke.py
py -3 -m venv .venv-build
.venv-build\Scripts\python -m pip install -r requirements-build.txt
.venv-build\Scripts\python tools/build.py
```

须在 Windows 构建 Windows EXE。`tools/build.py` 先运行单元测试与真实 Tk 控件自检，再生成 `dist/VideoBitrateCalculator.exe`。本次不捆绑 ffprobe。打包环境兼容脚本只初始化当前进程 Tcl，不修改系统设置。`build_windows.bat` 提供同样的隔离环境流程。

CI 在 Windows 执行测试与构建并保存 ZIP 附件；进程启动检查不等于人工完整 GUI 验收。单元测试的 MP4/MKV 为合成元数据样本，不代表全格式视频实测。最终成片体积和画质需要另行检查。见 [VALIDATION.md](VALIDATION.md)。

## 协议与文件

自有源码：[MIT](LICENSE)。Python/Tcl/Tk 和构建工具原协议：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。`bitrate_core.py` 为计算与读取核心，`bitrate_gui.pyw` 为界面，`test_bitrate_core.py` 为原单元测试；`tools/` 为归档构建及隔离检查辅助。EXE 未签名。归档边界见 [docs/ARCHIVE.md](docs/ARCHIVE.md)。
