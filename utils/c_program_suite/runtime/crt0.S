    .section .text.entry, "ax", @progbits
    .globl _start
_start:
    la gp, __global_pointer$
    la sp, __stack_top
    addi sp, sp, -16
    call main
    jal zero, test_halt

    .section .text.runtime, "ax", @progbits
    .globl test_halt
test_halt:
    la t0, __test_report_base
    sw a0, 0(t0)
    ebreak
1:
    j 1b
