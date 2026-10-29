#include <stdint.h>
typedef uint32_t (*Operation)(uint32_t, uint32_t);

static uint32_t base;
static Operation chosen;
__attribute__((noinline)) static uint32_t add(uint32_t a, uint32_t b) { return a + b + base; }
__attribute__((noinline)) static uint32_t sub(uint32_t a, uint32_t b) { return a - b + base; }
__attribute__((noinline)) static uint32_t mix(uint32_t a, uint32_t b) { return a ^ b ^ base; }
__attribute__((noinline)) static uint32_t bump(uint32_t a, uint32_t b) { base += a; return base + b; }
static Operation const operations[4] = {add, sub, mix, bump};

__attribute__((constructor(101))) static void first_init(void) { base = 7; }
__attribute__((constructor(202))) static void second_init(void) { base = base * 3 + 1; chosen = mix; }
void reset_reference(void) { first_init(); second_init(); }

__attribute__((noinline)) static uint32_t apply(Operation operation, uint32_t a, uint32_t b) {
    return operation(a, b);
}
uint32_t dispatch(uint32_t index, uint32_t a, uint32_t b) { return apply(operations[index & 3], a, b); }
uint32_t constructor_dispatch(uint32_t a, uint32_t b) { return apply(chosen, a, b); }
uint32_t dispatch_twice(uint32_t index, uint32_t a, uint32_t b) {
    Operation operation = operations[index & 3];
    uint32_t first = apply(operation, a, b);
    return first ^ apply(operation, b, a);
}
__attribute__((noinline)) static void copy_two(Operation *dest, Operation const *src) {
    __builtin_memcpy(dest, src, 2 * sizeof(Operation));
}
uint32_t copied_dispatch(uint32_t index, uint32_t a, uint32_t b) {
    Operation local[2];
    copy_two(local, operations);
    return apply(local[index & 1], a, b);
}
