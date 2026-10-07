-- pykaraok template source, extracted from an existing file
-- build: pykaraok build THIS_FILE --lyrics LYRICS.ass -o OUT.ass

--@meta style=JP

--@style Style: JP,汉仪正圆-85S,63,&H00DDD5DD,&H000000FF,&H00FF6D4F,&H009390B6,0,0,0,0,100,100,0,0,1,1,1,8,10,10,20,1

--@note 《リキッド・アイス》 karaoke template - Aegisub 自带 Karaoke Templater 2.1.7 (自动化 > Apply karaoke template)

--@note 构思: 未唱=冻结的冰晶字(冰蓝填充+斜向晶面高光+蓝边) / 唱到=冰融化(白光一闪, 晶面消失, 转为暖白+淡口红粉边) / 长音=字底凝出水滴落下 / 退场=字向下融化流走

--@note 图层: 1 深蓝光晕 / 2 字体本体 / 3 冰晶高光 / 4 唱到时的光晕扩散 / 5 入场扫光 / 6 水滴 / 7 星光与冰尘

--@note 尾句 (开始时间 >= T.finale, 即 5:47.15 的「願う—/我祈愿—」) 不向下融化, 改为化作星光上升. 颜色/时间参数都在下面几行 code once 的 COL / T / STY 表里, 改完重新 Apply 即可. 生成行 effect=fx, 重新 Apply 会自动删除旧的 fx 行

--@code once
_G.setmetatable(tenv, {__index = _G}) fmt = string.format floor, max, min, abs, sin, cos = math.floor, math.max, math.min, math.abs, math.sin, math.cos PREV_END = {}

--@code once
COL = { frost = '&HFFDCC9&', sheen = '&HFFFFFF&', sheenA = '&H00&', edge = '&HF2785C&', halo = '&H5A1C14&', haloA = '&H70&', haloWarm = '&H6E2E7A&', glint = '&HFFEAA8&', melt = '&HFAF4FF&', rouge = '&HBF8CF0&', sparkA = '&HFFE0A0&', sparkB = '&HDDB8FF&', drop = '&HFFF3EA&', dropEdge = '&HFFB48A&' }

--@code once
T = {E = 480, stIn = 38, X = 380, stOut = 34, sweepDelay = 380, sweepSpeed = 1.6, dropMin = 700, finale = 347150, finStep = 150, finDur = 1000} STY = { JP = {lead = 380, fall = 46, gb = 0.76, rise = 45}, CN = {lead = 380, fall = 28, gb = 0.76, rise = 110} } STAR = 'm 0 -13 b 1.3 -3.2 3.2 -1.3 13 0 b 3.2 1.3 1.3 3.2 0 13 b -1.3 3.2 -3.2 1.3 -13 0 b -3.2 -1.3 -1.3 -3.2 0 -13' DROP = 'm 0 0 b 2.2 4.5 7 8.5 7 13 b 7 17 4 19.5 0 19.5 b -4 19.5 -7 17 -7 13 b -7 8.5 -2.2 4.5 0 0' DOT = 'm 0 -2 b 1.1 -2 2 -1.1 2 0 b 2 1.1 1.1 2 0 2 b -1.1 2 -2 1.1 -2 0 b -2 -1.1 -1.1 -2 0 -2'

--@code once
function n2(x) local s = fmt('%.2f', x):gsub('0+$', ''):gsub('%.$', '') return s end function hrand(k) local v = sin(k * 12.9898 + 78.233) * 43758.5453 return v - floor(v) end function rr(a, b, salt) return a + (b - a) * hrand(orgline.start_time * 0.0137 + syl.i * 1.618 + (j or 0) * 7.77 + (salt or 0) * 3.31) end function tt(t) return floor(t - (line.start_time - orgline.start_time) + 0.5) end

--@code once
function syl_times() local vi, ldur = VI[syl.i] or 0, orgline.duration TIN = floor(-LEAD + vi * T.stIn) if FIN then XS0 = floor(ldur - 250 + vi * T.finStep) XE0 = XS0 + T.finDur else local xs = max(ldur - T.X - (NV - 1 - vi) * T.stOut, min(syl.end_time, ldur - 220)) XS0, XE0 = floor(xs), floor(min(ldur, xs + T.X)) end TAIL = max(0, XE0 - ldur) return '' end function rt_in() syl_times() retime('line', TIN, TAIL) E, HS, HE, XS, XE = T.E, tt(syl.start_time), tt(syl.end_time), tt(XS0), tt(XE0) return '' end function swell() return fmt([[\t(%d,%d,0.5,\fscx107\fscy107)\t(%d,%d,1.3,\fscx100\fscy100)]], HS, HS + 110, HS + 110, HS + 460) end function exit_main() if FIN then return fmt([[\t(%d,%d,0.6,\fscx135\fscy135\blur8\1c&HFFFFFF&\3c%s\alpha&HFF&)]], XS, XE, COL.glint) end return fmt([[\t(%d,%d,1.5,\fscx94\fscy122\blur5\alpha&HFF&)]], XS, XE) end function exit_halo() return fmt([[\t(%d,%d,\alpha&HFF&\blur12)]], XS, XE) end function sheen_clip() local l, r = orgline.left + syl.left - 6, orgline.left + syl.right + 6 local t, h = orgline.top - 8, orgline.height local y1, y2 = orgline.top + h * 0.60, orgline.top + h * 0.34 return fmt([[\clip(m %s %s l %s %s l %s %s l %s %s)]], n2(l), n2(t), n2(r), n2(t), n2(r), n2(y2), n2(l), n2(y1)) end

--@code once
function rt_bloom() BD = floor(max(600, min(syl.duration + 200, 1600))) retime('presyl', 0, BD) return '' end function bloom_col() return (((VI[syl.i] or 0) % 2) == 0) and COL.sparkB or COL.sparkA end function rt_sweep() local w = (j == 1) and 140 or 46 SW_A = (j == 1) and '&H98&' or '&H30&' local x0, x1 = orgline.left - 90, orgline.left + orgline.width + 90 local dur = floor((x1 - x0) / T.sweepSpeed) local ts = floor(-LEAD + T.sweepDelay) retime('preline', ts, ts + dur) local y0, y1 = n2(orgline.top - 30), n2(orgline.bottom + 30) SW_CLIP = fmt([[\clip(%s,%s,%s,%s)\t(0,%d,\clip(%s,%s,%s,%s))]], n2(x0 - w / 2), y0, n2(x0 + w / 2), y1, dur, n2(x1 - w / 2), y0, n2(x1 + w / 2), y1) return '' end

--@code once
PFX = {} function PFX.dust(k) local cx, cy = orgline.left + syl.center, orgline.middle local a, r = rr(0, 6.2832, k), rr(24, 44, k + 10) local t0, dur = TIN + floor(rr(0, 140, k + 20)), 440 local s = floor(rr(70, 130, k + 25)) retime('preline', t0, t0 + dur) relayer(7) return fmt([[{\an5\move(%s,%s,%s,%s,0,%d)\bord0\shad0\blur0.8\1c&HFFFFFF&\alpha&H30&\fscx%d\fscy%d\t(0,%d,1.4,\alpha&HFF&\fscx40\fscy40)\p1}%s]], n2(cx + r * cos(a)), n2(cy + r * sin(a) * 0.6), n2(cx + rr(-6, 6, k + 30)), n2(cy + rr(-6, 6, k + 40)), dur, s, s, dur, DOT) end function PFX.spark(k) local cx, cy, w, h = orgline.left + syl.center, orgline.middle, syl.width, orgline.height local t0, dur = syl.start_time + ((k == 1) and 0 or floor(syl.duration * 0.55)), 560 local sx, sy = cx + rr(-0.5, 0.5, k + 50) * w, cy - h * rr(0.12, 0.44, k + 60) local sz, rot = floor(rr(60, 110, k + 70)), floor(rr(-30, 30, k + 90)) local col = (rr(0, 1, k + 80) < 0.5) and COL.sparkA or COL.sparkB retime('preline', t0, t0 + dur) relayer(7) return fmt([[{\an5\pos(%s,%s)\bord1.3\blur1.8\shad0\1c&HFFFFFF&\3c%s\fscx0\fscy0\frz%d\t(0,130,0.6,\fscx%d\fscy%d)\t(130,%d,1.5,\fscx0\fscy0\frz%d)\p1}%s]], n2(sx), n2(sy), col, rot, sz, sz, dur, rot + 70, STAR) end function PFX.grow() local P = STY[orgline.style] or STY.JP local t0, t1 = syl.start_time + floor(syl.duration * 0.3), syl.end_time DX = orgline.left + syl.center + rr(-0.12, 0.12, 100) * syl.width DY = orgline.top + orgline.height * P.gb retime('preline', t0, t1) relayer(6) return fmt([[{\an8\pos(%s,%s)\bord1.2\blur0.6\shad0\1c%s\3c%s\1a&H18&\fscx0\fscy0\t(0,%d,0.6,\fscx78\fscy78)\p1}%s]], n2(DX), n2(DY), COL.drop, COL.dropEdge, t1 - t0, DROP) end function PFX.fall() local P = STY[orgline.style] or STY.JP local t0, dur = syl.end_time, 560 retime('preline', t0, t0 + dur) relayer(6) return fmt([[{\an8\move(%s,%s,%s,%s,0,%d)\bord1.2\blur0.6\shad0\1c%s\3c%s\1a&H18&\fscx78\fscy78\t(0,%d,1.8,\fscx62\fscy104\alpha&HFF&)\p1}%s]], n2(DX), n2(DY), n2(DX), n2(DY + P.fall), dur, COL.drop, COL.dropEdge, dur, DROP) end

--@code once
function PFX.rise(k) local P = STY[orgline.style] or STY.JP local cx, cy, w, h = orgline.left + syl.center, orgline.middle, syl.width, orgline.height local t0, dur = XS0 + floor(rr(0, 500, k + 200)), floor(rr(1100, 1700, k + 210)) local x0, y0 = cx + rr(-0.45, 0.45, k + 220) * w, cy + rr(-0.3, 0.3, k + 230) * h local x1, y1 = x0 + rr(-30, 30, k + 240), y0 - P.rise * rr(0.5, 1, k + 250) local sz, rot = floor(rr(40, 90, k + 260)), floor(rr(-40, 40, k + 270)) local col = ((k % 2) == 0) and COL.sparkA or COL.sparkB retime('preline', t0, t0 + dur) relayer(7) return fmt([[{\an5\move(%s,%s,%s,%s)\bord1.2\blur1.6\shad0\1c&HFFFFFF&\3c%s\fscx0\fscy0\frz%d\t(0,200,\fscx%d\fscy%d)\t(200,%d,1.3,\fscx20\fscy20\frz%d\alpha&HFF&)\p1}%s]], n2(x0), n2(y0), n2(x1), n2(y1), col, rot, sz, sz, dur, rot + 90, STAR) end function particle() if j == 1 then syl_times() PL = {{'dust', 1}, {'dust', 2}, {'dust', 3}, {'spark', 1}} if syl.duration >= T.dropMin then PL[#PL + 1] = {'spark', 2} PL[#PL + 1] = {'grow'} PL[#PL + 1] = {'fall'} end if FIN then for k = 1, 6 do PL[#PL + 1] = {'rise', k} end end maxloop(#PL) end local p = PL[j] return PFX[p[1]](p[2]) end

--@code line all
VI, NV = {}, 0 for i = 1, orgline.kara.n do local s = orgline.kara[i] local t = s.text_stripped:gsub('[ \t\n\r]', ''):gsub('　', '') if s.duration > 0 and t ~= '' then VI[i] = NV NV = NV + 1 end end local P, pe = STY[orgline.style] or STY.JP, PREV_END[orgline.style] LEAD = pe and max(0, min(P.lead, orgline.start_time - pe - 60)) or P.lead PREV_END[orgline.style] = orgline.end_time FIN = orgline.start_time >= T.finale DYX = FIN and -16 or 7

--@template syl noblank notext all layer=1
!rt_in()!{\an5\move($center,$middle,$center,!$middle+DYX!,!XS!,!XE!)\shad0\bord7\blur7\1c!COL.halo!\3c!COL.halo!\alpha&HFF&\t(0,!E!,\alpha!COL.haloA!)!swell()!\t(!HS!,!HE+250!,\1c!COL.haloWarm!\3c!COL.haloWarm!)!exit_halo()!}!syl.text_spacestripped!

--@template syl noblank notext all layer=2
!rt_in()!{\an5\move($center,$middle,$center,!$middle+DYX!,!XS!,!XE!)\shad0\bord2\blur6\fscx112\fscy112\1c&HFFFFFF&\3c!COL.glint!\alpha&HFF&\t(0,!E*0.5!,\alpha&H00&)\t(0,!E!,0.5,\blur0.7\fscx100\fscy100\1c!COL.frost!\3c!COL.edge!)!swell()!\t(!HS!,!HS+90!,\1c&HFFFFFF&\3c!COL.glint!\bord2.6\blur1.4)\t(!HS+90!,!HE+250!,0.7,\1c!COL.melt!\3c!COL.rouge!\bord2\blur0.7)!exit_main()!}!syl.text_spacestripped!

--@template syl noblank notext all layer=3
!rt_in()!{\an5\move($center,$middle,$center,!$middle+DYX!,!XS!,!XE!)\shad0\bord0\blur0.6\fscx112\fscy112\1c!COL.sheen!\alpha&HFF&!sheen_clip()!\t(0,!E*0.5!,\alpha!COL.sheenA!)\t(0,!E!,0.5,\fscx100\fscy100)!swell()!\t(!HS!,!HS+320!,\alpha&HFF&)}!syl.text_spacestripped!

--@template syl noblank notext all layer=4
!rt_bloom()!{\an5\pos($center,$middle)\shad0\bord3\blur6\1c&HFFFFFF&\3c!bloom_col()!\alpha&H40&\t(0,!BD!,0.6,\fscx120\fscy120\blur10\alpha&HFF&)}!syl.text_spacestripped!

--@template syl noblank notext all loop 2 layer=5
!rt_sweep()!{\an5\pos($center,$middle)\shad0\bord2.4\blur2\1c&HFFFFFF&\3c&HFFFFFF&\alpha!SW_A!!SW_CLIP!}!syl.text_spacestripped!

--@template syl noblank notext all layer=7
!particle()!
