(module (func (export "run") (param $n i32) (result i32) (local $sum i32)
 block $done loop $again local.get $n i32.eqz br_if $done
 local.get $sum local.get $n i32.add local.set $sum
 local.get $n i32.const 1 i32.sub local.set $n br $again end end local.get $sum))
