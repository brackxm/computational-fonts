;; Three expensive runtime operations in one font: two divisions, then multiply.
;; The product wraps modulo 2^64; either zero divisor traps.
(module
  (func (export "run") (param $a i64) (param $b i64)
                      (param $c i64) (param $d i64) (result i64)
    local.get $a local.get $b i64.div_u
    local.get $c local.get $d i64.div_u
    i64.mul))
