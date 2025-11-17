#include <stdint.h>

#include "test_runtime.h"

static uint32_t mul_shift(uint32_t lhs, uint32_t rhs) {
    uint32_t acc = 0;
    while (rhs != 0) {
        if (rhs & 1U) {
            acc += lhs;
        }
        lhs <<= 1U;
        rhs >>= 1U;
    }
    return acc;
}

static uint32_t fib(uint32_t n) {
    uint32_t prev = 0;
    uint32_t curr = 1;
    for (uint32_t i = 0; i < n; ++i) {
        uint32_t next = prev + curr;
        prev = curr;
        curr = next;
    }
    return prev;
}

int main(void) {
    uint32_t accumulator = 0;
    for (uint32_t i = 0; i < 7; ++i) {
        const uint32_t lhs = i << 1U;
        const uint32_t rhs = i + 3U;
        accumulator += lhs ^ rhs;
    }

    const uint32_t rotate_mix = (accumulator << 5U) | (accumulator >> (32U - 5U));
    const int32_t signed_mix = (int32_t)accumulator - 1234;
    const uint32_t shift_product = mul_shift(accumulator & 0xFFU, 7U);
    const uint32_t fib_value = fib(7U);

    test_report(0, accumulator);
    test_report(1, rotate_mix);
    test_report(2, (uint32_t)signed_mix);
    test_report(3, shift_product);
    test_report(4, fib_value);

    test_pass();
}
