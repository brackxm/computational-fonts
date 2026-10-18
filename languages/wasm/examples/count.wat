(module
  (func (export "run") (param $x i64) (result i64)
    local.get $x
    i64.popcnt
    i64.const 3
    i64.add))
