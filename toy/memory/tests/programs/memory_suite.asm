    addi x1, x0, 0          // base pointer into data memory

    lb   x2, 0(x1)          // sign-extend negative byte
    lbu  x3, 1(x1)          // zero-extend positive byte
    lh   x4, 2(x1)          // sign-extend halfword
    lhu  x5, 4(x1)          // zero-extend halfword
    lw   x6, 8(x1)          // load full word

    addi x7, x0, -2         // byte store value (0xFE)
    sb   x7, 12(x1)
    lbu  x8, 12(x1)        // confirm byte store

    addi x9, x0, 0x7B       // build 0x7B9A
    slli x9, x9, 8
    addi x9, x9, 0x9A
    sh   x9, 14(x1)
    lhu  x11, 14(x1)       // confirm half store

    addi x12, x0, 0xCA      // build 0xCAFEBABE
    slli x12, x12, 8
    addi x12, x12, 0xFE
    slli x12, x12, 8
    addi x12, x12, 0xBA
    slli x12, x12, 8
    addi x12, x12, 0xBE
    sw   x12, 16(x1)
    lw   x13, 16(x1)       // confirm word store

    lw   x14, 12(x1)       // capture word with mixed stores

    ebreak
