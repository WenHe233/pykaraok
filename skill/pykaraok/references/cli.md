# pykaraok 命令速查

所有命令都支持 `--json`。时间参数可写成 `83.4`、`1:23.4` 或 `0:01:23.40`。

`--fonts` 可以是字体目录、字体文件或字体包 zip，可以重复给。目录只取第一层的字体文件，要用子目录里的字体，把那个字体文件或子目录另外传给 `--fonts`。默认值是 .ass 所在目录：目录里的字体文件，加上文件名含 font 或“字体”的 zip。给了 `--fonts` 就不再用默认值。zip 包会解压到缓存。

`--video` 不给时，读取 .ass 里记录的 Video File。找不到视频时会打印 warning，改用灰底和 23.976 fps。字体默认也会在视频所在目录里找。

build 和 apply 把输出写到别的目录时，会改写记录的视频、音频路径，让它们从新位置也能找到。手工把文件挪到别处后，记得给 check 和 render 加 `--video` 和 `--fonts`。

render 不给 `-o` 时，输出写到**当前目录**，文件名为 `<输入文件名>_<类型>`。不要在用户的歌词目录里运行，以免把文件写到那里。

出错时只打印一行 `error: ...`；设置 `PYKARAOK_DEBUG=1` 才显示完整 traceback。

## 环境

| 命令 | 作用 |
|---|---|
| `pykaraok doctor` | 依赖、ffmpeg、moonc、缓存、0x539、各 Lua 库的状态 |
| `pykaraok paths` | 仓库、examples、skill、fxlib、vendor、缓存的位置 |
| `pykaraok setup moonc\|0x539\|libs\|all` | 下载 moonc；下载并编译 0x539 模板器、0x.color、karaOK；安装 ILL、clipper2、requireffi。`setup libs --source DIR` 改为从本地 automation/include 目录拷贝 |
| `pykaraok skill install [--target DIR] [--copy]` | 把本 skill 链接到 ~/.claude/skills 和 ~/.agents/skills |

## 构建与套用

| 命令 | 作用 |
|---|---|
| `pykaraok build SRC.fx.lua --lyrics L.ass -o OUT.ass` | 模板源文件加歌词，得到单文件特效并套用。`--engine stock\|0x539`、`--styles A,B`（歌词样式）、`--k keep\|line\|char`、`--no-apply`、`--strip-comments` |
| `pykaraok apply IN.ass -o OUT.ass` | 对已经含模板的文件执行 “Apply karaoke template”。`--in-place` 覆盖原文件 |
| `pykaraok extract X.ass -o SRC.fx.lua` | 把文件里的模板、代码、说明行导出成源文件 |
| `pykaraok fxlib [模块]` | 列出 fxlib 模块，或打印某个模块的源码 |
| `pykaraok run-macro SCRIPT.lua\|.moon IN.ass -o OUT.ass [--macro 名称] [--list]` | 无界面运行任意 Automation 4 宏。`--selected 1,2,3`、`--dialog '{"button":"OK","values":{...}}'` |

build、apply、run-macro 共用的选项：
- `--fonts`
- `--include DIR`：额外的 Lua include 目录。
- `--metrics auto|gdi|fonttools`
- `--video V` 或 `--fps 24000/1001`：提供 `aegisub.video_size` 和 `frame_from_ms`。
- `--seed N`：固定 math.random，0x539 每次运行会重新播种，这个选项把它固定住。
- `--trace N`：日志级别。
- `--echo`：运行时打印日志。

## 检查

| 命令 | 作用 |
|---|---|
| `pykaraok check X.ass` | 静态检查。加 `--reapply` 检查重套一致性；加 `--jumps`、`--perf` 做出图检查（`--from`/`--to` 限定区间）；加 `--original O.ass --steady [--diff-dir D]` 做稳态逐像素对比 |
| `pykaraok diff A.ass B.ass [--all] [--effect fx]` | 比较两份文件的事件，差异分为 identical、time_round、extradata、numeric、structural 几类 |
| `pykaraok fonts check X.ass` | 列出用到的字体，以及每个字体缺哪些字 |
| `pykaraok fonts unpack 字体包.zip` | 解压字体包到缓存，打印目录 |

## 出图

| 命令 | 作用 |
|---|---|
| `render frame X.ass --at T [--width 960] [--crop x,y,w,h] [--label]` | 单帧 |
| `render sheet X.ass --from A --to B [--step S \| --fps F] [--cols 6] [--crop ...] [--width 480]` | 一段时间的帧拼成一张图（一次解码）。`--crop` 可以给多个框（用 `;` 分隔），上下拼接，宽度不同时右侧补齐；宽高会取偶数 |
| `render lines X.ass [--first N --count M] [--per-sheet 8] [--phases in,in+,mid,out-,out] [--crop auto\|full\|x,y,w,h;...]` | 每句一行：入场、入场后、中段、退场前、退场后。时间相同的日文和中文合成一行，`--first`、`--count` 按合并后的行计数。默认自动裁出字幕所在的几条横带（有 fx 行时按 fx 的位置，并收窄到 fx 覆盖的水平范围；没有时按各样式的对齐和边距）。`-o` 给的是前缀，实际文件为 `前缀_01.png`、`前缀_02.png`…… |
| `render zoom X.ass --at T --crop x,y,w,h --scale 2` | 局部放大看细节 |
| `render preview X.ass [--from --to] -o P.mp4 [--bitrate 4500k \| --crf 20] [--width 1280] [--no-audio]` | 压歌曲段预览，带音频，时间从 0 开始 |
| `render perf X.ass [--from --to]` | libass 每帧耗时 |
| `render vsf X.ass --at T` | 用 Aegisub 附带的 VSFilter 出一帧，只用来提示兼容问题 |

共用选项：
- `--video`、`--no-video`。
- `--bg gray|black|checker|#RRGGBB`：没有视频时的背景。
- `--fonts`、`-o`。

时间 T 取 T 或之后的第一帧，帧的时间戳先四舍五入到毫秒再比较。字幕按这一帧的时间戳渲染，`render vsf` 也一样。`render sheet` 按同样的规则给每个取样时间取帧，输出的 `times` 是这些帧的时间戳。

## 其它

| 命令 | 作用 |
|---|---|
| `pykaraok cht IN.ass -o OUT.ass --styles 中文样式 [--rule 你=妳] [--mode s2twp]` | 繁体化，只改指定样式的文字 |
| `pykaraok draw text 文字 --font 字体名或文件 --size 55` | 字形转 `\p` 绘图，原点为文字格左上角 |
| `pykaraok draw compose --font F --size 55 --part 气 --part '汽@0.4,0,1,1+-0.3,0'` | 用字形部件拼出缺字 |
| `pykaraok beats 视频 --from 19:20 --to 20:20` | 节拍网格，输出可直接贴进模板的 `BEAT = px.beat(...)` |
