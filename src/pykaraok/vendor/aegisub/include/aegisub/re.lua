-- Compiled from aegisub/re.moon by moonc v0.7.0 (tools/build_vendor.py). Do not edit.
local error = error
local next = next
local select = select
local type = type
local bit = require('bit')
local ffi = require('ffi')
local ffi_util = require('aegisub.internal.ffi')
local check = require('aegisub.internal.argcheck')
ffi.cdef([[  typedef struct agi_re_flag {
    const char *name;
    int value;
  } agi_re_flag;
]])
local regex_flag = ffi.typeof('agi_re_flag')
local regex = require('aegisub.__re_impl')
local search
search = function(re, str, start)
  if not (start <= str:len()) then
    return 
  end
  local res = regex.search(re, str, str:len(), start)
  if not (res ~= nil) then
    return 
  end
  local first, last = res[0], res[1]
  ffi.gc(res, ffi.C.free)
  return first, last
end
local replace
replace = function(re, replacement, str, max_count)
  return ffi_util.string(regex.replace(re, replacement, str, str:len(), max_count))
end
local match
match = function(re, str, start)
  assert(start <= str:len())
  local m = regex.match(re, str, str:len(), start)
  if not (m ~= nil) then
    return 
  end
  return ffi.gc(m, regex.match_free)
end
local get_match
get_match = function(m, idx)
  local res = regex.get_match(m, idx)
  if not (res ~= nil) then
    return 
  end
  return res[0], res[1]
end
local err_buff = ffi.new('char *[1]')
local compile
compile = function(pattern, flags)
  err_buff[0] = nil
  local re = regex.compile(pattern, flags, err_buff)
  if err_buff[0] ~= nil then
    return ffi.string(err_buff[0])
  end
  return ffi.gc(re, regex.regex_free)
end
local select_first
select_first = function(n, a, ...)
  if n == 0 then
    return 
  end
  return a, select_first(n - 1, ...)
end
local process_flags
process_flags = function(...)
  local flags = 0
  for i = 1, select('#', ...) do
    local v = select(i, ...)
    if not ffi.istype(regex_flag, v) then
      error('Flags must follow all non-flag arguments', 3)
    end
    flags = bit.bor(flags, v.value)
  end
  return flags
end
local unpack_args
unpack_args = function(...)
  local flags_start = nil
  for i = 1, select('#', ...) do
    local v = select(i, ...)
    if ffi.istype(regex_flag, v) then
      flags_start = i
      break
    end
  end
  if not (flags_start) then
    return 0, ...
  end
  return process_flags(select(flags_start, ...)), select_first(flags_start - 1, ...)
end
local replace_match
replace_match = function(match, func, str, last, acc)
  if last < match.last then
    acc[#acc + 1] = str:sub(last, match.first - 1)
  end
  local repl = func(match.str, match.first, match.last)
  if type(repl) == 'string' then
    acc[#acc + 1] = repl
  else
    acc[#acc + 1] = match.str
  end
  return match.first, match.last + 1
end
local do_single_replace_fun
do_single_replace_fun = function(re, func, str, acc, pos)
  local matches = re:match(str, pos)
  if not (matches) then
    return pos
  end
  local start
  if #matches == 1 then
    start = 1
  else
    start = 2
  end
  local last = pos
  local first
  for i = start, #matches do
    first, last = replace_match(matches[i], func, str, last, acc)
  end
  if first == last then
    acc[#acc + 1] = str:sub(last, last)
    last = last + 1
  end
  return last, matches[1].first <= str:len()
end
local do_replace_fun
do_replace_fun = function(re, func, str, max)
  local acc = { }
  local pos = 1
  local i
  for i = 1, max do
    local more
    pos, more = do_single_replace_fun(re, func, str, acc, pos)
    if not (more) then
      max = i
      break
    end
  end
  return table.concat(acc, '') .. str:sub(pos)
end
local RegEx
do
  local _class_0
  local _base_0 = {
    _check_self = function(self)
      if not (self.__class == RegEx) then
        return error('re method called with invalid self. You probably used . when : is needed.', 3)
      end
    end,
    gsplit = check('RegEx string ?boolean ?number')(function(self, str, skip_empty, max_split)
      if not max_split or max_split <= 0 then
        max_split = str:len()
      end
      local start = 0
      local prev = 1
      local do_split
      do_split = function()
        if not str or str:len() == 0 then
          return 
        end
        local first, last
        if max_split > 0 then
          first, last = search(self._regex, str, start)
        end
        if not first or first > str:len() then
          local ret = str:sub(prev, str:len())
          str = nil
          if skip_empty and ret:len() == 0 then
            return nil
          else
            return ret
          end
        end
        local ret = str:sub(prev, first - 1)
        prev = last + 1
        if start >= last then
          start = start + 1
        else
          start = last
        end
        if skip_empty and ret:len() == 0 then
          return do_split()
        else
          max_split = max_split - 1
          return ret
        end
      end
      return do_split
    end),
    split = check('RegEx string ?boolean ?number')(function(self, str, skip_empty, max_split)
      local _accum_0 = { }
      local _len_0 = 1
      for v in self:gsplit(str, skip_empty, max_split) do
        _accum_0[_len_0] = v
        _len_0 = _len_0 + 1
      end
      return _accum_0
    end),
    gfind = check('RegEx string')(function(self, str)
      local start = 0
      return function()
        local first, last = search(self._regex, str, start)
        if not (first) then
          return 
        end
        if last > start then
          start = last
        else
          start = start + 1
        end
        return str:sub(first, last), first, last
      end
    end),
    find = check('RegEx string')(function(self, str)
      local ret
      do
        local _accum_0 = { }
        local _len_0 = 1
        for s, f, l in self:gfind(str) do
          _accum_0[_len_0] = {
            str = s,
            first = f,
            last = l
          }
          _len_0 = _len_0 + 1
        end
        ret = _accum_0
      end
      return next(ret) and ret
    end),
    sub = check('RegEx string string|function ?number')(function(self, str, repl, max_count)
      if not max_count or max_count == 0 then
        max_count = str:len() + 1
      end
      if type(repl) == 'function' then
        return do_replace_fun(self, repl, str, max_count)
      elseif type(repl) == 'string' then
        return replace(self._regex, repl, str, max_count)
      end
    end),
    gmatch = check('RegEx string ?number')(function(self, str, start)
      if start then
        start = start - 1
      else
        start = 0
      end
      local m = match(self._regex, str, start)
      local i = 0
      return function()
        if not (m) then
          return 
        end
        local first, last = get_match(m, i)
        if not (first) then
          return 
        end
        i = i + 1
        return {
          str = str:sub(first + start, last + start),
          first = first + start,
          last = last + start
        }
      end
    end),
    match = check('RegEx string ?number')(function(self, str, start)
      local ret
      do
        local _accum_0 = { }
        local _len_0 = 1
        for v in self:gmatch(str, start) do
          _accum_0[_len_0] = v
          _len_0 = _len_0 + 1
        end
        ret = _accum_0
      end
      if next(ret) == nil then
        return nil
      end
      return ret
    end)
  }
  _base_0.__index = _base_0
  _class_0 = setmetatable({
    __init = function(self, _regex, _level)
      self._regex, self._level = _regex, _level
    end,
    __base = _base_0,
    __name = "RegEx"
  }, {
    __index = _base_0,
    __call = function(cls, ...)
      local _self_0 = setmetatable({}, _base_0)
      cls.__init(_self_0, ...)
      return _self_0
    end
  })
  _base_0.__class = _class_0
  RegEx = _class_0
end
local real_compile
real_compile = function(pattern, level, flags, stored_level)
  if pattern == '' then
    error('Regular expression must not be empty', level + 1)
  end
  local re = compile(pattern, flags)
  if type(re) == 'string' then
    error(regex, level + 1)
  end
  return RegEx(re, stored_level or level + 1)
end
local invoke
invoke = function(str, pattern, fn, flags, ...)
  local compiled_regex = real_compile(pattern, 3, flags)
  return compiled_regex[fn](compiled_regex, str, ...)
end
local gen_wrapper
gen_wrapper = function(impl_name)
  return check('string string ...')(function(str, pattern, ...)
    return invoke(str, pattern, impl_name, unpack_args(...))
  end)
end
do
  local re = {
    compile = check('string ...')(function(pattern, ...)
      return real_compile(pattern, 2, process_flags(...), 2)
    end),
    split = gen_wrapper('split'),
    gsplit = gen_wrapper('gsplit'),
    find = gen_wrapper('find'),
    gfind = gen_wrapper('gfind'),
    match = gen_wrapper('match'),
    gmatch = gen_wrapper('gmatch'),
    sub = gen_wrapper('sub')
  }
  local i = 0
  local flags = regex.get_flags()
  while flags[i].name ~= nil do
    re[ffi.string(flags[i].name)] = flags[i]
    i = i + 1
  end
  return re
end
