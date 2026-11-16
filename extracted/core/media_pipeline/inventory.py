import json
from pathlib import Path

from .models import Inventory, MediaFile


def save_inventory(inventory: Inventory, destination: str | Path) -> Path:
    """Persiste um :class:`Inventory` como uma lista de registros JSON."""
    records = [media.to_dict() for media in inventory.media_files]
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


def load_inventory(source: str | Path) -> Inventory:
    """Carrega um inventário salvo nos formatos atual ou legado."""
    records = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("O inventário JSON deve conter uma lista de mídias.")

    def value(record: dict[str, object], current: str, legacy: str) -> object:
        if current in record:
            return record[current]
        if legacy in record:
            return record[legacy]
        raise ValueError(f"Registro de mídia sem o campo '{current}'.")

    media_files: list[MediaFile] = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Cada registro de mídia deve ser um objeto JSON.")
        media_files.append(
            MediaFile(
                category=str(value(record, "category", "categoria")),
                muscle_group=str(value(record, "muscle_group", "grupo")),
                filename=str(value(record, "filename", "arquivo")),
                stem=str(value(record, "stem", "nome_original")),
                normalized_name=str(value(record, "normalized_name", "nome_normalizado")),
                extension=str(value(record, "extension", "extensao")),
                size=int(value(record, "size", "tamanho")),
                sha256=str(record["sha256"]),
                path=Path(str(value(record, "path", "caminho"))),
            )
        )
    return Inventory(media_files=media_files)
