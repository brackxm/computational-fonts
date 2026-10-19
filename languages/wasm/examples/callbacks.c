// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

// Volatile function pointers keep runtime table dispatch in the Wasm binary.
// The exported ABI uses integers; apply receives a real C function pointer.
typedef unsigned long long u64;
typedef u64 (*operation)(u64, u64);
static u64 add(u64 a, u64 b) { return a + b; }
static u64 mix(u64 a, u64 b) { return a ^ b; }
static u64 divide(u64 a, u64 b) { return a / b; }
static operation volatile operations[3] = {add, mix, divide};

__attribute__((noinline)) static u64 apply(operation fn, u64 a, u64 b) {
    return fn(a, b);
}
u64 run(u64 a, u64 b, unsigned selected) {
    if (selected >= 3) __builtin_trap();
    return apply(operations[selected], a, b);
}
