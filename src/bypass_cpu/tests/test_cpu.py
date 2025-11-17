"""End-to-end regression tests for the Naive RV32I CPU."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import pytest

from src.bypass_cpu.main import run_cpu
from utils import rv32i_asm_to_hex


WRITEBACK_RE = re.compile(r"naive-wb\s*\|\s*x(\d+)\s*<=\s*0x([0-9a-fA-F]{8})")
EBREAK_RE = re.compile(r"naive-exec\s*\|\s*ebreak")


@dataclass(frozen=True)
class CpuCase:
    name: str
    asm_file: str
    expected_regs: Dict[int, int]
    data_file: str | None = None
    depth_log: int = 7


CASE_DIR = Path(__file__).parent / "programs"
WORKSPACE_ROOT = Path(__file__).parent / "workspace"


CASES: Sequence[CpuCase] = [
    CpuCase(
        name="many_hazards",
        asm_file="many_hazards.asm",
        expected_regs={
            1: 0x00000405,
        },
        depth_log=7,
    ),
    CpuCase(
        name="arithmetic_suite",
        asm_file="arithmetic_suite.asm",
        expected_regs={
            1: 0x0000004F,
            2: 0x00000005,
            3: 0xFFFFFFF9,
            4: 0x0000000F,
            5: 0x00000014,
            6: 0x0000000A,
            7: 0x00000004,
            8: 0x00000000,
            9: 0x00000123,
            10: 0x00000127,
            11: 0x00000120,
            12: 0x00000007,
            13: 0x00000002,
            14: 0x0000000A,
            15: 0x0000003C,
            16: 0x00000007,
            17: 0x00000001,
            18: 0xFFFFFFFC,
            19: 0xFFFFFFFE,
            20: 0x00000001,
            21: 0x00000001,
            22: 0x00000000,
            23: 0x00000001,
            24: 0x00000000,
        },
        depth_log=7,
    ),
    CpuCase(
        name="memory_suite",
        asm_file="memory_suite.asm",
        data_file="memory_suite.data",
        expected_regs={
            2: 0xFFFFFF80,
            3: 0x000000CC,
            4: 0xFFFFAA55,
            5: 0x00004488,
            6: 0xDEADBEEF,
            8: 0x000000FE,
            11: 0x00007B9A,
            13: 0xCAFEBABE,
            14: 0x7B9A66FE,
        },
        depth_log=7,
    ),
    CpuCase(
        name="branch_suite",
        asm_file="branch_suite.asm",
        data_file="branch_suite.data",
        expected_regs={
            1: 18,
            20: 3,
            21: 3,
            22: 3,
            23: 3,
            24: 3,
            25: 3,
        },
        depth_log=7,
    ),
    CpuCase(
        name="jump_suite",
        asm_file="jump_suite.asm",
        expected_regs={
            2: 0x00000111,
            3: 0x00000222,
            9: 0x00000001,
            10: 0x00000123,
        },
        depth_log=6,
    ),
    CpuCase(
        name="upper_suite",
        asm_file="upper_suite.asm",
        expected_regs={
            5: 0x12345000,
            6: 0x00ABC07F,
            7: 0x00000000,
            8: 0xFFFFF014,
        },
        depth_log=6,
    ),
]


@pytest.mark.parametrize("case", CASES)
def test_cpu_cases(case: CpuCase):
    asm_path = CASE_DIR / case.asm_file
    program_words = rv32i_asm_to_hex.assemble_file(asm_path)
    data_path = CASE_DIR / case.data_file if case.data_file else None

    workspace = WORKSPACE_ROOT / case.name
    workspace.mkdir(parents=True, exist_ok=True)

    sim_output, _ = run_cpu(
        program=program_words,
        data_image=data_path,
        workspace=workspace,
        depth_log=case.depth_log,
    )

    (workspace / "sim.log").write_text(sim_output)

    if not EBREAK_RE.search(sim_output):
        print(sim_output)
        pytest.fail("Simulator output did not terminate with an ebreak.")

    observed = _collect_registers(sim_output)
    for reg, expected in case.expected_regs.items():
        if reg not in observed:
            print(sim_output)
            pytest.fail(f"Register x{reg} was never written in case {case.name}.")
        if observed[reg] != expected:
            print(sim_output)
            pytest.fail(
                f"Case {case.name}: x{reg} expected 0x{expected:08x}, saw 0x{observed[reg]:08x}."
            )


def _collect_registers(sim_output: str) -> Dict[int, int]:
    regs: Dict[int, int] = {}
    for reg_name, value in WRITEBACK_RE.findall(sim_output):
        regs[int(reg_name)] = int(value, 16)
    return regs
