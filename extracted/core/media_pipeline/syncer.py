"""Orquestrador de sincronização: Inventory → Cloudinary → resultado para persistência.

Este módulo não depende de Django.  Recebe um ``CloudinaryUploader`` (ou mock)
e processa o inventário inteiro, produzindo um ``SyncReport`` com o resultado
de cada mídia.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from .cloudinary import CloudinaryUploader, UploadResult, build_public_id
from .models import Inventory, MediaFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resultado por arquivo
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SyncResult:
    """Resultado da sincronização de um único arquivo."""

    media: MediaFile
    public_id: str
    secure_url: str
    action: Literal["uploaded", "reused", "skipped", "failed"]
    error: str | None = None


# ---------------------------------------------------------------------------
# Relatório agregado
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SyncReport:
    """Relatório consolidado de uma execução completa do syncer."""

    results: list[SyncResult] = field(default_factory=list)

    @property
    def uploaded(self) -> int:
        return sum(1 for r in self.results if r.action == "uploaded")

    @property
    def reused(self) -> int:
        return sum(1 for r in self.results if r.action == "reused")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.action == "skipped")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.action == "failed")

    @property
    def total(self) -> int:
        return len(self.results)


# ---------------------------------------------------------------------------
# Syncer
# ---------------------------------------------------------------------------

class CloudinarySyncer:
    """Itera pelo inventário, faz upload (ou reusa) e devolve ``SyncReport``.

    Erros por arquivo são capturados individualmente — a pipeline nunca
    aborta por conta de um único arquivo com falha.
    """

    def __init__(
        self,
        uploader: CloudinaryUploader,
        *,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.uploader = uploader
        self.overwrite = overwrite
        self.dry_run = dry_run

    def sync(self, inventory: Inventory) -> SyncReport:
        """Processa todas as mídias do inventário."""
        report = SyncReport()

        for media in inventory.media_files:
            result = self._sync_one(media)
            report.results.append(result)

        logger.info(
            "Sync concluído: %d total, %d uploads, %d reusados, %d skipped, %d falhas",
            report.total,
            report.uploaded,
            report.reused,
            report.skipped,
            report.failed,
        )
        return report

    def _sync_one(self, media: MediaFile) -> SyncResult:
        """Processa uma única mídia."""
        public_id = self._build_public_id(media)

        if self.dry_run:
            logger.debug("DRY-RUN: %s → %s", media.filename, public_id)
            return SyncResult(
                media=media,
                public_id=public_id,
                secure_url="",
                action="skipped",
            )

        try:
            # Verificar se já existe
            if not self.overwrite and self.uploader.exists(public_id):
                secure_url = self.uploader.build_url(public_id)
                media.cloudinary_public_id = public_id
                media.cloudinary_url = secure_url
                logger.debug("REUSADO: %s → %s", media.filename, public_id)
                return SyncResult(
                    media=media,
                    public_id=public_id,
                    secure_url=secure_url,
                    action="reused",
                )

            # Upload real
            upload_result: UploadResult = self.uploader.upload(
                media.path,
                public_id,
                overwrite=self.overwrite,
            )
            media.cloudinary_public_id = upload_result.public_id
            media.cloudinary_url = upload_result.secure_url
            logger.debug("UPLOAD: %s → %s", media.filename, upload_result.secure_url)
            return SyncResult(
                media=media,
                public_id=upload_result.public_id,
                secure_url=upload_result.secure_url,
                action="uploaded",
            )

        except Exception as exc:
            logger.warning("FALHA: %s — %s", media.filename, exc)
            return SyncResult(
                media=media,
                public_id=public_id,
                secure_url="",
                action="failed",
                error=str(exc),
            )

    @staticmethod
    def _build_public_id(media: MediaFile) -> str:
        """Delega ao helper do módulo cloudinary."""
        return build_public_id(
            category=media.category,
            muscle_group=media.muscle_group,
            normalized_name=media.stem,
        )
