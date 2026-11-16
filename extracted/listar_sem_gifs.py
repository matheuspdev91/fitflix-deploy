import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "projeto.settings")

import django

django.setup()

import csv
from core.models import VariacaoExercicio

with open("sem_gifs.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow(["id", "exercicio", "variacao"])

    for v in VariacaoExercicio.objects.filter(gif=""):
        writer.writerow([v.id, v.exercicio.nome, v.nome])

print("Arquivo gerado.")
