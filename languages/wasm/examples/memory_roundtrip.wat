(module (memory 1) (func (export "run") (param $addr i32) (param $value i32) (result i32) local.get $addr local.get $value i32.store local.get $addr i32.load))
