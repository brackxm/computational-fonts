;; Four runtime operations: two signed divisions, multiplication, and popcount.
;; Return the wrapping product and its number of set bits.
(module
  (func (export "run") (param $a i64) (param $b i64)
                      (param $c i64) (param $d i64) (result i64 i64)
    (local $product i64)
    local.get $a local.get $b i64.div_s
    local.get $c local.get $d i64.div_s
    i64.mul local.tee $product
    local.get $product i64.popcnt))
