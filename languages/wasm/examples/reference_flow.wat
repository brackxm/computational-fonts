;; Nullable references move through a typed select, helper, block and global.
(module
  (type $binary (func (param i64 i64) (result i64)))
  (table 3 funcref)
  (elem (i32.const 0) funcref (ref.func $add) (ref.null func) (ref.func $divide))
  (global $chosen (mut funcref) (ref.null func))
  (func $add (type $binary) local.get 0 local.get 1 i64.add)
  (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
  (func $choose (param funcref funcref i32) (result funcref)
    local.get 0 local.get 1 local.get 2 select (result funcref))
  (func (export "run") (param $a i64) (param $b i64) (param $slot i32) (param $use_slot i32)
    (result i64 i64) (local $answer i64)
    local.get $slot table.get ref.func $add local.get $use_slot call $choose
    block (param funcref) (result funcref) end global.set $chosen
    i32.const 1 global.get $chosen table.set
    local.get $a local.get $b i32.const 1 call_indirect (type $binary)
    local.tee $answer local.get $answer i64.popcnt))
