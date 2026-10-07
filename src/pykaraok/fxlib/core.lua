-- 基础：模板环境、数字格式、确定性随机数、时间和常用标签
-- 用法：模板源文件里写 --@use core（其它模块都依赖它，放在最前）

--@code once | pykaraok.core 环境
-- kara-templater 的模板环境里只有 string、math、_G。让它能直接用 pairs、ipairs、tonumber、table、unicode、aegisub 等全局
_G.setmetatable(tenv, {__index = _G})
px = px or {}
px.version = "0.1"

--@code once | pykaraok.core 数字
-- px.num(x, d)：保留 d 位小数（默认 2）并去掉多余的 0，用于写进标签
function px.num(x, d)
  local s = string.format("%." .. (d or 2) .. "f", x):gsub("0+$", ""):gsub("%.$", "")
  if s == "-0" then s = "0" end
  return s
end
function px.clamp(x, a, b) if x < a then return a elseif x > b then return b end return x end
function px.lerp(a, b, t) return a + (b - a) * t end
-- 把 x 从区间 [a, b] 映射到 [0, 1] 并截断
function px.norm(x, a, b) if b == a then return 0 end return px.clamp((x - a) / (b - a), 0, 1) end
function px.smooth(t) t = px.clamp(t, 0, 1) return t * t * (3 - 2 * t) end
px.ease = {
  in_quad = function(t) return t * t end,
  out_quad = function(t) return 1 - (1 - t) * (1 - t) end,
  in_out_sine = function(t) return 0.5 - 0.5 * math.cos(math.pi * t) end,
  out_back = function(t, s) s = s or 1.70158 t = t - 1 return t * t * ((s + 1) * t + s) + 1 end,
}

--@code once | pykaraok.core 随机数
-- 随机值必须由行和音节决定，重新套用模板时结果才一致，所以不用 math.random
-- px.hash(a, b, c)：三个数映射到 [0, 1)
function px.hash(a, b, c)
  local x = math.sin(a * 12.9898 + b * 78.233 + (c or 0) * 37.719) * 43758.5453
  return x - math.floor(x)
end
-- px.rand(a, b, salt)：当前 orgline、音节序号、循环序号 j 和 salt 决定的 [a, b) 随机数
function px.rand(a, b, salt)
  local t = orgline and orgline.start_time or 0
  local si = (syl and syl.i) or 0
  local u = px.hash(t * 0.0137 + si * 1.618, (j or 0) * 7.77 + (salt or 0) * 3.31, (orgline and orgline.layer or 0) + si)
  return a + (b - a) * u
end
-- 需要一串随机数时：px.seed(n) 之后反复调用 px.rnd()（Park-Miller，各平台结果相同）
px._rs = 1
function px.seed(s) px._rs = (math.floor(s) % 2147483646) + 1 end
function px.rnd() px._rs = (px._rs * 16807) % 2147483647 return px._rs / 2147483647 end
function px.pick(list) return list[math.floor(px.rnd() * #list) + 1] end

--@code once | pykaraok.core 时间与标签
-- px.ms(t)：取整到 10 ms（ASS 时间精度）
function px.ms(t) return math.floor(t / 10 + 0.5) * 10 end
-- px.rel(t)：绝对时间 t（ms）换算成当前输出行内的相对时间，用于 \t、\move（行被 retime 后也正确）
function px.rel(t) return math.floor(t - line.start_time + 0.5) end
-- px.at_syl(off)：当前音节开始后 off 毫秒，换算成当前输出行内的相对时间（retime 之后用）
function px.at_syl(off) return px.rel(orgline.start_time + syl.start_time + (off or 0)) end
-- px.at_syl_end(off)：当前音节结束后 off 毫秒，同上
function px.at_syl_end(off) return px.rel(orgline.start_time + syl.end_time + (off or 0)) end
-- 只在 template line 的第一个音节返回 true；template line 会对每个音节各求值一次
function px.first() return syl == nil or syl.i == 1 end
function px.t(t1, t2, tags, accel)
  if accel and accel ~= 1 then
    return string.format("\\t(%d,%d,%s,%s)", t1, t2, px.num(accel), tags)
  end
  return string.format("\\t(%d,%d,%s)", t1, t2, tags)
end
function px.pos(x, y) return string.format("\\pos(%s,%s)", px.num(x), px.num(y)) end
function px.move(x1, y1, x2, y2, t1, t2)
  if t1 then
    return string.format("\\move(%s,%s,%s,%s,%d,%d)", px.num(x1), px.num(y1), px.num(x2), px.num(y2), t1, t2)
  end
  return string.format("\\move(%s,%s,%s,%s)", px.num(x1), px.num(y1), px.num(x2), px.num(y2))
end
function px.fad(a, b) return string.format("\\fad(%d,%d)", a, b) end
function px.clip(x1, y1, x2, y2) return string.format("\\clip(%s,%s,%s,%s)", px.num(x1), px.num(y1), px.num(x2), px.num(y2)) end
function px.alpha(v) return string.format("&H%02X&", px.clamp(math.floor(v + 0.5), 0, 255)) end
-- 一个永远不会开始的 \t。libass 会把时间重叠、又没有 \pos/\move/\org/\t 的行挤开；
-- 不想加 \pos 的行加上它，就不会被挪动，画面不变
px.still = "\\t(99999999,99999999,\\1a&HFF&)"
