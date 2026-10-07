-- pykaraok template source, extracted from an existing file
-- build: pykaraok build THIS_FILE --lyrics LYRICS.ass -o OUT.ass

--@meta style='E10插入曲 - JP'

--@style Style: E10插入曲 - JP,FOT-KafuNagomi Std B,72,&H00FEFEFE,&H000000FF,&H00393939,&H00000000,0,0,0,0,100,100,0,0,1,4,0,8,0,0,5,1
--@style Style: E10插入曲 - 标题,VDL-MegaG DB,60,&H00FEFEFE,&H000000FF,&H00393939,&H00000000,0,0,0,0,100,100,0,0,1,4,0,1,0,0,20,1

--@note ══════ Live《A·I》插入曲 · 卡拉OK模板（Aegisub Karaoke Templater，按 libass 渲染编写）══════

--@note 用法：Automation → Karaoke Templater → Apply karaoke template。重复应用会先删掉旧的 fx 行，再重新生成。

--@note 歌词行：Effect 为 karaoke 的 Comment 行，k 标签和 3c 标签都保持原样。模板从 3c 判断演唱者：阿尔玛 &HC0A000& / 玛琪娜 &H7A45E9& / 妮恩 &H007FFF&。

--@note 合唱行（说话人=合唱）没有 3c：按舞台站位生成彩虹渐变描边（左→右 玛琪娜粉 → 阿尔玛青 → 妮恩橙），随 165 BPM 缓缓流动。

--@note 背景歌词（JP 小 / CN 小）沿用你设的垂直边距；“广阔”按你设的边距定位，只加了圆角标签底。JP 行须排在对应 CN 行之前（CN 行借用 JP 行的发声时间）。

--@note 图层：0 曲目卡底板｜1 暗色柔光、气泡、进度条｜2 彩色辉光｜3 文字｜4 光环、故障切片、扫描线｜5 星光、爱心、鼠标光标。

--@note 节拍：165 BPM，拍点 = 0:19:20.128 + n×363.6 ms（从音频实测）；发声后的辉光随拍呼吸。

--@note 开关：改下面 0b-config 那一行 code once 里的 true / false，可单独关掉光晕、辉光、光环、星光、气泡、关键词特效、渐变流动、节拍呼吸。

--@note 关键词特效（表在 6-params 的 KW）：エラー/错误=故障｜解析/分析=扫描线｜更新=翻转｜伸ばせば/伸出手=拉伸｜笑顔/笑容=闪光｜アイと/爱（AI）=爱心｜すき/喜欢=小爱心｜A-Ma-Ne=金色｜フォルダ=进度条｜アクセス=鼠标点击。

--@note 曲目信息卡：样式“E10插入曲 - 标题”，对应 19:21.90–19:29.50 那一条 karaoke 行；不需要时整行连同样式删掉即可。

--@note [code line] 每个歌词行开始时先做预处理（函数在下面的 code once 里）

--@code line all
LC = build_line(orgline)

--@note [code syl] 每个音节开始时决定可选层

--@code syl all noblank
syl_gate()

--@note [template] 层1 气泡（长音≥0.52秒）

--@template syl all noblank notext fxgroup bubble loop 1 layer=1
!maxloop(#S_.bubbles)!!fx_bubble(j)!

--@note [template] 层1 字后暗色柔光

--@template char all noblank fxgroup halo layer=1
!fx_halo()!

--@note [template] 层2 彩色辉光

--@template char all noblank fxgroup glow layer=2
!fx_glow()!

--@note [template] 层3 入场

--@template char all noblank fxgroup lyric layer=3
!fx_enter()!

--@note [template] 层3 主体

--@template char all noblank fxgroup lyric layer=3
!fx_main()!

--@note [template] 层4 光环

--@template syl all noblank notext fxgroup ring layer=4
!fx_ring()!

--@note [template] 层5 星光（每颗 2 条：星 + 柔光）

--@template syl all noblank notext fxgroup spark loop 1 layer=5
!maxloop(#S_.sparks*2)!!fx_spark(j)!

--@note [template] 关键词特效 / 标签 / 进度条 / 光标（图层在函数里指定）

--@template syl all noblank notext fxgroup extra loop 1 layer=3
!maxloop(#S_.extras)!!fx_extra(j)!

--@note [template] 曲目信息卡（只作用于样式“E10插入曲 - 标题”）

--@template line notext loop 1 style='E10插入曲 - 标题' layer=3
!maxloop(#LC.T)!!fx_title(j)!

--@note ──────── 以下是模板用到的函数库（code once，与位置无关，会在处理任何歌词行之前先运行）────────

--@note [code once] 把标准函数带进模板环境

--@code once
pairs=_G.pairs; ipairs=_G.ipairs; type=_G.type; select=_G.select; tostring=_G.tostring; tonumber=_G.tonumber table=_G.table; unicode=_G.unicode; aegisub=_G.aegisub; unpack=_G.unpack; pcall=_G.pcall floor=math.floor; ceil=math.ceil; abs=math.abs; sin=math.sin; cos=math.cos; pi=math.pi; max=math.max; min=math.min; sqrt=math.sqrt; fmt=string.format

--@note [code once] 开关（true/false）

--@code once
CFG = {halo = true, glow = true, ring = true, spark = true, bubble = true, keyword = true, flow = true, throb = true}

--@note [code once] 数字格式化

--@code once
function n1(x) local s = fmt("%.1f", x); if s:sub(-2) == ".0" then s = s:sub(1, -3) end; if s == "-0" then s = "0" end; return s end function n0(x) return fmt("%d", floor(x + 0.5)) end function clamp(x, a, b) if x < a then return a elseif x > b then return b else return x end end function lerp(a, b, t) return a + (b - a) * t end

--@note [code once] 固定种子的伪随机（每次应用结果一致）

--@code once
RS = 20251010 function rseed(s) RS = (floor(s) % 2147483646) + 1 end function rnd() RS = (RS * 16807) % 2147483647; return RS / 2147483647 end function rr(a, b) return a + (b - a) * rnd() end

--@note [code once] 颜色：三位演唱者、金色、颜色转换

--@code once
WHITE = {254, 254, 254}; DARK = {57, 57, 57} ALMA = {0, 160, 192}; MACHINA = {233, 69, 122}; NYNE = {255, 127, 0} GOLD_LO = {236, 165, 24}; GOLD_HI = {255, 243, 176} function rgb_ass(c) return fmt("&H%02X%02X%02X&", floor(c[3] + .5), floor(c[2] + .5), floor(c[1] + .5)) end function ass_rgb(s) local b, g, r = s:match("&H(%x%x)(%x%x)(%x%x)&"); if not r then return nil end; return {tonumber(r, 16), tonumber(g, 16), tonumber(b, 16)} end function mixc(a, b, t) return {a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, a[3] + (b[3] - a[3]) * t} end

--@note [code once] 合唱行的彩虹色板与流动

--@code once
PAL = {{0, {233, 69, 122}}, {.0833, {204, 72, 196}}, {.1667, {140, 92, 240}}, {.25, {60, 132, 245}}, {.3333, {0, 160, 192}}, {.4167, {28, 184, 140}}, {.5, {140, 196, 60}}, {.5833, {255, 196, 40}}, {.6667, {255, 127, 0}}, {.8333, {255, 95, 90}}, {1, {233, 69, 122}}} function pal(v) v = v % 1 for i = 1, #PAL - 1 do local a, b = PAL[i], PAL[i + 1] if v <= b[1] then return mixc(a[2], b[2], (v - a[1]) / (b[1] - a[1])) end end return PAL[1][2] end FLOW_T = 6500 function base_rgb(C, tabs) if LC.chorus and not C.col then return pal(C.u * 2 / 3 - (CFG.flow and (tabs - orgline.start_time) / FLOW_T or 0)) end return C.rgb end

--@note [code once] 图形：圆、四角星、爱心、圆角矩形（libass 的 p 图形要用正坐标）

--@code once
function circ(cx, cy, r, ccw) local k = r * 0.5523 if not ccw then return fmt("m %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s", n1(cx), n1(cy - r), n1(cx + k), n1(cy - r), n1(cx + r), n1(cy - k), n1(cx + r), n1(cy), n1(cx + r), n1(cy + k), n1(cx + k), n1(cy + r), n1(cx), n1(cy + r), n1(cx - k), n1(cy + r), n1(cx - r), n1(cy + k), n1(cx - r), n1(cy), n1(cx - r), n1(cy - k), n1(cx - k), n1(cy - r), n1(cx), n1(cy - r)) end return fmt("m %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s b %s %s %s %s %s %s", n1(cx), n1(cy - r), n1(cx - k), n1(cy - r), n1(cx - r), n1(cy - k), n1(cx - r), n1(cy), n1(cx - r), n1(cy + k), n1(cx - k), n1(cy + r), n1(cx), n1(cy + r), n1(cx + k), n1(cy + r), n1(cx + r), n1(cy + k), n1(cx + r), n1(cy), n1(cx + r), n1(cy - k), n1(cx + k), n1(cy - r), n1(cx), n1(cy - r)) end function star4(R, a) a = a or 0.11 * R local function p(x, y) return n1(R + x) .. " " .. n1(R + y) end return "m " .. p(0, -R) .. " b " .. p(a, -a) .. " " .. p(a, -a) .. " " .. p(R, 0) .. " b " .. p(a, a) .. " " .. p(a, a) .. " " .. p(0, R) .. " b " .. p(-a, a) .. " " .. p(-a, a) .. " " .. p(-R, 0) .. " b " .. p(-a, -a) .. " " .. p(-a, -a) .. " " .. p(0, -R) end function heart(r) local function p(x, y) return n1((x + 1) * r) .. " " .. n1((y + 1) * r) end return "m " .. p(0, .95) .. " b " .. p(-.35, .62) .. " " .. p(-1, .15) .. " " .. p(-1, -.3) .. " b " .. p(-1, -.75) .. " " .. p(-.45, -1) .. " " .. p(0, -.55) .. " b " .. p(.45, -1) .. " " .. p(1, -.75) .. " " .. p(1, -.3) .. " b " .. p(1, .15) .. " " .. p(.35, .62) .. " " .. p(0, .95) end function rrect(w, h, r) local x0, y0, x1, y1, k = 0, 0, w, h, r * 0.5523 local function p(x, y) return n1(x) .. " " .. n1(y) end return "m " .. p(x0 + r, y0) .. " l " .. p(x1 - r, y0) .. " b " .. p(x1 - r + k, y0) .. " " .. p(x1, y0 + r - k) .. " " .. p(x1, y0 + r) .. " l " .. p(x1, y1 - r) .. " b " .. p(x1, y1 - r + k) .. " " .. p(x1 - r + k, y1) .. " " .. p(x1 - r, y1) .. " l " .. p(x0 + r, y1) .. " b " .. p(x0 + r - k, y1) .. " " .. p(x0, y1 - r + k) .. " " .. p(x0, y1 - r) .. " l " .. p(x0, y0 + r) .. " b " .. p(x0, y0 + r - k) .. " " .. p(x0 + r - k, y0) .. " " .. p(x0 + r, y0) end

--@note [code once] 参数：节拍、时长、弹跳幅度、关键词表

--@code once
P = {stag = 22, stag_total = 380, rise = 26, ent_max = 250, exit_dur = 190, exit_lift = 34, exit_lead = 60, pop_up = 30, pop_peak = 45, pop_settle = 300, beat = 364} KP = {jp = {pop = 1.28, glow = 1.0, vdir = 1, throb = 1}, cn = {pop = 1.16, glow = 0.8, vdir = -1, throb = 0.8}, jps = {pop = 1.2, glow = 0.8, vdir = 1, throb = 0.6}, cns = {pop = 1.12, glow = 0.7, vdir = -1, throb = 0.5}} KW = {{"エラー", "glitch"}, {"错误", "glitch"}, {"解析", "scan"}, {"分析", "scan"}, {"更新", "spin"}, {"伸ばせば", "stretch"}, {"伸出手", "stretch"}, {"笑顔", "smile"}, {"笑容", "smile"}, {"アイと", "heart"}, {"爱（AI）", "heart"}, {"すき", "love"}, {"喜欢", "love"}, {"A−Ma−Ne", "gold"}, {"A-Ma-Ne", "gold"}, {"フォルダ", "folder"}, {"アクセス", "access"}} BEAT0 = 1160128; BEAT_T = 60000 / 165 function beats_in(a, b) local out, k = {}, ceil((a - BEAT0) / BEAT_T) while BEAT0 + k * BEAT_T <= b do out[#out + 1] = BEAT0 + k * BEAT_T; k = k + 1 end return out end

--@note [code once] 判断行属于 JP / CN / JP 小 / CN 小

--@code once
function kind_of(style) if style:find("JP 小", 1, true) then return "jps" elseif style:find("CN 小", 1, true) then return "cns" elseif style:find("JP", 1, true) then return "jp" else return "cn" end end

--@note [code once] 每行预处理：逐字位置、演唱者颜色、发声时间、关键词、星光和气泡的位置

--@code once
function build_line(line) if line.style:find("标题", 1, true) then return build_title(line) end local kind = kind_of(line.style); local kp = KP[kind] local LC = {line = line, kind = kind, kp = kp, chorus = (line.actor == "合唱"), dur = line.duration, cy = line.middle, size = line.styleref.fontsize} local L0, L1 = line.start_time, line.end_time local cols, cur, n, txt, pos = {}, nil, 0, line.text, 1 while pos <= #txt do local ob = txt:find("{", pos, true) local plain = ob and txt:sub(pos, ob - 1) or txt:sub(pos) for _ in unicode.chars(plain) do n = n + 1; cols[n] = cur end if not ob then break end local cb = txt:find("}", ob, true) or #txt local a = txt:sub(ob, cb):match("\\3c(&H%x+&)") if a then cur = ass_rgb(a) end pos = cb + 1 end LC.syl, LC.chars = {}, {} local ci, first, last = 0, nil, nil for si = 1, line.kara.n do local syl = line.kara[si] local S = {i = si, t0 = syl.start_time, t1 = syl.end_time, dur = syl.duration, chars = {}, txt = syl.text_stripped, sparks = {}, bubbles = {}, extras = {}} local nch = unicode.len(syl.text_stripped) local left, k = syl.left, 0 for c in unicode.chars(syl.text_stripped) do ci = ci + 1; k = k + 1 local w = aegisub.text_extents(syl.style, c) local C = {c = c, ci = ci, k = k, nk = nch, si = si, left = left, w = w, cx = line.left + left + w / 2, col = cols[ci], S = S} C.blank = (c:find("^[ \t]$") ~= nil) or c == "　" S.chars[k] = C; LC.chars[ci] = C left = left + w end if #S.chars > 0 then S.cx = (S.chars[1].cx + S.chars[#S.chars].cx) / 2 else S.cx = line.left + syl.left end if syl.duration > 0 and not syl.text_stripped:find("^[ \t]*$") and syl.text_stripped ~= "　" then first = first or si; last = si; S.sung = true end LC.syl[si] = S end LC.n = ci; LC.first, LC.last = first or 1, last or line.kara.n local key = L0 .. "_" .. L1 local w0, w1 if kind == "jp" or kind == "jps" then w0 = LC.syl[LC.first] and LC.syl[LC.first].t0 or 0; w1 = LC.syl[LC.last] and LC.syl[LC.last].t1 or LC.dur remember("win_" .. kind .. "_" .. key, {w0, w1}) else local w = recall("win_" .. (kind == "cn" and "jp" or "jps") .. "_" .. key) if w then w0, w1 = w[1], w[2] else w0, w1 = min(250, LC.dur * 0.1), LC.dur - 120 end end LC.w0, LC.w1 = w0, w1 local nn = 0 for _, C in ipairs(LC.chars) do if not C.blank then nn = nn + 1 end end LC.nn = nn local s, b2c, bp = "", {}, 1 for _, C in ipairs(LC.chars) do b2c[bp] = C.ci; bp = bp + #C.c; s = s .. C.c end for _, kw in ipairs(KW) do local init = 1 while true do local a, b = s:find(kw[1], init, true) if not a then break end local c1, cnt = b2c[a], unicode.len(kw[1]) for i = 0, cnt - 1 do local C = LC.chars[c1 + i] if C and not C.kw then C.kw = kw[2]; C.kwi = i + 1; C.kwn = cnt end end init = b + 1 end end LC.gloss = (s == "广阔") local q = 0 local stag = min(P.stag, P.stag_total / max(ci, 1)) for _, C in ipairs(LC.chars) do local S = C.S if kind == "jp" or kind == "jps" then C.ts = S.t0 + (C.k - 1) / C.nk * S.dur; C.te = S.t0 + C.k / C.nk * S.dur else if not C.blank then q = q + 1 end local span = w1 - w0 C.ts = w0 + span * (q - 1) / max(nn, 1); C.te = w0 + span * q / max(nn, 1) end local u = clamp((C.cx - line.left) / max(line.width, 1), 0, 1) C.u = u if C.col then C.rgb = C.col elseif LC.chorus then C.rgb = pal(u * 2 / 3) else C.rgb = DARK end C.tsa = L0 + C.ts; C.tea = L0 + C.te C.es = L0 - 20 + (C.ci - 1) * stag C.em = clamp(C.tsa - 40, C.es + 130, C.es + 130 + P.ent_max - 130) C.xs = max(L1 - P.exit_lead + (C.ci - 1) * stag * 0.2, C.tsa + 160) C.xe = C.xs + P.exit_dur end rseed(L0 * 3 + 17) local vd, size = kp.vdir, LC.size local function add_spark(S, cx, t, big, C0) local ang = rr(15, 165) * pi / 180; local rad = size * rr(0.62, 0.95) local sx = cx + cos(ang) * rad * 1.15 * (rnd() < 0.5 and 1 or -1) local sy = LC.cy + vd * sin(ang) * rad * 0.9 S.sparks[#S.sparks + 1] = {t = t, x = sx, y = sy, R = size * (big and rr(0.34, 0.46) or rr(0.22, 0.32)), life = rr(460, 680), rot = rr(-35, 35), C = C0} end if kind == "jp" or kind == "jps" then for _, S in ipairs(LC.syl) do if S.sung then local nsp = (S.dur >= 300) and 2 or ((rnd() < 0.34) and 1 or 0) for m = 1, nsp do add_spark(S, S.cx, S.t0 + rr(0, 90), m == 1 and S.dur >= 300, S.chars[1]) end if S.dur >= 520 then S.bubbles[1] = {t = S.t0 + 40, x = S.cx + rr(-14, 14), y = LC.cy + vd * size * 0.3, dx = rr(-34, 34), dy = vd * rr(62, 112), r = size * rr(0.20, 0.30), life = rr(900, 1300), C = S.chars[1]} end S.ring = (S.dur >= 300) or (S.i == LC.last) end end else local S = LC.syl[LC.first] local M = clamp(floor(nn / 5 + 0.5), 2, 5) for m = 1, M do local qi = floor(nn * m / (M + 1) + 0.5); local cnt, C = 0, nil for _, c in ipairs(LC.chars) do if not c.blank then cnt = cnt + 1; if cnt == qi then C = c; break end end end if C then add_spark(S, C.cx, C.ts + rr(0, 60), m % 2 == 1, C) end end end local function extra(S, d) S.extras[#S.extras + 1] = d end for _, C in ipairs(LC.chars) do local S = C.S if C.kw and not C.blank then if C.kw == "glitch" then for v = 1, 5 do extra(S, {k = "glitch", C = C, v = v}) end elseif C.kw == "gold" then extra(S, {k = "gold", C = C}); if C.kwi % 2 == 1 then add_spark(S, C.cx, C.ts + rr(0, 80), true, C) end elseif C.kw == "smile" then add_spark(S, C.cx, C.ts + rr(0, 60), true, C); add_spark(S, C.cx, C.ts + rr(60, 160), false, C) elseif C.kw == "heart" or C.kw == "love" then local nh = (C.kw == "heart") and 3 or 2 for m = 1, nh do extra(S, {k = "heart", C = C, t = C.ts + rr(0, 90), x = C.cx + rr(-16, 16), y = LC.cy + vd * size * 0.35, dx = rr(-30, 30), dy = vd * rr(46, 96), r = size * ((C.kw == "heart") and rr(0.17, 0.27) or rr(0.12, 0.19)), life = rr(650, 950), rot = rr(-25, 25), hue = rnd()}) end elseif C.kw == "scan" and C.kwi == 1 then extra(S, {k = "scan", C = C, C2 = LC.chars[C.ci + C.kwn - 1]}) end end end if LC.gloss then local C1, C2 = LC.chars[1], LC.chars[#LC.chars] extra(C1.S, {k = "chip", C = C1, C2 = C2}) end if plan_more then plan_more(LC, extra, rr, rnd) end return LC end

--@note [code once] 取当前字的数据

--@code once
function cur_char() local S = LC.syl[syl.i] local best, bd = S.chars[1], 1e9 for _, C in ipairs(S.chars) do local d = abs(C.left - syl.left); if d < bd then best, bd = C, d end end return best end

--@note [code once] 每个音节决定哪些可选层要生成

--@code once
function syl_gate() if LC.title then fxgroup.lyric = false; fxgroup.halo = false; fxgroup.glow = false; fxgroup.ring = false; fxgroup.spark = false; fxgroup.bubble = false; fxgroup.extra = false; return "" end local S = LC.syl[syl.i]; S_ = S fxgroup.lyric = true fxgroup.halo = CFG.halo; fxgroup.glow = CFG.glow fxgroup.ring = CFG.ring and (S.ring == true) and (LC.kind == "jp" or LC.kind == "jps") fxgroup.spark = CFG.spark and #S.sparks > 0 fxgroup.bubble = CFG.bubble and #S.bubbles > 0 fxgroup.extra = CFG.keyword and #S.extras > 0 return "" end

--@note [code once] 描边颜色随时间的变化（合唱流动 + 发声闪白）

--@code once
function col_seq(C, es, ee, marks) local flow = CFG.flow and LC.chorus and not C.col local ts = {es} if flow then local k = 1; while es + k * P.beat < ee - 20 do ts[#ts + 1] = es + k * P.beat; k = k + 1 end end for _, m in ipairs(marks or {}) do if m[1] > es + 4 and m[1] < ee - 4 then ts[#ts + 1] = m[1] end end ts[#ts + 1] = ee table.sort(ts) local u = {ts[1]} for i = 2, #ts do if ts[i] - u[#u] >= 8 then u[#u + 1] = ts[i] end end local function wmix(t) local m = marks; if not m or #m == 0 then return 0 end if t <= m[1][1] then return m[1][2] end for i = 1, #m - 1 do if t <= m[i + 1][1] then return m[i][2] + (m[i + 1][2] - m[i][2]) * (t - m[i][1]) / (m[i + 1][1] - m[i][1]) end end return m[#m][2] end local function colat(t) local c = flow and base_rgb(C, t) or C.rgb; local w = wmix(t); if w > 0 then c = mixc(c, WHITE, w) end; return rgb_ass(c) end local first = colat(u[1]); local parts, prev = {}, first for i = 2, #u do local c = colat(u[i]) if c ~= prev then parts[#parts + 1] = fmt("\\t(%d,%d,\\3c%s)", u[i - 1] - es, u[i] - es, c) end prev = c end return first, table.concat(parts) end

--@note [code once] 入场：字从下方升起，略过冲

--@code once
function fx_enter() local C = cur_char(); local x, y = C.cx, LC.cy local D = C.em - C.es retime("abs", C.es, C.em) local c0 = col_seq(C, C.es, C.em, nil) local fill = (C.kw == "gold") and ("\\1c" .. rgb_ass(GOLD_LO)) or "" return fmt("{\\an5\\move(%s,%s,%s,%s,0,%d)\\3c%s%s\\bord4\\shad2\\4c&H000000&\\blur0.6\\1a&HFF&\\3a&HFF&\\4a&HFF&\\fscx60\\fscy60\\t(0,%d,0.5,\\1a&H00&\\3a&H00&\\4a&H78&\\fscx108\\fscy108)\\t(%d,%d,\\fscx100\\fscy100)}", n1(x), n1(y + P.rise), n1(x), n1(y), D, c0, fill, floor(D * 0.72), floor(D * 0.72), D) end

--@note [code once] 主体：发声时弹一下，长音保持放大，行尾上浮淡出

--@code once
function fx_main() local C = cur_char(); local S = C.S; local kp = LC.kp local x, y = C.cx, LC.cy retime("abs", C.em, C.xe) local ts, te = C.tsa - C.em, C.tea - C.em local xs, xe = C.xs - C.em, C.xe - C.em local a0 = max(ts - P.pop_up, 0) local c0, cseq = col_seq(C, C.em, C.xe, {{C.tsa - P.pop_up, 0}, {C.tsa + P.pop_peak, 0.62}, {C.tsa + P.pop_peak + P.pop_settle, 0}}) local t = {} local fill = (C.kw == "gold") and ("\\1c" .. rgb_ass(GOLD_LO)) or "" t[#t + 1] = fmt("{\\an5\\move(%s,%s,%s,%s,%d,%d)\\3c%s%s\\bord4\\shad2\\4c&H000000&\\4a&H78&\\blur0.6", n1(x), n1(y), n1(x), n1(y - P.exit_lift), xs, xe, c0, fill) t[#t + 1] = cseq local pk = kp.pop; local rot = (C.ci % 2 == 0) and 5 or -5 local hold = (S.dur >= 380 and (LC.kind == "jp" or LC.kind == "jps")) local tp = a0 + P.pop_up + P.pop_peak if C.kw == "spin" then t[#t + 1] = fmt("\\t(%d,%d,0.6,\\fscx%s\\fscy%s\\bord5.5)\\t(%d,%d,\\fry360)", a0, tp, n0(pk * 100), n0(pk * 100), a0, a0 + max(C.te - C.ts, 340) + 60) t[#t + 1] = fmt("\\t(%d,%d,0.5,\\fscx100\\fscy100\\bord4)", tp, tp + P.pop_settle) elseif C.kw == "stretch" then t[#t + 1] = fmt("\\t(%d,%d,0.6,\\fscx136\\fscy92\\bord5.5)\\t(%d,%d,0.5,\\fscx100\\fscy100\\bord4)", a0, tp, max(te, tp) , max(te, tp) + 220) else t[#t + 1] = fmt("\\t(%d,%d,0.6,\\fscx%s\\fscy%s\\frz%d\\bord5.5)", a0, tp, n0(pk * 100), n0(pk * 100), rot) t[#t + 1] = fmt("\\t(%d,%d,0.5,\\fscx%d\\fscy%d\\frz0\\bord4)", tp, tp + P.pop_settle, hold and 110 or 100, hold and 110 or 100) if hold then t[#t + 1] = fmt("\\t(%d,%d,\\fscx100\\fscy100)", te, te + 160) end end t[#t + 1] = fmt("\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&\\4a&HFF&\\blur6\\fscx108\\fscy108)}", xs, xe) return table.concat(t) end

--@note [code once] 辉光：唱到的字亮起，之后随拍呼吸

--@code once
function fx_glow() local C = cur_char(); local S = C.S; local kp = LC.kp local lead = 90 local es = C.tsa - lead retime("abs", es, C.xe) local x, y = C.cx, LC.cy local pk = kp.pop local hold = (S.dur >= 380 and (LC.kind == "jp" or LC.kind == "jps")) local te = C.tea - es local xs, xe = C.xs - es, C.xe - es local g = kp.glow local c0, cseq = col_seq(C, es, C.xe, nil) local sx, sy = pk * 100, pk * 100 if C.kw == "stretch" then sx, sy = 136, 92 end local t = {} t[#t + 1] = fmt("{\\an5\\move(%s,%s,%s,%s,%d,%d)\\1a&HFF&\\3c%s\\bord9\\blur9\\3a&HFF&\\shad0\\fscx100\\fscy100", n1(x), n1(y), n1(x), n1(y - P.exit_lift), xs, xe, c0) t[#t + 1] = cseq t[#t + 1] = fmt("\\t(%d,%d,0.6,\\3a&H%02X&\\fscx%s\\fscy%s\\bord11)", lead - P.pop_up, lead + P.pop_peak, floor(0x38 + (1 - g) * 0x60), n0(sx), n0(sy)) t[#t + 1] = fmt("\\t(%d,%d,0.5,\\3a&H%02X&\\fscx%d\\fscy%d\\bord9)", lead + P.pop_peak, lead + P.pop_peak + 320, floor(0x98 + (1 - g) * 0x30), hold and 110 or 100, hold and 110 or 100) if hold then t[#t + 1] = fmt("\\t(%d,%d,\\fscx100\\fscy100)", te, te + 160) end local th = CFG.throb and (kp.throb or 0) or 0 if th > 0 then local a_lo = floor(0x98 + (1 - g) * 0x30); local a_hi = floor(0x98 - th * 0x38 + (1 - g) * 0x30) for _, b in ipairs(beats_in(es + lead + P.pop_peak + 340, C.xs - 300)) do local rb = b - es t[#t + 1] = fmt("\\t(%d,%d,\\3a&H%02X&\\bord10.5)\\t(%d,%d,0.6,\\3a&H%02X&\\bord9)", rb - 10, rb + 40, a_hi, rb + 40, rb + 300, a_lo) end end t[#t + 1] = fmt("\\t(%d,%d,1.3,\\3a&HFF&\\blur14)}", xs, xe) return table.concat(t) end

--@note [code once] 光环：长音的扩散圆环

--@code once
function fx_ring() local S = S_; local L0 = orgline.start_time local a = L0 + S.t0 - 20 retime("abs", a, a + 560) local C = S.chars[max(1, floor(#S.chars / 2 + 0.5))] local col = mixc(base_rgb(C, a), WHITE, 0.3) return fmt("{\\an5\\pos(%s,%s)\\p1\\1a&HFF&\\3c%s\\bord5\\blur0.5\\fscx50\\fscy50\\3a&H20&\\t(0,560,0.45,\\fscx210\\fscy210\\bord0.7\\3a&HFF&)}%s", n1(S.cx), n1(LC.cy), rgb_ass(col), circ(LC.size * 0.40, LC.size * 0.40, LC.size * 0.40)) end

--@note [code once] 星光：四角星 + 柔光

--@code once
function fx_spark(j) local S = S_; local m = ceil(j / 2); local sp = S.sparks[m]; local L0 = orgline.start_time retime("abs", L0 + sp.t, L0 + sp.t + sp.life) local tint = mixc(base_rgb(sp.C, L0 + sp.t), WHITE, 0.25) local up = floor(sp.life * 0.42) if j % 2 == 1 then return fmt("{\\an5\\pos(%s,%s)\\p1\\bord2.2\\1c&HFFFFFF&\\3c%s\\blur0.7\\fscx0\\fscy0\\frz%d\\t(0,%d,0.6,\\fscx100\\fscy100\\frz%d)\\t(%d,%d,1.4,\\fscx0\\fscy0\\frz%d)}%s", n1(sp.x), n1(sp.y), rgb_ass(tint), floor(sp.rot), up, floor(sp.rot + 40), up, floor(sp.life), floor(sp.rot + 90), star4(sp.R)) end relayer(4) return fmt("{\\an5\\pos(%s,%s)\\p1\\bord0\\1c%s\\1a&H78&\\blur7\\fscx0\\fscy0\\t(0,%d,0.6,\\fscx100\\fscy100)\\t(%d,%d,1.4,\\fscx0\\fscy0)}%s", n1(sp.x), n1(sp.y), rgb_ass(tint), up, up, floor(sp.life), circ(sp.R * 0.9, sp.R * 0.9, sp.R * 0.9)) end

--@note [code once] 气泡：长音飘出一个泡泡

--@code once
function fx_bubble(j) local S = S_; local b = S.bubbles[j]; local L0 = orgline.start_time retime("abs", L0 + b.t, L0 + b.t + b.life) local tint = mixc(mixc(base_rgb(b.C, L0 + b.t), WHITE, 0.55), {200, 235, 255}, 0.3) local r = b.r local shape = circ(r, r, r) .. " " .. circ(r, r, r - 2.6, true) .. " " .. circ(r * 0.58, r * 0.58, r * 0.17) return fmt("{\\an5\\move(%s,%s,%s,%s,0,%d)\\p1\\bord0\\1c%s\\1a&H70&\\blur0.8\\fscx30\\fscy30\\t(0,220,0.6,\\fscx100\\fscy100)\\t(%d,%d,\\fscx124\\fscy124\\1a&HFF&)}%s", n1(b.x), n1(b.y), n1(b.x + b.dx), n1(b.y + b.dy), floor(b.life), rgb_ass(tint), floor(b.life - 170), floor(b.life), shape) end

--@note [code once] 关键词特效：故障、金色、爱心、扫描线、“广阔”标签

--@code once
function fx_extra(j) local S = S_; local d = S.extras[j]; local L0 = orgline.start_time; local C = d.C local x, y, size = C.cx, LC.cy, LC.size if d.k == "glitch" then local v = d.v local a = C.tsa - 20 + ((v > 2) and (v - 3) * 70 or 0) local dur = (v <= 2) and 480 or 260 retime("abs", a, a + dur) if v <= 2 then local sgn = (v == 1) and 1 or -1 relayer(2) return fmt("{\\an5\\move(%s,%s,%s,%s,0,%d)\\bord0\\shad0\\1c%s\\1a&H30&\\blur0.5\\t(0,%d,\\1a&H90&)\\t(%d,%d,\\1a&HFF&)}%s", n1(x + sgn * 12), n1(y - sgn * 4), n1(x + sgn * 3), n1(y), dur, (v == 1) and "&H4050FF&" or "&HFFE040&", floor(dur * 0.4), floor(dur * 0.4), dur, C.c) end local bands = {{-0.52, -0.14, 19}, {-0.14, 0.16, -23}, {0.16, 0.52, 14}} local bd = bands[v - 2] relayer(4) return fmt("{\\an5\\pos(%s,%s)\\clip(%s,%s,%s,%s)\\1c&HFFFFFF&\\3c%s\\bord4\\blur0.5\\t(%d,%d,\\1a&HFF&\\3a&HFF&)}%s", n1(x + bd[3]), n1(y), n1(x - size), n1(y + size * bd[1]), n1(x + size), n1(y + size * bd[2]), rgb_ass(C.rgb), floor(dur * 0.55), dur, C.c) elseif d.k == "gold" then retime("abs", C.em, C.xe) relayer(4) local ts = C.tsa - C.em; local xs, xe = C.xs - C.em, C.xe - C.em local pk = LC.kp.pop; local a0 = max(ts - P.pop_up, 0); local tp = a0 + P.pop_up + P.pop_peak return fmt("{\\an5\\move(%s,%s,%s,%s,%d,%d)\\clip(%s,%s,%s,%s)\\bord0\\shad0\\3a&HFF&\\1c%s\\blur0.6\\1a&HFF&\\t(0,140,\\1a&H00&)\\t(%d,%d,0.6,\\fscx%s\\fscy%s)\\t(%d,%d,0.5,\\fscx100\\fscy100)\\t(%d,%d,1.3,\\1a&HFF&)}%s", n1(x), n1(y), n1(x), n1(y - P.exit_lift), xs, xe, n1(x - size), n1(y - size), n1(x + size), n1(y + size * 0.04), rgb_ass(GOLD_HI), a0, tp, n0(pk * 100), n0(pk * 100), tp, tp + P.pop_settle, xs, xe, C.c) elseif d.k == "heart" then retime("abs", L0 + d.t, L0 + d.t + d.life) relayer(5) local col = (LC.chorus and not C.col) and pal(d.hue) or mixc({255, 105, 150}, WHITE, d.hue * 0.25) return fmt("{\\an5\\move(%s,%s,%s,%s,0,%d)\\p1\\1c%s\\3c&HFFFFFF&\\bord1.6\\blur0.7\\fscx0\\fscy0\\frz%d\\t(0,170,0.55,\\fscx100\\fscy100)\\t(%d,%d,\\1a&HFF&\\3a&HFF&)}%s", n1(d.x), n1(d.y), n1(d.x + d.dx), n1(d.y + d.dy), floor(d.life), rgb_ass(col), floor(d.rot), floor(d.life - 260), floor(d.life), heart(d.r)) elseif d.k == "scan" then local C2 = d.C2 local a, b = C.tsa - 40, C2.tea + 40 retime("abs", a, b) relayer(4) local col = mixc(base_rgb(C, C.tsa), WHITE, 0.4) local h = size * 0.62 return fmt("{\\an5\\move(%s,%s,%s,%s,40,%d)\\p1\\1c&HFFFFFF&\\3c%s\\bord3\\blur3\\fad(60,120)}m 0 0 l 5 0 l 5 %s l 0 %s", n1(C.cx - C.w * 0.5), n1(y), n1(C2.cx + C2.w * 0.5), n1(y), floor(b - a - 40), rgb_ass(col), n1(2 * h), n1(2 * h)) elseif d.k == "chip" then local C2 = d.C2 local a, b = orgline.start_time, orgline.end_time local cx = (C.cx + C2.cx) / 2; local w = (C2.cx - C.cx) + C.w + 34; local h = size + 14 retime("abs", C.es, C2.xe) relayer(1) local col = mixc(base_rgb(C, C.tsa), WHITE, 0.15) local D = C.em - C.es local xs = C2.xs - C.es; local xe = C2.xe - C.es return fmt("{\\an5\\pos(%s,%s)\\p1\\1c&H301810&\\1a&HFF&\\3c%s\\3a&HFF&\\bord1.6\\blur0.5\\fscx30\\fscy100\\t(0,%d,0.5,\\1a&H70&\\3a&H10&\\fscx100)\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&\\fscx60)}%s", n1(cx), n1(y), rgb_ass(col), D + 120, xs, xe, rrect(w, h, h * 0.5)) end if fx_more then local r = fx_more(d); if r then return r end end retime("abs", 0, 0) return "" end

--@note [code once] 曲目信息卡的布局

--@code once
function build_title(line) local LC = {title = true, line = line, kind = "title", T = {}} local st = {} for k, v in pairs(line.styleref) do st[k] = v end local function tw(font, size, text, sp) st.fontname = font; st.fontsize = size; st.spacing = sp or 0; return (aegisub.text_extents(st, text)) end local VDL, FZ = "VDL-MegaG DB", "FZVDLZhaoHeiS Medium" local T = LC.T local function add(d) T[#T + 1] = d end local SC = 0.88 local function q(v) return v * SC end local function r0(v) return floor(v + 0.5) end local PW, PH = q(700), q(322) local PX, PY = 84, 1068 - PH local X = PX + q(56) add({k = "panel", x = PX, y = PY, w = PW, h = PH, at = 0}) local cs = {MACHINA, ALMA, NYNE} for i = 1, 3 do add({k = "bar", x = PX + q(22), y = PY + q(24) + (i - 1) * q(88), w = q(9), h = q(82), c = cs[i], at = 160 + i * 70}) end add({k = "text", txt = "LIVE  ·  {\\fn" .. FZ .. "\\fs" .. r0(q(28)) .. "}插入曲", font = VDL, size = r0(q(26)), sp = 5, x = X, y = PY + q(40), fill = {214, 234, 255}, out = ALMA, bord = 1.6, at = 320}) local ts = r0(q(112)) local w1 = tw(VDL, ts, "A", 6); local w2 = tw(VDL, ts, "·", 6) local ty = PY + q(132) add({k = "text", txt = "A", font = VDL, size = ts, sp = 6, x = X, y = ty, fill = WHITE, out = MACHINA, bord = 5, at = 420}) add({k = "text", txt = "·", font = VDL, size = ts, sp = 6, x = X + w1, y = ty, fill = WHITE, out = ALMA, bord = 5, at = 470}) add({k = "text", txt = "I", font = VDL, size = ts, sp = 6, x = X + w1 + w2, y = ty, fill = WHITE, out = NYNE, bord = 5, at = 520}) add({k = "text", txt = "A-Ma-Ne", font = VDL, size = r0(q(54)), sp = 4, x = X + q(246), y = ty + q(14), fill = WHITE, out = {120, 92, 240}, bord = 3, at = 640}) local names = {{"阿尔玛", "月城日花", ALMA}, {"玛琪娜", "長江里加", MACHINA}, {"妮恩", "矢野妃菜喜", NYNE}} local cw, gap = q(134), q(12) for i, nm in ipairs(names) do local cx = X + (i - 1) * (cw + gap) + cw / 2 add({k = "chip", x = cx, y = PY + q(206), w = cw, h = q(42), c = nm[3], at = 760 + i * 90}) add({k = "text", txt = nm[1], font = FZ, size = r0(q(27)), sp = 2, x = cx, y = PY + q(206), an = 5, fill = WHITE, out = mixc(nm[3], DARK, 0.55), bord = 1.8, at = 800 + i * 90}) add({k = "text", txt = nm[2], font = VDL, size = r0(q(24)), sp = 1, x = cx, y = PY + q(246), an = 5, fill = WHITE, out = nm[3], bord = 2, at = 840 + i * 90}) end add({k = "text", txt = "{\\fn" .. FZ .. "}作词{\\fn" .. VDL .. "}  こだまさおり     {\\fn" .. FZ .. "}作曲・编曲{\\fn" .. VDL .. "}  鳥海剛史", font = VDL, size = r0(q(22)), sp = 1, x = X, y = PY + q(290), fill = {226, 232, 246}, out = {60, 52, 110}, bord = 1.6, at = 1200}) return LC end

--@note [code once] 曲目信息卡的绘制

--@code once
function fx_title(j) local d = LC.T[j]; local L0, L1 = orgline.start_time, orgline.end_time local es, ee = L0 + d.at, L1 + 340 retime("abs", es, ee) local E = ee - es; local xs = L1 - es local ex = fmt("\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&\\4a&HFF&\\blur6)", xs, E) if d.k == "panel" then relayer(0) return fmt("{\\an5\\pos(%s,%s)\\p1\\1c&H1E0E12&\\1a&H62&\\3c&HFFFFFF&\\3a&HB0&\\bord1.5\\blur0.6\\clip(%d,%d,%d,%d)\\t(0,460,0.5,\\clip(%d,%d,%d,%d))\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&)}%s", n1(d.x + d.w / 2), n1(d.y + d.h / 2), d.x, d.y - 4, d.x, d.y + d.h + 4, d.x, d.y - 4, d.x + d.w + 4, d.y + d.h + 4, xs, E, rrect(d.w, d.h, 26)) elseif d.k == "bar" then relayer(1) return fmt("{\\an5\\pos(%s,%s)\\p1\\bord0\\1c%s\\blur0.5\\fscy0\\t(0,300,0.5,\\fscy100)\\t(%d,%d,1.3,\\fscy0)}m 0 0 l %s 0 l %s %s l 0 %s", n1(d.x + d.w / 2), n1(d.y + d.h / 2), rgb_ass(d.c), xs, E, n1(d.w), n1(d.w), n1(d.h), n1(d.h)) elseif d.k == "chip" then relayer(2) return fmt("{\\an5\\pos(%s,%s)\\p1\\bord1.4\\1c%s\\3c&HFFFFFF&\\3a&H60&\\1a&HFF&\\blur0.5\\fscx40\\fscy40\\t(0,300,0.5,\\1a&H10&\\fscx100\\fscy100)\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&)}%s", n1(d.x), n1(d.y), rgb_ass(d.c), xs, E, rrect(d.w, d.h, d.h / 2)) elseif d.k == "text" then relayer(3) local an = d.an or 4 return fmt("{\\an%d\\move(%s,%s,%s,%s,0,340)\\fn%s\\fs%d\\fsp%s\\1c%s\\3c%s\\bord%s\\shad2\\4c&H000000&\\blur0.6\\1a&HFF&\\3a&HFF&\\4a&HFF&\\t(0,340,0.5,\\1a&H00&\\3a&H00&\\4a&H80&)%s}%s", an, n1(d.x - 40), n1(d.y), n1(d.x), n1(d.y), d.font, d.size, n1(d.sp or 0), rgb_ass(d.fill), rgb_ass(d.out), n1(d.bord or 3), ex, d.txt) end retime("abs", 0, 0) return "" end

--@note [code once] 歌词专属特效的规划：进度条、鼠标点击

--@code once
function plan_more(LC, extra, rr, rnd) if LC.kind ~= "jp" and LC.kind ~= "jps" then return end local line = LC.line local chars = LC.chars for _, C in ipairs(chars) do if C.kw == "folder" and C.kwi == 1 then local N = 20 local x0, W, h = line.left, line.width, 9 local y = LC.cy + LC.size * 0.5 + 14 local ta = C.tsa - 40 local tb = line.start_time + LC.w1 local d0 = {C = C, x0 = x0, W = W, h = h, y = y, ta = ta, tb = tb, N = N} d0.k = "pbar_track"; extra(C.S, d0) for i = 1, N do extra(C.S, {k = "pbar_seg", C = C, i = i, x0 = x0, W = W, h = h, y = y, ta = ta, tb = tb, N = N}) end extra(C.S, {k = "pbar_head", C = C, x0 = x0, W = W, h = h, y = y, ta = ta, tb = tb}) extra(C.S, {k = "pbar_label", C = C, x0 = x0, W = W, h = h, y = y, ta = ta, tb = tb}) elseif C.kw == "access" and C.kwi == 1 then local C2 = chars[C.ci + C.kwn - 1] extra(C.S, {k = "cursor", C = C, C2 = C2}) extra(C.S, {k = "ping", C = C2}) end end end

--@note [code once] 歌词专属特效的绘制

--@code once
function fx_more(d) local L0, L1 = orgline.start_time, orgline.end_time local size = LC.size if d.k == "pbar_track" then local Cl = LC.chars[LC.last_c or #LC.chars] retime("abs", d.ta - 200, Cl.xe) relayer(1) local xs = Cl.xs - (d.ta - 200) return fmt("{\\an5\\pos(%s,%s)\\p1\\1c&HFFFFFF&\\1a&HC8&\\3c&HFFFFFF&\\3a&HA0&\\bord1.2\\blur0.6\\fscx0\\t(0,260,0.5,\\fscx100)\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&)}%s", n1(d.x0 + d.W / 2), n1(d.y), xs, xs + P.exit_dur, rrect(d.W, d.h, d.h / 2)) elseif d.k == "pbar_seg" then local Cl = LC.chars[#LC.chars] local a = d.ta - 60 retime("abs", a, Cl.xe) relayer(2) local sw = d.W / d.N local xl = d.x0 + (d.i - 1) * sw local col = pal(((d.i - 0.5) / d.N) * 2 / 3) local dur = d.tb - d.ta local xs = Cl.xs - a return fmt("{\\an5\\pos(%s,%s)\\p1\\bord0\\1c%s\\blur0.4\\clip(%s,%s,%s,%s)\\t(60,%d,\\clip(%s,%s,%s,%s))\\t(%d,%d,1.3,\\1a&HFF&)}m 0 0 l %s 0 l %s %s l 0 %s", n1(xl + sw / 2), n1(d.y), rgb_ass(col), n1(d.x0 - 3), n1(d.y - 12), n1(d.x0 - 3), n1(d.y + 12), 60 + dur, n1(d.x0 - 3), n1(d.y - 12), n1(d.x0 + d.W + 3), n1(d.y + 12), xs, xs + P.exit_dur, n1(sw + 1), n1(sw + 1), n1(d.h), n1(d.h)) elseif d.k == "pbar_head" then local a = d.ta - 60 local dur = d.tb - d.ta retime("abs", a, d.tb + 260) relayer(4) return fmt("{\\an5\\move(%s,%s,%s,%s,60,%d)\\p1\\bord0\\1c&HFFFFFF&\\blur3\\fscx0\\fscy0\\t(0,120,\\fscx100\\fscy100)\\t(%d,%d,1.3,\\fscx0\\fscy0)}%s", n1(d.x0), n1(d.y), n1(d.x0 + d.W), n1(d.y), 60 + dur, 60 + dur, 60 + dur + 240, circ(11, 11, 11)) elseif d.k == "pbar_label" then local Cl = LC.chars[#LC.chars] local a = d.tb - 60 retime("abs", a, Cl.xe) relayer(5) local xs = Cl.xs - a return fmt("{\\an4\\move(%s,%s,%s,%s,0,260)\\fnVDL-MegaG DB\\fs30\\fsp2\\1c&HFFFFFF&\\3c%s\\bord3\\shad0\\blur0.5\\1a&HFF&\\3a&HFF&\\fscx70\\fscy70\\t(0,260,0.5,\\1a&H00&\\3a&H00&\\fscx100\\fscy100)\\t(%d,%d,1.3,\\1a&HFF&\\3a&HFF&)}100%%", n1(d.x0 + d.W + 6), n1(d.y + 8), n1(d.x0 + d.W + 20), n1(d.y + 8), rgb_ass(mixc(ALMA, WHITE, 0.1)), xs, xs + P.exit_dur) elseif d.k == "cursor" then local C, C2 = d.C, d.C2 local tclick = C2.tsa local a = tclick - 460 retime("abs", a, tclick + 620) relayer(5) local function path(s) local pts = {{0, 0}, {0, 17}, {4, 13.2}, {7, 20}, {9.6, 18.8}, {6.6, 12.4}, {12, 12.4}} local o = {} for i, p in ipairs(pts) do o[#o + 1] = (i == 1 and "m " or "l ") .. n1(p[1] * s) .. " " .. n1(p[2] * s) end return table.concat(o, " ") end local tx, ty = C2.cx + 4, LC.cy + 6 local sx, sy = C.cx - 90, LC.cy + 92 return fmt("{\\an7\\move(%s,%s,%s,%s,0,420)\\p1\\1c&HFFFFFF&\\3c&H302418&\\bord2.4\\shad1.5\\4c&H000000&\\4a&H90&\\blur0.4\\1a&HFF&\\3a&HFF&\\4a&HFF&\\t(0,180,\\1a&H00&\\3a&H00&\\4a&H90&)\\t(420,500,0.7,\\fscx82\\fscy82)\\t(500,620,\\fscx100\\fscy100)\\t(760,1000,\\1a&HFF&\\3a&HFF&\\4a&HFF&)}%s", n1(sx), n1(sy), n1(tx), n1(ty), path(2.0)) elseif d.k == "ping" then local C = d.C local a = C.tsa retime("abs", a, a + 600) relayer(4) local col = mixc(base_rgb(C, a), WHITE, 0.25) local R = size * 0.34 return fmt("{\\an5\\pos(%s,%s)\\p1\\1a&HFF&\\3c%s\\bord4\\blur0.5\\fscx40\\fscy40\\3a&H20&\\t(0,600,0.4,\\fscx240\\fscy240\\bord0.6\\3a&HFF&)}%s", n1(C.cx + 4), n1(LC.cy + 6), rgb_ass(col), circ(R, R, R)) end return nil end

--@note [code once] 字后暗色柔光，浅色画面上也看得清

--@code once
function fx_halo() local C = cur_char() local x, y = C.cx, LC.cy local D = C.em - C.es local a = C.es + floor(D * 0.4) retime("abs", a, C.xe) local xs, xe = C.xs - a, C.xe - a local fin = C.em - a + 120 return fmt("{\\an5\\move(%s,%s,%s,%s,%d,%d)\\1a&HFF&\\3c&H2A1A38&\\bord7\\blur5\\shad0\\3a&HFF&\\t(0,%d,\\3a&H74&)\\t(%d,%d,1.3,\\3a&HFF&)}", n1(x), n1(y), n1(x), n1(y - P.exit_lift), xs, xe, fin, xs, xe) end
