from assassyn.frontend import *
from ..common import (
    btb_index_bits,
    btb_tag_bits,
    decoded_instr,
    AluOp,
    MemWidth,
    BranchCond,
    SPEC_TAG_BITS,
    fetch_prediction,
    init_counter,
    pack_btb_entry,
    update_counter,
)


class Executor(Module):
    """Single-cycle execute stage with BTB feedback."""

    def __init__(self):
        super().__init__(
            ports={
                "inst": Port(decoded_instr),
                "pc_value": Port(Bits(32)),
                "branch_meta": Port(fetch_prediction),
            }
        )
        self.name = "Executor"

    @module.combinational
    def build(
        self,
        reg_file: Array,
        reg_avail: Array,
        memory: Module,
        dcache: Module,
        data_offset: int,
        data_bytes: int,
        word_addr_width: int,
        on_hazard: Array,
        branch_mispredict: Array,
        correct_pc: Array,
        btb_write_enable: Array,
        btb_write_index: Array,
        btb_write_data: Array,
        spec_tag: Array,
        exec_bypass_reg: Array,
        exec_bypass_data: Array,
        mem_bypass_reg: Array,
        mem_bypass_data: Array,
    ):
        inst_peek = self.inst.peek()
        pc_peek = self.pc_value.peek()
        current_tag = spec_tag[0]
        stale = inst_peek.spec_tag != current_tag

        with Condition(stale):
            log(
                "branch-exec | drop stale pc:0x{:08x} inst_tag=0x{:02x} curr_tag=0x{:02x}",
                pc_peek,
                inst_peek.spec_tag,
                current_tag,
            )

        with Condition(~stale & inst_peek.is_ebreak):
            x1_value = reg_file[Bits(5)(1)]
            log("naive-exec | ebreak at pc: 0x{:08x}, x1=0x{:08x}", pc_peek, x1_value)

        exec_bypass_valid = exec_bypass_reg[0] != Bits(5)(0)
        mem_bypass_valid = mem_bypass_reg[0] != Bits(5)(0)
        rs1_exec_ready = exec_bypass_valid & (exec_bypass_reg[0] == inst_peek.rs1)
        rs1_mem_ready = mem_bypass_valid & (mem_bypass_reg[0] == inst_peek.rs1)
        rs2_exec_ready = exec_bypass_valid & (exec_bypass_reg[0] == inst_peek.rs2)
        rs2_mem_ready = mem_bypass_valid & (mem_bypass_reg[0] == inst_peek.rs2)
        rs1_avail = inst_peek.rs1_is_source.select(
            reg_avail[inst_peek.rs1] | rs1_exec_ready | rs1_mem_ready,
            Bits(1)(1),
        )
        rs2_avail = inst_peek.rs2_is_source.select(
            reg_avail[inst_peek.rs2] | rs2_exec_ready | rs2_mem_ready,
            Bits(1)(1),
        )
        operands_ready = rs1_avail & rs2_avail
        operands_ready = stale.select(Bits(1)(1), operands_ready)
        with Condition(~operands_ready & ~stale):
            on_hazard[0] = Bits(1)(1)
            log(
                "naive-exec | hazard pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=x{:02} use_imm={} rs2_src={}",
                pc_peek,
                inst_peek.rd,
                inst_peek.rs1,
                inst_peek.rs2,
                inst_peek.use_imm,
                inst_peek.rs2_is_source,
            )

        wait_until(operands_ready)
        on_hazard[0] = Bits(1)(0)
        inst, pc_value, branch_meta = self.pop_all_ports(False)

        valid_inst = ~stale
        inst_is_load = inst.is_load & valid_inst
        inst_is_store = inst.is_store & valid_inst
        inst_is_branch = inst.is_branch & valid_inst
        inst_is_jump = inst.is_jump & valid_inst
        inst_is_jal = inst.is_jal & valid_inst
        inst_is_jalr = inst.is_jalr & valid_inst
        inst_is_ebreak = inst.is_ebreak & valid_inst

        write_enable = valid_inst & (inst.rd != Bits(5)(0))
        with Condition(write_enable):
            reg_avail[inst.rd] = Bits(1)(0)

        exec_bypass_valid = exec_bypass_reg[0] != Bits(5)(0)
        mem_bypass_valid = mem_bypass_reg[0] != Bits(5)(0)
        rs1_exec_match = exec_bypass_valid & (exec_bypass_reg[0] == inst.rs1)
        rs1_mem_match = mem_bypass_valid & (mem_bypass_reg[0] == inst.rs1)
        rs2_exec_match = exec_bypass_valid & (exec_bypass_reg[0] == inst.rs2)
        rs2_mem_match = mem_bypass_valid & (mem_bypass_reg[0] == inst.rs2)
        rs1_value = inst.rs1_is_source.select(
            rs1_exec_match.select(
                exec_bypass_data[0],
                rs1_mem_match.select(mem_bypass_data[0], reg_file[inst.rs1]),
            ),
            Bits(32)(0),
        )
        rs2_value = inst.rs2_is_source.select(
            rs2_exec_match.select(
                exec_bypass_data[0],
                rs2_mem_match.select(mem_bypass_data[0], reg_file[inst.rs2]),
            ),
            Bits(32)(0),
        )
        result, store_value = self._execute_alu(inst, rs1_value, rs2_value, pc_value)
        width_flags = self._decode_width(inst.mem_width)
        byte_offset, word_index = self._validate_memory_access(
            inst,
            result,
            data_offset,
            data_bytes,
            word_addr_width,
            width_flags,
            inst_is_load,
            inst_is_store,
        )
        new_word = self._prepare_store_word(
            inst,
            store_value,
            width_flags,
            dcache,
            word_index,
            byte_offset,
            inst_is_store,
        )

        dcache.build(we=inst_is_store, re=inst_is_load, addr=word_index, wdata=new_word)

        with Condition(valid_inst):
            log(
                "naive-exec | pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=x{:02} load={} store={} res=0x{:08x}",
                pc_value,
                inst.rd,
                inst.rs1,
                inst.rs2,
                inst.is_load,
                inst.is_store,
                result,
            )

        branch_taken = self._evaluate_branch(inst.branch_cond, rs1_value, rs2_value)
        pc_plus_4 = (pc_value.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        branch_target_value = (
            (pc_value.bitcast(Int(32)) + inst.imm.bitcast(Int(32))).bitcast(Bits(32))
        )
        jal_target = (
            (pc_value.bitcast(Int(32)) + inst.imm.bitcast(Int(32))).bitcast(Bits(32))
        )
        jalr_target = (
            (rs1_value.bitcast(Int(32)) + inst.imm.bitcast(Int(32))).bitcast(Bits(32))
            & Bits(32)(0xFFFFFFFE)
        )
        jump_target = inst_is_jal.select(jal_target, Bits(32)(0))
        jump_target = inst_is_jalr.select(jalr_target, jump_target)
        control_target = inst_is_jump.select(jump_target, branch_target_value)

        actual_taken_branch = inst_is_branch & branch_taken
        actual_taken = inst_is_jump | actual_taken_branch
        predicted_taken = branch_meta.predict_taken
        predicted_pc = predicted_taken.select(branch_meta.target_pc, pc_plus_4)
        correct_pc_value = actual_taken.select(control_target, pc_plus_4)

        target_mismatch = actual_taken & predicted_taken & (control_target != branch_meta.target_pc)
        direction_mismatch = actual_taken != predicted_taken
        control_op = inst_is_branch | inst_is_jump
        mispredict = control_op & (direction_mismatch | target_mismatch)

        with Condition(mispredict):
            branch_mispredict[0] = Bits(1)(1)
            correct_pc[0] = correct_pc_value
            next_tag_uint = spec_tag[0].bitcast(UInt(SPEC_TAG_BITS)) + UInt(SPEC_TAG_BITS)(1)
            spec_tag[0] = next_tag_uint.bitcast(Bits(SPEC_TAG_BITS))

        btb_write_index_bits = btb_index_bits(pc_value)
        btb_write_tag = btb_tag_bits(pc_value)
        next_counter = branch_meta.btb_hit.select(
            update_counter(branch_meta.counter, actual_taken),
            init_counter(actual_taken),
        )
        btb_payload = pack_btb_entry(
            valid=Bits(1)(1),
            tag=btb_write_tag,
            target_pc=control_target,
            counter=next_counter,
        )
        need_btb_write = control_op & ((~branch_meta.btb_hit) | mispredict)
        with Condition(need_btb_write):
            btb_write_enable[0] = Bits(1)(1)
            btb_write_index[0] = btb_write_index_bits
            btb_write_data[0] = btb_payload

        with Condition(inst_is_branch):
            log(
                "branch-exec | pc:0x{:08x} taken={} predicted={} target=0x{:08x} pred_pc=0x{:08x}",
                pc_value,
                branch_taken,
                predicted_taken,
                branch_target_value,
                predicted_pc,
            )

        with Condition(inst_is_jump):
            log(
                "branch-jump  | pc:0x{:08x} jal={} jalr={} target=0x{:08x}",
                pc_value,
                inst.is_jal,
                inst.is_jalr,
                jump_target,
            )
        
        with Condition(write_enable & inst.is_alu_instr):
            log(
                "naive-exec | bypass rd=x{:02} value=0x{:08x}",
                inst.rd,
                result,
            )
            exec_bypass_reg[0] = inst.rd
            exec_bypass_data[0] = result
        
        with Condition(~(write_enable & inst.is_alu_instr)):
            exec_bypass_reg[0] = Bits(5)(0)
            exec_bypass_data[0] = Bits(32)(0)

        memory.async_called(
            rd=inst.rd,
            exec_value=result,
            write_enable=write_enable,
            is_load=inst_is_load,
            is_store=inst_is_store,
            mem_width=inst.mem_width,
            mem_unsigned=inst.mem_unsigned,
            store_data=store_value,
            pc_value=pc_value,
            is_ebreak=inst_is_ebreak,
            byte_offset=byte_offset,
        )

    def _execute_alu(self, inst: Value, rs1_value: Value, rs2_value: Value, pc_value: Value):
        op_a = rs1_value
        op_b = inst.use_imm.select(inst.imm, rs2_value)
        shamt = inst.use_shamt.select(inst.shamt, rs2_value[0:4])

        results = [Bits(32)(0)] * AluOp.COUNT
        results[AluOp.ADD] = (op_a.bitcast(Int(32)) + op_b.bitcast(Int(32))).bitcast(Bits(32))
        results[AluOp.SUB] = (op_a.bitcast(Int(32)) - op_b.bitcast(Int(32))).bitcast(Bits(32))
        results[AluOp.SLL] = op_a << shamt
        results[AluOp.SRL] = op_a >> shamt
        results[AluOp.SRA] = (op_a.bitcast(Int(32)) >> shamt.bitcast(Int(5))).bitcast(Bits(32))
        results[AluOp.AND] = op_a & op_b
        results[AluOp.OR] = op_a | op_b
        results[AluOp.XOR] = op_a ^ op_b
        results[AluOp.SLT] = (op_a.bitcast(Int(32)) < op_b.bitcast(Int(32))).select(
            Bits(32)(1), Bits(32)(0)
        )
        results[AluOp.SLTU] = (op_a < op_b).select(Bits(32)(1), Bits(32)(0))

        result = inst.op_select.select1hot(*results)
        pc_plus_4 = (pc_value.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        result = inst.is_jump.select(pc_plus_4, result)
        auipc_value = (pc_value.bitcast(Int(32)) + inst.imm.bitcast(Int(32))).bitcast(Bits(32))
        result = inst.is_auipc.select(auipc_value, result)
        result = inst.is_lui.select(inst.imm, result)

        store_value = inst.rs2_is_source.select(rs2_value, Bits(32)(0))
        return result, store_value

    def _evaluate_branch(self, branch_cond: Value, rs1_value: Value, rs2_value: Value) -> Value:
        eq = rs1_value == rs2_value
        lt = rs1_value.bitcast(Int(32)) < rs2_value.bitcast(Int(32))
        ltu = rs1_value < rs2_value
        conds = [
            eq,
            ~eq,
            lt,
            ~lt,
            ltu,
            ~ltu,
        ]
        return branch_cond.select1hot(*conds)

    def _decode_width(self, mem_width: Value):
        width_half = mem_width == Bits(2)(MemWidth.HALF)
        width_word = mem_width == Bits(2)(MemWidth.WORD)
        width_byte = mem_width == Bits(2)(MemWidth.BYTE)
        return width_byte, width_half, width_word

    def _validate_memory_access(
        self,
        inst: Value,
        result: Value,
        data_offset: int,
        data_bytes: int,
        word_addr_width: int,
        width_flags: tuple[Value, Value, Value],
        inst_is_load: Value,
        inst_is_store: Value,
    ):
        width_byte, width_half, width_word = width_flags
        addr_uint = result.bitcast(UInt(32))
        base_uint = UInt(32)(data_offset & 0xFFFFFFFF)
        rel_uint = addr_uint - base_uint
        rel_bits = rel_uint.bitcast(Bits(32))

        total_bytes = UInt(32)(data_bytes)
        bytes_needed = UInt(32)(1)
        bytes_needed = width_half.select(UInt(32)(2), bytes_needed)
        bytes_needed = width_word.select(UInt(32)(4), bytes_needed)
        end_addr = rel_uint + bytes_needed

        addr_underflow = addr_uint < base_uint
        addr_overflow = end_addr > total_bytes
        is_mem = inst_is_load | inst_is_store

        with Condition(is_mem & (addr_underflow | addr_overflow)):
            upper = data_offset + data_bytes
            log(
                "naive-mem   | addr 0x{:08x} outside data memory [0x{:08x}, 0x{:08x})",
                result,
                Bits(32)(data_offset & 0xFFFFFFFF),
                Bits(32)(upper & 0xFFFFFFFF),
            )
            assume(Bits(1)(0))

        byte_offset = rel_bits[0:1]
        half_unaligned = width_half & byte_offset[0:0]
        word_unaligned = width_word & (byte_offset != Bits(2)(0))
        with Condition(is_mem & (half_unaligned | word_unaligned)):
            log("naive-mem   | misaligned addr=0x{:08x} width={}", result, inst.mem_width)
            assume(Bits(1)(0))

        upper_bit = 2 + max(word_addr_width - 1, 0)
        word_index = is_mem.select(rel_bits[2:upper_bit], Bits(word_addr_width)(0))
        return byte_offset, word_index

    def _prepare_store_word(
        self,
        inst: Value,
        store_value: Value,
        width_flags: tuple[Value, Value, Value],
        dcache: Module,
        word_index: Value,
        byte_offset: Value,
        store_active: Value,
    ) -> Value:
        width_byte, width_half, _ = width_flags
        shift_amount = self._byte_shift(byte_offset)
        store_mask = Bits(32)(0xFFFFFFFF)
        store_mask = width_half.select(Bits(32)(0x0000FFFF), store_mask)
        store_mask = width_byte.select(Bits(32)(0x000000FF), store_mask)
        mask_shifted = store_mask << shift_amount
        store_payload = (store_value & store_mask) << shift_amount

        word_value = dcache._payload[word_index].bitcast(Bits(32))
        new_word = (word_value & ~mask_shifted) | store_payload
        return store_active.select(new_word, Bits(32)(0))

    def _byte_shift(self, offset: Value) -> Value:
        shift = Bits(5)(0)
        shift = (offset == Bits(2)(1)).select(Bits(5)(8), shift)
        shift = (offset == Bits(2)(2)).select(Bits(5)(16), shift)
        shift = (offset == Bits(2)(3)).select(Bits(5)(24), shift)
        return shift
