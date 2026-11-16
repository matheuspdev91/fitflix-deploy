from dataclasses import dataclass, field
from pathlib import Path



@dataclass(slots=True)
class MediaFile:
    """
    Representa um arquivo de mídia encontrado pelo scanner.
    """

    path: Path

    category: str
    muscle_group: str

    filename: str
    stem: str

    normalized_name: str

    extension: str

    size: int

    sha256: str

    cloudinary_public_id: str = ""
    cloudinary_url: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serializa a mídia nos formatos atual e legado."""
        path = str(self.path)
        return {
            "category": self.category,
            "muscle_group": self.muscle_group,
            "filename": self.filename,
            "stem": self.stem,
            "normalized_name": self.normalized_name,
            "extension": self.extension,
            "size": self.size,
            "sha256": self.sha256,
            "path": path,
            "cloudinary_public_id": self.cloudinary_public_id,
            "cloudinary_url": self.cloudinary_url,
            "categoria": self.category,
            "grupo": self.muscle_group,
            "arquivo": self.filename,
            "nome_original": self.stem,
            "nome_normalizado": self.normalized_name,
            "extensao": self.extension,
            "tamanho": self.size,
            "caminho": path,
        }

@dataclass(slots=True)
class Variation:
    """
    Representa uma variação de exercício.
    """

    name: str

    media: MediaFile

@dataclass(slots=True)
class Exercise:
    """
    Representa um exercício composto por várias variações.
    """

    name: str

    category: str

    muscle_group: str

    variations: list[Variation] = field(default_factory=list)



@dataclass(slots=True)
class MatchResult:
    """
    Resultado produzido pelo Matcher.
    """

    matched: bool

    media: MediaFile | None = None

    exercise: Exercise | None = None

    variation: Variation | None = None

    score: float = 0.0

    reason: str = ""
    

@dataclass(slots=True)
class Inventory:
    """
    Inventário completo da biblioteca de mídias.
    """

    media_files: list[MediaFile] = field(default_factory=list)
