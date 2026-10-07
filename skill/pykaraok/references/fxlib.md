# fxlib：模板里用的 Lua 函数（px.*）

用法：在源文件写 `--@use core color shapes ...`。build 会把这些模块作为 code once 行嵌进输出文件，所以交付文件在 Aegisub 里重新套用时不依赖 pykaraok。源码在 `pykaraok fxlib 模块名`。

## core（其它模块都依赖它，放第一个）

| 函数 | 说明 |
|---|---|
| （环境） | `_G.setmetatable(tenv, {__index = _G})`：模板里可以直接用 pairs、ipairs、tonumber、table、unicode、aegisub |
| `px.num(x, d=2)` | 保留 d 位小数并去掉末尾的 0，写标签时用 |
| `px.clamp(x, a, b)`、`px.lerp(a, b, t)`、`px.norm(x, a, b)`、`px.smooth(t)` | 数值 |
| `px.ease.in_quad / out_quad / in_out_sine / out_back` | 缓动 |
| `px.hash(a, b, c)` | 三个数映射到 [0, 1) |
| `px.rand(a, b, salt)` | 由 orgline 开始时间、音节序号、j 和 salt 决定的随机数，重新套用时不变 |
| `px.seed(n)` + `px.rnd()`、`px.pick(list)` | 一串确定的随机数 |
| `px.ms(t)` | 取整到 10 ms |
| `px.rel(t_abs)` | 绝对时间转当前输出行内的相对时间（retime 之后用） |
| `px.at_syl(off)`、`px.at_syl_end(off)` | 音节开始、结束时间加 off，转成输出行内的相对时间 |
| `px.first()` | template line 里判断是否第一个音节 |
| `px.t(t1, t2, tags, accel)`、`px.pos(x, y)`、`px.move(...)`、`px.fad(a, b)`、`px.clip(...)`、`px.alpha(v)` | 拼标签 |
| `px.still` | 永不开始的 `\t`，让没有 `\pos` 的行不参与 libass 的防重叠挪动 |

## color

| 函数 | 说明 |
|---|---|
| `px.c(r, g, b)` | RGB 转 `&HBBGGRR&` |
| `px.hex("RRGGBB")` | 网页色转 ASS |
| `px.rgb(ass)` | ASS 颜色转 r, g, b |
| `px.mix(c1, c2, t)` | 混色 |
| `px.grad({{0, c1}, {0.5, c2}, {1, c3}}, u)` | 多段渐变 |
| `px.hsl(h, s, l)` | HSL 转 ASS |
| `px.style_color(styleref.color3)` | 样式颜色去掉透明度 |
| `px.tag_color(text, "3")` | 行内第一个 `\3c` 的颜色（用来按演唱者标色） |

## shapes（px.shape.*）

所有图形都画在正坐标里。libass 按包围盒对齐图形，出现负坐标会让整体偏移。

| 函数 | 说明 |
|---|---|
| `circle(r)`、`circle_at(cx, cy, r, ccw)`、`ellipse(rx, ry)` | 圆、椭圆；ccw 反向，可在别的图形里挖洞 |
| `star(n, R, r, rot)`、`sparkle(R, a)`、`heart(r)`、`rrect(w, h, r)`、`drop(w, h)`、`polygon(pts)` | 常用图形 |
| `boxed(shape, W, H)` | 前面加 `m 0 0 m W H`，固定包围盒，让几块图形用同一个原点对齐 |
| `xform(shape, sx, sy, dx, dy, deg)` | 缩放、旋转、平移 |
| `bounds(shape)`、`normalize(shape)` | 包围盒；平移到左上角为 0, 0 |

## layout（px.layout.*）

`px.layout.geom(line)` 按 libass 规则算原行每个字的位置，精确到 1/64 px，处理 `\an`、`\pos`、边距、行内 `\alpha`。用于静止时要与原行逐像素重合的效果（watercolor 示例）。写坐标用 `px.layout.p(x)`，保留 7 位小数。

## emit

`px.emit(build)` 配合 `--@template line notext`：一句歌词生成任意多行。`build(orgline)` 返回列表，每项用 `px.add(items, 图层, 相对开始, 相对结束, 文字)` 加入。适合整句级设计：先把一句里所有元素算好，再逐个输出。

## noise（px.noise.*）

| 函数 | 说明 |
|---|---|
| `value(x, y, seed)`、`fbm(x, y, seed, octaves)` | 值噪声、分形噪声，取值 0..1 |
| `contour(f, nx, ny, cs, t)` | 网格等值线，输出 `\p3` 绘图（坐标单位 1/4 px），带洞 |
| `blob(w, h, cs, t, fn)` | 在 w x h 区域对 fn(x, y) 取等值线 |
| `simplify(points, tol)` | 折线精简 |

用来画不规则的有机形状：水彩、墨迹、云。不会像叠椭圆那样看出一个个圈。

## beat

`BEAT = px.beat(bpm, 首拍毫秒)`，参数用 `pykaraok beats` 算。

| 方法 | 说明 |
|---|---|
| `BEAT.at(k)` | 第 k 拍的时间 |
| `BEAT.index(t)` | t 所在的拍序号 |
| `BEAT.snap(t, sub)` | 最近的拍点；sub 为细分 |
| `BEAT.next(t)` | t 之后的第一个拍点 |
| `BEAT.between(a, b)` | 区间内的所有拍点 |
