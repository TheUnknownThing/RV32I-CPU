#include <stddef.h>
#include <stdint.h>

#include "test_runtime.h"

static uint32_t words[] = {
    0x11223344u,
    0x55667788u,
    0xAABBCCDDu,
    0x01020304u,
};

static uint8_t raw_bytes[] = {0x80u, 0x10u, 0x7Fu, 0xFFu, 0x00u, 0x55u, 0x7Au, 0x33u};

static uint32_t xor_and_sum(void) {
    uint32_t total = 0;
    for (size_t i = 0; i < sizeof(words) / sizeof(words[0]); ++i) {
        words[i] ^= 0x0F0F0F0Fu;
        total += words[i];
    }
    return total;
}

static int32_t fold_stack(int32_t seed) {
    int32_t local_a = seed ^ (int32_t)0x55AA33CCu;
    int32_t local_b = (local_a << 3) - seed;
    int32_t local_c = (local_b >> 2) | 0x1234;
    return local_c - local_a;
}

int main(void) {
    const uint32_t total = xor_and_sum();
    const uint8_t unsigned_byte = raw_bytes[0];
    const int8_t signed_byte = (int8_t)raw_bytes[3];
    const uint16_t half_word = ((uint16_t*)raw_bytes)[1];
    const int32_t folded = fold_stack((int32_t)total);

    test_report(0, total);
    test_report(1, unsigned_byte);
    test_report(2, half_word);
    test_report(3, (uint32_t)signed_byte);
    test_report(4, (uint32_t)folded);

    test_pass();
}
