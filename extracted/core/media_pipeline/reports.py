"""Contratos para relatórios CSV, HTML e resumo; implementação posterior."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .auditor import AuditFinding


class ReportWriter(Protocol):
    def write_csv(self, findings: Sequence[AuditFinding], destination: Path) -> Path: ...
    def write_html(self, findings: Sequence[AuditFinding], destination: Path) -> Path: ...
