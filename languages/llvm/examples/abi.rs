// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
#[repr(C)]
pub struct Triple { pub a: u64, pub b: u64, pub c: u64 }
#[no_mangle]
#[inline(never)]
pub extern "C" fn rust_triple(x: u64, y: u64) -> Triple {
    Triple {a: x.wrapping_add(y), b: x ^ y, c: x.wrapping_sub(y)}
}
#[no_mangle]
#[inline(never)]
pub extern "C" fn rust_reverse_triple(x: u64, y: u64) -> Triple { rust_triple(y, x) }
#[no_mangle]
#[inline(never)]
pub extern "C" fn rust_use_triple(mut value: Triple) -> u64 {
    value.a = value.a.wrapping_add(7);
    value.a ^ value.b ^ value.c
}
#[no_mangle]
pub extern "C" fn rust_call_triple(x: u64, y: u64) -> u64 { rust_use_triple(rust_triple(x, y)) }
type Maker = extern "C" fn(u64, u64) -> Triple;
static MAKERS: [Maker; 2] = [rust_triple, rust_reverse_triple];
#[no_mangle]
pub extern "C" fn rust_choose_triple(which: u32, x: u64, y: u64) -> Triple {
    MAKERS[(which & 1) as usize](x, y)
}
