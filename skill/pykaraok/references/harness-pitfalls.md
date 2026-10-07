# 运行环境的坑

## 反斜杠

Claude Code 等环境的 Bash 工具会把命令里连续的两个反斜杠合成一个，而且不报错。下面几种写法都会出错：
- heredoc、`python -c`、`sed` 里写 ASS 标签，例如 `\\an5`；
- 用正则匹配 `\-fx` 这类内联标签。

**做法**：
- 模板、Lua、含 ASS 标签的 Python 一律用写文件工具（Write/Edit）写成文件，再用命令处理文件。
- 必须在命令行里拼反斜杠时，用 `chr(92)`。

## 编码

- Windows 控制台默认是 GBK，打印中文会报错或乱码。运行 pykaraok 之外的 Python 脚本时，先设 `PYTHONIOENCODING=utf-8`。pykaraok 自己的输出已强制使用 UTF-8。
- 读 .ass 用 `utf-8-sig`。pykaraok 写回时保留原文件的 BOM 和换行。
- 在 Windows 上用 Python 的 `write_text` 写文件时，`\n` 会被转成 `\r\n`。需要 LF 时用 `newline="\n"` 或 `write_bytes`。

## 路径

- ffmpeg 的滤镜参数里，Windows 盘符的冒号必须转义。pykaraok 的 render 命令已处理；自己写 ffmpeg 命令时，用相对路径或转义 `:`。
- 新版 ffmpeg 已删除 `-vsync`，改用 `-fps_mode`。

## 看图要省

- 用 `render sheet` 或 `render lines` 一次看多个时刻，不要逐帧出图再逐张读取。以前有会话因为读图太多用完了额度。
- 拼图默认每格 480 px 宽，看细节时用 `render zoom` 局部放大，不要输出整张 1080p。
