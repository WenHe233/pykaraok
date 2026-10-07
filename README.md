# pykaraok

在命令行里制作 ASS 特效字幕（卡拉 OK 模板、歌词特效）。主要使用者是 AI 编程助手，也可以手动使用。

- **无界面运行 Aegisub 的模板器**。在 LuaJIT 里按 Aegisub 源码重建 Automation 4 环境：
  - 直接运行 Aegisub 自带的 `kara-templater.lua`，以及 The0x539 的 KaraTemplater；
  - Windows 下字宽测量和 Aegisub 一样调用 GDI；
  - 时间取整、karaoke 解析、Extradata 都按 Aegisub 源码实现。
- **模板源文件**：模板、Lua 代码、说明写在一个 `.lua` 文本文件里。`build` 把它和用户的歌词文件合成一个单文件特效 `.ass`，用户可以直接在 Aegisub 里修改参数、重新套用。
- **出图与检查**：用 ffmpeg 加 libass 出单帧、时间段拼图、逐句拼图、局部放大和预览视频。`check` 检查以下项目：
  - Aegisub 的 50 行规则；
  - libass 碰撞挪动；
  - 单帧跳动；
  - 与原文件的稳态逐像素对比；
  - 字形覆盖；
  - 重新套用后结果是否一致；
  - 每帧渲染耗时。
- **素材工具**：繁体转换（OpenCC）、字形转 `\p` 绘图、用部件拼出缺字、节拍网格。
- **Lua 函数库 fxlib** 和 5 个示例模板（其中 4 个来自以往交付的项目）。
- **Aegisub 生态库**：Yutils 已自带；ILL、karaOK、0x.color 用 `setup` 安装后，可在模板里直接 require。

## 安装

```bash
pip install -e .
pykaraok doctor
```

需要 Python 3.11 以上，以及带 libass 的 ffmpeg。可选组件：

```bash
pip install opencc                  # 繁体转换（词组级）
pykaraok setup 0x539                # 下载并编译 The0x539 KaraTemplater、0x.color、karaOK
pykaraok setup libs                 # 安装 ILL、clipper2、requireffi（按 DependencyControl feed，校验 SHA-1）
pykaraok skill install              # 把 skill 链接到 ~/.claude/skills 和 ~/.agents/skills
```

0x539 模板器和 karaOK 的仓库没有许可证，本仓库不收录它们的源码，只在 `setup` 时下载到缓存（Windows 上是 `%LOCALAPPDATA%\pykaraok`）。

## 快速开始

```bash
# 从示例开始：复制 examples/starter/starter.fx.lua 改成自己的效果
pykaraok build examples/starter/starter.fx.lua --lyrics 歌词.ass -o 歌词_特效.ass
pykaraok check 歌词_特效.ass --reapply
pykaraok render lines 歌词_特效.ass
pykaraok render preview 歌词_特效.ass -o 预览.mp4
```

已经有模板的 .ass 文件，可以直接套用：

```bash
pykaraok apply 模板.ass -o 结果.ass
```

完整的工作流程和命令说明见 [skill/pykaraok/SKILL.md](skill/pykaraok/SKILL.md) 和它的 references 目录。

## 与 Aegisub 的一致性

`tests/test_regression.py` 用以往 4 个项目的交付文件做回归测试：重新套用模板后，fx 行与交付文件逐行比较。允许的差异只有三类：
- 以前的脚本对时间做截断，Aegisub 是逢 5 毫秒进位，所以有 10 ms 的取整差；
- kara-templater 会把折叠标记 Extradata 复制到 fx 行，以前的脚本丢掉了；
- alma 项目当时用 fontTools 估算字宽，与现在的结果最多差 0.1 px。

## 目录

| 路径 | 内容 |
|---|---|
| `src/pykaraok/aegi/` | Automation 4 环境（prelude.lua）、karaoke 解析、模板器入口、moonc 编译、aegisub.re |
| `src/pykaraok/ass/` | ASS 读写，保留未改动的行 |
| `src/pykaraok/metrics/` | 字宽测量（GDI、fontTools） |
| `src/pykaraok/build/` | 模板源文件解析、Lua 压行、构建 |
| `src/pykaraok/render/`、`qa/` | 出图、检查 |
| `src/pykaraok/draw/`、`text/`、`audio/` | 绘图、繁体、节拍 |
| `src/pykaraok/fxlib/` | 模板用的 Lua 函数库 |
| `src/pykaraok/vendor/` | Aegisub 自带脚本（BSD/ISC）、Yutils（MIT） |
| `examples/` | 示例模板 |
| `skill/pykaraok/` | 通用 Agent Skill |
| `tests/` | 测试 |

## 许可证

本仓库代码为 MIT。`src/pykaraok/vendor/` 下各目录保留原许可证。
