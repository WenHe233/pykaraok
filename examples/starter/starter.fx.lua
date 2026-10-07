-- 入门示例：日文逐音节、中文整句，演示 fxlib 的 core / color / shapes / emit
-- 构建：pykaraok build examples/starter/starter.fx.lua --lyrics 歌词.ass -o 歌词_特效.ass
-- 歌词文件里日文样式叫 JP、中文样式叫 CN；换成别的名字时改下面 style=

--@meta engine=stock style=JP
--@use core color shapes emit

--@note 入门示例：日文逐音节浮入、唱到时放大变色并洒出闪光；中文整句淡入，下面垫一层柔光

--@code once | 配置
-- 颜色用 RGB 网页写法，时间单位 ms
COL = {
  sung = px.hex("FFE08A"),     -- 唱到时的字色
  edge = px.hex("2050A0"),     -- 描边
  glow = px.hex("80B0FF"),     -- 柔光
  spark = px.hex("FFF4C0"),    -- 闪光
}
T = {lead = 300, stagger = 40, rise = 18, out = 250, pop = 120, settle = 300}

--@code once | 时间函数
-- 入场：每个音节比前一个晚 stagger 毫秒，从句首前 lead 毫秒开始。
-- 下面模板里 !px.num(...)! 把算出的数字截成两位小数，!px.at_syl(...)! 给出音节时间在输出行里的相对值
function entry_start() return -T.lead + (syl.i - 1) * T.stagger end

--@template syl noblank style=JP layer=2 | 日文本体
!retime("line", entry_start(), T.out)!
{\an5\move($scenter,!$smiddle + T.rise!,$scenter,$smiddle,0,!T.lead!)
\fad(!T.lead!,!T.out!)\3c!COL.edge!
!px.t(px.at_syl(0), px.at_syl(T.pop), "\\fscx125\\fscy125\\1c" .. COL.sung)!
!px.t(px.at_syl(T.pop), px.at_syl(T.settle), "\\fscx100\\fscy100")!}

--@template syl noblank loop 3 style=JP layer=3 | 日文闪光
!retime("syl", 0, 500)!
{\an5\move($scenter,$smiddle,!px.num($scenter + px.rand(-60, 60, 1))!,!px.num($smiddle + px.rand(-50, 30, 2))!)
\bord0\shad0\blur0.6\1c!COL.spark!\fscx!px.num(px.rand(60, 110, 3), 0)!\fscy!px.num(px.rand(60, 110, 3), 0)!
\t(0,500,\alpha&HFF&\frz!px.num(px.rand(-90, 90, 4), 0)!)\p1}!px.shape.sparkle(14)!

--@code once | 中文整句
function cn_build(ln)
  local items = {}
  local fin, fout = 300, 300
  local x, y = ln.center, ln.middle
  -- 柔光底：比文字略早出现，晚一点消失
  px.add(items, 1, -fin, ln.duration + fout,
    string.format("{\\an5\\pos(%s,%s)\\bord6\\blur8\\1a&HFF&\\3c%s\\3a&H90&\\fad(%d,%d)}%s",
      px.num(x), px.num(y), COL.glow, fin, fout, ln.text_stripped))
  -- 文字本体
  px.add(items, 2, -fin / 2, ln.duration + fout / 2,
    string.format("{\\an5\\pos(%s,%s)\\3c%s\\fad(%d,%d)}%s", px.num(x), px.num(y), COL.edge, fin, fout, ln.text_stripped))
  return items
end

--@template line notext style=CN | 中文整句
!px.emit(cn_build)!
