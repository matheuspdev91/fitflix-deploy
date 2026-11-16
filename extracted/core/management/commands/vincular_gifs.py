from django.core.management.base import BaseCommand
from django.conf import settings
import os
import unicodedata
from core.models import VariacaoExercicio


class Command(BaseCommand):
    help = "Vincular gif automaticamente"

    def normalizar(self, texto):
        texto = texto.lower()
        texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode()
        return texto

    def simplificar(self, texto):
        stopwords = ["com", "de", "para", "no", "na"]
        palavras = texto.split()
        return " ".join([p for p in palavras if p not in stopwords])

    def handle(self, *args, **kwargs):

        CAMINHO_GIF = os.path.join(settings.BASE_DIR, "media", "exercicios", "gif")

        print(f"📂 Caminho: {CAMINHO_GIF}")

        if not os.path.exists(CAMINHO_GIF):
            self.stdout.write(self.style.ERROR("❌ Pasta não encontrada"))
            return

        for arquivo in os.listdir(CAMINHO_GIF):
            nome_base = arquivo.replace(".gif", "")
            nome_limpo = self.simplificar(self.normalizar(nome_base))

            for variacao in VariacaoExercicio.objects.select_related("exercicio"):
                nome_var = self.simplificar(self.normalizar(variacao.nome))
                nome_ex = self.simplificar(self.normalizar(variacao.exercicio.nome))

                if nome_ex in nome_limpo and any(
                    p in nome_limpo for p in nome_var.split()
                ):
                    variacao.gif = f"exercicios/gif/{arquivo}"
                    variacao.save()

                    print(f"✔ {arquivo} → {variacao.exercicio.nome} / {variacao.nome}")
                    break
