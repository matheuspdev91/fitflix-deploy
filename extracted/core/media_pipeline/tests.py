"""Testes unitários do pipeline, sem inicializar Django ou banco de dados."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import unittest

from .cloudinary import (
    CloudinaryUploader,
    UploadResult,
    build_public_id,
    slugify_segment,
)
from .inventory import load_inventory, save_inventory
from .memory_builder import InMemoryCatalogBuilder
from .models import Inventory, MediaFile
from .normalizer import normalize_name
from .parser import ExerciseNameParser
from .scanner import MediaScanner
from .syncer import CloudinarySyncer, SyncReport, SyncResult


# ===================================================================
# Helpers
# ===================================================================

def _make_media(**overrides) -> MediaFile:
    """Cria um MediaFile de teste com defaults sensatos."""
    defaults = dict(
        path=Path("test/peitoral/supino_reto.gif"),
        category="GIFS ACADEMIA",
        muscle_group="PEITORAL",
        filename="supino_reto.gif",
        stem="supino_reto",
        normalized_name="supino reto",
        extension=".gif",
        size=1024,
        sha256="a" * 64,
    )
    defaults.update(overrides)
    return MediaFile(**defaults)


# ===================================================================
# Normalizer
# ===================================================================

class NormalizerTests(unittest.TestCase):
    def test_removes_known_file_artifacts(self) -> None:
        self.assertEqual(
            normalize_name("Supino-Reto (2)_final.gif"),
            "supino reto",
        )


# ===================================================================
# Parser
# ===================================================================

class ParserTests(unittest.TestCase):
    def test_splits_conventional_name(self) -> None:
        parsed = ExerciseNameParser().parse("Supino Inclinado Barra.gif")
        self.assertEqual(parsed.exercise, "Supino")
        self.assertEqual(parsed.variation, "Inclinado Barra")

    def test_honours_explicit_separator_for_compound_exercise(self) -> None:
        parsed = ExerciseNameParser().parse("Levantamento Terra - Romeno.gif")
        self.assertEqual(parsed.exercise, "Levantamento Terra")
        self.assertEqual(parsed.variation, "Romeno")


# ===================================================================
# Scanner
# ===================================================================

class ScannerTests(unittest.TestCase):
    def test_builds_asset_from_variable_depth_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            media_file = root / "GIFS" / "ACADEMIA" / "PEITORAL" / "Supino_Reto.gif"
            media_file.parent.mkdir(parents=True)
            media_file.write_bytes(b"GIF89a")

            media = MediaScanner().scan(root).media_files[0]

        self.assertEqual(media.category, "GIFS / ACADEMIA")
        self.assertEqual(media.muscle_group, "PEITORAL")
        self.assertEqual(media.normalized_name, "supino reto")
        self.assertEqual(len(media.sha256), 64)


# ===================================================================
# Inventory persistence
# ===================================================================

class InventoryPersistenceTests(unittest.TestCase):
    def test_round_trips_media_file_with_current_and_legacy_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "inventario.json"
            media = MediaFile(
                path=Path("midias/peitoral/supino.gif"),
                category="GIFS / ACADEMIA",
                muscle_group="PEITORAL",
                filename="supino.gif",
                stem="supino",
                normalized_name="supino",
                extension=".gif",
                size=6,
                sha256="a" * 64,
            )
            save_inventory(Inventory(media_files=[media]), path)
            loaded = load_inventory(path)

        self.assertEqual(loaded.media_files, [media])


# ===================================================================
# InMemoryCatalogBuilder
# ===================================================================

class InMemoryCatalogBuilderTests(unittest.TestCase):
    def test_groups_variations_under_the_parsed_exercise(self) -> None:
        media_files = [
            MediaFile(
                path=Path("supino_reto.gif"),
                category="ACADEMIA",
                muscle_group="PEITORAL",
                filename="Supino - Reto.gif",
                stem="Supino - Reto",
                normalized_name="supino reto",
                extension=".gif",
                size=1,
                sha256="a",
            ),
            MediaFile(
                path=Path("supino_inclinado.gif"),
                category="ACADEMIA",
                muscle_group="PEITORAL",
                filename="Supino - Inclinado.gif",
                stem="Supino - Inclinado",
                normalized_name="supino inclinado",
                extension=".gif",
                size=1,
                sha256="b",
            ),
        ]

        catalog = InMemoryCatalogBuilder().build(Inventory(media_files))

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0].name, "Supino")
        self.assertEqual(
            [variation.name for variation in catalog[0].variations],
            ["Reto", "Inclinado"],
        )


# ===================================================================
# Cloudinary — build_public_id & slugify
# ===================================================================

class BuildPublicIdTests(unittest.TestCase):
    def test_full_path_with_category_and_group(self) -> None:
        pid = build_public_id(
            category="GIFS ACADEMIA",
            muscle_group="PEITORAL",
            normalized_name="supino reto",
        )
        self.assertEqual(pid, "fitflix/gifs-academia/peitoral/supino-reto")

    def test_no_category(self) -> None:
        pid = build_public_id(
            category="",
            muscle_group="COSTAS",
            normalized_name="remada curvada",
        )
        self.assertEqual(pid, "fitflix/costas/remada-curvada")

    def test_no_category_no_group(self) -> None:
        pid = build_public_id(
            category="",
            muscle_group="",
            normalized_name="exercicio generico",
        )
        self.assertEqual(pid, "fitflix/exercicio-generico")

    def test_accented_characters_removed(self) -> None:
        pid = build_public_id(
            category="GIFS CALISTENIA",
            muscle_group="GLÚTEOS",
            normalized_name="elevação pélvica",
        )
        self.assertEqual(pid, "fitflix/gifs-calistenia/gluteos/elevacao-pelvica")


class SlugifySegmentTests(unittest.TestCase):
    def test_basic_slug(self) -> None:
        self.assertEqual(slugify_segment("GIFS ACADEMIA"), "gifs-academia")

    def test_accents(self) -> None:
        self.assertEqual(slugify_segment("GLÚTEOS"), "gluteos")

    def test_special_characters(self) -> None:
        self.assertEqual(slugify_segment("GIFS / ACADEMIA"), "gifs-academia")


# ===================================================================
# CloudinarySyncer — com uploader mockado
# ===================================================================

class CloudinarySyncerTests(unittest.TestCase):
    def _mock_uploader(self, *, exists_return=False) -> MagicMock:
        uploader = MagicMock(spec=CloudinaryUploader)
        uploader.exists.return_value = exists_return
        uploader.upload.return_value = UploadResult(
            public_id="fitflix/peitoral/supino-reto",
            secure_url="https://res.cloudinary.com/test/image/upload/fitflix/peitoral/supino-reto.gif",
            version=1,
            format="gif",
            bytes=1024,
            already_existed=False,
        )
        uploader.build_url.return_value = (
            "https://res.cloudinary.com/test/image/upload/fitflix/peitoral/supino-reto.gif"
        )
        return uploader

    def test_upload_new_media(self) -> None:
        """Mídia nova → action = 'uploaded'."""
        uploader = self._mock_uploader(exists_return=False)
        syncer = CloudinarySyncer(uploader)
        inventory = Inventory(media_files=[_make_media()])

        report = syncer.sync(inventory)

        self.assertEqual(report.uploaded, 1)
        self.assertEqual(report.reused, 0)
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.results[0].action, "uploaded")
        uploader.upload.assert_called_once()

    def test_reuse_existing_media(self) -> None:
        """Mídia já existente → action = 'reused', sem upload."""
        uploader = self._mock_uploader(exists_return=True)
        syncer = CloudinarySyncer(uploader)
        inventory = Inventory(media_files=[_make_media()])

        report = syncer.sync(inventory)

        self.assertEqual(report.reused, 1)
        self.assertEqual(report.uploaded, 0)
        uploader.upload.assert_not_called()
        uploader.build_url.assert_called_once()

    def test_overwrite_forces_upload(self) -> None:
        """Com overwrite=True, faz upload mesmo se já existe."""
        uploader = self._mock_uploader(exists_return=True)
        syncer = CloudinarySyncer(uploader, overwrite=True)
        inventory = Inventory(media_files=[_make_media()])

        report = syncer.sync(inventory)

        self.assertEqual(report.uploaded, 1)
        uploader.upload.assert_called_once()
        # exists() nunca é chamado em modo overwrite
        uploader.exists.assert_not_called()

    def test_dry_run_skips_all(self) -> None:
        """Dry-run → action = 'skipped', sem nenhuma chamada ao uploader."""
        uploader = self._mock_uploader()
        syncer = CloudinarySyncer(uploader, dry_run=True)
        inventory = Inventory(media_files=[_make_media()])

        report = syncer.sync(inventory)

        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.uploaded, 0)
        uploader.upload.assert_not_called()
        uploader.exists.assert_not_called()

    def test_upload_failure_captured(self) -> None:
        """Falha no upload → action = 'failed', erro capturado."""
        uploader = self._mock_uploader(exists_return=False)
        uploader.upload.side_effect = ConnectionError("Network down")
        syncer = CloudinarySyncer(uploader)
        inventory = Inventory(media_files=[_make_media()])

        report = syncer.sync(inventory)

        self.assertEqual(report.failed, 1)
        self.assertEqual(report.uploaded, 0)
        self.assertIn("Network down", report.results[0].error)

    def test_multiple_media_mixed_results(self) -> None:
        """Múltiplas mídias com resultados mistos."""
        uploader = self._mock_uploader(exists_return=False)
        # O segundo upload falha
        uploader.upload.side_effect = [
            UploadResult(
                public_id="fitflix/peitoral/supino-reto",
                secure_url="https://example.com/a.gif",
            ),
            ConnectionError("Timeout"),
        ]

        media_a = _make_media(filename="supino_reto.gif", normalized_name="supino reto")
        media_b = _make_media(filename="rosca_direta.gif", normalized_name="rosca direta")
        inventory = Inventory(media_files=[media_a, media_b])

        report = syncer = CloudinarySyncer(uploader)
        report = syncer.sync(inventory)

        self.assertEqual(report.total, 2)
        self.assertEqual(report.uploaded, 1)
        self.assertEqual(report.failed, 1)


# ===================================================================
# SyncReport — contadores
# ===================================================================

class SyncReportTests(unittest.TestCase):
    def test_counters(self) -> None:
        media = _make_media()
        report = SyncReport(results=[
            SyncResult(media=media, public_id="a", secure_url="u", action="uploaded"),
            SyncResult(media=media, public_id="b", secure_url="u", action="uploaded"),
            SyncResult(media=media, public_id="c", secure_url="u", action="reused"),
            SyncResult(media=media, public_id="d", secure_url="", action="skipped"),
            SyncResult(media=media, public_id="e", secure_url="", action="failed", error="err"),
        ])
        self.assertEqual(report.total, 5)
        self.assertEqual(report.uploaded, 2)
        self.assertEqual(report.reused, 1)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.failed, 1)

    def test_empty_report(self) -> None:
        report = SyncReport()
        self.assertEqual(report.total, 0)
        self.assertEqual(report.uploaded, 0)


# ===================================================================
# DatabaseMatcher
# ===================================================================

from .db_matcher import DatabaseMatcher, MatchStrategy

class DatabaseMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.variacoes = [
            {
                "id": 388,
                "nome": "De escápula",
                "exercicio_nome": "Dips",
                "gif_name": "exercicios/gif/Dips de escápula.gif",
            },
            {
                "id": 100,
                "nome": "Padrão",
                "exercicio_nome": "Supino Reto",
                "gif_name": "exercicios/gif/Supino.gif",
            },
            {
                "id": 101,
                "nome": "Com halteres",
                "exercicio_nome": "Supino Inclinado",
                "gif_name": "",  # Sem gif ainda
            },
        ]
        self.matcher = DatabaseMatcher(self.variacoes)

    def test_match_by_gif_path(self) -> None:
        """Deve matchear se o basename do arquivo for igual ao basename do campo gif."""
        result = self.matcher.match("Dips de escápula (1)")
        self.assertIsNotNone(result)
        self.assertEqual(result.variacao_id, 388)
        self.assertEqual(result.strategy, MatchStrategy.BY_GIF_PATH)
        self.assertEqual(result.confidence, 1.0)

    def test_match_by_full_name(self) -> None:
        """Deve matchear pelo exercicio_nome + nome se não houver match por gif."""
        # Supino Inclinado com Halteres
        result = self.matcher.match("Supino Inclinado com Halteres")
        self.assertIsNotNone(result)
        self.assertEqual(result.variacao_id, 101)
        self.assertEqual(result.strategy, MatchStrategy.BY_FULL_NAME)
        self.assertEqual(result.confidence, 0.95)

    def test_match_by_tokens(self) -> None:
        """Fallback por tokens quando os nomes exatos não batem perfeitamente."""
        # Nomes invertidos, mas mesmos tokens
        result = self.matcher.match("Escapula dips")
        self.assertIsNotNone(result)
        self.assertEqual(result.variacao_id, 388)
        self.assertEqual(result.strategy, MatchStrategy.BY_TOKENS)

    def test_no_match(self) -> None:
        """Retorna None para mídias sem correspondência."""
        result = self.matcher.match("Agachamento Livre")
        self.assertIsNone(result)

    def test_stopwords_ignored(self) -> None:
        """Stopwords não devem causar falsos positivos no token match."""
        # "com" é stopword, então não deve dar match em "Com halteres" se não tiver "halteres"
        result = self.matcher.match("Supino com barra")
        # Pode não dar match no 101 porque "barra" não é "halteres"
        self.assertNotEqual(getattr(result, 'variacao_id', None), 101)

if __name__ == "__main__":
    unittest.main()
