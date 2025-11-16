from assassyn.frontend import *
from ..common import decoded_instr, AluOp

class Executor(Module):
    """Single-cycle execute stage with a Select1Hot ALU."""

    def __init__(self):
        super().__init__(ports={"inst": Port(decoded_instr), "pc_value": Port(Bits(32))})
        self.name = "Executor"

    @module.combinational
    def build(self, reg_file: Array, reg_avail: Array, memory: Module):
        inst = self.inst.peek()
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
            # the below 3 values are passed to wb, but first we need to pass it to memory
            rd=inst.rd, 
            exec_value=result,
            write_enable=write_enable,
            is_load=inst.is_load,
            is_store=inst.is_store,
            mem_width=inst.mem_width,
            mem_unsigned=inst.mem_unsigned,
            store_data=store_value,
            pc_value=pc_value,
            is_ebreak=inst.is_ebreak, # handle ebreak at wb
        )