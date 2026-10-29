#![no_std]

#[no_mangle]
pub extern "C" fn rust_max(a: i32, b: i32) -> i32 {
    if a > b { a } else { b }
}

#[no_mangle]
pub extern "C" fn rust_mix(a: u64, b: u64) -> u64 {
    a.wrapping_add(b).rotate_left(7) ^ b
}
