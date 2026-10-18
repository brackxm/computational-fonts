;; Three independent dynamic full-width dividers, combined with wrapping adds.
;; Any zero divisor traps.
(module
  (func (export "run") (param i64 i64 i64 i64 i64 i64) (result i64)
    local.get 0 local.get 1 i64.div_u
    local.get 2 local.get 3 i64.div_u i64.add
    local.get 4 local.get 5 i64.div_u i64.add))
