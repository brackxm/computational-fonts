;; Copy one callback from a library into a separate, growing dispatch table.
(module
  (type $binary (func (param i64 i64) (result i64)))
  (table $library 3 3 funcref)
  (table $dispatch 1 2 funcref)
  (elem (i32.const 0) $add $xor $divide)
  (func $add (type $binary) local.get 0 local.get 1 i64.add)
  (func $xor (type $binary) local.get 0 local.get 1 i64.xor)
  (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
  (func (export "run") (param i64 i64 i32) (result i64 i32 i32)
    i32.const 0 local.get 2 i32.const 1 table.copy $dispatch $library
    i32.const 0 table.get $dispatch i32.const 1 table.grow $dispatch drop
    local.get 0 local.get 1 i32.const 1 call_indirect $dispatch (type $binary)
    table.size $library table.size $dispatch))
