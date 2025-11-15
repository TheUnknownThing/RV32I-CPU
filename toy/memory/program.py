"""Program helpers for the toy memory-capable RV32I CPU."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from ..add.program import (
    normalize_program as _normalize_program,
    read_program_file as _read_program_file,
    write_program_image as _write_program_image,
)


@dataclass(frozen=True)
class MemoryConfig:
    """Offsets describing where program and data memories live."""

    pc_offset: int = 0
    data_offset: int = 0


def normalize_program(program: Sequence[int] | Iterable[int] | Path | str | None) -> List[int]:
    return _normalize_program(program)


def read_program_file(path: Path) -> List[int]:
    return _read_program_file(path)


def write_program_image(words: Sequence[int], workspace: Path) -> Path:
    return _write_program_image(words, workspace)


def normalize_data_image(data: Sequence[int] | Iterable[int] | Path | str | None) -> List[int]:
    """Normalize the input data image into a byte array.

    The on-disk format mirrors the program hex files: each line contains a
    32-bit word encoded in hex with optional trailing comments.  In addition to
    file inputs, callers may also pass an iterable of 32-bit integers.
    """

    if data is None:
        words = [0]
    elif isinstance(data, (str, Path)):
        words = read_program_file(Path(data))
    else:
        words = [int(word) & 0xFFFFFFFF for word in data]

    if not words:
        words = [0]

    return _words_to_bytes(words)


def _words_to_bytes(words: Sequence[int]) -> List[int]:
    bytes_out: List[int] = []
    for word in words:
        value = int(word) & 0xFFFFFFFF
        for shift in range(0, 32, 8):
            bytes_out.append((value >> shift) & 0xFF)
    return bytes_out


def memory_address_width(byte_count: int) -> int:
    """Return the number of address bits required to index byte_count entries."""

    if byte_count <= 0:
        raise ValueError("byte_count must be positive.")
    width = (byte_count - 1).bit_length()
    return max(width, 1)


def read_memory_config(path: Path | str | None) -> MemoryConfig:
    """Parse a simple configuration file describing PC and data offsets."""

    if path is None:
        return MemoryConfig()

    raw_text = Path(path).read_text().strip()
    if not raw_text:
        return MemoryConfig()

    config_dict = ast.literal_eval(raw_text)

    def _to_int(value: object) -> int:
        if isinstance(value, str):
            return int(value, 0)
        return int(value)

    pc_offset = _to_int(config_dict.get("offset", 0)) & 0xFFFFFFFF
    data_offset = _to_int(config_dict.get("data_offset", 0)) & 0xFFFFFFFF
    return MemoryConfig(pc_offset=pc_offset, data_offset=data_offset)
