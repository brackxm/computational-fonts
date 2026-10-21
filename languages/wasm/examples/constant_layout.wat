(module
  (memory 1)
  (table $operations 2 funcref (ref.func $add_seed))
  (global $base i32 (i32.mul (i32.const 2) (i32.const 4)))
  (global $divisor i64 (i64.sub (i64.const 10) (i64.const 3)))
  (global $divide funcref (ref.func $divide_seed))
  ;; Place the seed at byte 8 and replace table slot 1 with division.
  (data (offset (global.get $base) (i32.const 0) i32.add)
    "\01\02\03\04\05\06\07\08")
  (elem (table $operations)
    (i32.sub (global.get $base) (i32.const 7)) funcref
    (item (global.get $divide)))
  (func $add_seed (param i64) (result i64)
    local.get 0 global.get $base i64.load i64.add)
  (func $divide_seed (param i64) (result i64)
    local.get 0 global.get $base i64.load i64.xor
    global.get $divisor i64.div_u)
  (func (export "run") (param $value i64) (param $operation i32) (result i64)
    local.get $value local.get $operation
    call_indirect $operations (param i64) (result i64)))
