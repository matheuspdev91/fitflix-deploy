from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = "Remove registros de ExercicioTreino com FK quebrada para VideoExercicio."

    def handle(self, *args, **options):
        self.stdout.write("Buscando exercicios invalidos...")

        tabelas = set(connection.introspection.table_names())

        if "core_exerciciotreino" not in tabelas:
            self.stdout.write(
                self.style.WARNING("Tabela core_exerciciotreino nao encontrada.")
            )
            return

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM core_exerciciotreino")
            total_exercicios_treino = cursor.fetchone()[0]

        if total_exercicios_treino == 0:
            self.stdout.write(self.style.SUCCESS("Nada pra corrigir."))
            return

        if "core_videoexercicio" not in tabelas:
            self.stdout.write(
                self.style.WARNING(
                    "Tabela core_videoexercicio nao encontrada. Todos os registros de "
                    "ExercicioTreino estao invalidos."
                )
            )
            removidos = self._deletar_todos()
            self.stdout.write(
                self.style.SUCCESS(f"Registros invalidos removidos: {removidos}")
            )
            return

        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM core_videoexercicio")
            ids_validos = {row[0] for row in cursor.fetchall()}

        if not ids_validos:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum VideoExercicio valido encontrado. Todos os registros de "
                    "ExercicioTreino serao removidos."
                )
            )
            removidos = self._deletar_todos()
            self.stdout.write(
                self.style.SUCCESS(f"Registros invalidos removidos: {removidos}")
            )
            return

        placeholders = ", ".join(["%s"] * len(ids_validos))
        sql_count = (
            "SELECT COUNT(*) FROM core_exerciciotreino "
            f"WHERE exercicio_id NOT IN ({placeholders})"
        )
        sql_delete = (
            "DELETE FROM core_exerciciotreino "
            f"WHERE exercicio_id NOT IN ({placeholders})"
        )
        params = list(ids_validos)

        with connection.cursor() as cursor:
            cursor.execute(sql_count, params)
            total_invalidos = cursor.fetchone()[0]

        self.stdout.write(f"Encontrados {total_invalidos} registros invalidos")

        if total_invalidos == 0:
            self.stdout.write(self.style.SUCCESS("Nada pra corrigir."))
            return

        with connection.constraint_checks_disabled():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql_delete, params)

        self.stdout.write(
            self.style.SUCCESS("Registros invalidos removidos com sucesso!")
        )

    def _deletar_todos(self):
        with connection.constraint_checks_disabled():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM core_exerciciotreino")
                    total = cursor.fetchone()[0]
                    cursor.execute("DELETE FROM core_exerciciotreino")
        return total
