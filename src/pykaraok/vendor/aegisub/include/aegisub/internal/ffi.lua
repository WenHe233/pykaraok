-- Compiled from aegisub/internal/ffi.moon by moonc v0.7.0 (tools/build_vendor.py). Do not edit.
local ffi = require('ffi')
ffi.cdef([[  void free(void *ptr);
]])
local char_ptr = ffi.typeof('char *')
local string
string = function(cdata)
  if cdata == nil then
    return nil
  end
  local str = ffi.string(cdata)
  if ffi.typeof(cdata) == char_ptr then
    ffi.C.free(cdata)
  end
  return str
end
local err_buff = ffi.new('char *[1]')
local err_arg_to_multiple_return
err_arg_to_multiple_return = function(f)
  return function(arg)
    err_buff[0] = nil
    local result
    if arg ~= nil then
      result = f(arg, err_buff)
    else
      result = f(err_buff)
    end
    local errmsg = string(err_buff[0])
    if errmsg then
      return nil, errmsg
    end
    return result
  end
end
return {
  string = string,
  err_arg_to_multiple_return = err_arg_to_multiple_return
}
