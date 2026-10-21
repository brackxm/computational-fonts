(module
  (type $binary (func (param i64 i64) (result i64 i32)))
  (table $library 3 (ref $binary) (ref.func $add))
  (table $dispatch 1 2 (ref $binary) (ref.func $add))
  (elem (table $library) (i32.const 1) (ref $binary)
    (ref.func $xor) (ref.func $divide))
  (func $add (type $binary)
    local.get 0 local.get 1 i64.add table.size $dispatch)
  (func $xor (type $binary)
    local.get 0 local.get 1 i64.xor table.size $dispatch)
  (func $divide (type $binary)
    local.get 0 local.get 1 i64.div_u table.size $dispatch)
  (func (export "run") (param i64 i64 i32) (result i64 i32)
    local.get 2 table.get $library i32.const 1 table.grow $dispatch drop
    local.get 0 local.get 1 i32.const 1 table.get $dispatch
    return_call_ref $binary))
