(module
  (memory 1)
  (func (export "run") (param $seed i64) (param $destination i32)
    (param $source i32) (param $length i32) (param $byte i32) (result i64 i64)
    ;; Initialize eight bytes from the seed, then fill the next eight bytes.
    i32.const 0 local.get $seed i64.store
    i32.const 8 local.get $byte i32.const 8 memory.fill
    ;; Copy from a snapshot, including when source and destination overlap.
    local.get $destination local.get $source local.get $length memory.copy
    ;; Return the entire 16-byte window as two little-endian i64 values.
    i32.const 0 i64.load
    i32.const 8 i64.load))
