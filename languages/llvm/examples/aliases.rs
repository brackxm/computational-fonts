// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0
// At -O1 Rust emits !callees; -O2 also merges the duplicate into an alias.
#[no_mangle]
#[inline(never)]
pub extern "C" fn original(x: u32) -> u32 { x.wrapping_add(7) }

#[no_mangle]
#[inline(never)]
pub extern "C" fn duplicate(x: u32) -> u32 { x.wrapping_add(7) }

#[no_mangle]
pub extern "C" fn alias_dispatch(which: u32, x: u32) -> u32 {
    let callback: extern "C" fn(u32) -> u32 =
        if which & 1 == 0 { original } else { duplicate };
    callback(x)
}
