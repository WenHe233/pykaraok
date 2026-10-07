-- Compiled from aegisub/unicode.moon by moonc v0.7.0 (tools/build_vendor.py). Do not edit.
local impl = require('aegisub.__unicode_impl')
local check = require('aegisub.internal.argcheck')
local ffi = require('ffi')
local ffi_util = require('aegisub.internal.ffi')
local err_buff = ffi.new('char *[1]')
local conv_func
conv_func = function(f)
  return check('string')(function(str)
    err_buff[0] = nil
    local result = f(str, err_buff)
    local errmsg = ffi_util.string(err_buff[0])
    if errmsg then
      error(errmsg, 2)
    end
    return ffi_util.string(result)
  end)
end
local unicode
unicode = {
  charwidth = check('string ?number')(function(s, i)
    local b = s:byte(i or 1)
    if not b then
      return 1
    elseif b < 128 then
      return 1
    elseif b < 224 then
      return 2
    elseif b < 240 then
      return 3
    else
      return 4
    end
  end),
  chars = check('string')(function(s)
    local curchar, i = 0, 1
    return function()
      if i > s:len() then
        return 
      end
      local j = i
      curchar = curchar + 1
      i = i + unicode.charwidth(s, i)
      return s:sub(j, i - 1), curchar
    end
  end),
  len = check('string')(function(s)
    local n = 0
    for c in unicode.chars(s) do
      n = n + 1
    end
    return n
  end),
  codepoint = check('string')(function(s)
    local b = s:byte(1)
    if b < 128 then
      return b
    end
    local res, w
    if b < 224 then
      res = b - 192
      w = 2
    elseif b < 240 then
      res = b - 224
      w = 3
    else
      res = b - 240
      w = 4
    end
    for i = 2, w do
      res = res * 64 + s:byte(i) - 128
    end
    return res
  end),
  to_upper_case = conv_func(impl.to_upper_case),
  to_lower_case = conv_func(impl.to_lower_case),
  to_fold_case = conv_func(impl.to_fold_case)
}
return unicode
