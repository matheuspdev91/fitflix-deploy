from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path(
        "api/variacoes/<int:exercicio_id>/",
        views.buscar_variacoes,
        name="buscar_variacoes",),

    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),
    path("alunos/novo/", views.criar_aluno, name="criar_aluno"),
    # Avaliações completas
    path("avaliacoes/nova/", views.criar_avaliacao, name="criar_avaliacao"),
    path(
        "avaliacoes/<int:id>/editar/", views.editar_avaliacao, name="editar_avaliacao"
    ),
    path(
        "avaliacoes/<int:id>/excluir/",
        views.excluir_avaliacao,
        name="excluir_avaliacao",
    ),
    path("avaliacoes/<int:id>/", views.detalhe_avaliacao, name="detalhe_avaliacao"),
    path("avaliacoes/", views.avaliacoes, name="avaliacoes"),
    path("avaliacoes/escolher-tipo/", views.escolher_tipo, name="escolher_tipo"),
    path(
        "avaliacoes/idoso/", views.criar_avaliacao_idoso, name="criar_avaliacao_idoso"
    ),
    path(
        "avaliacoes/crianca/",
        views.criar_avaliacao_crianca,
        name="criar_avaliacao_crianca",
    ),
    path(
        "treino/<int:treino_id>/exercicio/adicionar/",
        views.adicionar_exercicio,
        name="adicionar_exercicio",
    ),
    # Dashboard
    path("dashboard/<int:id>/", views.dashboard, name="dashboard"),
    # FitFlix
    path("fitflix/", views.fitflix, name="fitflix"),
    path("exercicios/novo/", views.criar_exercicio, name="criar_exercicio"),
    path("exercicio/<int:id>/", views.exercicio_detalhe, name="exercicio_detalhe"),
    path("treinos/novo/", views.criar_treino, name="criar_treino"),
    path("grupo/<int:id>/", views.lista_exercicios, name="lista_exercicios"),
    # Treinos
    path("treino/<int:treino_id>/", views.treino_detail, name="treino_detail"),
    path("aluno/<int:aluno_id>/", views.painel_aluno, name="painel_aluno"),
    path("treino/<uuid:token>/", views.ver_treino, name="ver_treino"),
    # Reset Password
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.html",
            success_url="/password-reset/done/"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url="/password-reset-complete/"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    # Editar treino
    path("treino/<int:treino_id>/editar/", views.editar_treino, name="editar_treino"),


    # Webhook Asaas
    path(
        "webhooks/asaas/",
        views.asaas_webhook,
        name="asaas_webhook"
    ),

    path(
    "api/assinatura/criar/",
    views.criar_assinatura,
    name="criar_assinatura",
),
]
