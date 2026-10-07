-- 事件列表输出：用一条 template line 从每句歌词生成任意多行特效
-- 依赖 core。适合整句级的设计：先在 Lua 里算好这句要画的所有元素（字、粒子、背景笔触……），
-- 再逐个输出成行。比为每种元素各写一条 template 更容易控制先后和图层。
--
-- 用法（模板源文件）：
--   --@code once | 我的效果
--   function build(ln)            -- ln 是 orgline（已由 karaskel 处理：有 kara、left、center 等）
--     local items = {}
--     px.add(items, 2, 0, ln.duration, "{\\an5\\pos(...)}" .. ln.text_stripped)   -- 图层、相对开始、相对结束、文字
--     return items
--   end
--   --@template line notext style=JP
--   !px.emit(build)!

--@code once | pykaraok.emit
-- 往列表里加一项；s、e 是相对 orgline 开始的毫秒数，会取整到 10 ms，e <= s 的项丢弃
function px.add(items, layer, s, e, text)
  s, e = px.ms(math.max(s, -orgline.start_time)), px.ms(e)
  if e > s then items[#items + 1] = {layer, s, e, text} end
end
-- 在 template line notext 里调用：第一次循环时调用 build(orgline) 得到列表并设置循环次数，
-- 之后每次循环输出一项（改图层、改时间）
function px.emit(build)
  if syl and syl.i ~= 1 then return "" end
  if j == 1 then
    px._items = build(orgline) or {}
    maxloop(math.max(1, #px._items))
  end
  local it = px._items[j]
  if not it then
    line.comment = true
    return ""
  end
  relayer(it[1])
  retime("set", orgline.start_time + it[2], orgline.start_time + it[3])
  return it[4]
end
