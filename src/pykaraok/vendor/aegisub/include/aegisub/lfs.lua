-- Compiled from aegisub/lfs.moon by moonc v0.7.0 (tools/build_vendor.py). Do not edit.
local impl = require('aegisub.__lfs_impl')
local check = require('aegisub.internal.argcheck')
local ffi = require('ffi')
local ffi_util = require('aegisub.internal.ffi')
for k, v in pairs(impl) do
  impl[k] = ffi_util.err_arg_to_multiple_return(v)
end
local string_ret
string_ret = function(f)
  return function(...)
    local res, err = f(...)
    return ffi_util.string(res), err
  end
end
local number_ret
number_ret = function(f)
  return function(...)
    local res, err = f(...)
    return tonumber(res), err
  end
end
local attributes = check('string ?string')(function(path, field)
  local _exp_0 = field
  if 'mode' == _exp_0 then
    local res, err = impl.get_mode(path)
    return ffi_util.string(res), err
  elseif 'modification' == _exp_0 then
    local res, err = impl.get_mtime(path)
    return tonumber(res), err
  elseif 'size' == _exp_0 then
    local res, err = impl.get_size(path)
    return tonumber(res), err
  else
    local mode, err = impl.get_mode(path)
    if err or mode == nil then
      return nil, err
    end
    local mod
    mod, err = impl.get_mtime(path)
    if err then
      return nil, err
    end
    local size
    size, err = impl.get_size(path)
    if err then
      return nil, err
    end
    return {
      mode = ffi_util.string(mode),
      modification = tonumber(mod),
      size = tonumber(size)
    }
  end
end)
local dir_iter
do
  local _class_0
  local _base_0 = {
    close = function(self)
      return impl.dir_close(self.iter)
    end,
    next = function(self)
      local str, err = impl.dir_next(self.iter)
      if err then
        error(err, 2)
      end
      return ffi_util.string(str)
    end
  }
  _base_0.__index = _base_0
  _class_0 = setmetatable({
    __init = function(self, iter)
      self.iter = ffi.gc(iter, function()
        return impl.dir_free(iter)
      end)
    end,
    __base = _base_0,
    __name = "dir_iter"
  }, {
    __index = _base_0,
    __call = function(cls, ...)
      local _self_0 = setmetatable({}, _base_0)
      cls.__init(_self_0, ...)
      return _self_0
    end
  })
  _base_0.__class = _class_0
  dir_iter = _class_0
end
local dir = check('string')(function(path)
  local obj, err = impl.dir_new(path)
  if err then
    error(2, err)
  end
  local iter = dir_iter(obj)
  return iter.next, iter
end)
return {
  attributes = attributes,
  chdir = check('string')(number_ret(impl.chdir)),
  currentdir = check('')(string_ret(impl.currentdir)),
  dir = dir,
  mkdir = check('string')(number_ret(impl.mkdir)),
  rmdir = check('string')(number_ret(impl.rmdir)),
  touch = check('string')(number_ret(impl.touch))
}
