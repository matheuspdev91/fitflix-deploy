"""Contratos para agrupamento por corpus; implementação será adicionada depois."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from .models import MediaFile


@dataclass(frozen=True, slots=True)
class ExerciseCluster:
    canonical_name: str
    media_files: tuple[MediaFile, ...]
    confidence: float


class AssetGrouper(Protocol):
    def group(self, media_files: Sequence[MediaFile]) -> tuple[ExerciseCluster, ...]: ...
