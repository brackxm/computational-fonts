(module
  (type $binary (func (param i64 i64) (result i64)))
  (global $add (ref $binary) (ref.func $add))
  (global $xor (ref $binary) (ref.func $xor))
  (global $divide (ref $binary) (ref.func $divide))
  (func $add (type $binary) local.get 0 local.get 1 i64.add)
  (func $xor (type $binary) local.get 0 local.get 1 i64.xor)
  (func $divide (type $binary) local.get 0 local.get 1 i64.div_u)
  (func $choose (param $operation i32) (result (ref null $binary))
    local.get $operation i32.const 3 i32.gt_u if unreachable end
    local.get $operation i32.const 3 i32.eq
    if (result (ref null $binary))
      ref.null $binary
    else
      local.get $operation i32.eqz
      if (result (ref $binary)) global.get $add
      else
        local.get $operation i32.const 1 i32.eq
        if (result (ref $binary)) global.get $xor else global.get $divide end
      end
    end)
  (func (export "run") (param i64 i64 i32) (result i64)
    local.get 0 local.get 1 local.get 2 call $choose call_ref $binary))
