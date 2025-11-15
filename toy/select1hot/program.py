"""Program helpers reused from the toy ADD example."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

from ..add.program import (
    normalize_program as _normalize_program,
    read_program_file as _read_program_file,
    write_program_image as _write_program_image,
)


def normalize_program(program: Sequence[int] | Iterable[int] | Path | str | None) -> List[int]:
    return _normalize_program(program)


def read_program_file(path: Path) -> List[int]:
    return _read_program_file(path)


def write_program_image(words: Sequence[int], workspace: Path) -> Path:
    return _write_program_image(words, workspace)
