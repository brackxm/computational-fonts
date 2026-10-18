(module
  (type $carry (func (param i32 i64 i64) (result i64 i64)))
  (func (export "run") (param $a i64) (param $b i64) (param $rounds i32)
    (result i64 i64) (local $n i32) (local $checksum i64) (local $remainder i64)
    ;; A multi-value block produces the full-width quotient and remainder.
    block (result i64 i64)
      local.get $a local.get $b i64.div_u
      local.get $a local.get $b i64.rem_u
    end
    local.set $remainder local.set $checksum
    local.get $rounds local.get $checksum local.get $remainder
    ;; Each backedge carries (rounds left, checksum, remainder) on the stack.
    loop $again (type $carry)
      local.set $remainder local.set $checksum local.tee $n i32.eqz
      if (result i64 i64)
        local.get $checksum local.get $remainder
      else
        local.get $n i32.const 1 i32.sub
        local.get $checksum local.get $remainder i64.add
        local.get $remainder i64.const 1 i64.add
        br $again
      end
    end))
