;; Populate a passive function segment, mutate a slot and grow the table.
(module
  (type $binary (func (param i64 i64) (result i64)))
  (table $ops 2 3 funcref)
  (elem $functions func $add $divide)
  (func $add (type $binary) local.get 0 local.get 1 i64.add)
  (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
  (func (export "run") (param $a i64) (param $b i64) (param $operation i32)
    (result i64 i64 i32) (local $chosen funcref) (local $answer i64)
    i32.const 0 i32.const 0 i32.const 2 table.init $ops $functions
    elem.drop $functions
    local.get $operation table.get $ops local.set $chosen
    i32.const 0 local.get $chosen table.set $ops
    local.get $chosen i32.const 1 table.grow $ops drop
    local.get $a local.get $b i32.const 2 call_indirect $ops (type $binary)
    local.tee $answer local.get $answer i64.popcnt table.size $ops))
