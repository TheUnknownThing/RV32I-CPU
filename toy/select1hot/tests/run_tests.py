"""Regression tests for the toy Select1Hot CPU."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from toy.select1hot.main import run_select1hot_cpu
from toy.select1hot.program import read_program_file
from utils import rv32i_asm_to_hex


@dataclass(frozen=True)
class SelectCase:
    name: str
    hex_file: str
    asm_file: str
    expected_regs: Dict[int, int]
    depth_log: int = 6


CASES = [
    SelectCase(
        "arithmetic_suite",
        "arithmetic_suite.hex",
        "arithmetic_suite.asm",
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
    ),
]

CASE_DIR = Path(__file__).parent / "programs"
WORKSPACE_ROOT = Path(__file__).parent / "workspace"
WRITEBACK_RE = re.compile(r"toy-wb\s*\|\s*x(\d+)\s*<=\s*0x([0-9a-fA-F]{8})")
EBREAK_RE = re.compile(r"toy-exec\s*\|\s*ebreak")


def _collect_registers(sim_output: str) -> Dict[int, int]:
    regs: Dict[int, int] = {}
    for reg_name, value in WRITEBACK_RE.findall(sim_output):
        regs[int(reg_name)] = int(value, 16)
    return regs


def _assert_hex_matches_asm(asm_path: Path, hex_path: Path) -> None:
    assembled = rv32i_asm_to_hex.assemble_file(asm_path)
    encoded = read_program_file(hex_path)
    if assembled != encoded:
        raise AssertionError(
            f"{hex_path} is out of date. Regenerate with "
            f"`python utils/rv32i_asm_to_hex.py {asm_path}`."
        )


def run_case(case: SelectCase) -> None:
    asm_path = CASE_DIR / case.asm_file
    hex_path = CASE_DIR / case.hex_file
    workspace = WORKSPACE_ROOT / case.name
    workspace.mkdir(parents=True, exist_ok=True)

    _assert_hex_matches_asm(asm_path, hex_path)

    asm_text = asm_path.read_text().strip()
    print(f"\n== Running {case.name} ==")
    print(asm_text)
    sim_output, _ = run_select1hot_cpu(
        program=hex_path,
        workspace=workspace,
        depth_log=case.depth_log,
    )
    if not EBREAK_RE.search(sim_output):
        print(f"Simulator output:\n{sim_output}")
        raise AssertionError("Simulator output does not show an ebreak event.")

    observed = _collect_registers(sim_output)
    for reg, expected in case.expected_regs.items():
        value = observed.get(reg)
        if value is None:
            print(f"Simulator output:\n{sim_output}")
            raise AssertionError(f"Register x{reg} was never written.")
        if value != expected:
            print(f"Simulator output:\n{sim_output}")
            raise AssertionError(f"x{reg} mismatch: observed 0x{value:08x}, expected 0x{expected:08x}")
    print(f"[PASS] {case.name}")
    (workspace / "sim.log").write_text(sim_output)


def main() -> None:
    for case in CASES:
        run_case(case)
    print("\nAll Select1Hot cases passed.")


if __name__ == "__main__":
    main()
