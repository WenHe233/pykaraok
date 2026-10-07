-- 噪声与等值线：生成不规则的有机形状（水彩笔触、墨迹、云、冰面裂纹的底）
-- 依赖 core。思路：在网格上算一个标量场（噪声加形状），取某个阈值的等值线，输出成 \p3 绘图。
-- 这样得到的边缘是不规则的，不会像椭圆叠加那样能看出一个个圈

--@code once | pykaraok.noise
px.noise = {}
local N = px.noise
-- 平滑值噪声，取值 0 到 1；s 为种子
function N.value(x, y, s)
  local xi, yi = math.floor(x), math.floor(y)
  local xf, yf = x - xi, y - yi
  local u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
  local a, b = px.hash(xi, yi, s), px.hash(xi + 1, yi, s)
  local c, d = px.hash(xi, yi + 1, s), px.hash(xi + 1, yi + 1, s)
  local top = a + (b - a) * u
  return top + (c + (d - c) * u - top) * v
end
-- 分形噪声（多层叠加），oct 为层数（默认 4）
function N.fbm(x, y, s, oct)
  local sum, amp, f, norm = 0, 1, 1, 0
  for o = 1, oct or 4 do
    sum = sum + amp * N.value(x * f, y * f, s + o * 1.7)
    norm = norm + amp
    amp, f = amp * 0.45, f * 2.03
  end
  return sum / norm
end
-- 闭合折线精简（Douglas-Peucker），tol 为允许偏差 px
function N.simplify(p, tol)
  local n = #p
  local q = {}
  for k = 1, n do q[k] = p[k] end
  q[n + 1] = p[1]
  local far, fd = 1, -1
  for k = 2, n do
    local dx, dy = q[k][1] - q[1][1], q[k][2] - q[1][2]
    if dx * dx + dy * dy > fd then far, fd = k, dx * dx + dy * dy end
  end
  local keep, stack, t2 = {[1] = true, [far] = true}, {{1, far}, {far, n + 1}}, tol * tol
  while #stack > 0 do
    local seg = table.remove(stack)
    local a, b = seg[1], seg[2]
    if b - a > 1 then
      local ax, ay = q[a][1], q[a][2]
      local dx, dy = q[b][1] - ax, q[b][2] - ay
      local L2 = dx * dx + dy * dy
      local best, bd = nil, t2
      for k = a + 1, b - 1 do
        local qx, qy = q[k][1] - ax, q[k][2] - ay
        local d
        if L2 == 0 then d = qx * qx + qy * qy else local c = qx * dy - qy * dx d = c * c / L2 end
        if d > bd then best, bd = k, d end
      end
      if best then
        keep[best] = true
        stack[#stack + 1] = {a, best}
        stack[#stack + 1] = {best, b}
      end
    end
  end
  local r = {}
  for k = 1, n do if keep[k] then r[#r + 1] = q[k] end end
  return r
end
-- 等值线（marching squares）：f 是 (nx+1)*(ny+1) 个格点的值，下标 j*(nx+1)+i（从 0 开始），格距 cs px；
-- 返回 f > t 区域的轮廓，坐标单位 1/4 px，配合 \p3 使用。网格最外一圈的值要低于 t，轮廓才闭合。
-- 外轮廓和洞方向相反，libass 按非零环绕规则填充时洞是空的
function N.contour(f, nx, ny, cs, t, tol)
  local W = nx + 1
  local pts, nxt, order = {}, {}, {}
  local function point(id)
    if pts[id] then return end
    local base = math.floor(id / 2)
    local i = base % W
    local jj = (base - i) / W
    local a = f[base]
    local b = id % 2 == 1 and f[base + W] or f[base + 1]
    local u = (t - a) / (b - a)
    if id % 2 == 1 then pts[id] = {i * cs, (jj + u) * cs} else pts[id] = {(i + u) * cs, jj * cs} end
  end
  for jj = 0, ny - 1 do
    for i = 0, nx - 1 do
      local n0 = jj * W + i
      local v0, v1, v2, v3 = f[n0], f[n0 + 1], f[n0 + W + 1], f[n0 + W]
      local c0, c1, c2, c3 = v0 > t, v1 > t, v2 > t, v3 > t
      if not (c0 == c1 and c1 == c2 and c2 == c3) then
        local cr = {}
        if c0 ~= c1 then cr[#cr + 1] = {n0 * 2, c1} end
        if c1 ~= c2 then cr[#cr + 1] = {(n0 + 1) * 2 + 1, c2} end
        if c2 ~= c3 then cr[#cr + 1] = {(n0 + W) * 2, c3} end
        if c3 ~= c0 then cr[#cr + 1] = {n0 * 2 + 1, c0} end
        local n = #cr
        local mid = (v0 + v1 + v2 + v3) / 4 > t
        for k = 1, n do
          if cr[k][2] then
            local m = (n == 2 or not mid) and k % n + 1 or (k - 2) % n + 1
            local e1, e2 = cr[k][1], cr[m][1]
            point(e1) point(e2)
            nxt[e1] = e2
            order[#order + 1] = e1
          end
        end
      end
    end
  end
  local out, used = {}, {}
  for _, e in ipairs(order) do
    if not used[e] then
      local loop, cur = {}, e
      while cur and not used[cur] do
        used[cur] = true
        loop[#loop + 1] = pts[cur]
        cur = nxt[cur]
      end
      if #loop >= 6 then
        loop = N.simplify(loop, tol or 0.35)
        local s = {}
        for k, p in ipairs(loop) do s[k] = math.floor(p[1] * 4 + 0.5) .. " " .. math.floor(p[2] * 4 + 0.5) end
        out[#out + 1] = "m " .. s[1] .. " l " .. table.concat(s, " ", 2)
      end
    end
  end
  return table.concat(out, " ")
end
-- 便捷函数：在 w x h 的区域里用 fn(x, y) 取值（x、y 为 px），格距 cs，返回阈值 t 的 \p3 轮廓。
-- fn 在边缘一圈会被强制取 0，保证轮廓闭合
function N.blob(w, h, cs, t, fn, tol)
  local nx, ny = math.ceil(w / cs), math.ceil(h / cs)
  local f = {}
  for jj = 0, ny do
    for i = 0, nx do
      local v = 0
      if i > 0 and jj > 0 and i < nx and jj < ny then v = fn(i * cs, jj * cs) end
      f[jj * (nx + 1) + i] = v
    end
  end
  return N.contour(f, nx, ny, cs, t, tol)
end
