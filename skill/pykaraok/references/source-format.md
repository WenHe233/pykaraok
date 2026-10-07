# 模板源文件格式（*.fx.lua）

一个文本文件，按 `--@指令` 分块，块的内容一直到下一条指令为止。第一条指令之前的内容是文件说明，构建时忽略。

```lua
-- 文件说明（忽略）

--@meta engine=stock style=JP          -- 全文件默认：引擎、默认样式
--@use core color shapes emit          -- 嵌入 fxlib 模块（作为 code once 行，放在本文件代码之前）

--@note 给 Aegisub 用户看的说明，生成 Effect 为 note 的注释行

--@style Style: Spark,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
--@style replace Style: JP,...        -- 加 replace 时覆盖歌词文件里的同名样式（默认只在缺少时补上）

--@code once | 配置                     -- “|” 后面的文字写进 Actor 栏，作为这一行的标题
COL = {ice = '&HFFDCC9&'}              -- 注释会保留成 --[[ ]]

--@template syl noblank style=JP layer=2 | 本体
!retime("line", -300, 200)!
{\an5\move($scenter,!$smiddle + 20!,$scenter,$smiddle,0,300)
\fad(300,200)}
-- 模板块里以 -- 开头的行是注释

--@mixin char style=JP                 -- 0x539 引擎
{\3c!util.gbc(C1, C2)!}
```

## 块类型

| 指令 | 生成的行 | 说明 |
|---|---|---|
| `--@code 类别 [修饰词] [style= layer=] [\| 标题]` | Comment，Effect = `code 类别 修饰词` | 代码压成一行。`--[[长字符串]]` 不能跨行。构建前用 LuaJIT 检查语法 |
| `--@template 类别 [修饰词] [style= layer=] [\| 标题]` | Comment，Effect = `template ...` | 每行去掉开头缩进后直接拼接，所以标签可以分行写 |
| `--@mixin ...` | Comment，Effect = `mixin ...` | 只用于 0x539 |
| `--@note 文字` | Comment，Effect = `note` | 两种模板器都忽略 |
| `--@style Style: ...` | 样式行 | 默认在歌词文件缺少该样式时补上 |
| `--@meta k=v ...` | 无 | `engine`、`style` |
| `--@use 模块...` | code once 行 | fxlib 模块，见 fxlib.md |

`style=` 有三个用途：
- 决定这行模板作用于哪个样式的歌词。stock 模板器按样式名匹配，带 `all` 修饰词时匹配所有样式。
- 决定哪些样式的行被当作歌词（会转成 karaoke/kara 注释行）。`--styles` 可以覆盖。
- 样式名有空格时写成 `style='E10插入曲 - JP'`。

## 构建做了什么

1. 读歌词文件，去掉旧的 fx 行和旧的模板、代码、说明行，所以已构建的文件也可以再当输入。
2. 歌词样式里 Effect 为空的可见行改成 Comment，Effect 改为 karaoke（stock）或 kara（0x539）。没有 `\k` 时按 `--k` 处理。
3. 生成行放在 [Events] 最前面。第一行模板超过第 50 行时，把 code once 行挪到模板后面（code once 总是先于一切执行，位置不影响结果）。
4. 套用模板，写出单文件。

## 从已有文件开始

```bash
pykaraok extract 旧特效.ass -o 旧特效.fx.lua
```

导出的代码块是一行（原文件就是一行），可以直接改，也可以手工重新分行。
