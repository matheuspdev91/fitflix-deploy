# Migration 0015 — Schema only
# Creates the DivisaoTreino table and adds the nullable FK on ExercicioTreino.
# No data operations.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_avaliacaofisica_aluno"),
    ]

    operations = [
        migrations.CreateModel(
            name="DivisaoTreino",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nome", models.CharField(max_length=50)),
                ("descricao", models.CharField(blank=True, max_length=200)),
                ("ordem", models.PositiveIntegerField(default=1)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "treino",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="divisoes",
                        to="core.treino",
                    ),
                ),
            ],
            options={
                "verbose_name": "Divisão de treino",
                "verbose_name_plural": "Divisões de treino",
                "ordering": ["ordem", "id"],
                "unique_together": {("treino", "nome")},
            },
        ),
        migrations.AddField(
            model_name="exerciciotreino",
            name="divisao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="exercicios",
                to="core.divisaotreino",
            ),
        ),
    ]
