;; A runtime i64 store and byte lookup in a 64-byte window.
(module
  (memory 1)
  (data (i32.const 0)
    "\01\12\23\34\45\56\67\78\89\9a\ab\bc\cd\de\ef\f0"
    "\10\21\32\43\54\65\76\87\98\a9\ba\cb\dc\ed\fe\0f"
    "\20\31\42\53\64\75\86\97\a8\b9\ca\db\ec\fd\0e\1f"
    "\30\41\52\63\74\85\96\a7\b8\c9\da\eb\fc\0d\1e\2f")
  (func (export "run") (param $offset i32) (param $seed i64) (result i32 i64)
    i32.const 32 local.get $seed i64.store
    local.get $offset i32.load8_u
    local.get $seed i64.popcnt))
