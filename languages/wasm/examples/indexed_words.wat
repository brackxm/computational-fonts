;; Fill a 64-byte runtime buffer, read two unaligned words, then compose them.
(module (memory 1)
  (func (export "run") (param i64 i64 i32 i32 i64) (result i64 i64) (local i64 i64)
    i32.const 0 local.get 0 i64.store
    i32.const 8 local.get 1 i64.store
    i32.const 16 local.get 0 i64.const 8 i64.rotl i64.store
    i32.const 24 local.get 1 i64.const -1 i64.xor i64.store
    i32.const 32 local.get 0 local.get 1 i64.add i64.store
    i32.const 40 local.get 0 local.get 1 i64.xor i64.store
    i32.const 48 local.get 1 i64.const 32 i64.rotl i64.store
    i32.const 56 local.get 0 local.get 1 i64.sub i64.store
    local.get 2 i64.load local.set 5
    local.get 3 i64.load local.set 6
    local.get 5 local.get 6 i64.add
    local.get 5 local.get 6 i64.xor local.get 4 i64.div_u))
