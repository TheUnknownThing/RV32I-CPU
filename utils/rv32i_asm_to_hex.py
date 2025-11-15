#!/usr/bin/env python3
"""Minimal RV32I assembler supporting arithmetic, memory, control, and system ops."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

REGISTER_RE = re.compile(r"x([0-9]|[12][0-9]|3[01])\Z")
LABEL_RE = re.compile(r"([A-Za-z_.$][\w.$]*)\s*:")

R_TYPE_MAP = {
    "add": (0b000, 0b0000000),
    "sub": (0b000, 0b0100000),
    "and": (0b111, 0b0000000),
    "or": (0b110, 0b0000000),
    "xor": (0b100, 0b0000000),
    "sll": (0b001, 0b0000000),
    "srl": (0b101, 0b0000000),
    "sra": (0b101, 0b0100000),
    "slt": (0b010, 0b0000000),
    "sltu": (0b011, 0b0000000),
}

I_TYPE_IMM_MAP = {
    "addi": 0b000,
    "andi": 0b111,
    "ori": 0b110,
    "xori": 0b100,
    "slti": 0b010,
    "sltiu": 0b011,
}

SHIFT_IMM_MAP = {
    "slli": (0b001, 0b0000000),
    "srli": (0b101, 0b0000000),
    "srai": (0b101, 0b0100000),
}

LOAD_MAP = {
    "lb": 0b000,
    "lh": 0b001,
    "lw": 0b010,
    "lbu": 0b100,
    "lhu": 0b101,
}

STORE_MAP = {
    "sb": 0b000,
    "sh": 0b001,
    "sw": 0b010,
}

BRANCH_MAP = {
    "beq": 0b000,
    "bne": 0b001,
    "blt": 0b100,
    "bge": 0b101,
    "bltu": 0b110,
    "bgeu": 0b111,
}

EBREAK_ENCODING = 0x00100073
ECALL_ENCODING = 0x00000073


class AssemblyError(RuntimeError):
    """Raised when the assembler encounters malformed input."""


@dataclass
class ParsedInstruction:
    mnemonic: str
    args: List[str]
    lineno: int
    address: int


def _strip_comment(line: str) -> str:
    for marker in ("//", "#", ";"):
        idx = line.find(marker)
        if idx != -1:
            line = line[:idx]
    return line.strip()


def _parse_register(token: str, *, lineno: int) -> int:
    match = REGISTER_RE.fullmatch(token.strip().lower())
    if not match:
        raise AssemblyError(f"Line {lineno}: invalid register '{token}'.")
    return int(match.group(1))


def _parse_imm(token: str, *, lineno: int) -> int:
    try:
        value = int(token, 0)
    except ValueError as err:
        raise AssemblyError(f"Line {lineno}: invalid immediate '{token}'.") from err
    return value


def _encode_r_type(rd: int, rs1: int, rs2: int, funct3: int, funct7: int, opcode: int) -> int:
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _encode_i_type(rd: int, rs1: int, imm: int, funct3: int, opcode: int) -> int:
    if imm < -2048 or imm > 2047:
        raise AssemblyError(f"Immediate {imm} is out of 12-bit range for I-type.")
    imm_bits = imm & 0xFFF
    return (
        ((imm_bits & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _encode_s_type(rs1: int, rs2: int, imm: int, funct3: int, opcode: int) -> int:
    if imm < -2048 or imm > 2047:
        raise AssemblyError(f"Immediate {imm} is out of 12-bit range for S-type.")
    imm_bits = imm & 0xFFF
    return (
        ((imm_bits >> 5) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((imm_bits & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _encode_b_type(rs1: int, rs2: int, imm: int, funct3: int, opcode: int) -> int:
    if imm % 2 != 0:
        raise AssemblyError("Branch offsets must be multiples of 2 bytes.")
    if imm < -4096 or imm > 4094:
        raise AssemblyError(f"Offset {imm} is out of range for B-type branch.")
    imm_bits = imm & 0x1FFF
    return (
        (((imm_bits >> 12) & 0x1) << 31)
        | (((imm_bits >> 5) & 0x3F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | (((imm_bits >> 1) & 0xF) << 8)
        | (((imm_bits >> 11) & 0x1) << 7)
        | (opcode & 0x7F)
    )


def _encode_j_type(rd: int, imm: int, opcode: int) -> int:
    if imm % 2 != 0:
        raise AssemblyError("JAL offsets must be multiples of 2 bytes.")
    if imm < -(1 << 20) or imm > ((1 << 20) - 2):
        raise AssemblyError(f"Offset {imm} is out of range for J-type.")
    imm_bits = imm & 0x1FFFFF
    return (
        (((imm_bits >> 20) & 0x1) << 31)
        | (((imm_bits >> 1) & 0x3FF) << 21)
        | (((imm_bits >> 11) & 0x1) << 20)
        | (((imm_bits >> 12) & 0xFF) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _encode_u_type(rd: int, imm: int, opcode: int) -> int:
    if imm < -(1 << 19) or imm > ((1 << 19) - 1):
        raise AssemblyError(f"Immediate {imm} is out of 20-bit range for U-type.")
    imm_bits = imm & 0xFFFFF
    return ((imm_bits & 0xFFFFF) << 12) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def _parse_mem_operand(token: str, *, lineno: int) -> tuple[int, int]:
    cleaned = token.replace(" ", "")
    if "(" not in cleaned or not cleaned.endswith(")"):
        raise AssemblyError(
            f"Line {lineno}: memory operand '{token}' must look like imm(xN)."
        )
    offset_str, reg_part = cleaned.split("(", 1)
    reg_token = reg_part[:-1]
    offset = 0 if offset_str == "" else _parse_imm(offset_str, lineno=lineno)
    base = _parse_register(reg_token, lineno=lineno)
    return offset, base


def _collect_instructions(lines: Sequence[str]) -> tuple[List[ParsedInstruction], dict[str, int]]:
    instructions: List[ParsedInstruction] = []
    labels: dict[str, int] = {}
    pc = 0
    for lineno, raw in enumerate(lines, start=1):
        line = _strip_comment(raw)
        if not line:
            continue
        while True:
            match = LABEL_RE.match(line)
            if not match:
                break
            label = match.group(1)
            if label in labels:
                raise AssemblyError(f"Line {lineno}: duplicate label '{label}'.")
            labels[label] = pc
            line = line[match.end() :].lstrip()
            if not line:
                break
        if not line:
            continue
        parts = line.split(None, 1)
        mnemonic = parts[0]
        arg_str = parts[1] if len(parts) > 1 else ""
        args = [arg.strip() for arg in arg_str.split(",") if arg.strip()]
        instructions.append(ParsedInstruction(mnemonic.lower(), args, lineno, pc))
        pc += 4
    if not instructions:
        raise AssemblyError("No instructions to assemble.")
    return instructions, labels


def _resolve_label(token: str, labels: dict[str, int], *, lineno: int) -> int:
    if token not in labels:
        raise AssemblyError(f"Line {lineno}: undefined label '{token}'.")
    return labels[token]


def assemble_instructions(
    instructions: Sequence[ParsedInstruction], labels: dict[str, int]
) -> List[int]:
    words: List[int] = []
    for ins in instructions:
        args = ins.args
        mnemonic = ins.mnemonic

        if mnemonic in R_TYPE_MAP:
            if len(args) != 3:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected 3 operands for {mnemonic}."
                )
            rd = _parse_register(args[0], lineno=ins.lineno)
            rs1 = _parse_register(args[1], lineno=ins.lineno)
            rs2 = _parse_register(args[2], lineno=ins.lineno)
            funct3, funct7 = R_TYPE_MAP[mnemonic]
            words.append(_encode_r_type(rd, rs1, rs2, funct3, funct7, opcode=0b0110011))
            continue

        if mnemonic in I_TYPE_IMM_MAP:
            if len(args) != 3:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected 3 operands for {mnemonic}."
                )
            rd = _parse_register(args[0], lineno=ins.lineno)
            rs1 = _parse_register(args[1], lineno=ins.lineno)
            imm = _parse_imm(args[2], lineno=ins.lineno)
            funct3 = I_TYPE_IMM_MAP[mnemonic]
            words.append(_encode_i_type(rd, rs1, imm, funct3, opcode=0b0010011))
            continue

        if mnemonic in SHIFT_IMM_MAP:
            if len(args) != 3:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected 3 operands for {mnemonic}."
                )
            rd = _parse_register(args[0], lineno=ins.lineno)
            rs1 = _parse_register(args[1], lineno=ins.lineno)
            shamt = _parse_imm(args[2], lineno=ins.lineno)
            if shamt < 0 or shamt > 31:
                raise AssemblyError(f"Line {ins.lineno}: shift amount must be 0-31.")
            funct3, funct7 = SHIFT_IMM_MAP[mnemonic]
            imm = (funct7 << 5) | (shamt & 0x1F)
            words.append(_encode_i_type(rd, rs1, imm, funct3, opcode=0b0010011))
            continue

        if mnemonic in LOAD_MAP:
            if len(args) != 2:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected rd, offset(rs1) for {mnemonic}."
                )
            rd = _parse_register(args[0], lineno=ins.lineno)
            offset, rs1 = _parse_mem_operand(args[1], lineno=ins.lineno)
            funct3 = LOAD_MAP[mnemonic]
            words.append(_encode_i_type(rd, rs1, offset, funct3, opcode=0b0000011))
            continue

        if mnemonic in STORE_MAP:
            if len(args) != 2:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected rs2, offset(rs1) for {mnemonic}."
                )
            rs2 = _parse_register(args[0], lineno=ins.lineno)
            offset, rs1 = _parse_mem_operand(args[1], lineno=ins.lineno)
            funct3 = STORE_MAP[mnemonic]
            words.append(_encode_s_type(rs1, rs2, offset, funct3, opcode=0b0100011))
            continue

        if mnemonic in BRANCH_MAP:
            if len(args) != 3:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected rs1, rs2, label for {mnemonic}."
                )
            rs1 = _parse_register(args[0], lineno=ins.lineno)
            rs2 = _parse_register(args[1], lineno=ins.lineno)
            target = _resolve_label(args[2], labels, lineno=ins.lineno)
            offset = target - ins.address
            funct3 = BRANCH_MAP[mnemonic]
            words.append(_encode_b_type(rs1, rs2, offset, funct3, opcode=0b1100011))
            continue

        if mnemonic == "jal":
            if len(args) == 2:
                rd = _parse_register(args[0], lineno=ins.lineno)
                label_token = args[1]
            elif len(args) == 1:
                rd = 1  # default link register x1
                label_token = args[0]
            else:
                raise AssemblyError(
                    f"Line {ins.lineno}: invalid operand count for jal."
                )
            target = _resolve_label(label_token, labels, lineno=ins.lineno)
            offset = target - ins.address
            words.append(_encode_j_type(rd, offset, opcode=0b1101111))
            continue

        if mnemonic == "jalr":
            if len(args) != 3:
                raise AssemblyError(
                    f"Line {ins.lineno}: expected rd, rs1, imm for jalr."
                )
            rd = _parse_register(args[0], lineno=ins.lineno)
            rs1 = _parse_register(args[1], lineno=ins.lineno)
            imm = _parse_imm(args[2], lineno=ins.lineno)
            words.append(_encode_i_type(rd, rs1, imm, funct3=0b000, opcode=0b1100111))
            continue

        if mnemonic == "auipc":
            if len(args) != 2:
                raise AssemblyError(f"Line {ins.lineno}: expected rd, imm for auipc.")
            rd = _parse_register(args[0], lineno=ins.lineno)
            imm = _parse_imm(args[1], lineno=ins.lineno)
            words.append(_encode_u_type(rd, imm, opcode=0b0010111))
            continue

        if mnemonic == "lui":
            if len(args) != 2:
                raise AssemblyError(f"Line {ins.lineno}: expected rd, imm for lui.")
            rd = _parse_register(args[0], lineno=ins.lineno)
            imm = _parse_imm(args[1], lineno=ins.lineno)
            words.append(_encode_u_type(rd, imm, opcode=0b0110111))
            continue

        if mnemonic == "ebreak":
            if args:
                raise AssemblyError(f"Line {ins.lineno}: ebreak takes no operands.")
            words.append(EBREAK_ENCODING)
            continue

        if mnemonic == "ecall":
            if args:
                raise AssemblyError(f"Line {ins.lineno}: ecall takes no operands.")
            words.append(ECALL_ENCODING)
            continue

        raise AssemblyError(f"Line {ins.lineno}: unsupported mnemonic '{mnemonic}'.")

    return words


def assemble_lines(lines: Iterable[str]) -> List[int]:
    materialized = list(lines)
    instructions, labels = _collect_instructions(materialized)
    return assemble_instructions(instructions, labels)


def assemble_file(path: Path) -> List[int]:
    with path.open("r", encoding="utf-8") as asm_file:
        return assemble_lines(asm_file)


def write_hex(words: Iterable[int], path: Path) -> None:
    with path.open("w", encoding="utf-8") as dst:
        for word in words:
            dst.write(f"{word:08x}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asm_file", type=Path, help="Path to the .asm source file.")
    args = parser.parse_args()

    output_path = args.asm_file.with_suffix(".hex")
    try:
        words = assemble_file(args.asm_file)
    except AssemblyError as err:
        raise SystemExit(str(err)) from err

    write_hex(words, output_path)
    print(f"Wrote {output_path} ({len(words)} instructions).")


if __name__ == "__main__":
    main()
