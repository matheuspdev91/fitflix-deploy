import json
from pathlib import Path


class Catalog:

    def __init__(self):
        
        self.base_path = (
            Path(__file__).resolve().parent.parent.parent / "catalog"
        )

        self.grupos = self._load("grupos.json")
        self.exercicios = self._load("exercicios.json")
        self.variacoes = self._load("variacoes.json")

        # Índices para busca rápida
        self.grupos_index = {
            grupo["pk"]: grupo
            for grupo in self.grupos
        }

        self.exercicios_index = {
            exercicio["pk"]: exercicio
            for exercicio in self.exercicios
        }

    def _load(self, arquivo):

        caminho = self.base_path / arquivo

        with caminho.open(
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def grupo_por_pk(self, pk):
        return self.grupos_index.get(pk)

    def exercicio_por_pk(self, pk):
        return self.exercicios_index.get(pk)

    def gerar_catalogo(self):

        catalogo = []

        for variacao in self.variacoes:

            exercicio = self.exercicio_por_pk(
                variacao["fields"]["exercicio"]
            )

            grupo = self.grupo_por_pk(
                exercicio["fields"]["grupo_muscular"]
            )

            catalogo.append(
                {
                    "grupo": grupo["fields"]["nome"],
                    "exercicio": exercicio["fields"]["nome"],
                    "variacao": variacao["fields"]["nome"],
                    "nome_completo": (
                        f'{exercicio["fields"]["nome"]} '
                        f'{variacao["fields"]["nome"]}'
                    ),
                }
            )

        return catalogo