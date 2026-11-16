from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Adipometria,
    Aluno,
    AvaliacaoCrianca,
    AvaliacaoFisica,
    AvaliacaoIdoso,
    Circunferencia,
    Exercicio,
    ExercicioTreino,
    GrupoMuscular,
    Treino,
    Usuario,
    VariacaoExercicio,
    VideoExercicio,
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("email", "username", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active", "groups")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("email",)

    fieldsets = UserAdmin.fieldsets + (
        (
            "Informações profissionais",
            {
                "fields": ("cref", "telefone"),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Dados do usuário",
            {
                "fields": ("email", "cref", "telefone"),
            },
        ),
    )


class CircunferenciaInline(admin.StackedInline):
    model = Circunferencia
    extra = 1
    max_num = 1
    can_delete = False


class AdipometriaInline(admin.StackedInline):
    model = Adipometria
    extra = 1
    max_num = 1
    can_delete = False


class AvaliacaoCriancaInline(admin.StackedInline):
    model = AvaliacaoCrianca
    extra = 1
    max_num = 1


class AvaliacaoIdosoInline(admin.StackedInline):
    model = AvaliacaoIdoso
    extra = 1
    max_num = 1


@admin.register(AvaliacaoFisica)
class AvaliacaoFisicaAdmin(admin.ModelAdmin):
    list_display = ("nome", "peso", "sexo", "usuario", "criado_em")
    search_fields = ("nome", "usuario__email", "usuario__username")
    list_filter = ("sexo", "criado_em")
    ordering = ("-criado_em",)
    readonly_fields = ("criado_em", "data")
    inlines = [
        CircunferenciaInline,
        AdipometriaInline,
        AvaliacaoCriancaInline,
        AvaliacaoIdosoInline,
    ]

    fieldsets = (
        (
            "Dados pessoais",
            {
                "fields": ("usuario", "nome", "sexo", "data_nascimento"),
            },
        ),
        (
            "Dados antropométricos",
            {
                "fields": ("altura", "peso", "objetivo", "percentual_gordura"),
                "classes": ("wide",),
            },
        ),
        (
            "Controle",
            {
                "fields": ("data", "criado_em"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ("nome", "user", "telefone", "data_nascimento")
    search_fields = ("nome", "user__email", "user__username", "telefone")
    ordering = ("nome",)


@admin.register(GrupoMuscular)
class GrupoMuscularAdmin(admin.ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    ordering = ("nome",)


class VariacaoInline(admin.TabularInline):
    model = VariacaoExercicio
    extra = 1
    fields = ("nome", "grupo_muscular", "gif")


@admin.register(VideoExercicio)
class VideoExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome", "grupo_muscular", "criado_em")
    list_filter = ("grupo_muscular", "criado_em")
    search_fields = ("nome", "descricao", "grupo_muscular__nome")
    ordering = ("nome",)
    inlines = [VariacaoInline]

    class Media:
        js = ("js/exercicio_auto.js",)


@admin.register(VariacaoExercicio)
class VariacaoExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome", "exercicio", "grupo_muscular")
    list_filter = ("grupo_muscular", "exercicio")
    search_fields = ("nome", "exercicio__nome", "grupo_muscular__nome")
    ordering = ("exercicio__nome", "nome")


class ExercicioTreinoInline(admin.TabularInline):
    model = ExercicioTreino
    extra = 1
    fields = (
        "exercicio",
        "variacao",
        "series",
        "repeticoes",
        "descanso",
        "carga",
        "ordem",
    )


@admin.register(Treino)
class TreinoAdmin(admin.ModelAdmin):
    list_display = ("nome", "aluno", "criado_em")
    list_filter = ("criado_em",)
    search_fields = ("nome", "aluno__nome")
    ordering = ("-criado_em",)
    readonly_fields = ("token", "criado_em")
    inlines = [ExercicioTreinoInline]


@admin.register(ExercicioTreino)
class ExercicioTreinoAdmin(admin.ModelAdmin):
    list_display = (
        "treino",
        "exercicio",
        "variacao",
        "series",
        "repeticoes",
        "ordem",
    )
    list_filter = ("treino", "exercicio")
    search_fields = ("treino__nome", "exercicio__nome", "variacao__nome")
    ordering = ("treino__nome", "ordem")


@admin.register(Exercicio)
class ExercicioAdmin(admin.ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    ordering = ("nome",)


from .models import Assinatura, WebhookEvent

@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "status", "plano", "criado_em")
    list_filter = ("status", "plano", "criado_em")
    search_fields = ("usuario__email", "asaas_subscription_id")
    ordering = ("-criado_em",)
    readonly_fields = ("criado_em", "atualizado_em")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "event_id", "payment_id", "status", "criado_em")
    list_filter = ("status", "event_type", "criado_em")
    search_fields = ("event_id", "payment_id")
    ordering = ("-criado_em",)
    readonly_fields = ("criado_em", "event_id", "payload")

