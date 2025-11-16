"""Decode helpers for the toy Select1Hot CPU."""

from __future__ import annotations

from assassyn.frontend import *

from ..common import AluOp, MemWidth, decoded_instr

OPCODE_OP = 0b0110011
OPCODE_OPIMM = 0b0010011
OPCODE_LOAD = 0b0000011
OPCODE_STORE = 0b0100011
FUNCT7_SUB_SRA = 0b0100000
EBREAK_ENCODING = 0x00100073

class Decoder(Module):
    """Decodes RV32I instructions into the compact bundle used downstream."""

    def __init__(self):
        super().__init__(ports={"pc_value": Port(Bits(32))})
        self.name = "Decoder"

    @module.combinational
    def build(self, executor: Module, rdata: RegArray):
        pc_value = self.pop_all_ports(False)
        raw_inst = rdata[0].bitcast(Bits(32))
        inst = _decode_instruction(raw_inst)
        log(
            "toy-decode | pc=0x{:08x} rd=x{:02} rs1=x{:02} rs2=x{:02} load={} store={}",
            pc_value,
            inst.rd,
            inst.rs1,
            inst.rs2,
            inst.is_load,
            inst.is_store,
        )

        exec_call = executor.async_called(inst=inst, pc_value=pc_value)
        exec_call.bind.set_fifo_depth(inst=2)


def _sign_extend_bits(value: Value, width: int, target: int = 32) -> Value:
    if width == target:
        return value
    pad_width = target - width
    msb = value[width - 1 : width - 1]
    pad = msb.select(Bits(pad_width)((1 << pad_width) - 1), Bits(pad_width)(0))
    return concat(pad, value)


def _decode_instruction(instr: Value) -> Value:
    """Decode a raw 32-bit instruction into the decoded_instr bundle."""

    opcode = instr[0:6]
    rd = instr[7:11]
    funct3 = instr[12:14]
    rs1 = instr[15:19]
    rs2 = instr[20:24]
    funct7 = instr[25:31]
    imm_i = _sign_extend_bits(instr[20:31], 12)
    shamt = instr[20:24]
    imm_upper = instr[25:31]
    imm_store = _sign_extend_bits(concat(instr[25:31], instr[7:11]), 12)

    is_op = opcode == Bits(7)(OPCODE_OP)
    is_op_imm = opcode == Bits(7)(OPCODE_OPIMM)
    is_load = opcode == Bits(7)(OPCODE_LOAD)
    is_store = opcode == Bits(7)(OPCODE_STORE)

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

    is_lb = is_load & funct3_eq[0b000]
    is_lh = is_load & funct3_eq[0b001]
    is_lw = is_load & funct3_eq[0b010]
    is_lbu = is_load & funct3_eq[0b100]
    is_lhu = is_load & funct3_eq[0b101]

    is_sb = is_store & funct3_eq[0b000]
    is_sh = is_store & funct3_eq[0b001]
    is_sw = is_store & funct3_eq[0b010]

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
        | is_lb
        | is_lh
        | is_lw
        | is_lbu
        | is_lhu
        | is_sb
        | is_sh
        | is_sw
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
    use_imm = use_imm | is_load | is_store
    use_shamt = is_slli | is_srli | is_srai

    mem_width = Bits(2)(0)
    mem_width = (is_lb | is_lbu | is_sb).select(Bits(2)(MemWidth.BYTE), mem_width)
    mem_width = (is_lh | is_lhu | is_sh).select(Bits(2)(MemWidth.HALF), mem_width)
    mem_width = (is_lw | is_sw).select(Bits(2)(MemWidth.WORD), mem_width)

    mem_unsigned = (is_lbu | is_lhu).select(Bits(1)(1), Bits(1)(0))

    imm = is_store.select(imm_store, imm_i)
    rs2_is_source = is_op | is_store

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
    op_select = (is_load | is_store).select(mask(AluOp.ADD), op_select)

    # why? because if we encounter an ebreak, there are no 1-hot instructions.
    # this line does not select a valid ALU operation, but it keeps Select1Hot happy.
    op_select = is_ebreak.select(mask(AluOp.ADD), op_select) 

    rd_value = is_store.select(Bits(5)(0), rd)

    log(
        "toy-decode | rd=x{:02} rs1=x{:02} rs2=x{:02} load={} store={} memw={} uns={} op=0x{:03x}",
        rd_value,
        rs1,
        rs2,
        is_load,
        is_store,
        mem_width,
        mem_unsigned,
        op_select,
    )

    return decoded_instr.bundle(
        rs1=rs1,
        rs2=rs2,
        rd=rd_value,
        imm=imm,
        shamt=shamt,
        op_select=op_select,
        use_imm=use_imm,
        use_shamt=use_shamt,
        is_ebreak=is_ebreak,
        rs2_is_source=rs2_is_source,
        is_load=is_load,
        is_store=is_store,
        mem_width=mem_width,
        mem_unsigned=mem_unsigned,
    )
