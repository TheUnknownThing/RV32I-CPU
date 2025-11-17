#include <stdint.h>

#include "test_runtime.h"

static int32_t clamp(int32_t value, int32_t lo, int32_t hi) {
    if (value < lo) {
        return lo;
    }
    if (value > hi) {
        return hi;
    }
    return value;
}

static uint32_t walk_sequence(uint32_t seed) {
    uint32_t state = seed;
    for (uint32_t i = 0; i < 9; ++i) {
        if ((state & 1U) != 0U) {
            state = (state >> 1U) ^ 0xB400U;
        } else {
            state >>= 1U;
        }
        state += i;
    }
    return state;
}

static uint32_t triangular(uint32_t n) {
    if (n == 0U) {
        return 0;
    }
    return n + triangular(n - 1U);
}

static uint32_t popcount(uint32_t value) {
    uint32_t bits = 0;
    while (value != 0U) {
        bits += value & 1U;
        value >>= 1U;
    }
    return bits;
}

int main(void) {
    int32_t accum = 0;
    for (int32_t i = -12; i <= 9; ++i) {
        accum += clamp(i * 3, -21, 17);
    }

    const uint32_t sequence = walk_sequence(0xACE1U);
    const uint32_t triangle = triangular(8U);
    const uint32_t bit_count = popcount(sequence ^ triangle);

    test_report(0, (uint32_t)accum);
    test_report(1, sequence);
    test_report(2, triangle);
    test_report(3, bit_count);

    test_pass();
}
