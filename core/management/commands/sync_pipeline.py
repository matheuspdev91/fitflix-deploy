import os

from django.core.management.base import BaseCommand
from django.db import transaction

from core.media_pipeline.cloudinary import CloudinaryConfig, CloudinaryUploader
from core.media_pipeline.db_matcher import DatabaseMatcher
from core.media_pipeline.scanner import MediaScanner
from core.media_pipeline.syncer import CloudinarySyncer
from core.media_pipeline.utils import validate_directory
from core.models import VariacaoExercicio


class Command(BaseCommand):
    help = "Sincroniza a pipeline de mídias com o Cloudinary e o banco de dados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="media/exercicios",
            help="Caminho para a pasta raiz de GIFs.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem upload nem gravação no banco.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Reenvia o arquivo mesmo quando o public_id já existe no Cloudinary.",
        )
        parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Pula a etapa de upload ao Cloudinary (usa paths locais).",
        )
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help="Cria exercícios/variações novos para mídias sem correspondência no BD.",
        )

    def handle(self, *args, **options):
        caminho_gifs = options["path"]
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        skip_upload = options["skip_upload"]
        create_missing = options["create_missing"]

        if not os.path.exists(caminho_gifs):
            self.stdout.write(
                self.style.ERROR(f"Pasta '{caminho_gifs}' não encontrada.")
            )
            return

        pasta = validate_directory(caminho_gifs)

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("  FITFLIX SYNC PIPELINE")
        self.stdout.write("=" * 60)

        # ---------------------------------------------------------------
        # 1. Scanner → Inventory
        # ---------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("1/3  Escaneando mídias..."))

        scanner = MediaScanner()
        inventory = scanner.scan(pasta)
        self.stdout.write(
            self.style.SUCCESS(
                f"     {len(inventory.media_files)} mídias encontradas."
            )
        )

        # ---------------------------------------------------------------
        # 2. Cloudinary Sync
        # ---------------------------------------------------------------
        self.stdout.write("")
        sync_report = None

        if skip_upload:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    "2/3  Upload Cloudinary — PULADO (--skip-upload)"
                )
            )
        else:
            mode = "DRY-RUN" if dry_run else "ATIVO"
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"2/3  Upload Cloudinary ({mode})...")
            )

            try:
                config = CloudinaryConfig.from_env()
            except EnvironmentError as exc:
                self.stdout.write(self.style.ERROR(f"     {exc}"))
                self.stdout.write(
                    self.style.WARNING(
                        "     Use --skip-upload para pular esta etapa."
                    )
                )
                return

            uploader = CloudinaryUploader(config)
            syncer = CloudinarySyncer(
                uploader,
                overwrite=overwrite,
                dry_run=dry_run,
            )
            sync_report = syncer.sync(inventory)

            self.stdout.write(
                self.style.SUCCESS(
                    f"     Uploads: {sync_report.uploaded}  |  "
                    f"Reusados: {sync_report.reused}  |  "
                    f"Skipped: {sync_report.skipped}  |  "
                    f"Falhas: {sync_report.failed}"
                )
            )

            if sync_report.failed:
                for r in sync_report.results:
                    if r.action == "failed":
                        self.stdout.write(
                            self.style.ERROR(
                                f"     ✗ {r.media.filename}: {r.error}"
                            )
                        )

        # ---------------------------------------------------------------
        # 3. Match + Persistência no banco
        # ---------------------------------------------------------------
        self.stdout.write("")

        if dry_run:
            self.stdout.write(
                self.style.MIGRATE_HEADING("3/3  Persistência — SIMULAÇÃO (--dry-run)")
            )
        else:
            self.stdout.write(
                self.style.MIGRATE_HEADING("3/3  Vinculando mídias ao banco...")
            )

        # Índice de sync results: filename → public_id
        sync_index: dict[str, str] = {}
        if sync_report:
            for r in sync_report.results:
                if r.action in ("uploaded", "reused"):
                    sync_index[r.media.filename] = r.public_id

        # Carregar todas as variações do BD para o matcher
        variacoes_qs = (
            VariacaoExercicio.objects.select_related("exercicio")
            .values_list("id", "nome", "exercicio__nome", "gif")
        )
        variacoes_data = [
            {
                "id": vid,
                "nome": nome,
                "exercicio_nome": ex_nome,
                "gif_name": gif_name,
            }
            for vid, nome, ex_nome, gif_name in variacoes_qs
        ]

        matcher = DatabaseMatcher(variacoes_data)
        sizes = matcher.index_sizes
        self.stdout.write(
            f"     Índices: {sizes['gif_path']} gif_path | "
            f"{sizes['full_name']} full_name | "
            f"{sizes['tokens']} tokens"
        )

        # Processar cada mídia
        matched = 0
        updated = 0
        already_ok = 0
        unmatched_files = []

        for media in inventory.media_files:
            result = matcher.match(media.stem)

            if result is None:
                unmatched_files.append(media.filename)
                continue

            matched += 1

            # Determinar o valor do campo gif
            cloud_id = sync_index.get(media.filename)
            if cloud_id and not skip_upload:
                gif_value = f"{cloud_id}{media.path.suffix.lower()}"
            else:
                gif_value = media.filename

            if dry_run:
                self.stdout.write(
                    f"     MATCH V#{result.variacao_id} <- "
                    f"{media.filename} "
                    f"[{result.strategy.value}, {result.confidence}]"
                )
                continue

            # Atualizar no BD
            try:
                variacao = VariacaoExercicio.objects.get(pk=result.variacao_id)
                if variacao.gif.name != gif_value:
                    variacao.gif = gif_value
                    variacao.save(update_fields=["gif"])
                    updated += 1
                else:
                    already_ok += 1
            except VariacaoExercicio.DoesNotExist:
                unmatched_files.append(media.filename)

        # Relatório de não-matcheados
        if unmatched_files:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"     {len(unmatched_files)} mídias sem correspondência no BD:"
                )
            )
            for fname in unmatched_files[:20]:
                self.stdout.write(self.style.WARNING(f"       • {fname}"))
            if len(unmatched_files) > 20:
                self.stdout.write(
                    self.style.WARNING(
                        f"       ... e mais {len(unmatched_files) - 20}"
                    )
                )

            if not create_missing:
                self.stdout.write(
                    self.style.NOTICE(
                        "     Use --create-missing para criar registros "
                        "para mídias sem correspondência."
                    )
                )

        # Resumo
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"     Matcheadas:   {matched}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"     Atualizadas:  {updated}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"     Já corretas:  {already_ok}")
        )
        self.stdout.write(
            self.style.WARNING(
                f"     Sem match:    {len(unmatched_files)}"
            )
        )

        # ---------------------------------------------------------------
        # Resumo final
        # ---------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(
            self.style.SUCCESS("  Sincronização concluída com sucesso!")
        )
        self.stdout.write("=" * 60)
