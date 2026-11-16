import re

def nome_bonito(nome):
    nome = nome.lower()
    nome = re.sub(r"\s+", " ", nome)
    nome = re.sub(r"\b(com|na|no|de|do|da)$", "", nome)

    nome = nome.strip().title()

    # correções de acento
    nome = nome.replace("Triceps", "Tríceps")
    nome = nome.replace("Biceps", "Bíceps")
    nome = nome.replace("Gluteo", "Glúteo")

    return nome