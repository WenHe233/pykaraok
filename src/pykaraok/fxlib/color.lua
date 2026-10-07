-- 颜色：ASS 颜色和 RGB 互转、混色、多段渐变、HSL
-- 依赖 core。ASS 颜色写法是 &HBBGGRR&（蓝绿红），这里的 RGB 一律按红绿蓝顺序

--@code once | pykaraok.color
-- px.c(r, g, b)：RGB 转 ASS 颜色
function px.c(r, g, b)
  local function q(v) return px.clamp(math.floor(v + 0.5), 0, 255) end
  return string.format("&H%02X%02X%02X&", q(b), q(g), q(r))
end
-- px.hex("RRGGBB") 或 px.hex("#RRGGBB")：网页颜色转 ASS 颜色
function px.hex(h)
  h = h:gsub("^#", "")
  return px.c(tonumber(h:sub(1, 2), 16), tonumber(h:sub(3, 4), 16), tonumber(h:sub(5, 6), 16))
end
-- px.rgb(s)：ASS 颜色（&HBBGGRR& 或样式里的 &HAABBGGRR）转 r, g, b
function px.rgb(s)
  local d = s:match("&H(%x+)") or "0"
  local v = tonumber(d:sub(-6), 16) or 0
  return v % 256, math.floor(v / 256) % 256, math.floor(v / 65536) % 256
end
-- px.mix(c1, c2, t)：两种 ASS 颜色按 t 混合
function px.mix(c1, c2, t)
  local r1, g1, b1 = px.rgb(c1)
  local r2, g2, b2 = px.rgb(c2)
  return px.c(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)
end
-- px.grad(stops, u)：多段渐变。stops = {{0, "&H...&"}, {0.5, "&H...&"}, {1, "&H...&"}}，u 在 0 到 1
function px.grad(stops, u)
  u = px.clamp(u, 0, 1)
  for i = 1, #stops - 1 do
    local a, b = stops[i], stops[i + 1]
    if u <= b[1] then return px.mix(a[2], b[2], px.norm(u, a[1], b[1])) end
  end
  return stops[#stops][2]
end
-- px.hsl(h, s, l)：h 为 0 到 360 度，s、l 为 0 到 1
function px.hsl(h, s, l)
  h = (h % 360) / 360
  local function f(p, q, t)
    if t < 0 then t = t + 1 end
    if t > 1 then t = t - 1 end
    if t < 1 / 6 then return p + (q - p) * 6 * t end
    if t < 1 / 2 then return q end
    if t < 2 / 3 then return p + (q - p) * (2 / 3 - t) * 6 end
    return p
  end
  if s == 0 then return px.c(l * 255, l * 255, l * 255) end
  local q = l < 0.5 and l * (1 + s) or l + s - l * s
  local p = 2 * l - q
  return px.c(f(p, q, h + 1 / 3) * 255, f(p, q, h) * 255, f(p, q, h - 1 / 3) * 255)
end
-- 样式颜色：px.style_color(line.styleref.color3) 去掉透明度，得到 &HBBGGRR&
function px.style_color(sc) local r, g, b = px.rgb(sc) return px.c(r, g, b) end
-- 行内文字里第一个 \3c（或 \1c 等）标签的颜色，找不到返回 nil，用于“每个演唱者一种描边色”之类的标记
function px.tag_color(text, which)
  return text:match("\\" .. (which or "3") .. "c(&H%x+&)")
end
