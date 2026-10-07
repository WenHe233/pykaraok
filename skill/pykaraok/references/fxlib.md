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
| `star(n, R, r, rot)` | n 角星，外半径 R、内半径 r，rot 为起始角（度，默认 -90 即尖朝上） |
| `sparkle(R, a)` | 四角闪光，半径 R；a 是四条曲线在中心收腰处离中心的距离，越小越细（默认 0.11 R） |
| `heart(r)`、`rrect(w, h, r)`、`drop(w, h)`、`polygon(pts)` | 心形、圆角矩形、水滴（尖头朝上）、多边形 |
| `boxed(shape, W, H)` | 前面加 `m 0 0 m W H`，固定包围盒，让几块图形用同一个原点对齐 |
| `xform(shape, sx, sy, dx, dy, deg)` | 缩放、旋转、平移 |
| `bounds(shape)`、`normalize(shape)` | 包围盒；平移到左上角为 0, 0 |

## layout（px.layout.*）

按 libass 规则算原行每个字的位置，精确到 1/64 px，处理 `\an`、`\pos`、边距、行内 `\alpha`。用于静止时要与原行重合的效果（watercolor 示例）。

| 函数 | 返回 |
|---|---|
| `geom(line)` | 表 g：`g.chars[i] = {c, x, w, cx, a1, a3, hide, sp}`（x 为字左边，px；a1/a3 为该字的填充、描边透明度；hide 为不可见；sp 为空格）；`g.an` 原行对齐；`g.lan` 同样垂直对齐的靠左 `\an`（1/4/7）；`g.py` 锚点 y；`g.cyc` 字的垂直中心；`g.fs` 字号乘纵向缩放；`g.base` 行首标签块去掉 `\fad` 后的内容；`g.rest` 去掉行首标签块后的正文；`g.fin`/`g.fout` 行内 `\fad` 的淡入淡出（没有为 0） |
| `cached(orgline)` | 同一行只算一次的 geom |
| `syl_range(orgline, si)` | 第 si 个音节对应 g.chars 的第 first..last 个字 |
| `syl_box(g, orgline, si)` | `{x, w, cx, an, y, first, last}`：音节左边、宽、中心，以及要用的 `\an` 和 y |
| `p(x)` | 坐标写成 7 位小数（libass 1/64 px 取整需要） |

逐音节、静止时与原行重合的最小写法（tests/data/layout.fx.lua）：

```lua
--@use core layout
--@code once | 逐音节定位
function at_syl()
  local g = px.layout.cached(orgline)
  local b = px.layout.syl_box(g, orgline, syl.i)
  return string.format("\\an%d\\pos(%s,%s)", b.an, px.layout.p(b.x), px.num(b.y, 3))
end
--@template syl noblank
{!at_syl()!}
```

libass 排整行时带字距调整，逐音节摆放没有字距调整，所以拉丁字母可能有亚像素级的边缘差异。

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
