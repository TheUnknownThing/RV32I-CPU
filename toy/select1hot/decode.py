"""Decode helpers for the toy Select1Hot CPU."""

from __future__ import annotations

from assassyn.frontend import Bits, Condition, Value, assume, concat, log

from .common import AluOp, decoded_instr

OPCODE_OP = 0b0110011
OPCODE_OPIMM = 0b0010011
FUNCT7_SUB_SRA = 0b0100000
EBREAK_ENCODING = 0x00100073


def _sign_extend_bits(value: Value, width: int, target: int = 32) -> Value:
    if width == target:
        return value
    pad_width = target - width
    msb = value[width - 1 : width - 1]
    pad = msb.select(Bits(pad_width)((1 << pad_width) - 1), Bits(pad_width)(0))
    return concat(pad, value)


def decode_instruction(instr: Value) -> Value:
    """Decode a raw 32-bit instruction into the decoded_instr bundle."""

    opcode = instr[0:6]
    rd = instr[7:11]
    funct3 = instr[12:14]
    rs1 = instr[15:19]
    rs2 = instr[20:24]
    funct7 = instr[25:31]
    imm = _sign_extend_bits(instr[20:31], 12)
    shamt = instr[20:24]
    imm_upper = instr[25:31]

    is_op = opcode == Bits(7)(OPCODE_OP)
    is_op_imm = opcode == Bits(7)(OPCODE_OPIMM)

    funct3_eq = {
        0b000: funct3 == Bits(3)(0b000),
        0b001: funct3 == Bits(3)(0b001),
        0b010: funct3 == Bits(3)(0b010),
        0b011: funct3 == Bits(3)(0b011),
        0b100: funct3 == Bits(3)(0b100),
        0b101: funct3 == Bits(3)(0b101),
        0b110: funct3 == Bits(3)(0b110),
        0b111: funct3 == Bits(3)(0b111),
    }

    funct7_is_zero = funct7 == Bits(7)(0)
    funct7_is_sub = funct7 == Bits(7)(FUNCT7_SUB_SRA)

    # R-type arithmetic
    is_add = is_op & funct3_eq[0b000] & funct7_is_zero
    is_sub = is_op & funct3_eq[0b000] & funct7_is_sub
    is_sll = is_op & funct3_eq[0b001] & funct7_is_zero
    is_srl = is_op & funct3_eq[0b101] & funct7_is_zero
    is_sra = is_op & funct3_eq[0b101] & funct7_is_sub
    is_and = is_op & funct3_eq[0b111] & funct7_is_zero
    is_or = is_op & funct3_eq[0b110] & funct7_is_zero
    is_xor = is_op & funct3_eq[0b100] & funct7_is_zero
    is_slt = is_op & funct3_eq[0b010] & funct7_is_zero
    is_sltu = is_op & funct3_eq[0b011] & funct7_is_zero

    # Immediate arithmetic and shifts
    is_addi = is_op_imm & funct3_eq[0b000]
    is_slti = is_op_imm & funct3_eq[0b010]
    is_sltiu = is_op_imm & funct3_eq[0b011]
    is_xori = is_op_imm & funct3_eq[0b100]
    is_ori = is_op_imm & funct3_eq[0b110]
    is_andi = is_op_imm & funct3_eq[0b111]
    is_slli = is_op_imm & funct3_eq[0b001] & (imm_upper == Bits(7)(0))
    is_srli = is_op_imm & funct3_eq[0b101] & (imm_upper == Bits(7)(0))
    is_srai = is_op_imm & funct3_eq[0b101] & (imm_upper == Bits(7)(FUNCT7_SUB_SRA))

    is_ebreak = instr == Bits(32)(EBREAK_ENCODING)

    supported = (
        is_add
        | is_sub
        | is_sll
        | is_srl
        | is_sra
        | is_and
        | is_or
        | is_xor
        | is_slt
        | is_sltu
        | is_addi
        | is_slti
        | is_sltiu
        | is_xori
        | is_ori
        | is_andi
        | is_slli
        | is_srli
        | is_srai
        | is_ebreak
    )

    with Condition(~supported):
        log("toy-decode | unsupported instruction opcode=0x{:x}", opcode)
        assume(Bits(1)(0))

    use_imm = (
        is_addi
        | is_slti
        | is_sltiu
        | is_xori
        | is_ori
        | is_andi
        | is_slli
        | is_srli
        | is_srai
    )
    use_shamt = is_slli | is_srli | is_srai

    mask = lambda op: Bits(AluOp.COUNT)(1 << op)

    op_select = Bits(AluOp.COUNT)(0)
    op_select = (is_add | is_addi).select(mask(AluOp.ADD), op_select)
    op_select = is_sub.select(mask(AluOp.SUB), op_select)
    op_select = (is_sll | is_slli).select(mask(AluOp.SLL), op_select)
    op_select = (is_srl | is_srli).select(mask(AluOp.SRL), op_select)
    op_select = (is_sra | is_srai).select(mask(AluOp.SRA), op_select)
    op_select = (is_and | is_andi).select(mask(AluOp.AND), op_select)
    op_select = (is_or | is_ori).select(mask(AluOp.OR), op_select)
    op_select = (is_xor | is_xori).select(mask(AluOp.XOR), op_select)
    op_select = (is_slt | is_slti).select(mask(AluOp.SLT), op_select)
    op_select = (is_sltu | is_sltiu).select(mask(AluOp.SLTU), op_select)

    log(
        "toy-decode | rd=x{:02} rs1=x{:02} rs2=0x{:02x} use_imm={} shamt={} op=0x{:03x}",
        rd,
        rs1,
        rs2,
        use_imm,
        shamt,
        op_select,
    )

    return decoded_instr.bundle(
        rs1=rs1,
        rs2=rs2,
        rd=rd,
        imm=imm,
        shamt=shamt,
        op_select=op_select,
        use_imm=use_imm,
        use_shamt=use_shamt,
        is_ebreak=is_ebreak,
    )
