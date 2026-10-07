-- 逐字版面：按 libass 的排版规则算出原行每个字的位置
-- 依赖 core。用于“特效要和用户原来的行完全重合”的场合（静止时与原行逐像素一致）。
-- karaskel 给的 syl.left、syl.center 已经够大多数模板用；这个模块额外处理 \an、\pos、边距，
-- 并按 libass 的 1/64 px 取整（lrint，.5 取偶）

--@code once | pykaraok.layout
px.layout = {}
local L = px.layout
-- libass 的 lrint：恰好 .5 时取偶数
function L.lrint(x)
  local f = math.floor(x)
  local r = x - f
  if r > 0.5 then return f + 1 elseif r < 0.5 then return f end
  if f % 2 == 0 then return f end
  return f + 1
end
-- 解析标签块里的 \alpha \1a \3a，返回更新后的填充、描边透明度
function L.alphas(tags, a1, a3)
  for name, val in tags:gmatch("\\(%d?%a+)([^\\}]*)") do
    if name:sub(1, 5) == "alpha" then val = name:sub(6) .. val name = "alpha"
    elseif name:match("^[1-4]a") then val = name:sub(3) .. val name = name:sub(1, 2) end
    local v = val:match("^&?H?(%x%x?)")
    v = v and tonumber(v, 16)
    if v then
      if name == "alpha" then a1, a3 = v, v elseif name == "1a" then a1 = v elseif name == "3a" then a3 = v end
    end
  end
  return a1, a3
end
-- px.layout.geom(line)：返回 g，g.chars[i] = {c, x, w, cx, a1, a3, hide, sp}（x 为字的左边，单位 px），
-- g.an、g.py（锚点 y）、g.cyc（字的垂直中心）、g.fs（字号乘纵向缩放）、g.base（行首标签块去掉 \fad 后的内容）、
-- g.rest（去掉行首标签块后的正文）、g.fin/g.fout（原行 \fad 的淡入淡出，没有时为 0）
function L.geom(ln)
  local st, t = ln.styleref, ln.text
  local an = tonumber(t:match("\\an(%d)"))
  if not an then
    local a = tonumber(t:match("\\a(%d+)"))
    if a then an = ({[1] = 1, [2] = 2, [3] = 3, [5] = 7, [6] = 8, [7] = 9, [9] = 4, [10] = 5, [11] = 6})[a] end
  end
  an = an or st.align
  local h, vc = an % 3, an <= 3 and 0 or (an <= 6 and 1 or 2)
  local px_, py = t:match("\\pos%(%s*([%-%d%.]+)%s*,%s*([%-%d%.]+)%s*%)")
  px_, py = tonumber(px_), tonumber(py)
  local ml = ln.margin_l > 0 and ln.margin_l or st.margin_l
  local mr = ln.margin_r > 0 and ln.margin_r or st.margin_r
  local mv = ln.margin_t > 0 and ln.margin_t or st.margin_t
  local first = t:match("^%b{}") or "{}"
  local g = {an = an, vc = vc, fs = st.fontsize * st.scale_y / 100}
  g.base = first:sub(2, -2):gsub("\\fade?%b()", "")
  g.rest = t:sub(#(t:match("^%b{}") or "") + 1)
  local fin, fout = first:match("\\fade?%(%s*(%d+)%s*,%s*(%d+)%s*%)")
  g.fin, g.fout = tonumber(fin) or 0, tonumber(fout) or 0
  local a1 = tonumber(st.color1:match("&H(%x%x)"), 16)
  local a3 = tonumber(st.color3:match("&H(%x%x)"), 16)
  local chars, pen = {}, 0
  for blk, tags in ("{}" .. t .. "{}"):gmatch("([^{]*)(%b{})") do
    for c in unicode.chars(blk) do
      local w = math.floor(aegisub.text_extents(st, c) * 64 + 0.5)
      chars[#chars + 1] = {c = c, pen = pen, wd = w, a1 = a1, a3 = a3, hide = a1 >= 255, sp = (c == " " or c == "　")}
      pen = pen + w
    end
    a1, a3 = L.alphas(tags, a1, a3)
  end
  local W = pen
  local function gx(p)
    if px_ then
      if h == 1 then return L.lrint(px_ * 64 + p) end
      if h == 2 then return L.lrint(px_ * 64 - W / 2 + p) end
      return L.lrint(px_ * 64 - W + p)
    end
    local maxw = (meta.res_x - mr) - ml
    local shift = h == 1 and 0 or (h == 2 and (maxw - W / 64) / 2 or (maxw - W / 64))
    return L.lrint(ml * 64 + p + L.lrint(shift * 64))
  end
  for _, ch in ipairs(chars) do
    ch.x = gx(ch.pen) / 64
    ch.w = ch.wd / 64
    ch.cx = ch.x + ch.w / 2
  end
  if not py then
    if vc == 0 then py = meta.res_y - mv elseif vc == 1 then py = meta.res_y / 2 else py = mv end
  end
  g.py = py
  g.cyc = vc == 0 and py - g.fs / 2 or (vc == 1 and py or py + g.fs / 2)
  g.chars = chars
  return g
end
-- 逐字坐标要精确到 1/128 px，写 \pos 时用 px.layout.p(x)
function L.p(x) return px.num(x, 7) end
