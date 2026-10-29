"""Leitura da árvore de mídia e identificação estrutural de categoria e grupo."""

from dataclasses import dataclass, field
from hashlib import sha256
import logging
from pathlib import Path

from .models import Inventory, MediaFile
from .normalizer import normalize_name
from .utils import validate_directory

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    extensions: frozenset[str] = field(default_factory=lambda: frozenset({".gif", ".mp4", ".webm"}))
    hash_chunk_size: int = 1024 * 1024


class MediaScanner:
    """Varre uma raiz onde o último diretório é sempre o grupo muscular.

    Todos os diretórios anteriores formam a categoria. Isso suporta árvores de
    profundidade variável, por exemplo ``GIFS EXERCÍCIOS/GIFS ACADEMIA/PEITORAL``.
    """

    def __init__(self, config: ScannerConfig | None = None) -> None:
        self.config = config or ScannerConfig()

    def scan(self, root: str | Path) -> Inventory:
        base = validate_directory(root)
        media_files: list[MediaFile] = []
        for path in sorted(base.rglob("*"), key=lambda item: str(item).casefold()):
            if not path.is_file() or path.suffix.casefold() not in self.config.extensions:
                continue
            media_files.append(self._asset_from_path(base, path))
        logger.info("Inventário concluído: %d mídia(s) em %s", len(media_files), base)
        return Inventory(media_files=media_files)

    def _asset_from_path(self, root: Path, path: Path) -> MediaFile:
        relative = path.relative_to(root)
        directories = relative.parts[:-1]
        category = " / ".join(directories[:-1]) if len(directories) > 1 else ""
        muscle_group = directories[-1] if directories else ""
        stat = path.stat()
        return MediaFile(
            category=category,
            muscle_group=muscle_group,
            filename=path.name,
            stem=path.stem,
            normalized_name=normalize_name(path.stem),
            extension=path.suffix.casefold(),
            size=stat.st_size,
            sha256=calculate_sha256(path, self.config.hash_chunk_size),
            path=path,
        )


def calculate_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as media_file:
        for chunk in iter(lambda: media_file.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
