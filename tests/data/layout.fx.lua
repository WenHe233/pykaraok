-- every syllable placed where the original line draws it (static look must match the original)

--@meta style=JP
--@use core layout

--@code once | 逐音节定位
function at_syl()
  local g = px.layout.cached(orgline)
  local b = px.layout.syl_box(g, orgline, syl.i)
  return string.format("\\an%d\\pos(%s,%s)", b.an, px.layout.p(b.x), px.num(b.y, 3))
end

--@template syl noblank
{!at_syl()!}
