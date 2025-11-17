# Validate LUI and AUIPC behaviors with positive and negative immediates.

        auipc x5, 0x12345        // expect 0x12345000 at pc=0
        lui   x6, 0x00ABC        // 0x00ABC000
        addi  x6, x6, 0x7F       // refine low bits
        auipc x7, 0              // pc=12, capture absolute PC
        addi  x7, x7, -12        // should reduce back to zero
        auipc x8, -1             // pc=20, expect pc-0x1000
        ebreak
