(module
  (func (export "run") (param $value i64) (result i64 i64)
    ;; Both operations reuse the same bounded-remainder divider circuit.
    local.get $value
    i64.const 10
    i64.div_u
    local.get $value
    i64.const 10
    i64.rem_u))
