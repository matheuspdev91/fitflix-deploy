from django.core.management.base import BaseCommand
from core.models import VariacaoExercicio
import requests


class Command(BaseCommand):
    help = "Audita GIFs"

    def handle(self, *args, **kwargs):

        suspeitos = []

        for v in VariacaoExercicio.objects.exclude(gif=""):

            try:
                r = requests.get(v.gif.url, timeout=10)

                if r.status_code != 200:
                    print(
                        f"{v.id} | "
                        f"{v.exercicio.nome} | "
                        f"{v.nome} | "
                        f"STATUS={r.status_code}"
                    )
                    print(v.gif.url)
                    print("-" * 80)

            except Exception as e:
                print(f"{v.id} | " f"{v.exercicio.nome} | " f"{v.nome} | " f"ERRO={e}")

        for v in VariacaoExercicio.objects.filter(id__in=suspeitos):

            print()
            print("=" * 80)

            print(f"ID: {v.id}")
            print(f"EXERCÍCIO: {v.exercicio.nome}")
            print(f"VARIAÇÃO: {v.nome}")
            print(f"GIF: {v.gif.url}")
