# Validate jal and jalr control flow along with link register side effects.

        addi x2, x0, 0
        addi x9, x0, 0
        jal  x5, handler        // link into x5 and jump

after_call:
        addi x2, x2, 0x111      // executes only after returning
        addi x9, x9, 1
        addi x10, x0, 0x123     // baseline value that should survive
        jal  x0, finished       // skip over handler body once done
        addi x10, x0, 0x666     // should never execute

handler:
        addi x3, x0, 0x222
        addi x30, x5, -4        // craft base to exercise jalr immediate addition
        jalr x0, x30, 4         // target = x5, return to caller
        addi x4, x0, 0x333      // unreachable if jalr behaved

finished:
        ebreak
