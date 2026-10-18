(module
  (func (export "run") (param $value i64) (result i64 i64)
    ;; Division truncates toward zero; remainder keeps the dividend's sign.
    local.get $value
    i64.const -7
    i64.div_s
    local.get $value
    i64.const -7
    i64.rem_s))
