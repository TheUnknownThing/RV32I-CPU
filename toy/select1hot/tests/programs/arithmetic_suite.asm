// Comprehensive arithmetic test covering all Select1Hot instructions.

    addi x2, x0, 5          // x2 = 5
    addi x3, x0, -7         // x3 = -7
    addi x4, x2, 10         // x4 = 15

    add  x5, x2, x4         // x5 = 20
    sub  x6, x4, x2         // x6 = 10

    andi x7, x5, 0b1110     // x7 = 0b0100
    and  x8, x5, x6         // x8 = 0

    ori  x9, x0, 0x123      // x9 = 0x123
    or   x10, x9, x2        // x10 = 0x127

    xori x11, x9, 0x3       // x11 = 0x120
    xor  x12, x11, x10      // x12 = 0x7

    addi x13, x0, 2
    slli x14, x2, 1         // x14 = 10
    sll  x15, x4, x13       // x15 = x4 << 2 = 60
    srli x16, x15, 3        // x16 = 7
    srl  x17, x16, x13      // x17 = 1

    srai x18, x3, 1         // arithmetic shift
    sra  x19, x3, x13

    slti x20, x3, 1         // signed compare
    slt  x21, x3, x2
    sltiu x22, x3, 1        // unsigned compare
    sltu x23, x2, x3
    sltu x24, x3, x2

    add  x1, x14, x15
    add  x1, x1, x16
    add  x1, x1, x17
    addi x1, x1, 1
    add  x0, x0, x0         // no-op, for x1 to write to RF

    ebreak
