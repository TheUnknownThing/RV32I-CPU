"""Common structures for the Naive RV32I CPU."""

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


class BranchCond:
    """Branch condition selector indices."""

    EQ = 0
    NE = 1
    LT = 2
    GE = 3
    LTU = 4
    GEU = 5
    COUNT = 6


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
    rs1_is_source=Bits(1),
    rs2_is_source=Bits(1),
    is_alu_instr=Bits(1),
    is_load=Bits(1),
    is_store=Bits(1),
    is_branch=Bits(1),
    is_jump=Bits(1),
    is_jal=Bits(1),
    is_jalr=Bits(1),
    is_auipc=Bits(1),
    is_lui=Bits(1),
    branch_cond=Bits(BranchCond.COUNT),
    mem_width=Bits(2),
    mem_unsigned=Bits(1),
)