// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

// Volatile keeps the array accesses in the compiled Wasm. The linker places
// these sixteen bytes after its 64-KiB stack, at address 65536.
static volatile unsigned values[4] = {3, 5, 7, 11};

unsigned run(unsigned count, unsigned bias) {
    if (count > 4) __builtin_trap();
    unsigned sum = 0;
    for (unsigned i = 0; i < count; ++i) {
        values[i] += bias;
        sum += values[i];
    }
    return sum;
}
