from core.media_pipeline.catalog import Catalog


def main():
    catalog = Catalog()

    print("Grupos:", len(catalog.grupos))
    print("Exercícios:", len(catalog.exercicios))
    print("Variações:", len(catalog.variacoes))

    print()

    print("Primeiro exercício:")
    print(catalog.exercicios[0])

    print()

    print("Primeira variação:")
    print(catalog.variacoes[0])

    print()

    dados = catalog.gerar_catalogo()

    print("Primeiro item do catálogo:")
    print(dados[0])


if __name__ == "__main__":
    main()