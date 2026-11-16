from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio
from rapidfuzz import fuzz
import csv


class Command(BaseCommand):
    help = "Sugere GIFs utilizando registros que já possuem GIF"

    def handle(self, *args, **kwargs):

        com_gif = list(
            VariacaoExercicio.objects.exclude(gif="").exclude(gif__isnull=True)
        )

        sem_gif = VariacaoExercicio.objects.filter(gif="").select_related("exercicio")

        with open("sugestoes_existentes.csv", "w", newline="", encoding="utf-8") as f:

            writer = csv.writer(f)

            writer.writerow(
                ["id", "exercicio", "variacao", "score", "gif_origem", "gif_name"]
            )

            for alvo in sem_gif:

                nome_alvo = (f"{alvo.exercicio.nome} {alvo.nome}").lower()

                melhor_score = 0
                melhor_gif = None

                for origem in com_gif:

                    nome_origem = (f"{origem.exercicio.nome} {origem.nome}").lower()

                    score = fuzz.token_sort_ratio(nome_alvo, nome_origem)

                    if score > melhor_score:
                        melhor_score = score
                        melhor_gif = origem

                if melhor_score >= 85 and melhor_gif:

                    writer.writerow(
                        [
                            alvo.id,
                            alvo.exercicio.nome,
                            alvo.nome,
                            round(melhor_score, 2),
                            melhor_gif.id,
                            melhor_gif.gif.name,
                        ]
                    )

        self.stdout.write(
            self.style.SUCCESS("Sugestões geradas em sugestoes_existentes.csv")
        )
