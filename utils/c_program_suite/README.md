# RV32I C Program Suite

This directory contains a self-contained toolchain for turning portable C
programs into RV32I instruction/data images that can be consumed by any
simulation flow (RTL, ISS, or FPGA prototypes).  It also ships with a few sample
programs and a minimal runtime (`test_runtime.h` + `crt0.S`) that makes it easy
to report architectural state back to the host without depending on a specific
SoC or firmware stack.

## Contents

```
utils/c_program_suite/
├── README.md                  # This document
├── __init__.py                # Python package export surface
├── programs/                  # Portable C regression programs
├── runtime/
│   ├── crt0.S                 # Minimal entry + ebreak halt routine
│   └── include/test_runtime.h # Helper APIs for tests
└── toolchain.py               # Clang-based build + ELF to HEX conversion
```

## Requirements

* Python 3.11+
* `clang` capable of emitting RV32I (`--target=riscv32-unknown-elf`)
* `riscv64-linux-gnu-ld` (Debian package `binutils-riscv64-linux-gnu`)
* `pyelftools` Python package (listed in `requirements.txt`)

The script discovers the compilers via `CToolchainOptions` and honors the
environment variables `RV32I_CLANG` and `RV32I_LINKER`.

## Quick Start

```python
from pathlib import Path
from utils.c_program_suite import compile_c_program

workspace = Path("workspace/alu_suite_c")
prog_dir = Path("utils/c_program_suite/programs")
build = compile_c_program(
    name="alu_suite_c",
    sources=[prog_dir / "alu_suite.c"],
    workspace=workspace,
)
print("Instruction words:", len(build.program_words))
print("Data words:", len(build.data_words))
```

After the call finishes you will find:

* `<workspace>/alu_suite_c.elf` – linked ELF image
* `<workspace>/alu_suite_c.program.hex` – instruction memory (one word per line)
* `<workspace>/alu_suite_c.data.hex` – data memory payload
* `<workspace>/alu_suite_c.disasm` (optional) – human-readable disassembly
* `<workspace>/sim/` (created by individual CPU harnesses) – simulator output

## Runtime Contract

Every C test `#include "test_runtime.h"` and uses these helpers:

* `test_report(slot, value)` – writes a 32-bit value into a reserved memory
  window exported via linker symbols (`__test_report_base`/`__test_report_slots`)
* `test_pass()` – halts the program with exit code `0`
* `test_fail(code)` – halts with a non-zero code

The bundled `crt0.S` sets up `gp`, `sp`, calls `main`, and ultimately traps via
`ebreak` after halting.  This makes the tests agnostic to the CPU harness: as
long as the simulator instantiates memories from the HEX files and watches the
`test_report` scratchpad, the exact RTL implementation does not matter.

## Integrating With Another CPU

1. Convert your target CPU's notion of program/data memories so they can be
   initialized from the generated HEX files (little-endian 32-bit words).
2. Ensure that the data memory contains at least `report_slots * 4` bytes at the
   start so the report buffer fits.  The default linker script reserves 64 bytes
   and grows automatically if you change `report_slots` in
   `CToolchainOptions`.
3. Load the instruction image at address `0x0000_0000`.  The runtime's entry
   point `_start` is also placed at this offset, so no other boot ROM is
   required.
4. Execute until the CPU logs a store into the report window (slot `0` is the
   exit code) followed by the `ebreak` log.  The existing
   `src/naive_cpu/tests/test_c_programs.py` script shows how to collect those
   values from simulator output.

You can easily extend the suite by adding more `.c` files into
`utils/c_program_suite/programs` or by pointing `compile_c_program` to your own
sources.  The Python API exposes `CProgramCase` so that pytest suites can
describe the expected observations once and reuse the compilation artifacts for
any CPU top level.
