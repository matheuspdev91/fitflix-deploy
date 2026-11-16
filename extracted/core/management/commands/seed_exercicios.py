from django.core.management.base import BaseCommand
from core.models import GrupoMuscular, VariacaoExercicio, VideoExercicio



EXERCICIOS_POR_GRUPO = {

    "Peito": [
        {
            "nome": "Supino",
            "descricao": "Exercicio base para peitoral.",
            "variacoes": [
                "Reto barra",
                "Reto halter",
                "Inclinado barra",
                "Inclinado halter",
                "Máquina",
            ],
        },

        {
            "nome": "Crucifixo",
            "variacoes": [
                "Reto halter",
                "Inclinado halter",
                "Máquina",
                "Cross (cabo)",
            ],
        },
    ],


    "Costas": [
        {
            "nome": "Remada",
            "variacoes": [
                "Curvada barra",
                "Unilateral halter",
                "Máquina",
                "Cavalinho",
            ],
        },

        {
            "nome": "Puxada",
            "variacoes": [
                "Frontal aberta",
                "Frontal fechada",
                "Neutra",
                "Supinada",
            ],
        },
    ],


    "Ombros": [
        {
            "nome": "Desenvolvimento",
            "variacoes": [
                "Barra",
                "Halteres",
                "Máquina",
                "Arnold",
            ],
        },

        {
            "nome": "Elevação lateral",
            "variacoes": [
                "Halteres",
                "Polia",
                "Máquina",
            ],
        },

        {
            "nome": "Elevação frontal",
            "variacoes": [
                "Barra",
                "Halteres",
                "Polia",
            ],
        },
    ],


    "Bíceps": [
        {
            "nome": "Rosca",
            "variacoes": [
                "Direta com barra",
                "Direta com halteres",
                "Martelo",
                "Scott",
                "No cabo",
                "Concentrada",
                "Alternada",
            ],
        },
    ],


    "Tríceps": [
        {
            "nome": "Tríceps",
            "variacoes": [
                "Corda",
                "Barra reta",
                "Francês",
                "Testa",
                "Coice",
                "Banco",
            ],
        },
    ],


    "Glúteos": [
        {
            "nome": "Elevação pélvica",
            "variacoes": [
                "Barra",
                "Smith",
                "Unilateral",
            ],
        },

        {
            "nome": "Coice",
            "variacoes": [
                "Polia",
                "Máquina",
            ],
        },

        {
            "nome": "Abdução",
            "variacoes": [
                "Máquina",
                "Polia",
                "Elástico",
            ],
        },
    ],


    "Panturrilhas": [
        {
            "nome": "Panturrilha",
            "variacoes": [
                "Em pé",
                "Sentado",
                "Leg press",
                "Smith",
            ],
        },
    ],


    "Pernas": [
        {
            "nome": "Agachamento",
            "variacoes": [
                "Livre",
                "Smith",
                "Frontal",
                "Hack",
                "Sumô",
            ],
        },

        {
            "nome": "Leg press",
            "variacoes": [
                "45°",
                "Horizontal",
                "Unilateral",
            ],
        },

        {
            "nome": "Cadeira extensora",
            "variacoes": [
                "Unilateral",
                "Bilateral",
            ],
        },

        {
            "nome": "Mesa flexora",
            "variacoes": [
                "Unilateral",
                "Bilateral",
            ],
        },

        {
            "nome": "Stiff",
            "variacoes": [
                "Barra",
                "Halteres",
                "Smith",
            ],
        },

        {
            "nome": "Afundo",
            "variacoes": [
                "Livre",
                "Smith",
                "Passada",
            ],
        },
    ],
}



class Command(BaseCommand):
    help = "Popula o banco com grupos musculares, exercícios e variações."

    def handle(self, *args, **options):
        grupos_criados = 0
        exercicios_criados = 0
        variacoes_criadas = 0

        for nome_grupo, exercicios_data in EXERCICIOS_POR_GRUPO.items():

            # ===== GRUPO =====
            grupo, criado = GrupoMuscular.objects.get_or_create(nome=nome_grupo)

            if criado:
                grupos_criados += 1
                self.stdout.write(self.style.SUCCESS(f"✔ Grupo criado: {grupo.nome}"))
            else:
                self.stdout.write(f"- Já existe grupo: {grupo.nome}")

            # ===== EXERCÍCIOS =====
            for exercicio_data in exercicios_data:

                exercicio, criado = VideoExercicio.objects.get_or_create(
                    nome=exercicio_data["nome"],
                    grupo_muscular=grupo,
                    defaults={"descricao": exercicio_data.get("descricao", "")},
                )

                if criado:
                    exercicios_criados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"✔ Exercício criado: {exercicio.nome}")
                    )
                else:
                    self.stdout.write(f"- Já existe exercício: {exercicio.nome}")

                # ===== VARIAÇÕES =====
                variacoes = exercicio_data.get("variacoes", ["Padrão"])

                for nome_variacao in variacoes:
                    variacao, criada = VariacaoExercicio.objects.get_or_create(
                        exercicio=exercicio,
                        nome=nome_variacao,
                        defaults={"grupo_muscular": grupo},
                    )

                    if criada:
                        variacoes_criadas += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"✔ Variação criada: {variacao.nome}")
                        )
                    else:
                        self.stdout.write(f"- Já existe variação: {variacao.nome}")

        # ===== RESUMO =====
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed concluída:\n"
                f"✔ Grupos criados: {grupos_criados}\n"
                f"✔ Exercícios criados: {exercicios_criados}\n"
                f"✔ Variações criadas: {variacoes_criadas}"
            )
        )
