"""Common structures for the toy Select1Hot CPU."""

from assassyn.frontend import Bits, Record


class AluOp:
    """One-hot ALU operation indices."""

    ADD = 0
    SUB = 1
    SLL = 2
    SRL = 3
    SRA = 4
    AND = 5
    OR = 6
    XOR = 7
    SLT = 8
    SLTU = 9
    COUNT = 10


class MemWidth:
    """Memory access widths."""

    BYTE = 0
    HALF = 1
    WORD = 2


decoded_instr = Record(
    rs1=Bits(5),
    rs2=Bits(5),
    rd=Bits(5),
    imm=Bits(32),
    shamt=Bits(5),
    op_select=Bits(AluOp.COUNT),
    use_imm=Bits(1),
    use_shamt=Bits(1),
    is_ebreak=Bits(1),
    rs2_is_source=Bits(1),
    is_load=Bits(1),
    is_store=Bits(1),
    mem_width=Bits(2),
    mem_unsigned=Bits(1),
)
