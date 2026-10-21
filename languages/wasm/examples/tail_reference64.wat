(module
  (type $step (func (param i32 i64 i64) (result i64 i64)))
  (elem declare func $step)
  (func $step (type $step)
    local.get 0
    if (result i64 i64)
      local.get 0 i32.const 1 i32.sub
      local.get 1 local.get 2 i64.add
      local.get 2 i64.const 1 i64.add
      ref.func $step return_call_ref $step
    else local.get 1 local.get 2 end)
  (func (export "run") (param $dividend i64) (param $divisor i64)
    (param $rounds i32) (result i64 i64)
    local.get $rounds
    local.get $dividend local.get $divisor i64.div_u
    local.get $dividend local.get $divisor i64.rem_u
    ref.func $step return_call_ref $step))
