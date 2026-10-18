(module (func (export "run") (param $a i32) (param $b i32) (result i32) (i32.xor (i32.add (local.get $a) (local.get $b)) (i32.sub (local.get $a) (local.get $b)))))
