-- pykaraok: FFI-shaped stand-in for Aegisub's C++ regex module (aegisub.__re_impl).
-- re.moon calls these functions with the argument lists of libaegisub/lua/modules/re.cpp
-- and frees the results with ffi.gc / ffi.C.free, so results are real cdata.

local R = ...
local ffi = require 'ffi'

pcall(ffi.cdef, [[
  typedef struct pyk_re { int id; } pyk_re;
  typedef struct pyk_match { int id; int range[2]; } pyk_match;
  void *malloc(size_t size);
]])
-- re.moon declares agi_re_flag before requiring this module; declare it too in case it did not
pcall(ffi.cdef, [[ typedef struct agi_re_flag { const char *name; int value; } agi_re_flag; ]])

local function cstring(s)
  local p = ffi.cast('char *', ffi.C.malloc(#s + 1))
  ffi.copy(p, s, #s)
  p[#s] = 0
  return p
end

local impl = {}

function impl.compile(pattern, flags, err)
  local ok, res = R.compile(pattern, tonumber(flags) or 0)
  if not ok then
    if err ~= nil then err[0] = cstring(res) end
    return nil
  end
  return ffi.new('pyk_re', res)
end

function impl.regex_free(re) R.free(re.id) end

function impl.search(re, str, len, start, err)
  local a, b = R.search(re.id, str, tonumber(start))
  if a == nil then return nil end
  local p = ffi.cast('int *', ffi.C.malloc(2 * ffi.sizeof('int')))
  p[0], p[1] = a, b
  return p
end

function impl.match(re, str, len, start, err)
  local id = R.match(re.id, str, tonumber(start))
  if id == nil then return nil end
  return ffi.new('pyk_match', id)
end

function impl.get_match(m, idx)
  local a, b = R.get_match(m.id, tonumber(idx))
  if a == nil then return nil end
  m.range[0], m.range[1] = a, b
  return m.range
end

function impl.match_free(m) R.match_free(m.id) end

function impl.replace(re, replacement, str, len, max_count, err)
  return cstring(R.replace(re.id, replacement, str, tonumber(max_count)))
end

local flag_names = {}
local flag_array
function impl.get_flags()
  if not flag_array then
    local n = #R.flags
    flag_array = ffi.new('agi_re_flag[?]', n + 1)
    for i = 1, n do
      local f = R.flags[i]
      flag_names[i] = f.name
      flag_array[i - 1].name = flag_names[i]
      flag_array[i - 1].value = f.value
    end
    flag_array[n].name = nil
  end
  return flag_array
end

return impl
