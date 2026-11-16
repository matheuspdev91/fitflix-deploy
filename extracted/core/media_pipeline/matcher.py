from __future__ import annotations

from .aliases import AliasRegistry
from .models import Inventory, MatchResult, MediaFile
from .parser import ParsedExerciseName


class ExerciseMatcher:
    """Resolve um nome analisado para a melhor media conhecida no inventario."""

    def __init__(
        self,
        inventory: Inventory,
        aliases: AliasRegistry | None = None,
    ) -> None:
        self.inventory = inventory
        self.aliases = aliases or AliasRegistry()

    def match(self, parsed: ParsedExerciseName) -> MatchResult:
        """Executa a resolucao contra as midias do inventario."""
        if not parsed.exercise:
            return MatchResult(matched=False, reason="empty exercise")

        canonical_exercise = self.aliases.canonicalize(parsed.normalized_exercise)
        candidates = self._find_candidates(canonical_exercise)

        if not candidates:
            return MatchResult(matched=False, reason="no candidates")

        return self._best_candidate(parsed, candidates)

    def _find_candidates(self, canonical_name: str) -> list[MediaFile]:
        return [
            media
            for media in self.inventory.media_files
            if canonical_name in media.normalized_name
        ]

    def _best_candidate(
        self,
        parsed: ParsedExerciseName,
        candidates: list[MediaFile],
    ) -> MatchResult:
        candidate = candidates[0]
        return MatchResult(
            matched=True,
            media=candidate,
            score=self._score_candidate(parsed, candidate),
            reason="best candidate",
        )

    def _score_candidate(
        self,
        parsed: ParsedExerciseName,
        candidate: MediaFile,
    ) -> float:
        return 1.0
