// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

// The 512-byte frame keeps scratch at 65024, apart from globals at 65536.
// Only its first sixteen bytes are accessed. Passing it to a separate function
// preserves the frame and real pointer-based loads in the compiled module.
static volatile unsigned values[4] = {3, 5, 7, 11};
__attribute__((noinline)) static unsigned sum(volatile unsigned *items, unsigned count) {
    unsigned result = 0;
    for (unsigned i = 0; i < count; ++i) result += items[i];
    return result;
}
unsigned run(unsigned count, unsigned bias) {
    if (count > 4) __builtin_trap();
    volatile unsigned scratch[128];
    for (unsigned i = 0; i < count; ++i) scratch[i] = values[i] + bias;
    return sum(scratch, count);
}
