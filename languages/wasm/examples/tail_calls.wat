;; Divide once, then carry quotient and remainder through tail-recursive rounds.
(module
  (table $unused 0 funcref)
  (table $steps 1 funcref)
  (elem (table $steps) (i32.const 0) $advance)
  (func $advance (param i64 i64 i32) (result i64 i64)
    local.get 2 if (result i64 i64)
      local.get 0 local.get 1 i64.add
      local.get 1 i64.const 1 i64.add
      local.get 2 i32.const 1 i32.sub
      i32.const 0 return_call_indirect $steps (param i64 i64 i32) (result i64 i64)
    else local.get 0 local.get 1 end)
  (func (export "run") (param i64 i64 i32) (result i64 i64)
    local.get 0 local.get 1 i64.div_u
    local.get 0 local.get 1 i64.rem_u
    local.get 2 return_call $advance))
