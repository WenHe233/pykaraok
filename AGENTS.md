# AGENTS.md

给修改 pykaraok 本身的 AI 看。如果只是用它做特效字幕，读 `skill/pykaraok/SKILL.md`。

## 开发

```bash
pip install -e ".[dev,draw,cht]"
python -m pytest -q
```

- `tests/test_regression.py` 需要以往项目的文件夹（`PYKARAOK_PROJECTS`，默认 `C:\Users\Administrator\Desktop\github`），找不到就跳过。
- `tests/test_x0539.py` 需要先执行 `pykaraok setup 0x539`。`tests/test_libs.py` 的 ILL 部分需要先执行 `pykaraok setup libs`。

## 原则

- **与 Aegisub 行为一致优先。** 模拟层的每个细节都以 Aegisub 源码为准，注释里写明出处文件：
  - `src/auto4_lua*.cpp`
  - `src/ass_karaoke.cpp`
  - `libaegisub/ass/time.cpp`
  - `libaegisub/common/vfr.cpp`
  - 其它

  改动行为前先读对应源码（GitHub TypesettingTools/Aegisub），不要凭记忆。
- **未改动的内容按字节原样写回**（BOM、换行、注释、未知段、Extradata）。
- **命令行是唯一接口。** 新功能都要有对应命令，并支持 `--json`。
- **第三方代码的许可证**：
  - BSD、ISC、MIT 的可以放进 `vendor/`，附原许可证；
  - 没有许可证的（0x539、karaOK）只在 `setup` 时下载到缓存。

## 结构

| 模块 | 内容 |
|---|---|
| `aegi/lua/prelude.lua` | aegisub.* 接口、subs 对象、模块加载、include。Python 服务通过 PY 表传入 |
| `aegi/runtime.py` | 一个 Lua 状态。对应 Aegisub 里加载一个脚本 |
| `aegi/templater.py` | 套用入口：stock 和 0x539 两个引擎 |
| `aegi/karaoke.py` | parse_karaoke_data，Python 实现 |
| `aegi/re_impl.py` 加 `aegi/lua/re_impl.lua` | `aegisub.__re_impl`；上层用 Aegisub 原版 re.moon |
| `aegi/moon.py` | moonc 编译和缓存 |
| `ass/document.py`、`ass/codec.py` | 文件模型、时间、颜色、Extradata 编码 |
| `metrics/` | GDI、fontTools 字宽 |
| `build/` | 模板源文件格式、Lua 压行、build |
| `render/`、`qa/` | ffmpeg 出图、检查 |
| `fxlib/*.lua` | 嵌进交付文件的 Lua 函数库；每个块都是 `--@code once` |
| `vendor/aegisub/moon-src` | 改动后运行 `python tools/build_vendor.py` 重新编译，编译结果一并提交 |

## 写代码时注意

- **含反斜杠的文件用写文件工具写**，不要用 Bash heredoc 或 `sed`：Bash 工具会把 `\\` 吞成 `\`。
- 在 Windows 上用 Python 写文本时指定 `newline="\n"`，或者用 `write_bytes`。
- LuaJIT 在 Windows 上用 SEH 异常实现 Lua 错误。pytest 里已关闭 faulthandler，否则每次 pcall 都会打印一条 “fatal exception”。
