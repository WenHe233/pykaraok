# Aegisub 自带 Karaoke Templater 2.1.7 速查

内容来自 `vendor/aegisub/autoload/kara-templater.lua` 源码。

## 输入和输出

- 输入行有两种：Effect 为空的可见 Dialogue 行，以及 Effect 为 `karaoke` 的行。只有当某条模板作用到这一行时，才会把它改成 Comment 加 karaoke。
- 生成的行 Effect 为 `fx`。每次套用前，先删掉所有 Effect 为 `fx` 的行。手工加的、不想被删的行，Effect 写别的值（如 `logo`）。
- 菜单项 “Apply karaoke template” 只在前 50 个对话行里出现 Effect 以 `template` 开头的行时才可用。pykaraok build 会自动保证这一点。

## code 行（Effect = `code 类别 修饰词`）

| 类别 | 何时执行 |
|---|---|
| `once`（默认） | 套用开始时执行一次，先于所有行。和它在文件里的位置无关 |
| `line` | 每个输入行开始时执行一次 |
| `syl` | 每个音节执行一次 |
| `furi` | 每个注音音节执行一次 |

修饰词：
- `all`：不限样式。
- `noblank`：跳过空白音节。
- `loop N`：执行 N 次。

## template 行（Effect = `template 类别 修饰词`）

| 类别 | 结果 |
|---|---|
| `syl`（默认） | 每个音节生成一行，文字为模板结果加音节文字 |
| `line` | 每个输入行生成一行。模板依次套用到每个音节，结果拼接起来。**所以 `!...!` 会对每个音节各求值一次**，只想执行一次的函数要判断 `syl.i == 1`（`px.first()`） |
| `pre-line` | 每个输入行生成一行，模板结果放在整行文字前面 |
| `furi` | 每个注音音节生成一行 |

修饰词：

| 修饰词 | 作用 |
|---|---|
| `char` | 配合 syl：按字而不是按音节生成 |
| `all` | 不限样式。注意：会让文件里所有 Effect 为空的可见对白也被套用 |
| `noblank` | 跳过空白和零长度音节。不加时，第 0 个占位音节也会生成一行空文字 |
| `notext` | 不附加原文字（画粒子、图形时用） |
| `keeptags` | 保留原行里除 `\k` 外的标签 |
| `loop N` / `repeat N` | 生成 N 份，序号在 `j`，总数在 `maxj` |
| `multi` | 多段高亮的音节逐段生成 |
| `fx 名称` | 只作用于带内联特效 `\-名称` 的音节 |
| `fxgroup 名称` | 代码里令 `fxgroup.名称 = false` 可以跳过这一组模板 |

## 内联变量（`$名称`，只能是小写字母和下划线）

| 层级 | 变量 |
|---|---|
| 行 | `$lstart $lend $ldur $lmid $li $layer $style $actor $syln` `$lleft $lcenter $lright $lwidth $ltop $lmiddle $lbottom $lheight $lx $ly` `$margin_l $margin_r $margin_t $margin_b $margin_v` |
| 音节 | `$sstart $send $sdur $skdur $smid $si` `$sleft $scenter $sright $swidth $stop $smiddle $sbottom $sheight $sx $sy` |
| 通用 | `$start $end $dur $kdur $mid $i $left $center $right $width $top $middle $bottom $height $x $y`：syl 模板里取音节的值，line 模板里取行的值 |

说明：
- 音节时间是相对行开始的毫秒数。
- 坐标是取整后的绝对像素。
- 竖排行另有规则。

## 内联表达式 `!Lua 表达式!`

在模板环境 tenv 里求值。tenv 默认只有这些名字：
- `string`、`math`、`_G`、`meta`
- `line`：正在生成的输出行，可以改它的时间、图层、样式。
- `orgline`：原始输入行，带 karaskel 算好的 `left`、`center`、`width`、`kara` 等字段。
- `syl`、`basesyl`、`j`、`maxj`

要用 `pairs`、`tonumber`、`table`、`unicode`、`aegisub`：
- 用 `--@use core`（它执行 `_G.setmetatable(tenv, {__index = _G})`）；
- 或者写 `_G.pairs`。

**表达式结果为 nil 时，原文 `!...!` 会原样留在输出里。** 只为副作用调用的函数要返回 `""`。

内置函数：

| 函数 | 作用 |
|---|---|
| `retime(mode, add_start, add_end)` | 改输出行时间。基准是**当前输出行**的 `line.start_time`，调用两次会叠加 |
| `relayer(n)` | 改图层 |
| `restyle(name)` | 改样式 |
| `maxloop(n)` / `loopctl(j, maxj)` | 运行时改循环次数 |
| `remember(name, value)` / `recall.name` | 在行之间传值 |
| `remember_line`、`remember_syl`、`remember_if` | 同上，按行或音节区分 |

retime 的模式，以下 S 为输出行原开始时间：

| mode | 新开始 | 新结束 |
|---|---|---|
| `syl` | S + 音节开始 | S + 音节结束 |
| `presyl` | S + 音节开始 | S + 音节开始 |
| `postsyl` | S + 音节结束 | S + 音节结束 |
| `line` | S | 行结束 |
| `preline` / `postline` | S / 行结束 | S / 行结束 |
| `start2syl` | S | S + 音节开始 |
| `syl2end` | S + 音节结束 | 行结束 |
| `sylpct` | 按音节时长的百分比 | 同左 |
| `set` / `abs` | add_start | add_end（绝对时间） |

## 常见坑

- `code line` 只能读到当前行和之前的行，读不到下一句的时间。退场只能放在本句时间之内；需要整首信息时，把汇总逻辑放在最后一行（12_IN 的“罐子行”做法）。
- 在 Aegisub 里，`math.random` 每次套用得到的序列相同，但取决于调用顺序：加一条模板就会让其它模板的随机值全部变化。用 `px.rand`。
- 测字宽依赖字体：在 Aegisub 里重新套用的机器上必须装好同样的字体，否则位置会变。
- 歌词行里的标签（例如第一个音节里的 `{\fad(300,300)}`）不在 `syl.text_stripped` 里，生成的行默认也不带（`keeptags` 才保留）。要沿用原行的淡入淡出，读 `px.layout.geom(orgline)` 的 `fin`/`fout`，或自己从 `orgline.text` 里解析。
- 套用时 karaskel 会给**每个**样式生成一个 `样式-furigana` 样式（不管有没有注音），Aegisub 会把它们写进文件。pykaraok 默认删掉其中没有被任何行使用的，`--keep-furigana-styles` 保留。

## 各处能用哪些变量

| 位置 | 可用 |
|---|---|
| `code once` 里定义的函数 | 调用时的 tenv 全部可用：`orgline`、`line`、`syl`、`j` 等，取调用那一刻的值 |
| `code line` | `orgline` 和 `line` 是**同一张**输入行表（改它会改输入行）；`syl` 为 nil |
| `code syl` | `orgline`、`line`（输入行）、`syl` |
| `template line` / `syl` 的 `!...!` | `line` 是正在生成的输出行（输入行的复制）；`orgline` 是输入行 |
