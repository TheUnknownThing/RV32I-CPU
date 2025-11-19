from assassyn.frontend import *
from ..common import decoded_instr, AluOp, MemWidth

class Executor(Module):
    """Single-cycle execute stage with a Select1Hot ALU."""

    def __init__(self):
        super().__init__(ports={"instr": Port(decoded_instr), "pc_value": Port(Bits(32))})
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
    ):
        inst = self.instr.peek()
        pc_value = self.pc_value.peek()

        with Condition(inst.is_ebreak):
            x1_value = reg_file[Bits(5)(1)]
            log("toy-exec   | ebreak at pc: 0x{:08x}, x1=0x{:08x}", pc_value, x1_value)

        rs1_avail = reg_avail[inst.rs1]
        rs2_avail = inst.rs2_is_source.select(reg_avail[inst.rs2], Bits(1)(1))
        operands_ready = rs1_avail & rs2_avail
        with Condition(~operands_ready):
            log(
                "toy-exec   | hazard pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=x{:02} use_imm={} rs2_src={}",
                pc_value,
                inst.rd,
                inst.rs1,
                inst.rs2,
                inst.use_imm,
                inst.rs2_is_source,
            )

        wait_until(operands_ready)
        inst, pc_value = self.pop_all_ports(False)

        write_enable = inst.rd != Bits(5)(0)
        with Condition(write_enable):
            reg_avail[inst.rd] = Bits(1)(0)

        result, store_value = self._execute_alu(inst, reg_file)
        width_flags = self._decode_width(inst.mem_width)
        byte_offset, word_index = self._validate_memory_access(
            inst,
            result,
            data_offset,
            data_bytes,
            word_addr_width,
            width_flags,
        )
        current_word = dcache.dout[0].bitcast(Bits(32))
        new_word = self._prepare_store_word(
            inst,
            store_value,
            width_flags,
            current_word,
            byte_offset,
        )

        dcache.build(we=inst.is_store, re=inst.is_load, addr=word_index, wdata=new_word)

        log(
            "toy-exec   | pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=x{:02} load={} store={} res=0x{:08x}",
            pc_value,
            inst.rd,
            inst.rs1,
            inst.rs2,
            inst.is_load,
            inst.is_store,
            result,
        )

        memory.async_called(
            rd=inst.rd,
            exec_value=result,
            write_enable=write_enable,
            is_load=inst.is_load,
            is_store=inst.is_store,
            mem_width=inst.mem_width,
            mem_unsigned=inst.mem_unsigned,
            store_data=store_value,
            pc_value=pc_value,
            is_ebreak=inst.is_ebreak,
            byte_offset=byte_offset,
        )
    
    def _execute_alu(self, inst: Value, reg_file: Array):
        op_a = reg_file[inst.rs1]
        op_b = inst.use_imm.select(inst.imm, reg_file[inst.rs2])
        shamt = inst.use_shamt.select(inst.shamt, reg_file[inst.rs2][0:4])

        results = [Bits(32)(0)] * AluOp.COUNT
        results[AluOp.ADD] = (op_a.bitcast(Int(32)) + op_b.bitcast(Int(32))).bitcast(Bits(32))
        results[AluOp.SUB] = (op_a.bitcast(Int(32)) - op_b.bitcast(Int(32))).bitcast(Bits(32))
        results[AluOp.SLL] = op_a << shamt
        results[AluOp.SRL] = op_a >> shamt
        results[AluOp.SRA] = (op_a.bitcast(Int(32)) >> shamt.bitcast(Int(5))).bitcast(Bits(32))
        results[AluOp.AND] = op_a & op_b
        results[AluOp.OR] = op_a | op_b
        results[AluOp.XOR] = op_a ^ op_b
        results[AluOp.SLT] = (op_a.bitcast(Int(32)) < op_b.bitcast(Int(32))).select(Bits(32)(1), Bits(32)(0))
        results[AluOp.SLTU] = (op_a < op_b).select(Bits(32)(1), Bits(32)(0))

        result = inst.op_select.select1hot(*results)
        store_value = inst.rs2_is_source.select(reg_file[inst.rs2], Bits(32)(0))
        return result, store_value

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
        is_mem = inst.is_load | inst.is_store

        with Condition(is_mem & (addr_underflow | addr_overflow)):
            upper = data_offset + data_bytes
            log(
                "toy-memacc | addr 0x{:08x} outside data memory [0x{:08x}, 0x{:08x})",
                result,
                Bits(32)(data_offset & 0xFFFFFFFF),
                Bits(32)(upper & 0xFFFFFFFF),
            )
            assume(Bits(1)(0))

        byte_offset = rel_bits[0:1]
        half_unaligned = width_half & byte_offset[0:0]
        word_unaligned = width_word & (byte_offset != Bits(2)(0))
        with Condition(is_mem & (half_unaligned | word_unaligned)):
            log("toy-memacc | misaligned addr=0x{:08x} width={}", result, inst.mem_width)
            assume(Bits(1)(0))

        upper_bit = 2 + max(word_addr_width - 1, 0)
        word_index = is_mem.select(rel_bits[2:upper_bit], Bits(word_addr_width)(0))
        return byte_offset, word_index

    def _prepare_store_word(
        self,
        inst: Value,
        store_value: Value,
        width_flags: tuple[Value, Value, Value],
        current_word: Value,
        byte_offset: Value,
    ) -> Value:
        width_byte, width_half, _ = width_flags
        shift_amount = self._byte_shift(byte_offset)
        store_mask = Bits(32)(0xFFFFFFFF)
        store_mask = width_half.select(Bits(32)(0x0000FFFF), store_mask)
        store_mask = width_byte.select(Bits(32)(0x000000FF), store_mask)
        mask_shifted = store_mask << shift_amount
        store_payload = (store_value & store_mask) << shift_amount

        word_value = current_word
        new_word = (word_value & ~mask_shifted) | store_payload
        return inst.is_store.select(new_word, Bits(32)(0))

    def _byte_shift(self, offset: Value) -> Value:
        shift = Bits(5)(0)
        shift = (offset == Bits(2)(1)).select(Bits(5)(8), shift)
        shift = (offset == Bits(2)(2)).select(Bits(5)(16), shift)
        shift = (offset == Bits(2)(3)).select(Bits(5)(24), shift)
        return shift
