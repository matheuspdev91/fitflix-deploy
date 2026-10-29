"""Upload real de mídias para o Cloudinary.

Este módulo não depende de Django.  Toda a configuração é passada via
``CloudinaryConfig`` ou variáveis de ambiente.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cloudinary
import cloudinary.api
import cloudinary.uploader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocolo (contrato público)
# ---------------------------------------------------------------------------

class MediaUploader(Protocol):
    """Contrato genérico de upload — permite substituir por mocks nos testes."""

    def upload(self, path: Path, public_id: str) -> "UploadResult":
        """Envia o arquivo e devolve o resultado."""

    def exists(self, public_id: str) -> bool:
        """Verifica se o ``public_id`` já existe no destino."""

    def build_url(self, public_id: str) -> str:
        """Retorna a URL pública para um ``public_id`` já hospedado."""


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CloudinaryConfig:
    """Credenciais carregáveis de env vars ou passadas explicitamente."""

    cloud_name: str
    api_key: str
    api_secret: str

    @classmethod
    def from_env(cls) -> "CloudinaryConfig":
        """Carrega a partir de ``CLOUDINARY_CLOUD_NAME``, ``CLOUDINARY_API_KEY``
        e ``CLOUDINARY_API_SECRET``."""
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
        api_key = os.environ.get("CLOUDINARY_API_KEY", "")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET", "")
        if not all([cloud_name, api_key, api_secret]):
            raise EnvironmentError(
                "Variáveis CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY e "
                "CLOUDINARY_API_SECRET são obrigatórias."
            )
        return cls(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)


# ---------------------------------------------------------------------------
# Resultado de upload
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class UploadResult:
    """Dados retornados após upload (ou reuso) de um asset."""

    public_id: str
    secure_url: str
    version: int = 0
    format: str = ""
    bytes: int = 0
    already_existed: bool = False


# ---------------------------------------------------------------------------
# Implementação real
# ---------------------------------------------------------------------------

class CloudinaryUploader:
    """Implementação concreta de ``MediaUploader`` usando a SDK do Cloudinary."""

    def __init__(self, config: CloudinaryConfig) -> None:
        self.config = config
        cloudinary.config(
            cloud_name=config.cloud_name,
            api_key=config.api_key,
            api_secret=config.api_secret,
            secure=True,
        )

    def upload(
        self,
        path: Path,
        public_id: str,
        *,
        overwrite: bool = False,
    ) -> UploadResult:
        """Envia o arquivo local para o Cloudinary."""
        result = cloudinary.uploader.upload(
            str(path),
            public_id=public_id,
            resource_type="image",
            overwrite=overwrite,
            unique_filename=False,
        )
        return UploadResult(
            public_id=result.get("public_id", public_id),
            secure_url=result.get("secure_url") or result.get("url", ""),
            version=int(result.get("version", 0)),
            format=result.get("format", ""),
            bytes=int(result.get("bytes", 0)),
            already_existed=False,
        )

    def exists(self, public_id: str) -> bool:
        """Verifica se o ``public_id`` já existe no Cloudinary."""
        try:
            cloudinary.api.resource(public_id, resource_type="image")
            return True
        except Exception as exc:
            if _is_not_found(exc):
                return False
            raise

    def build_url(self, public_id: str) -> str:
        """Retorna a URL segura de um asset já hospedado."""
        return cloudinary.CloudinaryImage(public_id).build_url(secure=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SLUG_UNSAFE = re.compile(r"[^a-z0-9]+")


def slugify_segment(value: str) -> str:
    """Transforma um segmento de caminho em slug seguro para public_id."""
    decomposed = unicodedata.normalize("NFD", value)
    ascii_only = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return _SLUG_UNSAFE.sub("-", ascii_only.casefold()).strip("-")


def build_public_id(
    category: str,
    muscle_group: str,
    normalized_name: str,
    extension: str = "",
) -> str:
    """Monta o ``public_id`` determinístico a partir dos metadados da mídia.

    Formato: ``fitflix/{category}/{muscle_group}/{name}{extension}``
    """
    parts = ["fitflix"]
    if category:
        parts.append(slugify_segment(category))
    if muscle_group:
        parts.append(slugify_segment(muscle_group))
    parts.append(slugify_segment(normalized_name))
    
    base_id = "/".join(parts)
    return f"{base_id}{extension}"


def _is_not_found(exc: Exception) -> bool:
    class_name = exc.__class__.__name__
    if class_name == "NotFound":
        return True
    message = str(exc).lower()
    return "not found" in message or "404" in message
