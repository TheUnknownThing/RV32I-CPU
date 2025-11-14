"""Decode helpers for the toy ADD/ADDI core."""

from __future__ import annotations
from .common import decoded_instr

from assassyn.frontend import Bits, Condition, Record, Value, assume, concat, log

ADD_OPCODE = 0b0110011
ADDI_OPCODE = 0b0010011
SYSTEM_OPCODE = 0b1110011
FUNCT3_ADD = 0b000
FUNCT7_ADD = 0b0000000
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

    is_add = (
        (opcode == Bits(7)(ADD_OPCODE))
        & (funct3 == Bits(3)(FUNCT3_ADD))
        & (funct7 == Bits(7)(FUNCT7_ADD))
    )
    is_addi = (opcode == Bits(7)(ADDI_OPCODE)) & (funct3 == Bits(3)(FUNCT3_ADD))
    is_ebreak = instr == Bits(32)(EBREAK_ENCODING)

    log(
        "toy-decode | inst: 0x{:08x} | rd: x{:02} | rs1: x{:02} | rs2: x{:02} | imm: 0x{:08x}",
        instr,
        rd,
        rs1,
        rs2,
        imm,
    )

    return decoded_instr.bundle(
        rs1=rs1,
        imm=imm,
        rs2=rs2,
        rd=rd,
        alu_select=Bits(2)(0),  # not used
        is_addi=is_addi,
        is_ebreak=is_ebreak,
    )
