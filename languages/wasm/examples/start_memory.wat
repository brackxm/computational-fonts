(module
  (memory 0 1)
  (data $seed "\01\02\03\04\05\06\07\08\09\0a\0b\0c\0d\0e\0f\10")
  (global $starts (mut i32) (i32.const 0))
  ;; Instantiation initializes the memory before run receives its arguments.
  (start $initialize)
  (func $initialize
    i32.const 1 memory.grow drop
    i32.const 0 i32.const 0 i32.const 16 memory.init $seed
    data.drop $seed
    global.get $starts i32.const 1 i32.add global.set $starts)
  (func (export "run") (param $address i32) (param $value i32)
    (result i64 i64 i32 i32)
    local.get $address local.get $value i32.store8
    i32.const 0 i64.load i32.const 8 i64.load
    memory.size global.get $starts))
