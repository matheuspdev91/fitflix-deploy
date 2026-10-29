"""Normalização determinística de nomes de arquivos e diretórios."""

from __future__ import annotations

import re
import unicodedata

_COPY_MARKER = re.compile(r"\s*\(\s*\d+\s*\)")
_IGNORABLE_SUFFIXES = frozenset({"novo", "final", "copy", "copia"})
_SEPARATORS = re.compile(r"[_\-]+")
_WHITESPACE = re.compile(r"\s+")


def remove_accents(value: str) -> str:
    """Remove diacríticos sem alterar os demais caracteres."""
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def normalize_name(value: str) -> str:
    """Gera uma chave comparável para um nome humano ou nome de arquivo.

    Sufixos de trabalho (``_novo``, ``_final``), numeração de cópias e a
    extensão devem ser removidos antes de persistir uma chave de catálogo.
    """
    stem = value.rsplit(".", 1)[0] if "." in value else value
    normalized = remove_accents(stem).casefold()
    normalized = _COPY_MARKER.sub(" ", normalized)
    normalized = _SEPARATORS.sub(" ", normalized)
    words = normalized.split()
    while words and words[-1] in _IGNORABLE_SUFFIXES:
        words.pop()
    return " ".join(words)


def display_name(value: str) -> str:
    """Limpa separadores mantendo capitalização e acentos para exibição."""
    stem = value.rsplit(".", 1)[0] if "." in value else value
    cleaned = _COPY_MARKER.sub(" ", stem)
    cleaned = _SEPARATORS.sub(" ", cleaned)
    words = cleaned.split()
    while words and remove_accents(words[-1]).casefold() in _IGNORABLE_SUFFIXES:
        words.pop()
    return _WHITESPACE.sub(" ", " ".join(words)).strip()


# Compatibilidade com os scripts antigos em português.
normalizar_nome = normalize_name
remover_acentos = remove_accents
