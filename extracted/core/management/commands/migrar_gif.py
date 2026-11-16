from django.core.management.base import BaseCommand
from core.models import VideoExercicio, VariacaoExercicio
from core.models import GrupoMuscular
from core.util.texto import nome_bonito
from django.conf import settings

import os
import re
import unicodedata

BASE_PATH = os.path.join(
    settings.MEDIA_ROOT,
    "exercicios",
    "gif"
)

print("Pasta:", BASE_PATH)
print("Existe?", os.path.exists(BASE_PATH))
# =========================
# NORMALIZAÇÃO
# =========================

def normalizar(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()

# =========================
# EXERCÍCIOS BASE
# =========================

BASE_MAP = {
    "rosca": "Bíceps",
    "triceps": "Tríceps",
    "supino": "Peito",
    "crucifixo": "Peito",
    "remada": "Costas",
    "puxada": "Costas",
    "agachamento": "Pernas",
    "leg": "Pernas",
    "flexora": "Pernas",
    "extensora": "Pernas",
    "panturrilha": "Panturrilha",
    "gluteo": "Glúteo",
    "desenvolvimento": "Ombro",
    "elevacao lateral": "Ombro",
}

def detectar_base(nome):
    nome = normalizar(nome)

    for chave in BASE_MAP:
        if chave in nome:
            return chave

    return "outro"

def limpar_nome(nome):
    nome = os.path.splitext(nome)[0]
    nome = nome.replace("_", " ")
    nome = re.sub(r"[A-Za-z0-9]{6,}$", "", nome)  # remove hash tipo jUlexBk
    return nome.strip()


 #DETECTAR GRUPO

def detectar_grupo(caminho):
    pasta =  os.path.basename(os.path.dirname(caminho))
    return normalizar(pasta)





# ========================
# MAPA DOS GRUPOS
# ========================

GRUPO_MAP = {
    "biceps": "Bíceps",
    "triceps": "Tríceps",
    "costas": "Costas",
    "peitoral": "Peitoral",
    "pernas": "Pernas",
    "gluteos": "Glúteos",
    "panturrilhas": "Panturrilhas",
    "antebraco": "Antebraço",
    "cardio academia": "Cardio",
    "cadeira extensora": "Extensora",
    "cadeira flexora": "Flexora",
    "mesa flexora": "Flexora",
    "stiff": "Pernas",
    "barra fixa": "Costas",
    "levantamento frontal": "Ombro",
    "voador": "Peito",
    "flexao": "Peito",
    "elevacao pelvica": "Glúteo",
}




# =========================
# COMMAND
# =========================

class Command(BaseCommand):
    help = "Criar exercícios e variações automaticamente a partir dos GIFs"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        arquivos = []
        for root, dirs, files in os.walk(BASE_PATH):
            for f in files:
                if f.lower().endswith(".gif"):
                    arquivos.append(os.path.join(root, f))

        self.stdout.write(f"📦 TOTAL DE GIFs: {len(arquivos)}\n")

        criados = 0

        for caminho in arquivos:
            nome_arquivo = os.path.basename(caminho)
            nome_limpo = limpar_nome(nome_arquivo)
            variacao_nome = nome_bonito(nome_limpo)

            if not variacao_nome.strip():
                variacao_nome = "Exercicio"

            grupo_nome_raw = detectar_grupo(caminho)
            grupo_nome = GRUPO_MAP.get(grupo_nome_raw, "Outros")

            grupo, _= GrupoMuscular.objects.get_or_create(
                nome=grupo_nome.strip()
            )

            base = detectar_base(nome_limpo)


            if base == "outro":
                exercicio_nome = "Outros"
           
            else:
                exercicio_nome = nome_bonito(base)


            exercicio, _ = VideoExercicio.objects.get_or_create(
                nome=exercicio_nome,
                defaults={'grupo_muscular': grupo}
            )

            #Caso exista sem grupo

            if not exercicio.grupo_muscular:
                exercicio.grupo_muscular = grupo
                exercicio.save()


            variacao_nome = nome_bonito(nome_limpo)

            variacao, created = VariacaoExercicio.objects.get_or_create(
                exercicio=exercicio,
                nome=variacao_nome
            )

            if created:
                criados += 1

            if not dry_run:
                variacao.gif = caminho
                variacao.save()

            self.stdout.write(
                f"✅ {nome_arquivo} -> {exercicio.nome} / {variacao.nome}"
            )

        self.stdout.write("\n=========================")
        self.stdout.write(f"🔥 VARIAÇÕES CRIADAS: {criados}")
        self.stdout.write("=========================")