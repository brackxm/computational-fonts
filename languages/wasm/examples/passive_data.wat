(module
  (memory 1)
  ;; Passive data remains separate from linear memory until memory.init runs.
  (data $bytes "\01\02\03\04\05\06\07\08\09\0a\0b\0c\0d\0e\0f\10")
  (func (export "run") (param $destination i32) (param $source i32)
    (param $length i32) (param $drop_first i32) (result i64 i64)
    local.get $drop_first
    if data.drop $bytes end
    local.get $destination local.get $source local.get $length memory.init $bytes
    ;; Dropping the segment preserves bytes already copied into memory.
    data.drop $bytes
    i32.const 0 i64.load
    i32.const 8 i64.load))
