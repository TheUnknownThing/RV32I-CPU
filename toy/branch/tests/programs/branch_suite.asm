# Branch instruction validation program
# Each branch type executes one scenario that should not take and one that should take.
# Registers x20-x25 accumulate success bits. +1 means the not-taken path executed correctly,
# +2 means the taken path executed correctly. Any failure path adds a unique high bit.

        addi x1, x0, 0              // pc=0
        addi x20, x0, 0             // pc=4
        addi x21, x0, 0             // pc=8
        addi x22, x0, 0             // pc=c
        addi x23, x0, 0             // pc=10
        addi x24, x0, 0             // pc=14
        addi x25, x0, 0             // pc=18
# BEQ tests
        addi x2, x0, 1              // pc=1c
        addi x3, x0, 2              // pc=20
        beq x2, x3, beq_false_fail  // pc=24
        addi x20, x20, 1            // pc=28
        beq x0, x0, beq_false_done  // pc=2c
beq_false_fail:
        addi x20, x20, 0x100        // pc=30
beq_false_done:
        addi x2, x0, 7              // pc=34
        addi x3, x0, 7              // pc=38
        beq x2, x3, beq_true_pass  // pc=3c
        addi x20, x20, 0x200        // pc=40
        beq x0, x0, beq_true_done  // pc=44
beq_true_pass:
        addi x20, x20, 2            // pc=48
beq_true_done:

# BNE tests
        addi x4, x0, 5              // pc=4c
        addi x5, x0, 5              // pc=50
        bne x4, x5, bne_false_fail  // pc=54
        addi x21, x21, 1            // pc=58
        beq x0, x0, bne_false_done  // pc=5c
bne_false_fail:
        addi x21, x21, 0x100        // pc=60
bne_false_done:
        addi x4, x0, 3              // pc=64
        addi x5, x0, 9              // pc=68
        bne x4, x5, bne_true_pass  // pc=6c
        addi x21, x21, 0x200        // pc=70
        beq x0, x0, bne_true_done  // pc=74
bne_true_pass:
        addi x21, x21, 2            // pc=78
bne_true_done:

# BLT tests (signed)
        addi x6, x0, 4              // pc=7c
        addi x7, x0, -2             // pc=80
        blt x6, x7, blt_false_fail  // pc=84
        addi x22, x22, 1            // pc=88
        beq x0, x0, blt_false_done  // pc=8c
blt_false_fail:
        addi x22, x22, 0x100        // pc=90
blt_false_done:
        addi x6, x0, -5             // pc=94
        addi x7, x0, 6              // pc=98
        blt x6, x7, blt_true_pass  // pc=9c
        addi x22, x22, 0x200        // pc=a0
        beq x0, x0, blt_true_done  // pc=a4
blt_true_pass:
        addi x22, x22, 2            // pc=a8
blt_true_done:

# BGE tests (signed)
        addi x8, x0, 2              // pc=ac
        addi x9, x0, 7              // pc=b0
        bge x8, x9, bge_false_fail  // pc=b4
        addi x23, x23, 1            // pc=b8
        beq x0, x0, bge_false_done  // pc=bc
bge_false_fail:
        addi x23, x23, 0x100        // pc=c0
bge_false_done:
        addi x8, x0, -4             // pc=c4
        addi x9, x0, -4             // pc=c8
        bge x8, x9, bge_true_pass  // pc=cc
        addi x23, x23, 0x200        // pc=d0
        beq x0, x0, bge_true_done  // pc=d4
bge_true_pass:
        addi x23, x23, 2            // pc=d8
bge_true_done:

# BLTU tests (unsigned)
        addi x10, x0, -1            // pc=dc
        addi x11, x0, 1             // pc=e0    
        bltu x10, x11, bltu_false_fail  // pc=e4
        addi x24, x24, 1            // pc=e8
        beq x0, x0, bltu_false_done  // pc=ec
bltu_false_fail:
        addi x24, x24, 0x100        // pc=f0
bltu_false_done:
        addi x10, x0, 1             // pc=f4
        addi x11, x0, 9             // pc=f8
        bltu x10, x11, bltu_true_pass  // pc=fc
        addi x24, x24, 0x200        // pc=100
        beq x0, x0, bltu_true_done  // pc=104
bltu_true_pass:
        addi x24, x24, 2            // pc=108
bltu_true_done:

# BGEU tests (unsigned)
        addi x12, x0, 2             // pc=10c
        addi x13, x0, 5             // pc=110
        bgeu x12, x13, bgeu_false_fail  // pc=114
        addi x25, x25, 1            // pc=118
        beq x0, x0, bgeu_false_done  // pc=11c
bgeu_false_fail:
        addi x25, x25, 0x100        // pc=120
bgeu_false_done:
        addi x12, x0, -1            // pc=124
        addi x13, x0, 3             // pc=128
        bgeu x12, x13, bgeu_true_pass  // pc=12c
        addi x25, x25, 0x200        // pc=130
        beq x0, x0, bgeu_true_done  // pc=134
bgeu_true_pass:
        addi x25, x25, 2            // pc=138
bgeu_true_done:

        # Summarize success flags into x1 for convenience
        addi x1, x0, 0              // pc=13c
        add x1, x1, x20             // pc=140
        add x1, x1, x21             // pc=144
        add x1, x1, x22             // pc=148
        add x1, x1, x23             // pc=14c
        add x1, x1, x24             // pc=150
        add x1, x1, x25             // pc=154

        ebreak                      // pc=158
