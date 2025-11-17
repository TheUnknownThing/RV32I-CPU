"""Naive RV32I CPU with memory support and precise in-order control flow."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from assassyn.frontend import *  # noqa: F401,F403
from assassyn.backend import *  # noqa: F401,F403
from assassyn import utils

from .common import AluOp, MemWidth, decoded_instr  # noqa: F401
from .modules.decode import Decoder
from .modules.fetch import Fetcher
from .modules.execute import Executor
from .modules.memory import MemoryAccess
from .modules.writeback import WriteBack
from .program import (
    memory_address_width,
    normalize_data_image,
    normalize_program,
    read_memory_config,
    write_program_image,
    bytes_to_words,
)


class Driver(Module):
    """Issues fetch requests for every word in the program image."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Driver"

    @module.combinational
    def build(self, fetcher: Module):
        fetcher.async_called()


DEFAULT_WORKSPACE = Path(__file__).with_name(".workspace")


def build_cpu(
    program: Sequence[int] | Iterable[int] | Path | str | None = None,
    *,
    data_image: Sequence[int] | Iterable[int] | Path | str | None = None,
    config_file: Path | str | None = None,
    depth_log: int = 4,
    workspace: Path | str | None = None,
):
    """Build and elaborate the Naive memory-capable RV32I CPU."""

    program_words = normalize_program(program)
    data_bytes = normalize_data_image(data_image)
    mem_config = read_memory_config(config_file)

    if depth_log <= 0:
        raise ValueError("depth_log must be positive.")

    depth = 1 << depth_log
    if len(program_words) > depth:
        raise ValueError(
            f"Program has {len(program_words)} words, exceeds instruction memory depth {depth}."
        )

    requested_words = max(1, (len(data_bytes) + 3) // 4)
    padded_words = requested_words + 1
    word_addr_width = memory_address_width(padded_words)
    data_word_depth = 1 << word_addr_width
    data_words = bytes_to_words(data_bytes, data_word_depth)
    total_data_bytes = data_word_depth * 4

    workspace_path = Path(workspace) if workspace is not None else DEFAULT_WORKSPACE
    workspace_path.mkdir(parents=True, exist_ok=True)
    program_image = write_program_image(program_words, workspace_path)

    sys = SysBuilder("NaiveRV32ICPU")

    with sys:
        fetcher = Fetcher()
        decoder = Decoder()
        executor = Executor()
        memory = MemoryAccess()
        writeback = WriteBack()
        driver = Driver()

        on_branch = RegArray(Bits(1), 1, initializer=[0])
        on_hazard = RegArray(Bits(1), 1, initializer=[0])

        pc_reg, pc_addr = fetcher.build(
            depth_log=depth_log,
            decoder=decoder,
            pc_offset=mem_config.pc_offset,
            on_branch=on_branch,
            on_hazard=on_hazard,
            program_words=len(program_words),
        )

        reg_file = RegArray(Bits(32), 32, initializer=[0] * 32)
        reg_avail = RegArray(Bits(1), 32, initializer=[1] * 32)

        icache = SRAM(width=32, depth=depth, init_file=str(program_image))
        icache.name = "naive_memory_icache"
        icache.build(
            we=Bits(1)(0),
            re=Bits(1)(1),
            addr=pc_addr,
            wdata=Bits(32)(0),
        )

        data_image_file = workspace_path / "data.hex"
        with data_image_file.open("w", encoding="utf-8") as dst:
            for word in data_words:
                dst.write(f"{word:08x}\n")

        dcache = SRAM(width=32, depth=data_word_depth, init_file=str(data_image_file))
        dcache.name = "naive_memory_dcache"

        decoder.build(
            executor=executor,
            rdata=icache.dout,
            on_branch=on_branch,
            on_hazard=on_hazard,
        )
        executor.build(
            reg_file=reg_file,
            reg_avail=reg_avail,
            memory=memory,
            dcache=dcache,
            data_offset=mem_config.data_offset,
            data_bytes=total_data_bytes,
            word_addr_width=word_addr_width,
            on_branch=on_branch,
            on_hazard=on_hazard,
            pc_reg=pc_reg,
        )
        memory.build(
            dout=dcache.dout,
            wb=writeback,
        )
        writeback.build(reg_file=reg_file, reg_avail=reg_avail)

        driver.build(fetcher=fetcher)

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


def run_cpu(
    program: Sequence[int] | Iterable[int] | Path | str | None = None,
    **kwargs,
):
    """Build the Naive CPU and run its simulator."""

    sys, simulator_binary, verilog_path = build_cpu(program, **kwargs)
    sim_output = utils.run_simulator(binary_path=simulator_binary)
    return sim_output, verilog_path


if __name__ == "__main__":
    sys, simulator_binary, verilog_path = build_cpu()
    print("Naive RV32I CPU built successfully!")
