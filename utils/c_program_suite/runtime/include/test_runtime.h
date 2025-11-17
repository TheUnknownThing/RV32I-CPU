#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

extern volatile uint32_t __test_report_base[];
extern const uint32_t __test_report_slots;

void test_halt(uint32_t code) __attribute__((noreturn));

static inline void test_report(uint32_t slot, uint32_t value) {
    volatile uint32_t* base = __test_report_base;
    const uint32_t slot_count = (uint32_t)(uintptr_t)&__test_report_slots;
    const uint32_t available = slot_count > 0 ? slot_count - 1 : 0;
    if (slot < available) {
        base[slot + 1] = value;
    } else {
        test_halt(0xBAD00000u | slot);
    }
}

static inline void test_pass(void) __attribute__((noreturn));
static inline void test_pass(void) {
    test_halt(0);
}

static inline void test_fail(uint32_t code) __attribute__((noreturn));
static inline void test_fail(uint32_t code) {
    if (code == 0) {
        code = 1;
    }
    test_halt(code);
}

#ifdef __cplusplus
}
#endif
