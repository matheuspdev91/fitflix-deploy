from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio
import csv


class Command(BaseCommand):
    help = "Aplica sugestões de GIFs existentes"

    def handle(self, *args, **kwargs):

        with open("sugestoes_existentes.csv", newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            total = 0

            for row in reader:

                alvo = VariacaoExercicio.objects.get(id=row["id"])

                origem = VariacaoExercicio.objects.get(id=row["gif_origem"])

                self.stdout.write(f"{alvo.id} receberia {origem.gif.name}")

                total += 1

                self.stdout.write(f"{alvo.id} <- {origem.id}")

        self.stdout.write(self.style.SUCCESS(f"{total} registros atualizados."))
