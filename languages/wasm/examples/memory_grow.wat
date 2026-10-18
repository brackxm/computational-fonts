(module
  ;; Growth changes the logical page count; memory starts with one 64-KiB page.
  (memory 1 3)
  (func (export "run") (param $first i32) (param $second i32)
    (param $value i64) (result i32 i32 i32 i64)
    ;; Existing bytes survive successful and failed growth attempts.
    i32.const 0 local.get $value i64.store
    local.get $first memory.grow
    local.get $second memory.grow
    memory.size
    i32.const 0 i64.load))
