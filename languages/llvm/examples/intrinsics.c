#include <stdint.h>

static const uint32_t weights[4] = {3, 5, 7, 11};

uint32_t constant_lookup(uint32_t index) { return weights[index & 3]; }

uint32_t copied_array(uint32_t index, uint32_t value) {
    uint32_t cells[4] = {3, 5, 7, 11};
    cells[index & 3] ^= value;
    return cells[(index + 1) & 3] + cells[index & 3];
}

uint64_t checked_add(uint32_t a, uint32_t b) {
    uint32_t result;
    unsigned overflow = __builtin_add_overflow(a, b, &result);
    return (uint64_t)result | ((uint64_t)overflow << 32);
}

uint64_t checked_multiply(int32_t a, int32_t b) {
    int32_t result;
    unsigned overflow = __builtin_mul_overflow(a, b, &result);
    return (uint64_t)(uint32_t)result | ((uint64_t)overflow << 32);
}
