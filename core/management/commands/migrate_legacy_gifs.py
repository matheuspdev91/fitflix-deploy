from pathlib import Path

from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio

from core.media_pipeline.scanner import MediaScanner
from core.media_pipeline.cloudinary import build_public_id, CloudinaryUploader, CloudinaryConfig
from core.media_pipeline.normalizer import normalize_name


class Command(BaseCommand):
    help = "Audita e prepara a migração dos GIFs legados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="media/exercicios",
            help="Caminho para a biblioteca local de mídias.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Mostra cada registro analisado.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Executa a migração real. Sem isso, roda apenas em modo dry-run.",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Testa a migração para uma VariacaoExercicio específica.",
        )

    def handle(self, *args, **options):
        caminho = Path(options["path"])
        verbose = options["verbose"]
        execute = options["execute"]
        variacao_id = options.get("id")

        if not caminho.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"Pasta '{caminho}' não encontrada."
                )
            )
            return

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("  FITFLIX — AUDITORIA DE MIGRAÇÃO DE GIFS LEGADOS")
        self.stdout.write("=" * 70)

        # ------------------------------------------------------------
        # 1. Inventário local
        # ------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write("1/3  Escaneando biblioteca local...")

        inventory = MediaScanner().scan(caminho)

        self.stdout.write(
            self.style.SUCCESS(
                f"     {len(inventory.media_files)} mídias encontradas."
            )
        )

        # ------------------------------------------------------------
        # 2. Índices locais
        #
        # Dois índices:
        #
        #   categoria + nome
        #       -> match preferencial
        #
        #   nome
        #       -> fallback quando o caminho legado não representa
        #          mais a localização física atual do arquivo
        #
        # A biblioteca local é a fonte de verdade para categoria,
        # grupo muscular e nome do asset.
        # ------------------------------------------------------------

        local_by_category_and_name = {}
        local_by_name = {}

        for media in inventory.media_files:
            category_key = normalize_name(media.category)
            name_key = normalize_name(media.stem)

            category_name_key = (
                category_key,
                name_key,
            )

            local_by_category_and_name.setdefault(
                category_name_key,
                [],
            )

            local_by_category_and_name[
                category_name_key
            ].append(media)

            local_by_name.setdefault(
                name_key,
                [],
            )

            local_by_name[name_key].append(media)

        # ------------------------------------------------------------
        # 3. Analisar registros legados
        # ------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write("2/3  Analisando registros legados...")

        antigos = (
            VariacaoExercicio.objects
            .filter(gif__startswith="fitflix/")
            .exclude(gif__startswith="fitflix/gifs-academia/")
            .select_related("exercicio", "grupo_muscular")
            .order_by("id")
        )

        if variacao_id:
            antigos = antigos.filter(id=variacao_id)
            if not antigos.exists():
                self.stdout.write(
                    self.style.ERROR(
                        f"VariacaoExercicio com ID {variacao_id} não encontrada "
                        "ou não é elegível para migração (já pode estar no formato novo)."
                    )
                )
                return

        migrar = []
        ambiguos = []
        sem_arquivo = []

        for variacao in antigos:
            gif_name = variacao.gif.name or ""

            partes = gif_name.split("/")

            # --------------------------------------------------------
            # O banco possui dois formatos legados conhecidos:
            #
            #   fitflix/<arquivo>.gif
            #   fitflix/<categoria>/<arquivo>.gif
            #
            # Portanto, categoria é opcional.
            # --------------------------------------------------------

            filename = partes[-1]
            stem = Path(filename).stem
            name_key = normalize_name(stem)

            legacy_category = None
            category_key = None

            if len(partes) >= 3:
                legacy_category = partes[1]
                category_key = normalize_name(legacy_category)

            # --------------------------------------------------------
            # Estratégia 1:
            #
            # Se existe categoria no caminho legado, tentamos primeiro
            # categoria + nome.
            # --------------------------------------------------------

            candidates = []

            if category_key:
                candidates = local_by_category_and_name.get(
                    (category_key, name_key),
                    [],
                )

            # --------------------------------------------------------
            # Estratégia 2:
            #
            # Se a categoria antiga não encontrou o arquivo, ou se o
            # registro antigo não possui categoria, procuramos apenas
            # pelo nome.
            #
            # Isso permite recuperar registros no formato:
            #
            #   fitflix/arquivo.gif
            #
            # mesmo quando o arquivo hoje está em:
            #
            #   media/exercicios/GIFS ACADEMIA/GRUPO/arquivo.gif
            # --------------------------------------------------------

            if not candidates:
                candidates = local_by_name.get(
                    name_key,
                    [],
                )

            # --------------------------------------------------------
            # Nenhum candidato
            # --------------------------------------------------------

            if not candidates:
                sem_arquivo.append(
                    (
                        variacao,
                        f"nenhum arquivo local para {filename}",
                    )
                )
                continue

            # --------------------------------------------------------
            # Mais de um candidato:
            #
            # NÃO escolher automaticamente.
            #
            # Isso protege casos como:
            #
            #   Superman.gif
            #   Flexão de joelhos.gif
            #
            # quando existem em categorias diferentes.
            # --------------------------------------------------------

            if len(candidates) > 1:
                ambiguos.append(
                    (
                        variacao,
                        candidates,
                    )
                )
                continue

            # --------------------------------------------------------
            # Exatamente um candidato
            # --------------------------------------------------------

            media = candidates[0]

            # --------------------------------------------------------
            # Construir o novo public_id usando a estrutura REAL
            # encontrada pelo Scanner.
            # --------------------------------------------------------

            new_public_id = build_public_id(
                category=media.category,
                muscle_group=media.muscle_group,
                normalized_name=media.stem,
            )

            new_file_name = (
                f"{new_public_id}{media.path.suffix.lower()}"
            )

            item = {
                "variacao": variacao,
                "media": media,
                "old_name": gif_name,
                "public_id": new_public_id,
                "new_name": new_file_name,
            }

            migrar.append(item)

            if verbose:
                self.stdout.write(
                    f"     MIGRAR V#{variacao.id} | "
                    f"{gif_name} -> {new_file_name}"
                )

        # ------------------------------------------------------------
        # Relatório
        # ------------------------------------------------------------

        self.stdout.write("")
        self.stdout.write("3/3  Resultado da auditoria")
        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                f"     Migração segura: {len(migrar)}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"     Ambíguos:         {len(ambiguos)}"
            )
        )

        self.stdout.write(
            self.style.ERROR(
                f"     Sem arquivo:      {len(sem_arquivo)}"
            )
        )

        # ------------------------------------------------------------
        # Casos ambíguos
        # ------------------------------------------------------------

        if ambiguos:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING("CASOS AMBÍGUOS:")
            )

            for variacao, candidates in ambiguos:
                self.stdout.write(
                    f"\nV#{variacao.id} | "
                    f"{variacao.exercicio.nome} | "
                    f"{variacao.nome}"
                )

                self.stdout.write(
                    f"  Banco: {variacao.gif.name}"
                )

                for media in candidates:
                    self.stdout.write(
                        f"  -> {media.path}"
                    )

        # ------------------------------------------------------------
        # Casos sem arquivo
        # ------------------------------------------------------------

        if sem_arquivo:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR("SEM ARQUIVO LOCAL:")
            )

            for variacao, motivo in sem_arquivo:
                self.stdout.write(
                    f"V#{variacao.id} | "
                    f"{variacao.exercicio.nome} | "
                    f"{variacao.nome}"
                )

                self.stdout.write(
                    f"  {motivo}"
                )

        # ------------------------------------------------------------
        # Execução (se solicitado)
        # ------------------------------------------------------------

        if execute and migrar:
            self.stdout.write("")
            self.stdout.write("4/4  Executando migração...")
            self.stdout.write("")
            
            uploader = CloudinaryUploader(CloudinaryConfig.from_env())
            
            for item in migrar:
                variacao = item["variacao"]
                media = item["media"]
                new_public_id = item["public_id"]
                new_file_name = item["new_name"]
                
                try:
                    if not uploader.exists(new_public_id):
                        upload_result = uploader.upload(media.path, new_public_id)
                        secure_url = upload_result.secure_url
                        action = "UPLOADED"
                    else:
                        secure_url = uploader.build_url(new_public_id)
                        action = "REUSED"
                        
                    variacao.gif.name = new_file_name
                    variacao.save(update_fields=["gif"])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"     [OK] V#{variacao.id} | {action} | {new_file_name}"
                        )
                    )
                    if verbose or variacao_id:
                        self.stdout.write(f"          URL: {secure_url}")
                        
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(
                            f"     [ERRO] V#{variacao.id} falhou: {exc}"
                        )
                    )

        # ------------------------------------------------------------
        # Encerramento
        # ------------------------------------------------------------

        self.stdout.write("")
        self.stdout.write("=" * 70)
        if execute:
            self.stdout.write("  MIGRAÇÃO concluída.")
        else:
            self.stdout.write(
                "  DRY-RUN concluído — nenhum arquivo ou registro foi alterado."
            )
        self.stdout.write("=" * 70)
