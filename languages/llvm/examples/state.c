#include <stdint.h>

uint32_t saturating_add(uint32_t a, uint32_t b) {
    return __builtin_elementwise_add_sat(a, b);
}

int32_t saturating_sub(int32_t a, int32_t b) {
    return __builtin_elementwise_sub_sat(a, b);
}

static uint32_t counter = 5;
__attribute__((noinline)) static uint32_t advance(uint32_t value) {
    counter += value;
    return counter;
}
uint32_t global_calls(uint32_t a, uint32_t b) {
    counter = 5;
    return advance(a) ^ advance(b);
}

static uint32_t first = 3, second = 11;
static uint32_t *slots[2] = {&first, &second};
uint32_t pointer_table(uint32_t index, uint32_t value) {
    first = 3; second = 11;
    slots[index & 1] = &first;
    slots[(index + 1) & 1] = &second;
    *slots[index & 1] = value;
    return *slots[(index + 1) & 1] + *slots[index & 1];
}

__attribute__((noinline)) static void copy_pointers(uint32_t **dest, uint32_t **src) {
    __builtin_memcpy(dest, src, 2 * sizeof(uint32_t *));
}
uint32_t pointer_copy(uint32_t index, uint32_t value) {
    uint32_t values[2] = {value, value + 1};
    uint32_t *source[2] = {&values[0], &values[1]};
    uint32_t *dest[2];
    copy_pointers(dest, source);
    return *dest[index & 1];
}
