"""Simple regression-style tests for the toy ADD/ADDI CPU."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from toy.add.main import run_toy_cpu


@dataclass(frozen=True)
class ToyCase:
    name: str
    hex_file: str
    asm_file: str
    expected_x1: int


CASES = [
    ToyCase("addi_only", "addi_only.hex", "addi_only.asm", expected_x1=12),
    ToyCase("add_mix", "add_mix.hex", "add_mix.asm", expected_x1=13),
    ToyCase("chain_add", "chain_add.hex", "chain_add.asm", expected_x1=9),
]

CASE_DIR = Path(__file__).parent / "programs"
WORKSPACE_ROOT = Path(__file__).parent / "workspace"
WRITEBACK_RE = re.compile(r"toy-wb\s*\|\s*x(\d+)\s*<=\s*0x([0-9a-fA-F]{8})")
EBREAK_RE = re.compile(r"toy-exec\s+\|\s+ebreak")


def _extract_x1_value(sim_output: str) -> int:
    writes = WRITEBACK_RE.findall(sim_output)
    for reg_str, raw_value in reversed(writes):
        if int(reg_str) == 1:
            return int(raw_value, 16)
    raise AssertionError("No write to x1 observed in simulator output.")


def run_case(case: ToyCase) -> None:
    hex_path = CASE_DIR / case.hex_file
    asm_path = CASE_DIR / case.asm_file
    workspace = WORKSPACE_ROOT / case.name
    workspace.mkdir(parents=True, exist_ok=True)

    asm_text = asm_path.read_text().strip()
    print(f"\n== Running {case.name} ==")
    print(asm_text)
    sim_output, _ = run_toy_cpu(program=hex_path, workspace=workspace)
    if not EBREAK_RE.search(sim_output):
        print(f"Simulator output:\n{sim_output}")
        raise AssertionError("Simulator output does not show an ebreak event.")
    observed = _extract_x1_value(sim_output)
    if observed != case.expected_x1:
        raise AssertionError(
            f"x1 mismatch: observed 0x{observed:08x}, expected 0x{case.expected_x1:08x}"
        )
    print(f"[PASS] {case.name}: x1=0x{observed:08x}")


def main() -> None:
    for case in CASES:
        try:
            run_case(case)
        except Exception as err:  # pylint: disable=broad-except
            print(f"[FAIL] {case.name}: {err}")
            raise SystemExit(f"Toy ADD test failed: {case.name}")
        
    print("\nAll toy ADD test cases passed.")


if __name__ == "__main__":
    main()

