import os
import unicodedata

from core.models import VideoExercicio


BASE_DIR = "media/exercicios/gif"

arquivos = os.listdir(BASE_DIR)


def normalizar(texto):
    texto = texto.lower()

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")

    return texto


corrigidos = 0

for video in VideoExercicio.objects.all():

    nome_video = normalizar(video.nome)

    for arquivo in arquivos:

        nome_arquivo = normalizar(arquivo)

        palavras_video = nome_video.split()

        acertos = sum(
            1 for palavra in palavras_video
            if palavra in nome_arquivo
        )

        if acertos >= max(1, len(palavras_video) // 2):

            caminho = f"exercicios/gif/{arquivo}"

            video.gif = caminho
            video.save()

            print(f"{video.nome} -> {arquivo}")

            corrigidos += 1
            break


print(f"\nTOTAL CORRIGIDOS: {corrigidos}")