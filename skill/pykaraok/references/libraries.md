# 图形和文字库：模板里用 Lua 库，还是在 Python 里预先算

## 在模板里用（用户在 Aegisub 里重新套用时也会执行）

| 库 | 加载 | 常用功能 | 用户机器上的要求 |
|---|---|---|---|
| Yutils（已自带） | `Y = _G.require('Yutils')`（只加载一次；用 include 重复加载会因 ffi.cdef 重定义而报错） | `Y.decode.create_font(名, 粗, 斜, 下划线, 删除线, 字号).text_to_shape(文字)`；`Y.shape.to_pixels`（粒子消散）、`flatten`、`filter`、`split` | Aegisub 3.5 起不再自带，用户要自己装 |
| ILL（`pykaraok setup libs`） | `ILL = _G.require('ILL.ILL')` | `ILL.Path(s):unite/difference/intersect/exclude/offset/simplify/move/scale/rotate/export`；`ILL.Font({fontname=..., fontsize=..., bold=..., italic=..., underline=..., strikeout=..., scale_x=100, scale_y=100, spacing=0}):getTextToShape(文字)` | 需要 ILL 和 clipper2.dll，可用 DependencyControl 安装 |
| karaOK（`setup 0x539`） | 0x539 模板器自动加载为 `ln` | 形状、颜色、波动、移动标签 | 需要 ln.kara |
| 0x.color | 0x539 模板器自动加载为 `colorlib` | LCH 插值等 | 需要 0x.color |

`--include DIR` 可以再加 include 目录。例如用户的 PCLAeg 插件库里有 ZF、arch、lyger 等，可以直接 require。

## 在 Python 里预先算好，作为数据嵌进模板

模板只依赖 fxlib，用户机器上什么都不用装。适合：
- 形状固定、不随行变化的图形；
- 缺字补形；
- 计算很重的图形（例如图片描摹）。

```bash
pykaraok draw text "気" --font "方正达利体简繁 Heavy" --size 55 --json
pykaraok draw compose --font F --size 55 --part 气 --part '汽@0.45,0.3,1,1+-0.2,0'
```

Python API：
- `pykaraok.draw.glyphs.text_drawing`
- `pykaraok.draw.compose.compose`、`path_to_ass`
- `pykaraok.draw.compose.shapely_to_ass`：shapely 多边形转绘图，带洞。

结果贴进 `--@code once` 的表里，例如 `GLYPH = {["気"] = "m ..."}`，模板里用 `{\an7\pos(...)\p1}!GLYPH[...]!` 输出。坐标原点是文字格的左上角，所以 `\an7\pos(orgline.left + 字的left, orgline.top)` 会正好落在原字的位置。

## 怎么选

- 效果要用到每句的文字形状，又希望用户能在 Aegisub 里改参数重套：用 Yutils 或 ILL，交付说明里写清用户要装什么。
- 用户不一定装了这些库，或者图形固定：在 Python 里预先算好。
