"""Utilitários de filesystem compartilhados pelo pipeline."""

from pathlib import Path


def validate_directory(path: str | Path) -> Path:
    directory = Path(path).expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(directory)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    return directory


validar_pasta = validate_directory
