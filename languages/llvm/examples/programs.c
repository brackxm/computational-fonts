#include <stdint.h>

int32_t max(int32_t a, int32_t b) { return a > b ? a : b; }
uint32_t mix(uint32_t a, uint32_t b) { return ((a + b) ^ (a >> 3)) * 3; }
uint32_t sum_loop(uint32_t n) {
    uint32_t sum = 0;
    for (uint32_t i = 0; i < n; ++i) sum += i;
    return sum;
}
uint32_t indexed(uint32_t index, uint32_t value) {
    uint32_t cells[4];
    cells[0] = 3; cells[1] = 5; cells[2] = 7; cells[3] = 11;
    cells[index & 3] = value;
    return cells[(index + 1) & 3] + cells[index & 3];
}
