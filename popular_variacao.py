import os
import re
import unicodedata

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "projeto.settings")

import django

django.setup()

import cloudinary
import cloudinary.api

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

from core.models import VariacaoExercicio


STOPWORDS = {
    "a",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "no",
    "para",
}


def limpar(txt):
    txt = os.path.splitext(str(txt))[0]
    txt = re.sub(r"_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,}$", "", txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = txt.encode("ASCII", "ignore").decode("ASCII")
    txt = txt.lower()
    txt = re.sub(r"[_\-/()]+", " ", txt)
    txt = re.sub(r"[^a-z0-9 ]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def normalizar_token(token):
    equivalencias = {
        "halteres": "halter",
        "bracos": "braco",
        "cabos": "cabo",
        "ombros": "ombro",
        "gluteos": "gluteo",
        "biceps": "biceps",
        "triceps": "triceps",
    }
    if token in equivalencias:
        return equivalencias[token]
    if len(token) > 4 and token.endswith("oes"):
        return token[:-3] + "ao"
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def tokens(txt):
    return [
        normalizar_token(token)
        for token in limpar(txt).split()
        if token not in STOPWORDS
    ]


def chave_tokens(txt):
    return " ".join(tokens(txt))


def montar_nome_completo(variacao):

    nome_variacao = variacao.nome.strip()
    nome_exercicio = variacao.exercicio.nome.strip()

    # evita:
    # Rosca Rosca no Cabo
    if nome_variacao.lower().startswith(
        nome_exercicio.lower()
    ):
        return nome_variacao

    return f"{nome_exercicio} {nome_variacao}".strip()


def pontuar_match(nome_variacao, nome_gif):
    alvo = chave_tokens(nome_variacao)
    gif = chave_tokens(nome_gif)

    if not alvo or not gif:
        return 0

    if alvo == gif:
        return 100

    alvo_compacto = alvo.replace(" ", "")
    gif_compacto = gif.replace(" ", "")
    if alvo_compacto and alvo_compacto in gif_compacto:
        return 95

    alvo_tokens = set(alvo.split())
    gif_tokens = set(gif.split())

    if not alvo_tokens:
        return 0

    acertos = alvo_tokens & gif_tokens
    cobertura = len(acertos) / len(alvo_tokens)

    # Evita associar nomes genericos como "Maquina", "Barra" ou matches
    # fracos quando o exercicio pai nao aparece no nome do arquivo.
    if len(alvo_tokens) >= 3 and cobertura >= 0.8:
        return int(cobertura * 90)
    if len(alvo_tokens) == 2 and cobertura == 1:
        return 85

    return 0


def listar_gifs_cloudinary():
    recursos = []
    next_cursor = None

    while True:
        params = {
            "type": "upload",
            "prefix": "media/gifs/",
            "resource_type": "image",
            "max_results": 500,
        }
        if next_cursor:
            params["next_cursor"] = next_cursor

        resultado = cloudinary.api.resources(**params)
        recursos.extend(resultado.get("resources", []))

        next_cursor = resultado.get("next_cursor")
        if not next_cursor:
            break

    return recursos


def escolher_melhor_gif(variacao, gifs, public_ids_usados):
    nome_completo = montar_nome_completo(variacao)
    candidatos = []

    for item in gifs:
        public_id = item["public_id"]
        if public_id in public_ids_usados:
            continue

        nome_gif = public_id.split("/")[-1]
        score = pontuar_match(nome_completo, nome_gif)
        if score:
            candidatos.append((score, nome_gif, item))

    candidatos.sort(key=lambda candidato: candidato[0], reverse=True)

    if not candidatos:
        return None, 0

    melhor_score, _, melhor_item = candidatos[0]
    segundo_score = candidatos[1][0] if len(candidatos) > 1 else 0

    if segundo_score and melhor_score == segundo_score:
        return None, melhor_score

    return melhor_item, melhor_score


def main():
    gifs = listar_gifs_cloudinary()
    variacoes = VariacaoExercicio.objects.select_related("exercicio").order_by("id")

    total = 0
    public_ids_usados = set()

    for variacao in variacoes:
        nome_completo = montar_nome_completo(variacao)
        item, score = escolher_melhor_gif(variacao, gifs, public_ids_usados)

        if not item:
            print(f"NÃO ASSOCIADO -> {nome_completo}")
            continue

        public_id = item["public_id"]
        variacao.gif.name = public_id
        variacao.save(update_fields=["gif"])

        public_ids_usados.add(public_id)
        total += 1

        print(f"OK -> {nome_completo}")
        print(f"     GIF: {public_id} (score {score})")

    print(f"\nTOTAL ASSOCIADO: {total}")


if __name__ == "__main__":
    main()
