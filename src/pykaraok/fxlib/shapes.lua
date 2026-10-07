-- 绘图：\p 图形和变换
-- 依赖 core。libass 按图形坐标的包围盒 [0, W] x [0, H] 对齐，坐标出现负数时整体位置会偏，
-- 所以这里的图形都画在正坐标里；几块图形要叠在一起对齐时，用 px.shape.boxed 给它们同一个包围盒

--@code once | pykaraok.shapes
px.shape = {}
local S = px.shape
local function n(v) return px.num(v, 2) end
local K = 0.5523
-- 以 (cx, cy) 为圆心、半径 r 的圆；ccw 为 true 时反向绘制（套在另一个图形里可挖出洞）
function S.circle_at(cx, cy, r, ccw)
  local k = r * K
  local p = function(x, y) return n(x) .. " " .. n(y) end
  if ccw then
    return "m " .. p(cx, cy - r) .. " b " .. p(cx - k, cy - r) .. " " .. p(cx - r, cy - k) .. " " .. p(cx - r, cy) ..
      " b " .. p(cx - r, cy + k) .. " " .. p(cx - k, cy + r) .. " " .. p(cx, cy + r) ..
      " b " .. p(cx + k, cy + r) .. " " .. p(cx + r, cy + k) .. " " .. p(cx + r, cy) ..
      " b " .. p(cx + r, cy - k) .. " " .. p(cx + k, cy - r) .. " " .. p(cx, cy - r)
  end
  return "m " .. p(cx, cy - r) .. " b " .. p(cx + k, cy - r) .. " " .. p(cx + r, cy - k) .. " " .. p(cx + r, cy) ..
    " b " .. p(cx + r, cy + k) .. " " .. p(cx + k, cy + r) .. " " .. p(cx, cy + r) ..
    " b " .. p(cx - k, cy + r) .. " " .. p(cx - r, cy + k) .. " " .. p(cx - r, cy) ..
    " b " .. p(cx - r, cy - k) .. " " .. p(cx - k, cy - r) .. " " .. p(cx, cy - r)
end
function S.circle(r) return S.circle_at(r, r, r) end
function S.ellipse(rx, ry)
  local kx, ky = rx * K, ry * K
  local p = function(x, y) return n(x) .. " " .. n(y) end
  local cx, cy = rx, ry
  return "m " .. p(cx, 0) .. " b " .. p(cx + kx, 0) .. " " .. p(2 * rx, cy - ky) .. " " .. p(2 * rx, cy) ..
    " b " .. p(2 * rx, cy + ky) .. " " .. p(cx + kx, 2 * ry) .. " " .. p(cx, 2 * ry) ..
    " b " .. p(cx - kx, 2 * ry) .. " " .. p(0, cy + ky) .. " " .. p(0, cy) ..
    " b " .. p(0, cy - ky) .. " " .. p(cx - kx, 0) .. " " .. p(cx, 0)
end
-- n 角星，外半径 R、内半径 r，中心在 (R, R)
function S.star(points, R, r, rot)
  local out = {}
  rot = math.rad(rot or -90)
  for i = 0, points * 2 - 1 do
    local rad = (i % 2 == 0) and R or r
    local a = rot + i * math.pi / points
    out[#out + 1] = n(R + rad * math.cos(a)) .. " " .. n(R + rad * math.sin(a))
  end
  return "m " .. out[1] .. " l " .. table.concat(out, " ", 2)
end
-- 四角闪光（曲线收腰），R 为半径，a 控制腰的粗细（默认 0.11 R）
function S.sparkle(R, a)
  a = a or 0.11 * R
  local p = function(x, y) return n(R + x) .. " " .. n(R + y) end
  return "m " .. p(0, -R) .. " b " .. p(a, -a) .. " " .. p(a, -a) .. " " .. p(R, 0) .. " b " .. p(a, a) .. " " .. p(a, a) .. " " .. p(0, R) ..
    " b " .. p(-a, a) .. " " .. p(-a, a) .. " " .. p(-R, 0) .. " b " .. p(-a, -a) .. " " .. p(-a, -a) .. " " .. p(0, -R)
end
function S.heart(r)
  local p = function(x, y) return n((x + 1) * r) .. " " .. n((y + 1) * r) end
  return "m " .. p(0, .95) .. " b " .. p(-.35, .62) .. " " .. p(-1, .15) .. " " .. p(-1, -.3) .. " b " .. p(-1, -.75) .. " " .. p(-.45, -1) .. " " .. p(0, -.55) ..
    " b " .. p(.45, -1) .. " " .. p(1, -.75) .. " " .. p(1, -.3) .. " b " .. p(1, .15) .. " " .. p(.35, .62) .. " " .. p(0, .95)
end
-- 圆角矩形
function S.rrect(w, h, r)
  r = math.min(r, w / 2, h / 2)
  local k = r * K
  local p = function(x, y) return n(x) .. " " .. n(y) end
  return "m " .. p(r, 0) .. " l " .. p(w - r, 0) .. " b " .. p(w - r + k, 0) .. " " .. p(w, r - k) .. " " .. p(w, r) ..
    " l " .. p(w, h - r) .. " b " .. p(w, h - r + k) .. " " .. p(w - r + k, h) .. " " .. p(w - r, h) ..
    " l " .. p(r, h) .. " b " .. p(r - k, h) .. " " .. p(0, h - r + k) .. " " .. p(0, h - r) ..
    " l " .. p(0, r) .. " b " .. p(0, r - k) .. " " .. p(r - k, 0) .. " " .. p(r, 0)
end
-- 水滴（尖头朝上），宽 w、高 h
function S.drop(w, h)
  local hw = w / 2
  local p = function(x, y) return n(x) .. " " .. n(y) end
  return "m " .. p(hw, 0) .. " b " .. p(hw + hw * 0.3, h * 0.25) .. " " .. p(w, h * 0.45) .. " " .. p(w, h * 0.68) ..
    " b " .. p(w, h * 0.88) .. " " .. p(hw + hw * 0.55, h) .. " " .. p(hw, h) ..
    " b " .. p(hw - hw * 0.55, h) .. " " .. p(0, h * 0.88) .. " " .. p(0, h * 0.68) ..
    " b " .. p(0, h * 0.45) .. " " .. p(hw - hw * 0.3, h * 0.25) .. " " .. p(hw, 0)
end
-- 多边形：pts = {{x, y}, ...}
function S.polygon(pts)
  local out = {}
  for i, q in ipairs(pts) do out[i] = n(q[1]) .. " " .. n(q[2]) end
  return "m " .. out[1] .. " l " .. table.concat(out, " ", 2)
end
-- 在图形前加 "m 0 0 m W H"：只移动不画线，把包围盒固定为 [0, W] x [0, H]，几块图形用同一个 W、H 就能对齐
function S.boxed(shape, W, H) return "m 0 0 m " .. n(W) .. " " .. n(H) .. " " .. shape end
-- 变换图形里的每个坐标：先缩放 (sx, sy)，再绕原点旋转 deg 度，再平移 (dx, dy)
function S.xform(shape, sx, sy, dx, dy, deg)
  local c, s = 1, 0
  if deg and deg ~= 0 then c, s = math.cos(math.rad(deg)), math.sin(math.rad(deg)) end
  return (shape:gsub("(%-?[%d%.]+)%s+(%-?[%d%.]+)", function(x, y)
    x, y = tonumber(x) * (sx or 1), tonumber(y) * (sy or sx or 1)
    return n(x * c - y * s + (dx or 0)) .. " " .. n(x * s + y * c + (dy or 0))
  end))
end
-- 包围盒：minx, miny, maxx, maxy
function S.bounds(shape)
  local x0, y0, x1, y1 = math.huge, math.huge, -math.huge, -math.huge
  for x, y in shape:gmatch("(%-?[%d%.]+)%s+(%-?[%d%.]+)") do
    x, y = tonumber(x), tonumber(y)
    if x < x0 then x0 = x end
    if y < y0 then y0 = y end
    if x > x1 then x1 = x end
    if y > y1 then y1 = y end
  end
  return x0, y0, x1, y1
end
-- 平移到正坐标（左上角对齐到 0, 0）
function S.normalize(shape)
  local x0, y0 = S.bounds(shape)
  return S.xform(shape, 1, 1, -x0, -y0)
end
