#include <stdint.h>
static uint32_t state;
__attribute__((constructor(101))) static void first_init(void) { state = 7; }
__attribute__((constructor(202))) static void second_init(void) { state = state * 3 + 1; }
uint32_t initialized(uint32_t value) { return state + value; }
