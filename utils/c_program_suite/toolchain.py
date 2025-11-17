"""End-to-end pipeline for compiling C programs into RV32I images."""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, MutableMapping, Sequence

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import Section

from utils import rv32i_asm_to_hex


@dataclass(frozen=True)
class CToolchainOptions:
    """Configuration knobs for the Clang-based RV32I build pipeline."""

    clang: str = os.environ.get("RV32I_CLANG", "clang")
    linker: str = os.environ.get("RV32I_LINKER", "riscv64-linux-gnu-ld")
    imem_bytes: int = 4096
    dmem_bytes: int = 4096
    stack_bytes: int = 512
    report_slots: int = 16
    opt_level: str = "O2"
    extra_cflags: Sequence[str] = field(default_factory=tuple)
    extra_ldflags: Sequence[str] = field(default_factory=tuple)

    def opt_flag(self) -> str:
        flag = self.opt_level if self.opt_level.startswith("-") else f"-{self.opt_level}"
        return flag


@dataclass(frozen=True)
class CompiledProgram:
    """Artifacts emitted by compile_c_program()."""

    name: str
    workspace: Path
    elf_path: Path
    disassembly: Path | None
    asm_sources: Mapping[Path, Path]
    program_hex: Path
    data_hex: Path
    program_words: List[int]
    data_words: List[int]
    metadata: Dict[str, int]


@dataclass(frozen=True)
class CProgramCase:
    """Description of a regression case expressed in C."""

    name: str
    sources: Sequence[str | Path]
    expected_reports: Mapping[int, int]
    depth_log: int = 7
    sim_threshold: int = 1024
    idle_threshold: int | None = None
    options: CToolchainOptions | None = None


def compile_c_program(
    name: str,
    sources: Sequence[str | Path],
    workspace: Path,
    *,
    options: CToolchainOptions | None = None,
) -> CompiledProgram:
    """Compile the given C sources into ELF, disassembly, and hex images."""

    if not sources:
        raise ValueError("At least one source file must be provided.")

    opts = options or CToolchainOptions()
    if opts.report_slots < 2:
        raise ValueError("report_slots must be at least 2.")
    if opts.stack_bytes <= 0:
        raise ValueError("stack_bytes must be positive.")
    if opts.stack_bytes >= opts.dmem_bytes:
        raise ValueError("stack_bytes must be smaller than dmem_bytes.")
    if shutil.which(opts.clang) is None:
        raise RuntimeError(f"Unable to find clang executable '{opts.clang}'.")
    if shutil.which(opts.linker) is None:
        raise RuntimeError(f"Unable to find linker executable '{opts.linker}'.")

    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    toolchain_root = Path(__file__).resolve().parent
    runtime_dir = toolchain_root / "runtime"
    include_dir = runtime_dir / "include"
    crt0_path = runtime_dir / "crt0.S"
    if not crt0_path.exists():
        raise FileNotFoundError(f"Missing crt0 stub: {crt0_path}")

    linker_script = workspace / "naive_cpu_tests.ld"
    _write_linker_script(linker_script, opts)

    asm_outputs: MutableMapping[Path, Path] = {}
    object_files: List[Path] = []
    for src in sources:
        src_path = Path(src).resolve()
        stem = src_path.stem
        asm_path = workspace / f"{stem}.s"
        obj_path = workspace / f"{stem}.o"
        compile_base = _clang_base_command(opts) + [
            "-I",
            str(include_dir),
        ]
        asm_cmd = compile_base + ["-S", str(src_path), "-o", str(asm_path)]
        obj_cmd = compile_base + ["-c", str(src_path), "-o", str(obj_path)]
        _run(asm_cmd, cwd=workspace)
        _run(obj_cmd, cwd=workspace)
        asm_outputs[src_path] = asm_path
        object_files.append(obj_path)

    crt_obj = workspace / "crt0.o"
    crt_cmd = _clang_base_command(opts) + [
        "-c",
        "-I",
        str(include_dir),
        str(crt0_path),
        "-o",
        str(crt_obj),
    ]
    _run(crt_cmd, cwd=workspace)
    object_files.insert(0, crt_obj)

    elf_path = workspace / f"{name}.elf"
    link_cmd = [
        opts.linker,
        "-melf32lriscv",
        "--no-check-sections",
        "--gc-sections",
        "--no-relax",
        "--strip-debug",
        "-nostdlib",
        "-T",
        str(linker_script),
        "-o",
        str(elf_path),
    ]
    link_cmd.extend(str(obj) for obj in object_files)
    link_cmd.extend(opts.extra_ldflags)
    _run(link_cmd, cwd=workspace)

    disasm_path = _disassemble_elf(elf_path, workspace)
    program_words, data_words, metadata = _extract_images(elf_path, opts)

    program_hex = workspace / f"{name}.program.hex"
    data_hex = workspace / f"{name}.data.hex"
    rv32i_asm_to_hex.write_hex(program_words, program_hex)
    rv32i_asm_to_hex.write_hex(data_words, data_hex)

    return CompiledProgram(
        name=name,
        workspace=workspace,
        elf_path=elf_path,
        disassembly=disasm_path,
        asm_sources=dict(asm_outputs),
        program_hex=program_hex,
        data_hex=data_hex,
        program_words=program_words,
        data_words=data_words,
        metadata=metadata,
    )


def _clang_base_command(opts: CToolchainOptions) -> List[str]:
    base = [
        opts.clang,
        "--target=riscv32-unknown-elf",
        "-march=rv32i",
        "-mabi=ilp32",
        "-nostdlib",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-stack-protector",
        "-fno-exceptions",
        "-fno-unwind-tables",
        "-fno-asynchronous-unwind-tables",
        "-fdata-sections",
        "-ffunction-sections",
        "-fno-pic",
        "-fomit-frame-pointer",
        "-msmall-data-limit=0",
        "-g0",
        opts.opt_flag(),
    ]
    base.extend(opts.extra_cflags)
    return base


def _write_linker_script(path: Path, opts: CToolchainOptions) -> None:
    script = textwrap.dedent(
        f"""
        OUTPUT_ARCH(riscv)
        ENTRY(_start)

        IMEM_SIZE = {opts.imem_bytes};
        DMEM_SIZE = {opts.dmem_bytes};
        STACK_SIZE = {opts.stack_bytes};
        REPORT_SLOTS = {opts.report_slots};

        MEMORY {{
            IMEM (rx) : ORIGIN = 0x00000000, LENGTH = IMEM_SIZE
            DMEM (rwx) : ORIGIN = 0x00000000, LENGTH = DMEM_SIZE
        }}

        SECTIONS {{
            . = ORIGIN(IMEM);
            .text :
            {{
                KEEP(*(.text.entry))
                *(.text .text.*)
                *(.gnu.linkonce.t.*)
            }} > IMEM

            . = ORIGIN(DMEM);
            .report (NOLOAD) :
            {{
                . = ALIGN(4);
                PROVIDE(__test_report_base = .);
                . += REPORT_SLOTS * 4;
                PROVIDE(__test_report_limit = .);
                PROVIDE(__test_report_slots = REPORT_SLOTS);
            }} > DMEM

            .rodata :
            {{
                *(.srodata .srodata.*)
                *(.rodata .rodata.*)
                *(.gnu.linkonce.r.*)
            }} > DMEM

            .data :
            {{
                PROVIDE(__global_pointer$ = . + 0x800);
                *(.sdata .sdata.*)
                *(.data .data.*)
                *(.gnu.linkonce.d.*)
            }} > DMEM

            .bss (NOLOAD) :
            {{
                *(.sbss .sbss.*)
                *(.bss .bss.*)
                *(COMMON)
                *(.gnu.linkonce.b.*)
            }} > DMEM

            . = ALIGN(16);
            PROVIDE(__stack_limit = ORIGIN(DMEM) + DMEM_SIZE - STACK_SIZE);
            PROVIDE(__stack_top = ORIGIN(DMEM) + DMEM_SIZE);
        }}
        """
    ).strip()
    path.write_text(script, encoding="utf-8")


def _disassemble_elf(elf_path: Path, workspace: Path) -> Path | None:
    objdump = shutil.which("llvm-objdump") or shutil.which("riscv64-linux-gnu-objdump")
    if objdump is None:
        return None
    disasm_path = workspace / f"{elf_path.stem}.disasm"
    cmd = [
        objdump,
    ]
    if objdump and objdump.endswith("llvm-objdump"):
        cmd.extend(["-d", "-M", "numeric"])
    else:
        cmd.extend(["-d", "-M", "numeric,no-aliases"])
    cmd.append(str(elf_path))
    with disasm_path.open("w", encoding="utf-8") as dst:
        subprocess.run(cmd, cwd=workspace, check=True, stdout=dst, stderr=subprocess.STDOUT)
    return disasm_path


def _extract_images(
    elf_path: Path,
    opts: CToolchainOptions,
) -> tuple[List[int], List[int], Dict[str, int]]:
    with elf_path.open("rb") as elf_file:
        elf = ELFFile(elf_file)
        text_image = _collect_section_bytes(
            elf,
            predicate=lambda sec: (sec["sh_flags"] & 0x4) != 0,
        )
        data_image = _collect_section_bytes(
            elf,
            predicate=lambda sec: (sec["sh_flags"] & 0x2) != 0 and (sec["sh_flags"] & 0x4) == 0,
            total_bytes=opts.dmem_bytes,
        )
        metadata = {
            "entry": elf.header["e_entry"],
        }
        for symbol in ("__test_report_base", "__test_report_slots", "__stack_top", "__stack_limit"):
            value = _read_symbol(elf, symbol)
            if value is not None:
                metadata[symbol] = value

    program_words = _bytes_to_words(text_image)
    data_words = _bytes_to_words(data_image)
    return program_words, data_words, metadata


def _collect_section_bytes(
    elf: ELFFile,
    *,
    predicate: Callable[[Section], bool],
    total_bytes: int | None = None,
) -> bytearray:
    sections = [sec for sec in elf.iter_sections() if predicate(sec)]
    if not sections:
        raise RuntimeError("ELF does not contain any sections matching predicate.")

    if total_bytes is None:
        max_end = 0
        for sec in sections:
            start = sec["sh_addr"]
            end = start + sec["sh_size"]
            max_end = max(max_end, end)
        total_bytes = ((max_end + 3) // 4) * 4

    image = bytearray(total_bytes)
    for sec in sections:
        start = sec["sh_addr"]
        size = sec["sh_size"]
        if start + size > total_bytes:
            raise RuntimeError(
                f"Section {sec.name} at 0x{start:08x} exceeds allocated image size {total_bytes}."
            )
        if size == 0 or sec["sh_type"] == "SHT_NOBITS":
            continue
        data = sec.data()
        image[start : start + len(data)] = data
    return image


def _read_symbol(elf: ELFFile, name: str) -> int | None:
    symtab = elf.get_section_by_name(".symtab")
    if symtab is None:
        return None
    symbols = symtab.get_symbol_by_name(name)
    if not symbols:
        return None
    return int(symbols[0]["st_value"])


def _bytes_to_words(data: Iterable[int]) -> List[int]:
    raw = bytes(data)
    if len(raw) % 4 != 0:
        raw += b"\x00" * (4 - len(raw) % 4)
    words: List[int] = []
    for offset in range(0, len(raw), 4):
        words.append(struct.unpack_from("<I", raw, offset)[0])
    return words


def _run(cmd: Sequence[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)
