import sqlite3

from django.core.management.base import BaseCommand

from core.models import (
    GrupoMuscular,
    VideoExercicio,
    VariacaoExercicio,
)


class Command(BaseCommand):
    help = "Migra dados do SQLite antigo para PostgreSQL"

    def handle(self, *args, **kwargs):

        caminho_sqlite = "db_backup.sqlite3"

        conn = sqlite3.connect(caminho_sqlite)
        cursor = conn.cursor()

        self.stdout.write(self.style.SUCCESS("Migrando grupos..."))

        cursor.execute("""
            SELECT id, nome
            FROM core_grupomuscular
        """)

        for grupo_id, nome in cursor.fetchall():

            GrupoMuscular.objects.update_or_create(
                id=grupo_id,
                defaults={
                    "nome": nome,
                },
            )

        self.stdout.write(self.style.SUCCESS("Migrando exercícios..."))

        cursor.execute("""
            SELECT
                id,
                nome,
                descricao,
                grupo_muscular_id
            FROM core_videoexercicio
        """)

        for (
            exercicio_id,
            nome,
            descricao,
            grupo_id,
        ) in cursor.fetchall():

            VideoExercicio.objects.update_or_create(
                id=exercicio_id,
                defaults={
                    "nome": nome,
                    "descricao": descricao or "",
                    "grupo_muscular_id": grupo_id,
                },
            )

        self.stdout.write(self.style.SUCCESS("Migrando variações..."))

        cursor.execute("""
            SELECT
                id,
                nome,
                gif,
                exercicio_id
            FROM core_variacaoexercicio
        """)

        for (
            variacao_id,
            nome,
            gif,
            exercicio_id,
        ) in cursor.fetchall():

            VariacaoExercicio.objects.update_or_create(
                id=variacao_id,
                defaults={
                    "nome": nome,
                    "gif": gif or "",
                    "exercicio_id": exercicio_id,
                },
            )

        conn.close()

        self.stdout.write(
            self.style.SUCCESS(
                "Migração concluída com sucesso!"
            )
        )