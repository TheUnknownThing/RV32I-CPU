"""Program helpers for the Naive RV32I CPU."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class MemoryConfig:
    """Offsets describing where program and data memories live."""

    pc_offset: int = 0
    data_offset: int = 0


def normalize_program(
    program: Sequence[int] | Iterable[int] | Path | str | None,
) -> List[int]:
    if isinstance(program, (str, Path)):
        return read_program_file(Path(program))

    values = [int(word) & 0xFFFFFFFF for word in program]
    if not values:
        raise ValueError("Program must contain at least one instruction.")
    return values


def read_program_file(path: Path) -> List[int]:
    words: List[int] = []
    with open(path, "r", encoding="utf-8") as src:
        for raw in src:
            raw = raw.split("//")[0].strip()
            if not raw:
                continue
            words.append(int(raw, 16))
    if not words:
        raise ValueError(f"Program file {path} is empty.")
    return words


def write_program_image(words: Sequence[int], workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    program_path = workspace / "program.hex"
    with open(program_path, "w", encoding="utf-8") as dst:
        for idx, word in enumerate(words):
            dst.write(f"{word:08x} // {idx * 4:04x}\n")
    return program_path


def normalize_data_image(data: Sequence[int] | Iterable[int] | Path | str | None) -> List[int]:
    """Normalize the input data image into a byte array."""

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


def bytes_to_words(byte_values: Sequence[int], depth_words: int) -> list[int]:
    """Helper function for initializing memory from bytes."""

    words: list[int] = []
    for word_idx in range(depth_words):
        assembled = 0
        for byte in range(4):
            idx = word_idx * 4 + byte
            if idx < len(byte_values):
                assembled |= (int(byte_values[idx]) & 0xFF) << (8 * byte)
        words.append(assembled & 0xFFFFFFFF)
    return words
