#![cfg_attr(not(native_reference), no_std)]

#[no_mangle]
pub extern "C" fn rust_saturating_add(a: u32, b: u32) -> u32 { a.saturating_add(b) }

#[no_mangle]
pub extern "C" fn rust_saturating_sub(a: i32, b: i32) -> i32 { a.saturating_sub(b) }

static mut COUNTER: u32 = 5;
#[inline(never)]
unsafe fn advance(value: u32) -> u32 {
    COUNTER = COUNTER.wrapping_add(value);
    COUNTER
}

#[no_mangle]
pub unsafe extern "C" fn rust_global_calls(a: u32, b: u32) -> u32 {
    COUNTER = 5;
    advance(a) ^ advance(b)
}

static mut FIRST: u32 = 3;
static mut SECOND: u32 = 11;
static mut SLOTS: [*mut u32; 2] = [core::ptr::addr_of_mut!(FIRST), core::ptr::addr_of_mut!(SECOND)];

#[no_mangle]
pub unsafe extern "C" fn rust_pointer_table(index: u32, value: u32) -> u32 {
    FIRST = 3; SECOND = 11;
    SLOTS[(index & 1) as usize] = core::ptr::addr_of_mut!(FIRST);
    SLOTS[(index.wrapping_add(1) & 1) as usize] = core::ptr::addr_of_mut!(SECOND);
    *SLOTS[(index & 1) as usize] = value;
    (*SLOTS[(index.wrapping_add(1) & 1) as usize]).wrapping_add(*SLOTS[(index & 1) as usize])
}

#[inline(never)]
unsafe fn copy_pointers(dest: *mut *mut u32, source: *const *mut u32) {
    core::ptr::copy_nonoverlapping(source, dest, 2);
}

#[no_mangle]
pub unsafe extern "C" fn rust_pointer_copy(index: u32, value: u32) -> u32 {
    let mut values = [value, value.wrapping_add(1)];
    let source = [values.as_mut_ptr(), values.as_mut_ptr().add(1)];
    let mut dest = [core::ptr::null_mut(); 2];
    copy_pointers(dest.as_mut_ptr(), source.as_ptr());
    *dest[(index & 1) as usize]
}
