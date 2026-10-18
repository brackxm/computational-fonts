/* Integer-only freestanding C. No runtime library or precomputed lookup tables. */
typedef unsigned int u32;
typedef unsigned long long u64;

__attribute__((noinline))
static u32 combine(u32 a, u32 b) {
    return (a + b) ^ (a - b);
}

u32 run(u32 a, u32 b) {
    u32 mixed = combine(a, b);
    return (a & 1u) ? mixed + (b ^ 0x5a5a5a5au)
                    : mixed - (a ^ 0xa5a5a5a5u);
}

u64 run64(u64 a, u64 b) {
    u64 mixed = (a + b) ^ (a - b);
    unsigned k = (unsigned)b & 63u;
    u64 rotated = (mixed << k) | (mixed >> ((64u - k) & 63u));
    return rotated + a;
}
