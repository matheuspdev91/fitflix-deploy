from pathlib import Path
from rapidfuzz import fuzz
from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio
import csv


class Command(BaseCommand):

    help = "Sugere GIFs para exercícios sem GIF"

    def handle(self, *args, **kwargs):

        gifs = []

        for arquivo in Path("media/exercicios").rglob("*.gif"):
            gifs.append({"nome": arquivo.stem.lower(), "caminho": str(arquivo)})

        with open("sugestoes_gifs.csv", "w", newline="", encoding="utf-8") as f:

            writer = csv.writer(f)

            writer.writerow(["id", "exercicio", "variacao", "score", "gif_sugerido"])

            for v in VariacaoExercicio.objects.filter(gif=""):

                busca = (f"{v.exercicio.nome} {v.nome}").lower()

                melhor_score = 0
                melhor_gif = ""

                for gif in gifs:

                    score = fuzz.token_sort_ratio(busca, gif["nome"])

                    if score > melhor_score:
                        melhor_score = score
                        melhor_gif = gif["caminho"]

                writer.writerow(
                    [v.id, v.exercicio.nome, v.nome, melhor_score, melhor_gif]
                )

        self.stdout.write(self.style.SUCCESS("Sugestões geradas."))
