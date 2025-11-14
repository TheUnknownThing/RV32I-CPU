"""Utility helpers for toy ADD/ADDI programs"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

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

