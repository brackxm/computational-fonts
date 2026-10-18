(module
  (func (export "run") (param $dividend i64) (param $divisor i64) (result i64 i64)
    local.get $dividend
    local.get $divisor
    i64.div_u
    local.get $dividend
    local.get $divisor
    i64.rem_u))
