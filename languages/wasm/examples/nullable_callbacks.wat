(module
  (table $callbacks 3 funcref)
  (table $dispatch 1 funcref)
  (elem (table $callbacks) (i32.const 0) $add)
  (elem (table $callbacks) (i32.const 2) $divide)
  (func $add (param i64 i64) (result i64)
    local.get 0 local.get 1 i64.add)
  (func $divide (param i64 i64) (result i64)
    local.get 0 local.get 1 i64.div_u)
  (func $choose (param $candidate funcref) (param $strict i32) (result funcref)
    local.get $strict
    if (result funcref)
      local.get $candidate ref.as_non_null
    else
      block $found (result funcref)
        local.get $candidate br_on_non_null $found
        ref.func $add
      end
    end)
  (func (export "run") (param $a i64) (param $b i64)
    (param $slot i32) (param $strict i32) (result i64)
    ;; Keep the operands below the callback-selection work on the stack.
    local.get $a local.get $b
    i32.const 0
    local.get $slot table.get $callbacks local.get $strict call $choose
    table.set $dispatch
    i32.const 0 call_indirect $dispatch (param i64 i64) (result i64)))
