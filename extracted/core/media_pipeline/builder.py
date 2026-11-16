"""Contrato para construção do catálogo."""

from __future__ import annotations

from typing import Protocol

from .models import Exercise, Inventory

class CatalogBuilder(Protocol):
    def build(
        self,
        inventory: Inventory,
    ) -> list[Exercise]:
        """Constrói o catálogo a partir do Inventory."""
