"""Common structures and helpers for the Branch RV32I CPU."""

from assassyn.frontend import Bits, Record, UInt, concat

# -----------------------------------------------------------------------------
# Architectural constants
# -----------------------------------------------------------------------------

BTB_INDEX_BITS = 8
BTB_TAG_BITS = 32 - BTB_INDEX_BITS - 2
BTB_COUNTER_BITS = 2
BTB_ENTRY_BITS = 1 + BTB_TAG_BITS + 32 + BTB_COUNTER_BITS
SPEC_TAG_BITS = 8


def btb_index_bits(pc_value):
    """Return Bits(BTB_INDEX_BITS) slice for BTB indexing (PC[9:2])."""

    return pc_value[2 : 2 + BTB_INDEX_BITS - 1]


def btb_tag_bits(pc_value):
    """Return Bits(BTB_TAG_BITS) slice for BTB tag (PC[31:10])."""

    return pc_value[10 : 9 + BTB_TAG_BITS]


def pack_btb_entry(*, valid, tag, target_pc, counter):
    """Pack BTB entry fields into a single bit vector for SRAM storage."""

    return concat(valid, tag, target_pc, counter)


def unpack_btb_entry(entry_bits):
    """Unpack the BTB entry bit vector into its constituent fields."""

    counter_msb = BTB_COUNTER_BITS - 1
    counter = entry_bits[0:counter_msb]

    target_lsb = BTB_COUNTER_BITS
    target_msb = target_lsb + 32 - 1
    target_pc = entry_bits[target_lsb:target_msb]

    tag_lsb = target_msb + 1
    tag_msb = tag_lsb + BTB_TAG_BITS - 1
    tag = entry_bits[tag_lsb:tag_msb]

    valid = entry_bits[BTB_ENTRY_BITS - 1 : BTB_ENTRY_BITS - 1]
    return valid, tag, target_pc, counter


def init_counter(actual_taken):
    """Return weakly taken/not-taken counter initialization value."""

    weak_taken = Bits(BTB_COUNTER_BITS)(0b10)
    weak_not_taken = Bits(BTB_COUNTER_BITS)(0b01)
    return actual_taken.select(weak_taken, weak_not_taken)


def update_counter(counter, actual_taken):
    """Apply 2-bit saturating counter update toward taken/not-taken."""

    max_value = Bits(BTB_COUNTER_BITS)((1 << BTB_COUNTER_BITS) - 1)
    min_value = Bits(BTB_COUNTER_BITS)(0)
    counter_uint = counter.bitcast(UInt(BTB_COUNTER_BITS))
    incremented = (counter_uint + UInt(BTB_COUNTER_BITS)(1)).bitcast(Bits(BTB_COUNTER_BITS))
    decremented = (counter_uint - UInt(BTB_COUNTER_BITS)(1)).bitcast(Bits(BTB_COUNTER_BITS))
    toward_taken = (counter != max_value).select(incremented, counter)
    toward_not_taken = (counter != min_value).select(decremented, counter)
    return actual_taken.select(toward_taken, toward_not_taken)


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
    spec_tag=Bits(SPEC_TAG_BITS),
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


fetch_prediction = Record(
    btb_hit=Bits(1),
    counter=Bits(BTB_COUNTER_BITS),
    predict_taken=Bits(1),
    target_pc=Bits(32),
)
