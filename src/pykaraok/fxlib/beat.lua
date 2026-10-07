-- 节拍网格：让粒子、闪光、缩放跟着拍子走
-- 依赖 core。拍点由 `pykaraok beats 视频 --from --to` 算出（第一拍的视频时间和 BPM），
-- 写进配置：BEAT = px.beat(165, 1160128)

--@code once | pykaraok.beat
-- px.beat(bpm, first_ms)：返回网格对象，时间都是视频里的绝对毫秒
function px.beat(bpm, first_ms)
  local g = {bpm = bpm, t0 = first_ms, len = 60000 / bpm}
  -- 第 k 拍的时间（k 可为负数或小数，0.5 表示半拍）
  function g.at(k) return g.t0 + k * g.len end
  -- t 所在的拍序号（小数）
  function g.index(t) return (t - g.t0) / g.len end
  -- 最近的拍点；sub 为细分（2 表示按半拍吸附）
  function g.snap(t, sub)
    local L = g.len / (sub or 1)
    return g.t0 + math.floor((t - g.t0) / L + 0.5) * L
  end
  -- t 之后（含 t）的第一个拍点
  function g.next(t, sub)
    local L = g.len / (sub or 1)
    return g.t0 + math.ceil((t - g.t0) / L) * L
  end
  -- [a, b] 之间的所有拍点
  function g.between(a, b, sub)
    local L = g.len / (sub or 1)
    local out, k = {}, math.ceil((a - g.t0) / L)
    while g.t0 + k * L <= b do
      out[#out + 1] = g.t0 + k * L
      k = k + 1
    end
    return out
  end
  return g
end
