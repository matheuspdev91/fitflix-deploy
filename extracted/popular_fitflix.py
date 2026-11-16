import os
import zipfile
import tempfile
import shutil
import unicodedata
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from django.core.files import File

from core.models import (
    GrupoMuscular,
    VideoExercicio,
    VariacaoExercicio,
)

# ==========================================
# CONFIG
# ==========================================

ZIPS_DIR = "zip"


# ==========================================
# NORMALIZAÇÃO
# ==========================================

def normalizar(texto):
    texto = texto.lower()

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")

    return texto.strip()


# ==========================================
# EXERCÍCIO BASE
# ==========================================

PALAVRAS_BASE = {
    "supino": "Supino",
    "rosca": "Rosca",
    "agachamento": "Agachamento",
    "remada": "Remada",
    "puxada": "Puxada",
    "triceps": "Tríceps",
    "tricep": "Tríceps",
    "crucifixo": "Crucifixo",
    "desenvolvimento": "Desenvolvimento",
    "elevacao lateral": "Elevação Lateral",
    "panturrilha": "Panturrilha",
    "stiff": "Stiff",
    "leg press": "Leg Press",
    "cadeira extensora": "Cadeira Extensora",
    "cadeira flexora": "Cadeira Flexora",
    "mesa flexora": "Mesa Flexora",
    "pulley": "Pulley",
    "barra fixa": "Barra Fixa",
}


def detectar_exercicio_base(nome):
    nome_norm = normalizar(nome)

    for chave, valor in PALAVRAS_BASE.items():
        if chave in nome_norm:
            return valor

    return nome.split()[0].title()


# ==========================================
# PROCESSAR ZIPS
# ==========================================

zips = Path(ZIPS_DIR).glob("*.zip")

for zip_path in zips:

    grupo_nome = (
        zip_path.stem
        .replace("(", "")
        .replace(")", "")
        .strip()
        .title()
    )

    print(f"\n📁 Grupo: {grupo_nome}")

    grupo, _ = GrupoMuscular.objects.get_or_create(
        nome=grupo_nome
    )

    temp_dir = tempfile.mkdtemp()

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_dir)

    arquivos = []

    for root, dirs, files in os.walk(temp_dir):
        for file in files:

            if file.lower().endswith((".gif", ".mp4", ".webp")):

                arquivos.append(
                    os.path.join(root, file)
                )

    for caminho_arquivo in arquivos:

        nome_arquivo = Path(caminho_arquivo).stem

        exercicio_base = detectar_exercicio_base(
            nome_arquivo
        )

        video, criado_video = VideoExercicio.objects.get_or_create(
            nome=exercicio_base,
            grupo_muscular=grupo,
        )

        if criado_video:

            with open(caminho_arquivo, "rb") as f:
                video.gif.save(
                    os.path.basename(caminho_arquivo),
                    File(f),
                    save=True
                )

            print(f"✅ Exercício criado: {video.nome}")

        variacao, criada_variacao = (
            VariacaoExercicio.objects.get_or_create(
                exercicio=video,
                nome=nome_arquivo,
                defaults={
                    "grupo_muscular": grupo
                }
            )
        )

        if criada_variacao:

            with open(caminho_arquivo, "rb") as f:
                variacao.gif.save(
                    os.path.basename(caminho_arquivo),
                    File(f),
                    save=True
                )

            print(f"   ↳ Variação criada: {nome_arquivo}")

    shutil.rmtree(temp_dir)

print("\n🔥 FINALIZADO")