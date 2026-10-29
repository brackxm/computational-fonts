#![cfg_attr(not(native_reference), no_std)]
type Operation = extern "C" fn(u32, u32) -> u32;
static mut BASE: u32 = 0;
static mut CHOSEN: Option<Operation> = None;

#[inline(never)]
extern "C" fn add(a: u32, b: u32) -> u32 { unsafe { a.wrapping_add(b).wrapping_add(BASE) } }
#[inline(never)]
extern "C" fn sub(a: u32, b: u32) -> u32 { unsafe { a.wrapping_sub(b).wrapping_add(BASE) } }
#[inline(never)]
extern "C" fn mix(a: u32, b: u32) -> u32 { unsafe { a ^ b ^ BASE } }
#[inline(never)]
extern "C" fn bump(a: u32, b: u32) -> u32 { unsafe { BASE = BASE.wrapping_add(a); BASE.wrapping_add(b) } }
static OPERATIONS: [Operation; 4] = [add, sub, mix, bump];

extern "C" fn initialize() { unsafe { BASE = 22; CHOSEN = Some(mix); } }
#[used]
#[cfg_attr(target_os = "macos", link_section = "__DATA,__mod_init_func")]
#[cfg_attr(not(target_os = "macos"), link_section = ".init_array")]
static INITIALIZE: extern "C" fn() = initialize;

#[no_mangle]
pub extern "C" fn rust_reset_reference() { initialize(); }
#[inline(never)]
fn apply(operation: Operation, a: u32, b: u32) -> u32 { operation(a, b) }
#[no_mangle]
pub extern "C" fn rust_dispatch(index: u32, a: u32, b: u32) -> u32 { apply(OPERATIONS[(index & 3) as usize], a, b) }
#[no_mangle]
pub extern "C" fn rust_constructor_dispatch(a: u32, b: u32) -> u32 {
    unsafe { match CHOSEN { Some(operation) => apply(operation, a, b), None => 0 } }
}
#[no_mangle]
pub extern "C" fn rust_dispatch_twice(index: u32, a: u32, b: u32) -> u32 {
    let operation = OPERATIONS[(index & 3) as usize];
    apply(operation, a, b) ^ apply(operation, b, a)
}
#[inline(never)]
unsafe fn copy_two(dest: *mut Operation, source: *const Operation) {
    core::ptr::copy_nonoverlapping(source, dest, 2);
}
#[no_mangle]
pub extern "C" fn rust_copied_dispatch(index: u32, a: u32, b: u32) -> u32 {
    let mut local = core::mem::MaybeUninit::<[Operation; 2]>::uninit();
    unsafe {
        let dest = local.as_mut_ptr().cast::<Operation>();
        copy_two(dest, OPERATIONS.as_ptr());
        apply(*dest.add((index & 1) as usize), a, b)
    }
}
