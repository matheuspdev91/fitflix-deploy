from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio
import csv


class Command(BaseCommand):
    help = "Audita GIFs locais"

    def handle(self, *args, **kwargs):

        raiz = Path("media/exercicios")

        gifs = []

        for arquivo in raiz.rglob("*.gif"):
            gifs.append({"nome": arquivo.stem.lower(), "caminho": str(arquivo)})

        self.stdout.write(f"{len(gifs)} gifs encontrados")

        with open("auditoria_gifs_locais.csv", "w", newline="", encoding="utf8") as f:

            writer = csv.writer(f)

            writer.writerow(["id", "exercicio", "variacao", "match"])

            for v in VariacaoExercicio.objects.filter(gif=""):

                nome = f"{v.exercicio.nome} {v.nome}".lower()

                encontrados = []

                for gif in gifs:

                    if (
                        v.exercicio.nome.lower() in gif["nome"]
                        or v.nome.lower() in gif["nome"]
                    ):
                        encontrados.append(gif["caminho"])

                writer.writerow(
                    [v.id, v.exercicio.nome, v.nome, ";".join(encontrados[:5])]
                )
