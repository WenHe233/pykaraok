-- pykaraok: headless Automation 4 environment.
--
-- Recreates what Aegisub sets up for a Lua automation script
-- (src/auto4_lua.cpp, src/auto4_lua_assfile.cpp, src/auto4_lua_progresssink.cpp,
-- libaegisub/lua/script_reader.cpp, libaegisub/lua/modules.cpp) on top of
-- lupa's LuaJIT.  Python services arrive in the PY table:
--
--   PY.load_source(path) -> lua source  (BOM stripped, .moon compiled)
--   PY.file_exists(path) -> bool
--   PY.text_extents(fontname, fontsize, bold, italic, underline, strikeout,
--                   encoding, spacing, scale_x, scale_y, text) -> w, h, d, e
--   PY.parse_kara(text, start_ms) -> list of syllable tables (1-based)
--   PY.log(level, msg), PY.progress(kind, value)
--   PY.case(kind, str) -> str            kind: upper | lower | fold
--   PY.frame_from_ms(ms), PY.ms_from_frame(frame) -> number or nil
--   PY.decode_path(path) -> str
--   PY.dialog(kind, dialog, buttons, button_ids) -> button, results
--   PY.include_dirs (array), PY.script_dir, PY.trace_level, PY.file_name,
--   PY.video (nil or {w, h, ar, artype}), PY.keyframes (array or nil),
--   PY.project (table), PY.res_x, PY.res_y
--
-- Returns the API table used by pykaraok.aegi.runtime.

local PY = ...
local ffi = require 'ffi'

local type, pairs, tostring, tonumber, select, error = type, pairs, tostring, tonumber, select, error
local floor, ceil = math.floor, math.ceil
local sformat = string.format
local unpack = unpack or table.unpack

---------------------------------------------------------------------------
-- Lua 5.2 compatibility that Aegisub's LuaJIT build has and lupa's lacks
---------------------------------------------------------------------------
table.unpack = table.unpack or unpack
table.pack = table.pack or function(...) return {n = select('#', ...), ...} end

local raw_ipairs, raw_pairs = ipairs, pairs
local function ipairs_iter(t, i)
  i = i + 1
  local v = t[i]
  if v ~= nil then return i, v end
end
function ipairs(t)
  local mt = getmetatable(t)
  if type(mt) == 'table' and mt.__ipairs then return mt.__ipairs(t) end
  if type(t) == 'table' then return raw_ipairs(t) end
  return ipairs_iter, t, 0
end
function pairs(t)
  local mt = getmetatable(t)
  if type(mt) == 'table' and mt.__pairs then return mt.__pairs(t) end
  return raw_pairs(t)
end
pairs = pairs
ipairs = ipairs

---------------------------------------------------------------------------
-- Module loading (script_reader.cpp: module_loader / Install / LoadFile)
---------------------------------------------------------------------------
local function load_chunk(path)
  local src = PY.load_source(path)
  local fn, err = loadstring(src, '@' .. path)
  if not fn then return nil, err end
  return fn
end

do
  local parts = {}
  for _, dir in raw_ipairs(PY.include_dirs) do
    parts[#parts + 1] = dir .. '/?.lua;' .. dir .. '/?/init.lua'
  end
  package.path = table.concat(parts, ';')
end

local function module_loader(name)
  local modpath = name:gsub('%.', '/')
  local tried = {}
  for tok in package.path:gmatch('[^;]+') do
    local filename = tok:gsub('%?', (modpath:gsub('%%', '%%%%')))
    local path = filename
    if path:sub(-4) == '.lua' then
      local moonpath = path:sub(1, -5) .. '.moon'
      if PY.file_exists(moonpath) then path = moonpath end
    end
    if PY.file_exists(path) then
      local fn, err = load_chunk(path)
      if not fn then
        error(sformat('Error loading Lua module "%s":\n%s', path, tostring(err)), 2)
      end
      return fn
    end
    tried[#tried + 1] = '\n\tno file \'' .. filename .. '\''
  end
  return table.concat(tried)
end
package.loaders[2] = module_loader

-- MoonScript is compiled with moonc on the Python side; expose the parts of
-- the moonscript module that scripts use.
package.loaded.moonscript = {
  loadstring = function(src, chunkname)
    local ok, lua = pcall(PY.compile_moon, src, chunkname or '=moonscript')
    if not ok then return nil, lua end
    return loadstring(lua, chunkname)
  end,
  loadfile = function(path) return load_chunk(path) end,
}

-- dofile and loadfile are replaced with include (auto4_lua.cpp)
dofile = nil
loadfile = nil

function include(filename)
  local path
  if filename:find('[/\\]') then
    path = PY.script_dir .. '/' .. filename
  else
    for _, dir in raw_ipairs(PY.include_dirs) do
      local cand = dir .. '/' .. filename
      if PY.file_exists(cand) then path = cand break end
    end
  end
  if not path or not PY.file_exists(path) then
    error(sformat('Lua include not found: %s', filename), 2)
  end
  local fn, err = load_chunk(path)
  if not fn then
    error(sformat('Error loading Lua include "%s":\n%s', filename, tostring(err)), 2)
  end
  return fn()
end

---------------------------------------------------------------------------
-- C modules preloaded by Aegisub (libaegisub/lua/modules.cpp)
---------------------------------------------------------------------------
-- aegisub.__unicode_impl: case conversion, called through unicode.moon's
-- conv_func, which expects a C string it can pass to ffi.string.
do
  local keep
  local function wrap(kind)
    return function(str, err)
      if type(str) ~= 'string' then str = ffi.string(str) end
      local s = PY.case(kind, str)
      keep = ffi.new('char[?]', #s + 1)
      ffi.copy(keep, s, #s)
      return ffi.cast('const char *', keep)
    end
  end
  package.preload['aegisub.__unicode_impl'] = function()
    return {to_upper_case = wrap('upper'), to_lower_case = wrap('lower'), to_fold_case = wrap('fold')}
  end
end

package.preload['aegisub.__re_impl'] = function()
  return PY.re_impl()
end

package.preload['aegisub.__lfs_impl'] = function()
  error('aegisub.lfs is not available in pykaraok', 2)
end

package.preload['lpeg'] = function()
  error('lpeg is not available in pykaraok (MoonScript is compiled with moonc instead)', 2)
end

---------------------------------------------------------------------------
-- Extradata registry (AssFile::Extradata / AddExtradata / GetExtradata)
---------------------------------------------------------------------------
local xdata = {list = {}, next_id = 0}

local function add_extradata(key, value)
  for _, e in raw_ipairs(xdata.list) do
    if e.key == key and e.value == value then return e.id end
  end
  local id = xdata.next_id
  xdata.list[#xdata.list + 1] = {id = id, key = key, value = value}
  xdata.next_id = id + 1
  return id
end

local function get_extradata(ids)
  local out = {}
  for _, id in raw_ipairs(ids) do
    for _, e in raw_ipairs(xdata.list) do
      if e.id == id then out[e.key] = e.value break end
    end
  end
  return out
end

---------------------------------------------------------------------------
-- AssEntry <-> Lua table conversion (auto4_lua_assfile.cpp)
---------------------------------------------------------------------------
local MAX_TIME = 10 * 60 * 60 * 1000 - 6

local function bad_field(expected, name, cls)
  error(sformat("Invalid or missing field '%s' in '%s' class subtitle line (expected %s)", name, cls, expected), 0)
end

local function get_string(t, name, cls)
  local v = t[name]
  if type(v) == 'string' then return v end
  if type(v) == 'number' then return tostring(v) end
  bad_field('string', name, cls)
end

local function get_double(t, name, cls)
  local v = tonumber(t[name])
  if v == nil then bad_field('number', name, cls) end
  return v
end

local function get_int(t, name, cls)
  local v = get_double(t, name, cls)
  if v >= 0 then return floor(v) else return ceil(v) end
end

local function get_bool(t, name, cls)
  local v = t[name]
  if type(v) ~= 'boolean' then bad_field('boolean', name, cls) end
  return v
end

local function clamp_time(ms)
  if ms < 0 then return 0 elseif ms > MAX_TIME then return MAX_TIME end
  return ms
end

-- agi::Color(string) then GetAssStyleFormatted()
local function norm_color(s)
  s = tostring(s):match('^%s*(.-)%s*$')
  local r, g, b, a = 0, 0, 0, 0
  if s:sub(1, 1) == '#' then
    local h = s:sub(2)
    r = tonumber(h:sub(1, 2), 16) or 0
    g = tonumber(h:sub(3, 4), 16) or 0
    b = tonumber(h:sub(5, 6), 16) or 0
    a = tonumber(h:sub(7, 8), 16) or 0
  elseif s:lower():sub(1, 4) == 'rgb(' then
    local x, y, z = s:match('(%d+)%s*,%s*(%d+)%s*,%s*(%d+)')
    r, g, b = tonumber(x) or 0, tonumber(y) or 0, tonumber(z) or 0
  else
    local v
    if s:sub(1, 2):lower() == '&h' then
      local digits = s:sub(3):match('^%x*')
      if #digits > 8 then digits = digits:sub(-8) end
      v = tonumber(digits ~= '' and digits or '0', 16)
    else
      v = tonumber((s:gsub('&+$', ''))) or 0
    end
    v = v % 4294967296
    r = v % 256
    g = floor(v / 256) % 256
    b = floor(v / 65536) % 256
    a = floor(v / 16777216) % 256
  end
  return sformat('&H%02X%02X%02X%02X', a, b, g, r)
end

local GROUP = {info = 1, style = 2, dialogue = 3}

local function to_entry(t)
  if type(t) ~= 'table' then error("Can't convert a non-table value to AssEntry", 0) end
  local cls = t.class
  if type(cls) ~= 'string' then error("Table lacks 'class' field, can't convert to AssEntry", 0) end
  cls = cls:lower()
  if cls == 'info' then
    return {class = 'info', key = get_string(t, 'key', 'info'), value = get_string(t, 'value', 'info')}
  elseif cls == 'style' then
    return {
      class = 'style',
      name = (get_string(t, 'name', 'style'):gsub(',', ';')),
      fontname = (get_string(t, 'fontname', 'style'):gsub(',', ';')),
      fontsize = get_double(t, 'fontsize', 'style'),
      color1 = norm_color(get_string(t, 'color1', 'style')),
      color2 = norm_color(get_string(t, 'color2', 'style')),
      color3 = norm_color(get_string(t, 'color3', 'style')),
      color4 = norm_color(get_string(t, 'color4', 'style')),
      bold = get_bool(t, 'bold', 'style'), italic = get_bool(t, 'italic', 'style'),
      underline = get_bool(t, 'underline', 'style'), strikeout = get_bool(t, 'strikeout', 'style'),
      scale_x = get_double(t, 'scale_x', 'style'), scale_y = get_double(t, 'scale_y', 'style'),
      spacing = get_double(t, 'spacing', 'style'), angle = get_double(t, 'angle', 'style'),
      borderstyle = get_int(t, 'borderstyle', 'style'),
      outline = get_double(t, 'outline', 'style'), shadow = get_double(t, 'shadow', 'style'),
      align = get_int(t, 'align', 'style'),
      margin_l = get_int(t, 'margin_l', 'style'), margin_r = get_int(t, 'margin_r', 'style'),
      margin_t = get_int(t, 'margin_t', 'style'), encoding = get_int(t, 'encoding', 'style'),
    }
  elseif cls == 'dialogue' then
    local e = {
      class = 'dialogue',
      comment = get_bool(t, 'comment', 'dialogue'),
      layer = get_int(t, 'layer', 'dialogue'),
      start_time = clamp_time(get_int(t, 'start_time', 'dialogue')),
      end_time = clamp_time(get_int(t, 'end_time', 'dialogue')),
      style = get_string(t, 'style', 'dialogue'),
      actor = get_string(t, 'actor', 'dialogue'),
      margin_l = get_int(t, 'margin_l', 'dialogue'),
      margin_r = get_int(t, 'margin_r', 'dialogue'),
      margin_t = get_int(t, 'margin_t', 'dialogue'),
      effect = get_string(t, 'effect', 'dialogue'),
      text = get_string(t, 'text', 'dialogue'),
      ids = {},
    }
    local extra = t.extra
    if type(extra) == 'table' then
      local ids = {}
      for k, v in raw_pairs(extra) do
        if type(k) == 'string' then
          ids[#ids + 1] = add_extradata(k, type(v) == 'string' and v or (type(v) == 'number' and tostring(v) or ''))
        end
      end
      table.sort(ids)
      e.ids = ids
    elseif extra ~= nil then
      error('dialogue extradata must be a table', 0)
    end
    return e
  end
  error(sformat('Found line with unknown class: %s', cls), 0)
end

local function fmt_time(ms)
  local t = (ms + 5) - (ms + 5) % 10
  return sformat('%d:%02d:%02d.%02d', floor(t / 3600000), floor(t % 3600000 / 60000),
                 floor(t % 60000 / 1000), floor(t % 1000 / 10))
end

local function raw_line(e)
  if e.class == 'info' then
    return e.key .. ': ' .. e.value
  elseif e.class == 'style' then
    return sformat('Style: %s,%s,%g,%s,%s,%s,%s,%d,%d,%d,%d,%g,%g,%g,%g,%d,%g,%g,%d,%d,%d,%d,%d',
      e.name, e.fontname, e.fontsize, e.color1, e.color2, e.color3, e.color4,
      e.bold and -1 or 0, e.italic and -1 or 0, e.underline and -1 or 0, e.strikeout and -1 or 0,
      e.scale_x, e.scale_y, e.spacing, e.angle, e.borderstyle, e.outline, e.shadow, e.align,
      e.margin_l, e.margin_r, e.margin_t, e.encoding)
  else
    local prefix = ''
    if #e.ids > 0 then
      local p = {}
      for i, id in raw_ipairs(e.ids) do p[i] = '=' .. id end
      prefix = '{' .. table.concat(p) .. '}'
    end
    return sformat('%s: %d,%s,%s,%s,%s,%d,%d,%d,%s,%s%s', e.comment and 'Comment' or 'Dialogue', e.layer,
      fmt_time(e.start_time), fmt_time(e.end_time), (e.style:gsub(',', ';')), (e.actor:gsub(',', ';')),
      e.margin_l, e.margin_r, e.margin_t, (e.effect:gsub(',', ';')), prefix, (e.text:gsub('[\r\n]', '')))
  end
end

local function to_lua(e)
  local t
  if e.class == 'info' then
    t = {section = '[Script Info]', key = e.key, value = e.value, class = 'info'}
  elseif e.class == 'style' then
    t = {
      section = '[V4+ Styles]', name = e.name, fontname = e.fontname, fontsize = e.fontsize,
      color1 = e.color1 .. '&', color2 = e.color2 .. '&', color3 = e.color3 .. '&', color4 = e.color4 .. '&',
      bold = e.bold, italic = e.italic, underline = e.underline, strikeout = e.strikeout,
      scale_x = e.scale_x, scale_y = e.scale_y, spacing = e.spacing, angle = e.angle,
      borderstyle = e.borderstyle, outline = e.outline, shadow = e.shadow, align = e.align,
      margin_l = e.margin_l, margin_r = e.margin_r, margin_t = e.margin_t, margin_b = e.margin_t,
      encoding = e.encoding, relative_to = 2, class = 'style',
    }
  else
    t = {
      section = '[Events]', comment = e.comment, layer = e.layer,
      start_time = e.start_time, end_time = e.end_time,
      style = e.style, actor = e.actor, effect = e.effect,
      margin_l = e.margin_l, margin_r = e.margin_r, margin_t = e.margin_t, margin_b = e.margin_t,
      text = e.text, extra = get_extradata(e.ids), class = 'dialogue',
    }
  end
  t.raw = raw_line(e)
  return t
end

---------------------------------------------------------------------------
-- The subtitle file object (LuaAssFile)
---------------------------------------------------------------------------
local lines = {}

local function check_uint(v, argn)
  local n = tonumber(v)
  if n == nil then error(sformat('bad argument #%d (number expected, got %s)', argn, type(v)), 3) end
  if n >= 0 then return floor(n) else return ceil(n) end
end

local function append_entries(...)
  for i = 1, select('#', ...) do
    local e = to_entry((select(i, ...)))
    if #lines == 0 then
      lines[1] = e
    else
      local placed = false
      for k = #lines, 1, -1 do
        if GROUP[lines[k].class] == GROUP[e.class] then
          table.insert(lines, k + 1, e)
          placed = true
          break
        end
      end
      if not placed then lines[#lines + 1] = e end
    end
  end
end

local methods = {}
function methods.append(...) append_entries(...) end
function methods.insert(before, ...)
  before = check_uint(before, 1)
  if not (before > 0 and before <= #lines + 1) then error('bad argument #1 (Out of range line index)', 2) end
  if before == #lines + 1 then return append_entries(...) end
  local new = {}
  for i = 1, select('#', ...) do new[i] = to_entry((select(i, ...))) end
  for i = #new, 1, -1 do table.insert(lines, before, new[i]) end
end
function methods.delete(...)
  local n = select('#', ...)
  if n == 0 then return end
  local ids = {}
  local first = ...
  if n == 1 and type(first) == 'table' then
    for _, v in raw_pairs(first) do
      local k = check_uint(v, 1)
      if not (k > 0 and k <= #lines) then error('bad argument #1 (Out of range line index)', 2) end
      ids[#ids + 1] = k
    end
  else
    for i = 1, n do
      local k = check_uint((select(i, ...)), i)
      if not (k > 0 and k <= #lines) then error(sformat('bad argument #%d (Out of range line index)', i), 2) end
      ids[#ids + 1] = k
    end
  end
  local del = {}
  for _, k in raw_ipairs(ids) do del[k] = true end
  local out = {}
  for i = 1, #lines do
    if not del[i] then out[#out + 1] = lines[i] end
  end
  for i = #lines, 1, -1 do lines[i] = nil end
  for i = 1, #out do lines[i] = out[i] end
end
function methods.deleterange(a, b)
  a = math.max(check_uint(a, 1), 1)
  b = math.min(check_uint(b, 2), #lines)
  if a > b then return end
  for i = b, a, -1 do table.remove(lines, i) end
end
function methods.script_resolution()
  return PY.res_x, PY.res_y
end

local subs = newproxy(true)
do
  local mt = getmetatable(subs)
  mt.__index = function(_, k)
    if type(k) == 'number' then
      local idx = (k >= 0) and floor(k) or ceil(k)
      if idx <= 0 or idx > #lines then
        error(sformat('Requested out-of-range line from subtitle file: %d', idx), 2)
      end
      return to_lua(lines[idx])
    elseif type(k) == 'string' then
      if k == 'n' then return #lines end
      local m = methods[k]
      if m then return m end
      error(sformat("Invalid indexing in Subtitle File object: '%s'", k), 2)
    end
    error(sformat("Attempt to index a Subtitle File object with value of type '%s'.", type(k)), 2)
  end
  mt.__newindex = function(_, k, v)
    local n = check_uint(k, 2)
    if n < 0 then
      methods.insert(-n, v)
    elseif n == 0 then
      append_entries(v)
    elseif v ~= nil then
      if n > #lines then error(sformat('Requested out-of-range line from subtitle file: %d', n), 2) end
      lines[n] = to_entry(v)
    else
      methods.delete(n)
    end
  end
  mt.__len = function() return #lines end
  mt.__ipairs = function()
    return function(_, i)
      if i >= #lines then return nil end
      return i + 1, to_lua(lines[i + 1])
    end, nil, 0
  end
  mt.__tostring = function() return 'pykaraok subtitle file' end
end

---------------------------------------------------------------------------
-- The aegisub table (auto4_lua.cpp LuaScript::Create + LuaProgressSink)
---------------------------------------------------------------------------
local CANCEL = setmetatable({}, {__tostring = function() return 'aegisub.cancel()' end})
local macros, filters = {}, {}

local function debug_out(...)
  local n = select('#', ...)
  local args = {...}
  local first, level = 1, -1
  if type(args[1]) == 'number' then
    level = args[1]
    if level > PY.trace_level then return end
    first = 2
  end
  local msg
  if n - first + 1 > 1 then
    local ok, res = pcall(sformat, unpack(args, first, n))
    if not ok then error(res, 2) end
    msg = res
  else
    msg = args[first]
  end
  if type(msg) ~= 'string' and type(msg) ~= 'number' then
    error(sformat('bad argument #1 to debug.out (string expected, got %s)', type(msg)), 2)
  end
  PY.log(level, tostring(msg))
end

local function dialog_fn(kind)
  return function(...) return PY.dialog(kind, ...) end
end

aegisub = {
  register_macro = function(name, description, fn, validate, is_active)
    for _, m in raw_ipairs(macros) do
      if m.name == name then error(sformat("A macro named '%s' is already defined", name), 2) end
    end
    macros[#macros + 1] = {name = name, description = description, fn = fn, validate = validate, is_active = is_active}
  end,
  register_filter = function(name, description, priority, fn, config)
    filters[#filters + 1] = {name = name, description = description, priority = priority, fn = fn, config = config}
  end,
  text_extents = function(style, text)
    if type(style) ~= 'table' then error('bad argument #1 to text_extents (table expected)', 2) end
    if type(text) ~= 'string' and type(text) ~= 'number' then error('bad argument #2 to text_extents (string expected)', 2) end
    if type(style.class) ~= 'string' or style.class:lower() ~= 'style' then error('Not a style entry', 2) end
    local c = 'style'
    return PY.text_extents((get_string(style, 'fontname', c):gsub(',', ';')), get_double(style, 'fontsize', c),
      get_bool(style, 'bold', c), get_bool(style, 'italic', c), get_bool(style, 'underline', c),
      get_bool(style, 'strikeout', c), get_int(style, 'encoding', c), get_double(style, 'spacing', c),
      get_double(style, 'scale_x', c), get_double(style, 'scale_y', c), tostring(text))
  end,
  frame_from_ms = function(ms) return PY.frame_from_ms(tonumber(ms) or 0) end,
  ms_from_frame = function(frame) return PY.ms_from_frame(tonumber(frame) or 0) end,
  video_size = function()
    local v = PY.video
    if v == nil then return nil end
    return v[1], v[2], v[3], v[4]
  end,
  keyframes = function() return PY.keyframes or {} end,
  decode_path = function(p) return PY.decode_path(p) end,
  cancel = function() error(CANCEL, 0) end,
  lua_automation_version = 4,
  __init_clipboard = function()
    return {get = function() return nil end, set = function() return false end}
  end,
  __raise_warning = function(msg) PY.log(1, 'warning: ' .. tostring(msg)) end,
  file_name = function() return PY.file_name end,
  gettext = function(s) return s end,
  project_properties = function() return PY.project end,
  get_audio_selection = function() return nil end,
  set_status_text = function() end,
  parse_karaoke_data = function(line)
    local e = to_entry(line)
    if e.class ~= 'dialogue' then error('bad argument #1 (Subtitle line must be a dialogue line)', 2) end
    local list = PY.parse_kara(e.text, e.start_time)
    local res = {}
    for i = 1, #list do res[i - 1] = list[i] end
    return res
  end,
  set_undo_point = function() end,
  progress = {
    set = function(v) PY.progress('set', tonumber(v) or 0) end,
    task = function(s) PY.progress('task', tostring(s)) end,
    title = function(s) PY.progress('title', tostring(s)) end,
    is_cancelled = function() return false end,
  },
  debug = {out = debug_out},
  log = debug_out,
  dialog = {display = dialog_fn('display'), open = dialog_fn('open'), save = dialog_fn('save')},
}

-- unicode-monkeypatch.lua makes io.open & co. accept UTF-8 paths on Windows
if ffi.os == 'Windows' and PY.monkeypatch then
  local fn = load_chunk(PY.monkeypatch)
  if fn then pcall(fn) end
end

---------------------------------------------------------------------------
-- API for the Python side
---------------------------------------------------------------------------
local api = {}

-- Initial lines from the file.  `_ids` carries the extradata ids parsed from
-- the line's {=N} prefix so they survive unchanged.
function api.add_entries(list)
  for i = 1, #list do
    local src = list[i]
    local e = to_entry(src)
    if src._ids then
      local ids = {}
      for k = 1, #src._ids do ids[k] = src._ids[k] end
      e.ids = ids
    end
    lines[#lines + 1] = e
  end
end

function api.set_extradata(list, next_id)
  xdata.list = {}
  for i = 1, #list do
    local e = list[i]
    xdata.list[i] = {id = e.id, key = e.key, value = e.value}
  end
  xdata.next_id = next_id
end

function api.get_entries()
  local out = {}
  for i = 1, #lines do
    local e = lines[i]
    local t = {}
    for k, v in raw_pairs(e) do t[k] = v end
    out[i] = t
  end
  return out
end

function api.get_extradata()
  return xdata.list, xdata.next_id
end

function api.load_script(path)
  local fn, err = load_chunk(path)
  if not fn then return false, tostring(err) end
  local ok, e = xpcall(fn, debug.traceback)
  if not ok then return false, tostring(e) end
  return true, ''
end

local function find_macro(name)
  for _, m in raw_ipairs(macros) do
    if m.name == name then return m end
  end
end

function api.macro_names()
  local out = {}
  for i, m in raw_ipairs(macros) do out[i] = m.name end
  return out
end

function api.filter_names()
  local out = {}
  for i, f in raw_ipairs(filters) do out[i] = f.name end
  return out
end

local function handler(e)
  if e == CANCEL then return CANCEL end
  return debug.traceback(tostring(e), 2)
end

function api.validate_macro(name, selected, active)
  local m = find_macro(name)
  if not m then return false, 'no macro named ' .. tostring(name) end
  if not m.validate then return true, '' end
  local ok, res = xpcall(m.validate, handler, subs, selected or {}, active or 0)
  if not ok then return false, tostring(res) end
  return res and true or false, ''
end

-- returns status ('ok' | 'cancelled' | 'error'), message
function api.run_macro(name, selected, active)
  local m = find_macro(name)
  if not m then return 'error', 'no macro named ' .. tostring(name) end
  local ok, res = xpcall(m.fn, handler, subs, selected or {}, active or 0)
  collectgarbage('collect')
  if ok then return 'ok', '' end
  if res == CANCEL then return 'cancelled', 'the script called aegisub.cancel()' end
  return 'error', tostring(res)
end

function api.run_filter(name, config)
  for _, f in raw_ipairs(filters) do
    if f.name == name then
      local ok, res = xpcall(f.fn, handler, subs, config or {})
      if ok then return 'ok', '' end
      if res == CANCEL then return 'cancelled', 'the script called aegisub.cancel()' end
      return 'error', tostring(res)
    end
  end
  return 'error', 'no filter named ' .. tostring(name)
end

api.subs = subs
api.include = include
return api
