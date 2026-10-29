"""Pipeline independente de banco para catalogar a biblioteca de mídias.

Este pacote não importa Django nem os modelos do FitFlix.  Ele pode, portanto,
ser executado em uma estação de curadoria antes que qualquer dado seja gravado.
"""

from .cloudinary import (
    CloudinaryConfig,
    CloudinaryUploader,
    MediaUploader,
    UploadResult,
    build_public_id,
)
from .inventory import load_inventory, save_inventory
from .models import Exercise, Inventory, MatchResult, MediaFile, Variation
from .parser import ExerciseNameParser, ParsedExerciseName
from .scanner import MediaScanner, ScannerConfig
from .syncer import CloudinarySyncer, SyncReport, SyncResult

__all__ = [
    "build_public_id",
    "CloudinaryConfig",
    "CloudinarySyncer",
    "CloudinaryUploader",
    "ExerciseNameParser",
    "Exercise",
    "Inventory",
    "load_inventory",
    "MatchResult",
    "MediaFile",
    "MediaScanner",
    "MediaUploader",
    "ParsedExerciseName",
    "save_inventory",
    "ScannerConfig",
    "SyncReport",
    "SyncResult",
    "UploadResult",
    "Variation",
]
