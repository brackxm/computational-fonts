; Copyright 2026 Michael Brackx
; SPDX-License-Identifier: Apache-2.0
; Strong aliases share data/code identity, including startup callbacks.
@state = global i32 0
@state_alias = internal alias i32, ptr @state
@add_alias = alias i32 (i32), ptr @add
@sub_alias = alias i32 (i32), ptr @sub
@init_alias = alias void (), ptr @init
@callbacks = constant [2 x ptr] [ptr @add_alias, ptr @sub_alias]
@llvm.global_ctors = appending global [1 x {i32, ptr, ptr}] [
  {i32, ptr, ptr} {i32 101, ptr @init_alias, ptr @state_alias}]

define void @init() {
  store i32 13, ptr @state_alias
  ret void
}

define i32 @add(i32 %x) {
  %base = load i32, ptr @state_alias
  %result = add i32 %x, %base
  ret i32 %result
}

define i32 @sub(i32 %x) {
  %base = load i32, ptr @state
  %result = sub i32 %x, %base
  ret i32 %result
}

define i32 @alias_table(i1 %which, i32 %x) {
  %index = zext i1 %which to i64
  %slot = getelementptr [2 x ptr], ptr @callbacks, i64 0, i64 %index
  %callback = load ptr, ptr %slot
  %result = call i32 %callback(i32 %x), !callees !0
  ret i32 %result
}

!0 = !{ptr @add_alias, ptr @sub_alias}
