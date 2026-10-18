(module (func (export "run") (param $a i64) (param $b i64) (result i64) (i64.xor (i64.add (local.get $a) (local.get $b)) (i64.sub (local.get $a) (local.get $b)))))
