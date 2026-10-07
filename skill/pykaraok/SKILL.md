---
name: pykaraok
description: 制作 ASS 特效字幕（卡拉OK模板、歌词特效、KFX）时使用。用 pykaraok 命令行无界面运行 Aegisub 自带 kara-templater 和 The0x539 KaraTemplater，把模板源文件和用户的歌词文件构建成可在 Aegisub 里重新套用的单文件特效 .ass，并用 libass 出图、拼图、检查。Use for karaoke / lyric effect subtitles, Aegisub karaoke templater, kara-templater, 0x.KaraTemplater, ASS \k timing effects, 特效字幕, 卡拉OK字幕, 歌词特效.
license: MIT
compatibility: 需要 Python 3.11+、带 libass 的 ffmpeg。Windows 下测字宽与 Aegisub 相同（GDI）；其它系统用 fontTools 近似。
metadata:
  repo: pykaraok
  version: "0.1"
---

# pykaraok：做 ASS 特效字幕

这个 skill 只负责“怎么用工具”。效果怎么设计由你根据歌词、画面和用户要求决定。

## 0. 环境

```bash
pykaraok doctor
```

- 找不到命令：在 pykaraok 仓库目录执行 `pip install -e .`。仓库位置用 `pykaraok paths` 查。
- 要用 0x539 模板器：`pykaraok setup 0x539`。
- 要在模板里用 ILL：`pykaraok setup libs`。Yutils 已自带。
- 所有命令都支持 `--json`，需要读结果时加上。

## 1. 先弄清输入和约束

向用户确认，或从文件里读出：

1. 歌词文件（.ass）：哪几个样式是歌词，日文行有没有逐音节 `\k`。**不要从音频推导 `\k`**，用用户给的时间。
2. 视频：.ass 的 `[Aegisub Project Garbage]` 里通常记着 Video File，工具会自动读取。
3. 字体：放在歌词文件旁边，或是一个字体包 zip，工具会自动找到。先跑 `pykaraok fonts check 歌词.ass`，缺字要先解决（见 references/fonts.md）。
4. 用户的硬性要求。以往用户的习惯如下，新项目开始时逐条确认：
   - 只保证 libass 下的效果。
   - 不改动原歌词行的位置、字体、样式。
   - 好看优先。
   - 新版本另存，不覆盖旧文件。
   - 画面里原有的文字要汉化时，只叠加在旁边，不遮盖原文。

## 2. 看画面和歌词

```bash
pykaraok render sheet 歌词.ass --from 19:20 --to 19:40 --step 1 --cols 5
pykaraok render lines 歌词.ass --count 8
```

先看清歌曲区间、画面色调和镜头切换，再定风格。看图要省：用拼图一次看多个时刻，不要逐帧出图。

## 3. 写模板源文件

从最接近的示例复制一份（`pykaraok paths` 给出 examples 目录，示例说明见 examples/README.md）：

- `starter`：入门。日文逐音节，中文整句，使用 fxlib。
- `ice_melt`、`watercolor`、`strawberry_jam`、`live_chorus`：以前交付过的完整效果。

源文件格式见 references/source-format.md。要点：

- **含反斜杠的内容一律用写文件工具写进 .lua 源文件**，不要放进 shell 命令或 heredoc，Bash 会吞掉反斜杠。
- 随机数用 `px.rand(a, b, salt)`（由行和音节决定，重新套用结果不变），不用 `math.random`。
- `!表达式!` 里算出的小数用 `px.num(x)` 截短；在 stock 模板器里，`!...!` 里的函数要返回 `""`，返回 nil 会把原文 `!...!` 留在输出里。
- 模板器语法：references/stock-templater.md（默认），references/0x539-templater.md（需要 mixin、具名循环、`if` 条件时用）。
- 函数库：`--@use core color shapes emit ...`，接口见 references/fxlib.md。
- 文字转图形、图形布尔运算可以在模板里用 Yutils、ILL，也可以在 Python 里预先算好嵌进模板，见 references/libraries.md。

## 4. 构建

```bash
pykaraok build 效果.fx.lua --lyrics 歌词.ass -o 歌词_特效.ass
```

- 歌词文件不会被修改。输出是单文件，包含三部分：说明行和模板行在最前（Aegisub 只在前 50 行找模板），歌词行转为 karaoke 注释行，后面是生成的 fx 行。
- 输出可以放在别的目录：build 会改写文件里记录的视频路径，之后 check 和 render 仍能找到视频，以及视频旁边的字体。看到 `warning: no video` 或 `no fonts` 时，加 `--video` 和 `--fonts`。
- 歌词行没有 `\k` 时：用 `--k line`（整句一个音节）或 `--k char`（按字平均分配）。
- 报错时看输出里的 Lua 错误和行号。`[log N]` 是模板里 `aegisub.log` 的输出。

## 5. 检查

```bash
pykaraok check 歌词_特效.ass --reapply
pykaraok check 歌词_特效.ass --jumps --perf --from 19:20 --to 22:20
pykaraok check 歌词_特效.ass --original 歌词.ass --steady
```

逐项含义见 references/qa.md。必须为零的项目：
- error 级别的问题。
- `collisions` 里的 fx 行。
- `jumps`。

`--reapply` 必须报告“结果完全一致”，这表示用户在 Aegisub 里点 Apply 会得到同样的结果。

## 6. 自己看效果

```bash
pykaraok render lines 歌词_特效.ass --per-sheet 8          # 每句的入场、中段、退场
pykaraok render sheet 歌词_特效.ass --from 1:31 --to 1:34 --fps 8
pykaraok render zoom 歌词_特效.ass --at 1:32.5 --crop 600,900,700,180 --scale 2
```

对照用户的要求逐条检查：位置、遮挡、可读性、和画面节奏是否同步、各句是否一致。发现问题后回到第 3 步修改。常见问题和解决办法见 references/libass-pitfalls.md 和 references/recipes.md。

## 7. 交付

按 references/delivery.md 执行：
- 文件命名，不覆盖旧文件。
- 预览视频：`pykaraok render preview`。
- 给用户的说明：先装字体；Aegisub 里要切到 libass 预览；如何修改参数。

## 参考文件

| 文件 | 内容 |
|---|---|
| references/cli.md | 全部命令和参数 |
| references/source-format.md | 模板源文件格式 |
| references/stock-templater.md | Aegisub 自带模板器速查与陷阱 |
| references/0x539-templater.md | 0x539 模板器速查 |
| references/fxlib.md | px.* 函数库 |
| references/libraries.md | Yutils、ILL、karaOK，以及 Python 端的 draw 命令 |
| references/fonts.md | 字体、缺字、繁体 |
| references/qa.md | check 各项的含义和处理 |
| references/libass-pitfalls.md | libass 渲染上的坑 |
| references/recipes.md | 以往项目的效果做法和用户反馈 |
| references/delivery.md | 交付规范 |
| references/harness-pitfalls.md | 运行环境的坑（反斜杠、编码） |
