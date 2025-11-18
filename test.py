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

DEFAULT_WORKSPACE = Path(__file__).with_name(".workspace")

class Driver(Module):
    """Issues fetch requests for every word in the program image."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Driver"

    @module.combinational
    def build(self):
        log("{}",Bits(1)(0) & Bits(1)(1))

def build_cpu(
    workspace: Path | str | None = None,
):
    """Build and elaborate the ADD/ADDI toy CPU.

    Args:
        workspace: Directory used for temporary program images and simulator
            outputs. Falls back to `toy/add/.workspace`.
    """

    workspace_path = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE

    sys = SysBuilder("ToyADDCPU")

    with sys:
        driver = Driver()
        driver.build()

        reg_file = RegArray(Bits(32), 32, initializer=[0] * 32)

        icache = SRAM(width=32, depth=64, init_file=None)
        icache.name = "toy_icache"
        icache.build(
            we=Bits(1)(0),
            re=Bits(1)(1),
            addr=Bits(32)(0),
            wdata=Bits(32)(0),
        )

        sys.expose_on_top(reg_file, kind="Output")

    print(sys)
    conf = config(
        verilog=utils.has_verilator(),
        sim_threshold=128,
        idle_threshold=128,
        resource_base=str(workspace_path),
        fifo_depth=1,
    )

    simulator_path, verilog_path = elaborate(sys, **conf)
    print("Building simulator binary...")
    simulator_binary = utils.build_simulator(simulator_path)
    print(f"Simulator binary built: {simulator_binary}")
    return sys, simulator_binary, verilog_path


def default_build_cpu():
    # pass `ebreak` to build
    WORKSPACE_ROOT = Path(__file__).parent / "workspace"
    workspace = WORKSPACE_ROOT / "default"
    workspace.mkdir(parents=True, exist_ok=True)

    return run_cpu(
        workspace=workspace,
    )


def run_cpu(
    workspace: Path | str | None = None,):
    """Build the Bypass CPU and run its simulator."""

    sys, simulator_binary, verilog_path = build_cpu(workspace)
    sim_output = utils.run_simulator(binary_path=simulator_binary)
    return sim_output, verilog_path


if __name__ == "__main__":
    simulator_binary, verilog_path = default_build_cpu()
    utils.run_verilator(verilog_path)
    print("Bypass RV32I CPU built successfully!")
