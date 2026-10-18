;; Two independent full-width signed dividers compose with wrapping addition.
;; All four operands are supplied at invocation time.
(module
  (func (export "run") (param $a i64) (param $b i64)
                      (param $c i64) (param $d i64) (result i64)
    local.get $a local.get $b i64.div_s
    local.get $c local.get $d i64.div_s
    i64.add))
