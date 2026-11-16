"""Match de mídias contra variações existentes no banco de dados.

Este módulo depende de Django (importa modelos do core).  Ele recebe um
queryset pré-carregado de ``VariacaoExercicio`` e constrói um índice
normalizado para lookup O(1) em três estratégias de match.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .normalizer import normalize_name

logger = logging.getLogger(__name__)


class MatchStrategy(Enum):
    """Como a correspondência foi encontrada."""

    BY_GIF_PATH = "gif_path"
    BY_FULL_NAME = "full_name"
    BY_TOKENS = "tokens"


@dataclass(frozen=True, slots=True)
class DbMatchResult:
    """Resultado do match de uma mídia com uma variação do BD."""

    variacao_id: int
    strategy: MatchStrategy
    confidence: float


# ---------------------------------------------------------------------------
# Stopwords para token match (preposições comuns em PT-BR)
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "com", "de", "do", "da", "dos", "das", "no", "na", "nos", "nas",
    "em", "e", "o", "a", "os", "as", "um", "uma", "por", "para",
    "ao", "aos", "tipo",
})


def _significant_tokens(text: str) -> frozenset[str]:
    """Extrai tokens significativos (sem stopwords) de um nome normalizado."""
    normalized = normalize_name(text)
    return frozenset(t for t in normalized.split() if t not in _STOPWORDS)


class DatabaseMatcher:
    """Resolve correspondências entre mídias do inventário e variações do BD.

    Constrói três índices a partir das variações existentes:

    1. **gif_path_index** — normaliza o campo ``gif`` da variação para comparar
       com o nome do arquivo da mídia.
    2. **full_name_index** — concatena ``exercicio.nome + variacao.nome`` e
       normaliza para comparar com o nome normalizado da mídia.
    3. **tokens** — fallback por interseção de tokens significativos.
    """

    def __init__(self, variacoes: list) -> None:
        """Recebe uma lista de dicts com chaves:
        ``id``, ``nome``, ``exercicio_nome``, ``gif_name``.
        """
        self._variacoes = variacoes

        # Índice 1: normalized(basename do gif) → variacao_id
        self._gif_path_index: dict[str, int] = {}

        # Índice 2: normalized(exercicio + variacao) → variacao_id
        self._full_name_index: dict[str, int] = {}

        # Índice 3: tokens → (variacao_id, tokens)
        self._token_entries: list[tuple[int, frozenset[str]]] = []

        for v in variacoes:
            vid = v["id"]
            gif_name = v["gif_name"] or ""
            ex_nome = v["exercicio_nome"]
            var_nome = v["nome"]

            # Índice 1: normalizar o basename do campo gif
            if gif_name:
                gif_basename = Path(gif_name).stem
                key = normalize_name(gif_basename)
                if key and key not in self._gif_path_index:
                    self._gif_path_index[key] = vid

            # Índice 2: nome completo
            full = f"{ex_nome} {var_nome}" if var_nome and var_nome != "Padrão" else ex_nome
            key = normalize_name(full)
            if key and key not in self._full_name_index:
                self._full_name_index[key] = vid

            # Índice 3: tokens
            tokens = _significant_tokens(full)
            if len(tokens) >= 2:
                self._token_entries.append((vid, tokens))

    def match(self, media_stem: str) -> DbMatchResult | None:
        """Tenta encontrar a variação existente para um nome de mídia.

        Retorna ``None`` se nenhuma correspondência for encontrada.
        """
        normalized = normalize_name(media_stem)

        # Estratégia 1: pelo campo gif existente
        vid = self._gif_path_index.get(normalized)
        if vid is not None:
            return DbMatchResult(
                variacao_id=vid,
                strategy=MatchStrategy.BY_GIF_PATH,
                confidence=1.0,
            )

        # Estratégia 2: pelo nome completo (exercicio + variacao)
        vid = self._full_name_index.get(normalized)
        if vid is not None:
            return DbMatchResult(
                variacao_id=vid,
                strategy=MatchStrategy.BY_FULL_NAME,
                confidence=0.95,
            )

        # Estratégia 3: por tokens (threshold >= 80%)
        media_tokens = _significant_tokens(media_stem)
        if len(media_tokens) < 2:
            return None

        best_score = 0.0
        best_vid = None
        second_score = 0.0

        for vid, db_tokens in self._token_entries:
            common = media_tokens & db_tokens
            if not common:
                continue
            score = len(common) / max(len(media_tokens), len(db_tokens))
            if score > best_score:
                second_score = best_score
                best_score = score
                best_vid = vid
            elif score > second_score:
                second_score = score

        # Exigir >= 80% e que o melhor se destaque do segundo
        if best_vid is not None and best_score >= 0.8:
            if best_score > second_score:
                return DbMatchResult(
                    variacao_id=best_vid,
                    strategy=MatchStrategy.BY_TOKENS,
                    confidence=round(best_score, 3),
                )

        return None

    @property
    def index_sizes(self) -> dict[str, int]:
        """Tamanho dos índices (para logging/debug)."""
        return {
            "gif_path": len(self._gif_path_index),
            "full_name": len(self._full_name_index),
            "tokens": len(self._token_entries),
        }
