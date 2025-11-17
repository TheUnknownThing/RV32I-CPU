"""Regression tests that compile C sources into RV32I programs automatically."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict

import pytest

from src.naive_cpu.main import run_cpu
from utils.c_program_suite import CProgramCase, CToolchainOptions, compile_c_program

REPORT_STORE_RE = re.compile(
    r"naive-mem\s*\|\s*store\s+pc=.*?addr=0x([0-9a-fA-F]{8}).*?value=0x([0-9a-fA-F]{8})"
)
EBREAK_RE = re.compile(r"naive-exec\s*\|\s*ebreak")

REPO_ROOT = Path(__file__).resolve().parents[3]
CASE_DIR = REPO_ROOT / "utils" / "c_program_suite" / "programs"
WORKSPACE_ROOT = Path(__file__).parent / "workspace" / "c_programs"

DEFAULT_OPTIONS = CToolchainOptions(
    imem_bytes=4096,
    dmem_bytes=4096,
    stack_bytes=1024,
    report_slots=16,
    opt_level="O2",
)

C_CASES = [
    CProgramCase(
        name="alu_suite_c",
        sources=[CASE_DIR / "alu_suite.c"],
        expected_reports={
            1: 0x00000020,
            2: 0x00000400,
            3: 0xFFFFFB4E,
            4: 0x000000E0,
            5: 0x0000000D,
        },
        depth_log=7,
    ),
    CProgramCase(
        name="memory_suite_c",
        sources=[CASE_DIR / "memory_suite.c"],
        expected_reports={
            1: 0x2C5884AF,
            2: 0x00000080,
            3: 0x0000FF7F,
            4: 0xFFFFFFFF,
            5: 0x6EDCA85B,
        },
        depth_log=7,
    ),
    CProgramCase(
        name="control_suite_c",
        sources=[CASE_DIR / "control_suite.c"],
        expected_reports={
            1: 0xFFFFFFB4,
            2: 0x000063C0,
            3: 0x00000024,
            4: 0x00000008,
        },
        depth_log=7,
    ),
]


@pytest.mark.parametrize("case", C_CASES)
def test_c_compiled_programs(case: CProgramCase):
    options = case.options or DEFAULT_OPTIONS
    if shutil.which(options.clang) is None:
        pytest.skip(f"clang executable '{options.clang}' is not available.")

    workspace = WORKSPACE_ROOT / case.name
    build = compile_c_program(
        case.name,
        case.sources,
        workspace,
        options=options,
    )

    sim_workspace = workspace / "sim"
    sim_workspace.mkdir(parents=True, exist_ok=True)

    sim_output, _ = run_cpu(
        program=build.program_words,
        data_image=build.data_words,
        workspace=sim_workspace,
        depth_log=case.depth_log,
        sim_threshold=case.sim_threshold,
        idle_threshold=case.idle_threshold or case.sim_threshold,
    )
    (sim_workspace / "sim.log").write_text(sim_output)

    assert EBREAK_RE.search(sim_output), "Simulation did not terminate with an ebreak."

    report_base = _metadata_value(build.metadata, "__test_report_base")
    report_slots = _metadata_value(build.metadata, "__test_report_slots")

    reports = _collect_reports(sim_output, report_base, report_slots)
    expected_status = case.expected_reports.get(0, 0)
    assert (
        reports.get(0) == expected_status
    ), f"{case.name}: status slot expected 0x{expected_status:08x}, got {reports.get(0)}."

    for slot, expected in case.expected_reports.items():
        assert (
            reports.get(slot) == expected
        ), f"{case.name}: slot {slot} expected 0x{expected:08x}, got {reports.get(slot)}."


def _metadata_value(metadata: Dict[str, int], key: str) -> int:
    if key not in metadata:
        raise AssertionError(f"Missing '{key}' in compile metadata.")
    return int(metadata[key])


def _collect_reports(sim_output: str, base_addr: int, slots: int) -> Dict[int, int]:
    reports: Dict[int, int] = {}
    upper_addr = base_addr + slots * 4
    for addr_hex, value_hex in REPORT_STORE_RE.findall(sim_output):
        addr = int(addr_hex, 16)
        value = int(value_hex, 16)
        if base_addr <= addr < upper_addr:
            slot = (addr - base_addr) // 4
            reports[slot] = value
    return reports
