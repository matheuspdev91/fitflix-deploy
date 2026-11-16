# Migration 0016 — Data migration
# Creates an initial "Treino A" division for each existing workout and
# associates orphan exercises. Uses a tracking table with exact division IDs
# so the reversal can surgically undo only what this migration did.

from django.db import migrations


def criar_divisoes_iniciais(apps, schema_editor):
    Treino = apps.get_model("core", "Treino")
    DivisaoTreino = apps.get_model("core", "DivisaoTreino")
    ExercicioTreino = apps.get_model("core", "ExercicioTreino")

    # 1. Cria a tabela de rastreamento com a coluna divisao_id
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS core_migracao_0016_tracking (
                tipo VARCHAR(20) NOT NULL,
                registro_id BIGINT NOT NULL,
                divisao_id BIGINT NULL,
                PRIMARY KEY (tipo, registro_id)
            )
            """
        )

    for treino in Treino.objects.all():
        divisao, created = DivisaoTreino.objects.get_or_create(
            treino=treino,
            nome="Treino A",
            defaults={
                "ordem": 1,
                "descricao": "",
            },
        )

        # 2. Registra na tabela de rastreamento apenas divisões criadas pela migração
        if created:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO core_migracao_0016_tracking (tipo, registro_id, divisao_id)
                    VALUES (%s, %s, %s)
                    """,
                    ["divisao", divisao.id, divisao.id],
                )

        # 3. Identifica exclusivamente exercícios sem divisão preexistente
        exercicios_pendentes_ids = list(
            ExercicioTreino.objects.filter(
                treino=treino,
                divisao__isnull=True,
            ).values_list("id", flat=True)
        )

        if exercicios_pendentes_ids:
            with schema_editor.connection.cursor() as cursor:
                for ex_id in exercicios_pendentes_ids:
                    cursor.execute(
                        """
                        INSERT INTO core_migracao_0016_tracking (tipo, registro_id, divisao_id)
                        VALUES (%s, %s, %s)
                        """,
                        ["exercicio", ex_id, divisao.id],
                    )

            ExercicioTreino.objects.filter(
                id__in=exercicios_pendentes_ids
            ).update(divisao=divisao)


def reverter_divisoes_iniciais(apps, schema_editor):
    DivisaoTreino = apps.get_model("core", "DivisaoTreino")
    ExercicioTreino = apps.get_model("core", "ExercicioTreino")

    # 0. Verifica se a tabela de rastreamento existe
    existing_tables = [
        t.lower()
        for t in schema_editor.connection.introspection.table_names()
    ]
    if "core_migracao_0016_tracking" not in existing_tables:
        raise RuntimeError(
            "Tabela de rastreamento da migração 0016 não encontrada. "
            "Rollback interrompido para proteger os dados."
        )

    # 1. Recuperar IDs das divisões criadas pela migração
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT registro_id FROM core_migracao_0016_tracking WHERE tipo = %s",
            ["divisao"],
        )
        divisao_ids = set(row[0] for row in cursor.fetchall())

        # 2. Recuperar IDs dos exercícios e suas respectivas divisões originais
        cursor.execute(
            "SELECT registro_id, divisao_id FROM core_migracao_0016_tracking WHERE tipo = %s",
            ["exercicio"],
        )
        exercicio_divisao_map = {row[0]: row[1] for row in cursor.fetchall()}

    exercicio_ids = set(exercicio_divisao_map.keys())

    # --- TODAS AS VERIFICAÇÕES DE SEGURANÇA ANTES DE QUALQUER ALTERAÇÃO ---

    # 3. Verificar se algum exercício não rastreado foi associado posteriormente a uma divisão criada pela migração
    for div_id in divisao_ids:
        exercicios_na_divisao = set(
            ExercicioTreino.objects.filter(
                divisao_id=div_id,
            ).values_list("id", flat=True)
        )
        nao_rastreados = exercicios_na_divisao - exercicio_ids
        if nao_rastreados:
            raise RuntimeError(
                f"A divisão ID {div_id} (criada pela migração 0016) possui "
                f"exercícios não rastreados vinculados a ela "
                f"(IDs: {sorted(nao_rastreados)}). "
                f"Esses exercícios foram vinculados após a migração e não podem "
                f"ser desassociados ou excluídos automaticamente. "
                f"Resolva manualmente antes de reverter."
            )

    # 4 & 5. Verificar se os exercícios rastreados continuam associados exatamente à divisão registrada
    exercicios_atuais = {
        ex.id: ex.divisao_id
        for ex in ExercicioTreino.objects.filter(id__in=exercicio_ids)
    }

    exercicios_desassociados = []
    exercicios_transferidos = []

    for ex_id, div_original_id in exercicio_divisao_map.items():
        if ex_id not in exercicios_atuais:
            raise RuntimeError(
                f"O exercício ID {ex_id} rastreado pela migração 0016 não foi encontrado no banco. "
                f"A reversão foi interrompida para proteger a integridade dos dados."
            )

        div_atual_id = exercicios_atuais[ex_id]
        if div_atual_id is None:
            exercicios_desassociados.append(ex_id)
        elif div_atual_id != div_original_id:
            exercicios_transferidos.append((ex_id, div_original_id, div_atual_id))

    if exercicios_desassociados:
        raise RuntimeError(
            f"Os exercícios (IDs: {sorted(exercicios_desassociados)}) foram "
            f"desassociados manualmente após a migração 0016. "
            f"A reversão foi interrompida para proteger os dados. "
            f"Resolva manualmente antes de reverter."
        )

    if exercicios_transferidos:
        detalhes = [
            f"Exercício {ex_id}: divisão original {orig} -> atual {atual}"
            for ex_id, orig, atual in exercicios_transferidos
        ]
        raise RuntimeError(
            f"Exercícios rastreados foram transferidos para outra divisão após a migração 0016: "
            f"{'; '.join(detalhes)}. "
            f"A reversão foi interrompida para proteger a nova organização dos treinos. "
            f"Resolva manualmente as transferências antes de reverter."
        )

    # 6. Observação: Renomeação da divisão não bloqueia a reversão pois a comparação é estritamente por ID!

    # --- INÍCIO DAS ALTERAÇÕES (somente após todas as verificações passarem com sucesso) ---

    # 7. Desassociar os exercícios rastreados
    if exercicio_ids:
        ExercicioTreino.objects.filter(id__in=exercicio_ids).update(divisao=None)

    # 8 & 9. Excluir exclusivamente as divisões criadas pela migração com proteção contra CASCADE
    if divisao_ids:
        ExercicioTreino.objects.filter(divisao_id__in=divisao_ids).update(divisao=None)
        DivisaoTreino.objects.filter(id__in=divisao_ids).delete()

    # 10. Remover a tabela auxiliar somente após uma reversão bem-sucedida
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP TABLE core_migracao_0016_tracking")


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("core", "0015_divisaotreino_schema"),
    ]

    operations = [
        migrations.RunPython(
            criar_divisoes_iniciais,
            reverter_divisoes_iniciais,
        ),
    ]
