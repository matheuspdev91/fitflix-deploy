"""Aliases expansíveis e normalizados para futuras etapas de matching."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalizer import normalize_name


@dataclass(frozen=True, slots=True)
class AliasRegistry:
    aliases: dict[str, frozenset[str]] = field(default_factory=dict)

    def canonicalize(self, value: str) -> str:
        normalized = normalize_name(value)
        for canonical, alternatives in self.aliases.items():
            options = {normalize_name(canonical), *(normalize_name(item) for item in alternatives)}
            if normalized in options:
                return normalize_name(canonical)
        return normalized
