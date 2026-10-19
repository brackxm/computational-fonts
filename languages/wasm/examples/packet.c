// Copyright 2026 Michael Brackx
// SPDX-License-Identifier: Apache-2.0

// A tiny packet decoder: copy a payload into a local buffer, adjust its bytes,
// then compute a rolling checksum in a separate function. Unsigned arithmetic
// wraps at 32 bits. At most seven payload bytes keep both loops within bounds.
static const volatile unsigned char packet[8] = {7, 0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76};

__attribute__((noinline)) static unsigned checksum(volatile unsigned char *data, unsigned count) {
    unsigned value = 2166136261u;
    for (unsigned i = 0; i < count; ++i) value = (value ^ data[i]) * 16777619u;
    return value;
}
unsigned run(unsigned count, unsigned adjustment) {
    if (count > packet[0]) __builtin_trap();
    volatile unsigned char payload[32];
    for (unsigned i = 0; i < count; ++i) payload[i] = packet[i + 1] + adjustment;
    return checksum(payload, count);
}
