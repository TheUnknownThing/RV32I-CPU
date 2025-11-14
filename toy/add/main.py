"""A tiny ADD/ADDI-only RV32I core built with Assassyn.

The goal of this example is to provide the smallest possible pipeline that still
touches all major pieces of an Assassyn design: fetch, decode, execute and
writeback.  All instruction-format helpers and the software golden model live in
`toy.add.program`, keeping this file focused solely on Assassyn semantics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from assassyn.frontend import *
from assassyn.backend import *
from assassyn import utils

from decode import decode_instruction
from common import decoded_instr
from program import normalize_program, write_program_image


class Fetcher(Module):
    """Holds the program counter."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Fetcher"

    @module.combinational
    def build(self, depth_log: int):
        # TODO: implement fetch logic
        # Remember we need to consider RAW hazards
        pass


class Decoder(Module):
    """Minimal ADD/ADDI decoder that produces a compact bundle."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Decoder"

    @module.combinational
    def build(self, executor: Module, rdata: RegArray):
        raw_inst = rdata[0].pop_all_ports(False)
        inst = decode_instruction(raw_inst)
        log("toy-decode | decoded inst: rd=x{:02}, rs1=x{:02}, rs2=x{:02}, is_addi={}", inst.rd, inst.rs1, inst.rs2, inst.is_addi)

        executor.async_called(inst = inst)

        # no return, because no wire to expose

class Executor(Module):
    """Single-cycle execution stage with a single adder."""

    def __init__(self):
        super().__init__(ports={"inst": Port(decoded_instr)})
        self.name = "Executor"

    @module.combinational
    def build(self, reg_file: Array, reg_avail: Value, wb: Module):
        inst = self.inst.peek()
        avail = reg_avail.bitcast(Bits(32))

        # hazard check: source registers must be available. For ADDI rs2 is an
        # immediate so it is always available.
        rs1_avail = avail[inst.rs1]
        rs2_avail = inst.is_addi.select(Bits(1)(1), avail[inst.rs2])

        with Condition(~(rs1_avail & rs2_avail)):
            log(
                "toy-exec   | hazard detected for inst rd=x{:02}, rs1=x{:02}, rs2/ximm=x{:02}, is_addi={}",
                inst.rd,
                inst.rs1,
                inst.rs2,
                inst.is_addi,
            )

        valid = rs1_avail & rs2_avail
        wait_until(valid)

        # execution
        op_a = reg_file[inst.rs1]

        imm32 = inst.rs2.bitcast(Bits(32))
        op_b = inst.is_addi.select(imm32, reg_file[inst.rs2])

        # TODO: implement ebreak instruction to finish simulation
        # finish = ...
        finished = False
        with Condition(finished):
            log('Finish Simulation')
            finish()

        result = (op_a.bitcast(Int(32)) + op_b.bitcast(Int(32))).bitcast(Bits(32))

        log(
            "toy-exec   | rd: x{:02} | a: 0x{:08x} | b: 0x{:08x} | res: 0x{:08x} | is_addi={}",
            inst.rd,
            op_a,
            op_b,
            result,
            inst.is_addi,
        )

        # disable writes to x0
        write_enable = (inst.rd != Bits(5)(0))

        wb.async_called(
            rd=inst.rd,
            value=result,
            enable=write_enable,
        )

        # seems that we do not need to return either


class WriteBack(Module):
    """Writes execution results into the architectural register file."""

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
    def build(self, reg_file: Array, reg_avail: Value):
        rd, value, enable = self.pop_all_ports(False)
        do_write = enable
        reg_avail[rd] = do_write # mark register as available

        with Condition(do_write):
            reg_file[rd] = value
            log("toy-wb     | x{:02} <= 0x{:08x}", rd, value)


# TODO: fix Driver to read instruction properly
class Driver(Module):
    """Stops the simulation once the program counter leaves the program image."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Driver"

    @module.combinational
    def build(self, pc: Array, program_words: int):
        pass


DEFAULT_WORKSPACE = Path(__file__).with_name(".workspace")


def build_cpu(
    program: Sequence[int] | Iterable[int] | Path | str | None = None,
    *,
    depth_log: int = 4,
    workspace: Path | str | None = None,
):
    """Build and elaborate the ADD/ADDI toy CPU.

    Args:
        program: Iterable of 32-bit instruction words or a path to a hex file.
        depth_log: log2(depth) of the instruction memory SRAM.
        workspace: Directory used for temporary program images and simulator
            outputs. Falls back to `toy/add/.workspace`.
    """

    program_words = normalize_program(program)
    if depth_log <= 0:
        raise ValueError("depth_log must be positive.")
    depth = 1 << depth_log

    # TODO: validate the write_program_image function
    workspace_path = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE
    program_image = write_program_image(program_words, workspace_path)

    sys = SysBuilder("Toy ADD CPU")

    with sys:
        fetcher = Fetcher()
        pc_reg, pc_value, pc_addr = fetcher.build(depth_log=depth_log)

        reg_file = RegArray(Bits(32), 32, initializer=[0] * 32)
        reg_avail = Bits(32)((1 << 32) - 1) 

        decoder = Decoder()
        executor = Executor()
        writeback = WriteBack()
        driver = Driver()

        icache = SRAM(width=32, depth=depth, init_file=str(program_image))
        icache.name = "toy_icache"
        icache.build(
            we=Bits(1)(0),
            re=Bits(1)(1),
            addr=pc_addr,
            wdata=Bits(32)(0),
        )

        decoder.build(executor=executor, rdata=icache.rdata)
        executor.build(reg_file=reg_file, reg_avail=reg_avail, wb=writeback)
        writeback.build(reg_file=reg_file, reg_avail=reg_avail)

        # TODO: fix driver build
        driver.build(pc=pc_reg, program_words=len(program_words))

        sys.expose_on_top(reg_file, kind="Output")
        sys.expose_on_top(pc_reg, kind="Output")

    print(sys)
    conf = config(
        verilog=utils.has_verilator(),
        sim_threshold=1024,
        idle_threshold=1024,
        resource_base=str(workspace_path),
        fifo_depth=1,
    )

    simulator_path, verilog_path = elaborate(sys, **conf)
    print("Building simulator binary...")
    simulator_binary = utils.build_simulator(simulator_path)
    print(f"Simulator binary built: {simulator_binary}")
    return sys, simulator_binary, verilog_path


def run_toy_cpu(program: Sequence[int] | Iterable[int] | Path | str | None = None, **kwargs):
    """Convenience wrapper that builds the CPU and runs its simulator."""
    # TODO: implement unit test of CPU similar to the example


if __name__ == "__main__":
    sys, simulator_binary, verilog_path = build_cpu()
    print("Toy ADD CPU built successfully!")
