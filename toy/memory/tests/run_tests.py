"""Regression tests for the toy memory-enabled CPU."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from toy.memory.main import run_memory_cpu
from toy.memory.program import read_program_file
from utils import rv32i_asm_to_hex


@dataclass(frozen=True)
class MemoryCase:
    name: str
    hex_file: str
    asm_file: str
    data_file: str
    config_file: str
    expected_regs: Dict[int, int]
    depth_log: int = 6


CASES = [
    MemoryCase(
        "memory_suite",
        "memory_suite.hex",
        "memory_suite.asm",
        "memory_suite.data",
        "memory_suite.config",
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


def run_case(case: MemoryCase) -> None:
    asm_path = CASE_DIR / case.asm_file
    hex_path = CASE_DIR / case.hex_file
    data_path = CASE_DIR / case.data_file
    config_path = CASE_DIR / case.config_file
    workspace = WORKSPACE_ROOT / case.name
    workspace.mkdir(parents=True, exist_ok=True)

    _assert_hex_matches_asm(asm_path, hex_path)

    asm_text = asm_path.read_text().strip()
    print(f"\n== Running {case.name} ==")
    print(asm_text)
    sim_output, _ = run_memory_cpu(
        program=hex_path,
        data_image=data_path,
        config_file=config_path,
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
    print("\nAll toy memory cases passed.")


if __name__ == "__main__":
    main()
