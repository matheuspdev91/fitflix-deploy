import os
import re
import unicodedata
from pathlib import Path

import cloudinary.api
import cloudinary.uploader
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import VariacaoExercicio


class Command(BaseCommand):
    help = "Envia GIFs locais de media/exercicios/gif para o Cloudinary e atualiza VariacaoExercicio.gif."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria enviado sem fazer upload nem salvar no banco.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Reenvia o arquivo mesmo quando o public_id ja existe no Cloudinary.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        gif_dir = Path(settings.MEDIA_ROOT) / "exercicios" / "gif"

        self.stdout.write(f"Pasta local: {gif_dir}")

        if not gif_dir.exists():
            self.stdout.write(self.style.ERROR("Pasta media/exercicios/gif nao encontrada."))
            return

        gif_files = sorted(path for path in gif_dir.iterdir() if path.suffix.lower() == ".gif")
        gif_index = {self._key(path.stem): path for path in gif_files}

        self.stdout.write(f"GIFs encontrados: {len(gif_files)}")

        total = uploaded = reused = updated = skipped = failed = 0
        used_files = set()

        variacoes = VariacaoExercicio.objects.select_related("exercicio").order_by("id")
        for variacao in variacoes:
            total += 1
            local_file = self._find_local_file(variacao, gif_dir, gif_index)

            label = f"#{variacao.pk} {variacao.exercicio.nome} / {variacao.nome}"
            if not local_file:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"IGNORADO {label}: arquivo local nao encontrado."))
                continue

            used_files.add(local_file)
            public_id = self._public_id(variacao)

            try:
                cloudinary_url = None

                if dry_run:
                    self.stdout.write(f"DRY-RUN {label}: upload/reuso {local_file.name} -> {public_id}")
                    continue

                exists = self._cloudinary_exists(public_id)

                if exists and not overwrite:
                    reused += 1
                    cloudinary_url = self._cloudinary_url(public_id)
                    self.stdout.write(f"OK {label}: ja existe no Cloudinary, sem duplicar.")
                else:
                    result = cloudinary.uploader.upload(
                        str(local_file),
                        public_id=public_id,
                        resource_type="image",
                        overwrite=overwrite,
                        unique_filename=False,
                    )
                    uploaded += 1
                    cloudinary_url = result.get("secure_url") or result.get("url")
                    self.stdout.write(f"UPLOAD {label}: {local_file.name} -> {cloudinary_url}")

                if variacao.gif.name != public_id:
                    variacao.gif.name = public_id
                    variacao.save(update_fields=["gif"])
                    updated += 1
                    self.stdout.write(f"SALVO {label}: gif={public_id}")
                else:
                    self.stdout.write(f"SEM MUDANCA {label}: campo gif ja esta atualizado.")

            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(f"ERRO {label}: {exc}"))
                continue

        unused_files = [path.name for path in gif_files if path not in used_files]
        if unused_files:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("GIFs locais sem VariacaoExercicio identificado:"))
            for file_name in unused_files:
                self.stdout.write(f"- {file_name}")

        self.stdout.write("")
        self.stdout.write("Resumo:")
        self.stdout.write(f"- Variacoes processadas: {total}")
        self.stdout.write(f"- Uploads feitos: {uploaded}")
        self.stdout.write(f"- Ja existentes reutilizados: {reused}")
        self.stdout.write(f"- Campos atualizados: {updated}")
        self.stdout.write(f"- Ignorados: {skipped}")
        self.stdout.write(f"- Falhas: {failed}")

    def _find_local_file(self, variacao, gif_dir, gif_index):
        current_name = (variacao.gif.name or "").strip()

        for path in self._candidate_paths(current_name, gif_dir):
            if path.exists() and path.suffix.lower() == ".gif":
                return path

        names = [
            variacao.nome,
            f"{variacao.exercicio.nome} {variacao.nome}",
        ]
        for name in names:
            match = gif_index.get(self._key(name))
            if match:
                return match

        return self._best_token_match(variacao, gif_index)

    def _candidate_paths(self, current_name, gif_dir):
        if not current_name or current_name.startswith(("http://", "https://")):
            return []

        media_root = Path(settings.MEDIA_ROOT)
        base_dir = Path(settings.BASE_DIR)
        current_path = Path(current_name)
        candidates = []

        if current_path.is_absolute():
            candidates.append(current_path)
        else:
            candidates.extend(
                [
                    media_root / current_name,
                    base_dir / current_name,
                    gif_dir / current_path.name,
                ]
            )

        return candidates

    def _cloudinary_exists(self, public_id):
        try:
            cloudinary.api.resource(public_id, resource_type="image")
            return True
        except Exception as exc:
            if exc.__class__.__name__ == "NotFound":
                return False
            message = str(exc).lower()
            if "not found" in message or "404" in message:
                return False
            raise

    def _cloudinary_url(self, public_id):
        return cloudinary.CloudinaryImage(public_id).build_url(secure=True)

    def _public_id(self, variacao):
        slug = slugify(variacao.nome) or f"variacao-{variacao.pk}"
        return f"exercicios/gif/variacao-{variacao.pk}-{slug}"

    def _key(self, value):
        value = os.path.splitext(str(value))[0]
        value = re.sub(r"_[A-Za-z0-9]{6,}$", "", value)
        value = value.replace("_", " ")
        value = unicodedata.normalize("NFKD", value).encode("ASCII", "ignore").decode("ASCII")
        value = re.sub(r"[^a-zA-Z0-9\s]", " ", value).lower()
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _tokens(self, value):
        stopwords = {"com", "de", "do", "da", "dos", "das", "no", "na", "em", "e"}
        return {token for token in self._key(value).split() if token not in stopwords}

    def _best_token_match(self, variacao, gif_index):
        wanted_tokens = self._tokens(f"{variacao.exercicio.nome} {variacao.nome}")
        if len(wanted_tokens) < 3:
            return None

        matches = []
        for key, path in gif_index.items():
            file_tokens = set(key.split())
            common_tokens = wanted_tokens & file_tokens
            score = len(common_tokens) / len(wanted_tokens)
            if score >= 0.8:
                matches.append((score, path))

        matches.sort(key=lambda item: item[0], reverse=True)
        if len(matches) == 1 or (len(matches) > 1 and matches[0][0] > matches[1][0]):
            return matches[0][1]

        return None
