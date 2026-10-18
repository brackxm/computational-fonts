(module
  (type $binary (func (param i64 i64) (result i64)))
  (table $operations 6 funcref)
  ;; Slots 0–3 select arithmetic; slot 4 has the wrong type; slot 5 is null.
  (elem (i32.const 0) $add $subtract $multiply $divide $wrong_type)
  (func $add (type $binary) local.get 0 local.get 1 i64.add)
  (func $subtract (type $binary) local.get 0 local.get 1 i64.sub)
  (func $multiply (type $binary) local.get 0 local.get 1 i64.mul)
  (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
  (func $wrong_type (param i32) (result i32) local.get 0)
  (func (export "run") (param $a i64) (param $b i64) (param $operation i32)
    (result i64 i64) (local $result i64)
    local.get $a local.get $b local.get $operation call_indirect $operations (type $binary)
    ;; The selected function's result feeds more Wasm instructions in this font.
    local.tee $result local.get $result i64.popcnt))
