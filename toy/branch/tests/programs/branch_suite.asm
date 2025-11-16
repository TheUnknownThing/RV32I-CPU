# Branch instruction validation program
# Each branch type executes one scenario that should not take and one that should take.
# Registers x20-x25 accumulate success bits. +1 means the not-taken path executed correctly,
# +2 means the taken path executed correctly. Any failure path adds a unique high bit.

        addi x1, x0, 0
        addi x20, x0, 0
        addi x21, x0, 0
        addi x22, x0, 0
        addi x23, x0, 0
        addi x24, x0, 0
        addi x25, x0, 0

# BEQ tests
        addi x2, x0, 1
        addi x3, x0, 2
        beq x2, x3, beq_false_fail
        addi x20, x20, 1
        beq x0, x0, beq_false_done
beq_false_fail:
        addi x20, x20, 0x100
beq_false_done:
        addi x2, x0, 7
        addi x3, x0, 7
        beq x2, x3, beq_true_pass
        addi x20, x20, 0x200
        beq x0, x0, beq_true_done
beq_true_pass:
        addi x20, x20, 2
beq_true_done:

# BNE tests
        addi x4, x0, 5
        addi x5, x0, 5
        bne x4, x5, bne_false_fail
        addi x21, x21, 1
        beq x0, x0, bne_false_done
bne_false_fail:
        addi x21, x21, 0x100
bne_false_done:
        addi x4, x0, 3
        addi x5, x0, 9
        bne x4, x5, bne_true_pass
        addi x21, x21, 0x200
        beq x0, x0, bne_true_done
bne_true_pass:
        addi x21, x21, 2
bne_true_done:

# BLT tests (signed)
        addi x6, x0, 4
        addi x7, x0, -2
        blt x6, x7, blt_false_fail
        addi x22, x22, 1
        beq x0, x0, blt_false_done
blt_false_fail:
        addi x22, x22, 0x100
blt_false_done:
        addi x6, x0, -5
        addi x7, x0, 6
        blt x6, x7, blt_true_pass
        addi x22, x22, 0x200
        beq x0, x0, blt_true_done
blt_true_pass:
        addi x22, x22, 2
blt_true_done:

# BGE tests (signed)
        addi x8, x0, 2
        addi x9, x0, 7
        bge x8, x9, bge_false_fail
        addi x23, x23, 1
        beq x0, x0, bge_false_done
bge_false_fail:
        addi x23, x23, 0x100
bge_false_done:
        addi x8, x0, -4
        addi x9, x0, -4
        bge x8, x9, bge_true_pass
        addi x23, x23, 0x200
        beq x0, x0, bge_true_done
bge_true_pass:
        addi x23, x23, 2
bge_true_done:

# BLTU tests (unsigned)
        addi x10, x0, -1
        addi x11, x0, 1
        bltu x10, x11, bltu_false_fail
        addi x24, x24, 1
        beq x0, x0, bltu_false_done
bltu_false_fail:
        addi x24, x24, 0x100
bltu_false_done:
        addi x10, x0, 1
        addi x11, x0, 9
        bltu x10, x11, bltu_true_pass
        addi x24, x24, 0x200
        beq x0, x0, bltu_true_done
bltu_true_pass:
        addi x24, x24, 2
bltu_true_done:

# BGEU tests (unsigned)
        addi x12, x0, 2
        addi x13, x0, 5
        bgeu x12, x13, bgeu_false_fail
        addi x25, x25, 1
        beq x0, x0, bgeu_false_done
bgeu_false_fail:
        addi x25, x25, 0x100
bgeu_false_done:
        addi x12, x0, -1
        addi x13, x0, 3
        bgeu x12, x13, bgeu_true_pass
        addi x25, x25, 0x200
        beq x0, x0, bgeu_true_done
bgeu_true_pass:
        addi x25, x25, 2
bgeu_true_done:

        # Summarize success flags into x1 for convenience
        addi x1, x0, 0
        add x1, x1, x20
        add x1, x1, x21
        add x1, x1, x22
        add x1, x1, x23
        add x1, x1, x24
        add x1, x1, x25

        ebreak
