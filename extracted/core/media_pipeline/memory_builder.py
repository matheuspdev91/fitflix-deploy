from __future__ import annotations

from .aliases import AliasRegistry
from .builder import CatalogBuilder
from .models import Exercise, Inventory, Variation
from .parser import ExerciseNameParser


class InMemoryCatalogBuilder(CatalogBuilder):
    """Constroi exercicios e variacoes sem persistencia em banco."""

    def __init__(
        self,
        parser: ExerciseNameParser | None = None,
        aliases: AliasRegistry | None = None,
    ) -> None:
        self.parser = parser or ExerciseNameParser()
        self.aliases = aliases or AliasRegistry()

    def build(self, inventory: Inventory) -> list[Exercise]:
        exercises: dict[tuple[str, str, str], Exercise] = {}

        for media in inventory.media_files:
            parsed = self.parser.parse(media.filename)
            canonical_name = self.aliases.canonicalize(parsed.normalized_exercise)
            key = (canonical_name, media.category, media.muscle_group)

            exercise = exercises.get(key)
            if exercise is None:
                exercise = Exercise(
                    name=parsed.exercise,
                    category=media.category,
                    muscle_group=media.muscle_group,
                )
                exercises[key] = exercise

            exercise.variations.append(
                Variation(name=parsed.variation, media=media)
            )

        return list(exercises.values())
