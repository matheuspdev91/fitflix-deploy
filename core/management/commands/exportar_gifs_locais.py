from pathlib import Path
from django.core.management.base import BaseCommand
import csv


class Command(BaseCommand):
    help = "Exporta todos os GIFs locais"

    def handle(self, *args, **kwargs):

        raiz = Path("media/exercicios")

        gifs = []

        for arquivo in raiz.rglob("*.gif"):
            gifs.append(
                {"nome": arquivo.stem, "arquivo": arquivo.name, "caminho": str(arquivo)}
            )

        gifs.sort(key=lambda x: x["nome"])

        with open("gifs_locais.csv", "w", newline="", encoding="utf-8") as f:

            writer = csv.writer(f)

            writer.writerow(["nome", "arquivo", "caminho"])

            for gif in gifs:
                writer.writerow([gif["nome"], gif["arquivo"], gif["caminho"]])

        self.stdout.write(self.style.SUCCESS(f"{len(gifs)} GIFs exportados."))
