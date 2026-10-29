#![cfg_attr(not(native_reference), no_std)]

static WEIGHTS: [u32; 4] = [3, 5, 7, 11];

#[no_mangle]
pub extern "C" fn rust_lookup(index: u32) -> u32 {
    WEIGHTS[(index & 3) as usize]
}

#[no_mangle]
pub extern "C" fn rust_checked_add(a: u32, b: u32) -> u64 {
    let (result, overflow) = a.overflowing_add(b);
    result as u64 | ((overflow as u64) << 32)
}

#[no_mangle]
pub extern "C" fn rust_checked_multiply(a: i32, b: i32) -> u64 {
    let (result, overflow) = a.overflowing_mul(b);
    result as u32 as u64 | ((overflow as u64) << 32)
}
