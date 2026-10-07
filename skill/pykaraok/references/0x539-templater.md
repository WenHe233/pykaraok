# The0x539 KaraTemplater 速查（engine=0x539）

先执行 `pykaraok setup 0x539`。完整文档在作者仓库的 doc/0x.KaraTemplater.md。下面只列与 stock 模板器不同的地方。

## 输入

- 只处理 Effect 为 `kara`（或 `karaoke`）的行，不会自动接管 Effect 为空的行。build 会把歌词样式的行标成 `kara`。
- 用 `anystyle` 的模板会作用于所有样式的 kara 行。要处理多个样式时，用 `--styles JP,CN` 告诉 build 哪些是歌词。
- 输入行的 Actor 栏按空格分成多个值，可用于条件判断，例如一行同时写 `chorus sun`。

## 组件

Effect 第一个词是 `code`、`template` 或 `mixin`，第二个词是类别：`once`（仅 code）、`line`、`syl`、`word`、`char`。

`mixin` 修改模板的输出：
- 默认放在对应文字前面；
- 加 `prefix` 修饰词时放在行首。

可以用一条 template 加多条 mixin 组合出效果。例如 `mixin char` 配合 `util.gbc` 做逐字渐变。

## 修饰词

| 修饰词 | 作用 |
|---|---|
| `style 名` / `anystyle` | 增加感兴趣的样式 / 任何样式（相当于 stock 的 all） |
| `actor 名` / `noactor 名` | 按输入行 Actor 值筛选 |
| `t_actor 名` / `no_t_actor 名` | mixin 按模板行的 Actor 筛选 |
| `layer N` | mixin 只作用于该图层的输出 |
| `if 名` / `unless 名`（`cond`） | 环境里同名布尔值或无参函数决定是否执行，每个组件只能写一个 |
| `sylfx 名` / `inlinefx 名` | 按音节的内联特效筛选 |
| `noblank` / `nok0` | 跳过空白 / 跳过零时长音节 |
| `loop 名 N`（`repeat`） | 具名循环，多个循环可嵌套。变量 `$loop_名`、`$maxloop_名`；mixin 用 `$mloop_名` |
| `notext`、`keeptags`、`keepspace`、`nomerge`、`multi` | 与 stock 类似；`nomerge` 不合并相邻标签块 |

## 变量与函数

- 内联变量：`$sylstart $sylend $syldur $kdur $ldur $li $si $wi $ci $cxf $sxf $wxf`，以及 `$loop_名` 等。
  - **没有 stock 的 `$scenter`、`$smiddle`**，改用 `!orgline.left + syl.center!`、`!orgline.middle!`。
- `!表达式!` 结果为 nil 时输出空字符串。
- `retime` 的模式比 stock 多：
  - `presyl2postline`、`preline2postsyl`、`delta`
  - `clamp`、`clampsyl`：把时间限制在行或音节范围内。
- `relayer`、`maxloop(名, 次数)`、`set(键, 值)`、`skip()`、`unskip()`、`mskip()`。
- `util` 下的函数：

| 函数 | 作用 |
|---|---|
| `util.xf()` | 当前字在行内的相对位置 0..1 |
| `util.gbc(c1, c2)` / `util.multi_gbc({...})` | 逐字渐变，颜色在 LCH 空间插值（0x.color） |
| `util.make_grad` / `util.get_grad` | 用 clip 做的渐变 |
| `util.fbf(...)` | 逐帧拆分，需要 `--video` 或 `--fps` |
| `util.ftoa(n, 2)` | 数字转短字符串 |
| `util.fad`、`util.tag_or_default` | 标签辅助 |
| `util.rand.sign/item/bool/choice` | 随机辅助 |
| `util.math.round` | 取整 |

- 已加载的库：`ln`（karaOK）、`colorlib`（0x.color）。

## 注意

- 每次运行时，`main` 都会执行 `math.randomseed(os.time())`，所以用 `math.random` 的模板在 Aegisub 里每次结果都不同。pykaraok 加 `--seed N` 可以固定，但用户在 Aegisub 里重套仍会变化。需要可重现时，自己用 hash 做随机数。
- 作者的仓库没有许可证，pykaraok 不收录它的源码，只在安装时下载。交付文件里只包含模板，不包含模板器本身。用户要在 Aegisub 里重新套用，需要自己装 0x.KaraTemplater（DependencyControl 里搜 0x539）。
