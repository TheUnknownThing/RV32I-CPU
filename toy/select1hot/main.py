"""A toy RV32I Select1Hot CPU supporting the arithmetic subset."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from assassyn.frontend import *
from assassyn.backend import *
from assassyn import utils

from .decode import decode_instruction
from .common import AluOp, decoded_instr
from .program import normalize_program, write_program_image


class Fetcher(Module):
    """Maintains the program counter."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Fetcher"

    @module.combinational
    def build(self, depth_log: int, decoder: Module):
        pc_reg = RegArray(Bits(32), 1, initializer=[0])
        pc_value = pc_reg[0]
        addr_bits = pc_value[2 : 2 + depth_log]
        pc_addr = addr_bits.bitcast(Int(depth_log))

        log("toy-fetch  | pc=0x{:08x}", pc_value)

        decoder.async_called(pc_value=pc_value)

        next_pc = (pc_value.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        pc_reg[0] = next_pc

        return pc_reg, pc_addr


class Decoder(Module):
    """Decodes all arithmetic RV32I instructions."""

    def __init__(self):
        super().__init__(ports={"pc_value": Port(Bits(32))})
        self.name = "Decoder"

    @module.combinational
    def build(self, executor: Module, rdata: RegArray):
        pc_value = self.pop_all_ports(False)
        raw_inst = rdata[0].bitcast(Bits(32))
        inst = decode_instruction(raw_inst)
        log(
            "toy-decode | pc=0x{:08x} rd=x{:02} rs1=x{:02} op=0x{:03x}",
            pc_value,
            inst.rd,
            inst.rs1,
            inst.op_select,
        )

        exec_call = executor.async_called(inst=inst, pc_value=pc_value)
        exec_call.bind.set_fifo_depth(inst=2)


class Executor(Module):
    """Single-cycle execute stage with a select1hot ALU."""

    def __init__(self):
        super().__init__(ports={"inst": Port(decoded_instr), "pc_value": Port(Bits(32))})
        self.name = "Executor"

    @module.combinational
    def build(
        self,
        reg_file: Array,
        reg_avail: Array,
        wb: Module,
    ):
        inst = self.inst.peek()
        pc_value = self.pc_value.peek()

        with Condition(inst.is_ebreak):
            x1_value = reg_file[Bits(5)(1)]
            log("toy-exec   | ebreak at pc: 0x{:08x}, x1=0x{:08x}", pc_value, x1_value)
            finish()

        rs1_avail = reg_avail[inst.rs1]
        rs2_avail = inst.use_imm.select(Bits(1)(1), reg_avail[inst.rs2])
        operands_ready = rs1_avail & rs2_avail

        with Condition(~operands_ready):
            log(
                "toy-exec   | hazard pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=0x{:02x} use_imm={}",
                pc_value,
                inst.rd,
                inst.rs1,
                inst.rs2,
                inst.use_imm,
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

        log(
            "toy-exec   | pc:0x{:08x} rd=x{:02} rs1=x{:02} rs2=0x{:02x} use_imm={} res=0x{:08x}",
            pc_value,
            inst.rd,
            inst.rs1,
            inst.rs2,
            inst.use_imm,
            result,
        )

        wb.async_called(
            rd=inst.rd,
            value=result,
            enable=write_enable,
        )


class WriteBack(Module):
    """Writes execution results into the register file."""

    def __init__(self):
        super().__init__(
            ports={
                "rd": Port(Bits(5)),
                "value": Port(Bits(32)),
                "enable": Port(Bits(1)),
            }
        )
        self.name = "WriteBack"

    @module.combinational
    def build(self, reg_file: Array, reg_avail: Array):
        rd, value, enable = self.pop_all_ports(False)
        reg_avail[rd] = Bits(1)(1)

        with Condition(enable):
            reg_file[rd] = value
            log("toy-wb     | x{:02} <= 0x{:08x}", rd, value)


class Driver(Module):
    """Stops the simulation when PC leaves program image."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Driver"

    @module.combinational
    def build(
        self,
        pc: Array,
        program_words: int,
        fetcher: Module,
    ):
        remaining_fetches = RegArray(Bits(32), 1, initializer=[program_words])
        remaining = remaining_fetches[0]
        has_remaining = remaining.bitcast(Int(32)) > Int(32)(0)

        with Condition(has_remaining):
            fetcher.async_called()
            next_remaining = (remaining.bitcast(Int(32)) - Int(32)(1)).bitcast(Bits(32))
            remaining_fetches[0] = next_remaining

        return has_remaining


DEFAULT_WORKSPACE = Path(__file__).with_name(".workspace")


def build_cpu(
    program: Sequence[int] | Iterable[int] | Path | str | None = None,
    *,
    depth_log: int = 4,
    workspace: Path | str | None = None,
):
    """Build and elaborate the Select1Hot toy CPU."""

    program_words = normalize_program(program)
    if depth_log <= 0:
        raise ValueError("depth_log must be positive.")
    depth = 1 << depth_log
    if len(program_words) > depth:
        raise ValueError(f"Program has {len(program_words)} words, exceeds instruction memory depth {depth}.")

    workspace_path = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE
    program_image = write_program_image(program_words, workspace_path)

    sys = SysBuilder("ToySelect1HotCPU")

    with sys:
        fetcher = Fetcher()
        decoder = Decoder()
        pc_reg, pc_addr = fetcher.build(depth_log=depth_log, decoder=decoder)

        reg_file = RegArray(Bits(32), 32, initializer=[0] * 32)
        reg_avail = RegArray(Bits(1), 32, initializer=[1] * 32)

        executor = Executor()
        writeback = WriteBack()
        driver = Driver()

        icache = SRAM(width=32, depth=depth, init_file=str(program_image))
        icache.name = "toy_select1hot_icache"
        icache.build(
            we=Bits(1)(0),
            re=Bits(1)(1),
            addr=pc_addr,
            wdata=Bits(32)(0),
        )

        decoder.build(executor=executor, rdata=icache.dout)
        executor.build(
            reg_file=reg_file,
            reg_avail=reg_avail,
            wb=writeback,
        )
        writeback.build(reg_file=reg_file, reg_avail=reg_avail)

        driver.build(
            pc=pc_reg,
            program_words=len(program_words),
            fetcher=fetcher,
        )

        sys.expose_on_top(reg_file, kind="Output")
        sys.expose_on_top(pc_reg, kind="Output")

    print(sys)
    conf = config(
        verilog=utils.has_verilator(),
        sim_threshold=256,
        idle_threshold=256,
        resource_base=str(workspace_path),
        fifo_depth=1,
    )

    simulator_path, verilog_path = elaborate(sys, **conf)
    print("Building simulator binary...")
    simulator_binary = utils.build_simulator(simulator_path)
    print(f"Simulator binary built: {simulator_binary}")
    return sys, simulator_binary, verilog_path


def run_select1hot_cpu(program: Sequence[int] | Iterable[int] | Path | str | None = None, **kwargs):
    """Convenience wrapper that builds and runs the Select1Hot CPU."""

    sys, simulator_binary, verilog_path = build_cpu(program, **kwargs)
    sim_output = utils.run_simulator(binary_path=simulator_binary)
    return sim_output, verilog_path


if __name__ == "__main__":
    sys, simulator_binary, verilog_path = build_cpu()
    print("Toy Select1Hot CPU built successfully!")
