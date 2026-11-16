import csv

from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio


class Command(BaseCommand):
    help = "Exporta variações sem GIF"

    def handle(self, *args, **kwargs):

        with open("variacoes_sem_gif.csv", "w", newline="", encoding="utf-8") as f:

            writer = csv.writer(f)

            writer.writerow(["id", "exercicio", "variacao"])

            for v in VariacaoExercicio.objects.filter(gif=""):

                writer.writerow([v.id, v.exercicio.nome, v.nome])

        self.stdout.write(
            self.style.SUCCESS(
                f"{VariacaoExercicio.objects.filter(gif='').count()} exportados."
            )
        )
