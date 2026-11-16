"""Contratos para auditorias futuras do inventário e do catálogo reconstruído."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Inventory


@dataclass(frozen=True, slots=True)
class AuditFinding:
    kind: str
    message: str
    paths: tuple[str, ...] = ()


class InventoryAuditor(Protocol):
    def audit(self, inventory: Inventory) -> tuple[AuditFinding, ...]: ...
