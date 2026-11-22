from django.http import Http404, JsonResponse
from core.services.asaas.subscription_service import SubscriptionService
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from decimal import Decimal
import secrets
import string
from collections import defaultdict
from django.http import HttpResponse
import json
import os
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.crypto import constant_time_compare
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django_ratelimit.decorators import ratelimit
from datetime import timedelta

from core.services.asaas import WebhookHandler

from .models import (
    Aluno,
    Treino,
    GrupoMuscular,
    AvaliacaoFisica,
    VideoExercicio,
    VariacaoExercicio,
    AvaliacaoCrianca,
    AvaliacaoIdoso,
    ExercicioTreino,
    DivisaoTreino,
)

from .forms import (
    CriarTreinoForm,
    AvaliacaoFisicaForm,
    CircunferenciaForm,
    AdipometriaForm,
    AvaliacaoCriancaForm,
    AvaliacaoIdosoForm,
    CriarAlunoForm,
    CircunferenciaIdosoForm,
    DivisaoTreinoForm,
    ExercicioTreinoForm,
)

from .email_service import enviar_email_acesso_aluno
from .decorators import apenas_aluno, apenas_personal

User = get_user_model()

# ==================
# HOME
# ==================


def home(request):
    if request.user.is_authenticated:
        if hasattr(request.user, "aluno"):
            return redirect("core:painel_aluno", aluno_id=request.user.aluno.id)
        else:
            return redirect("core:fitflix")

    return render(request, "core/home.html")


# ==================
# LOGIN
# ==================


@ratelimit(key='ip', rate='5/m', method='POST', block=True)
def login_view(request):
    if request.method == "GET":
        return render(
            request,
            "core/login.html",
            {"next": request.GET.get("next", "")},
        )

    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    next_url = request.POST.get("next", "").strip() or request.GET.get("next", "").strip()

    try:
        usuario = get_user_model().objects.get(email__iexact=email)
    except get_user_model().DoesNotExist:
        usuario = None
    except get_user_model().MultipleObjectsReturned:
        usuario = get_user_model().objects.filter(email__iexact=email).first()

    user = (
        authenticate(
            request,
            username=usuario.username,
            password=password,
        )
        if usuario
        else None
    )

    if user:
        login(request, user)

        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts=settings.ALLOWED_HOSTS
        ):
            return redirect(next_url)

        if hasattr(user, "aluno"):
            return redirect("core:painel_aluno", aluno_id=user.aluno.id)
        return redirect("core:fitflix")

    messages.error(request, "Email ou senha inválidos")
    return render(request, "core/login.html")


def logout_view(request):
    logout(request)
    return redirect("core:login")


# ==================
# REGISTER
# ==================


@ratelimit(key='ip', rate='3/m', method='POST', block=True)
def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Usuário já existe")
            return render(request, "core/register.html")

        user = User.objects.create_user(
            username=username, email=email, password=password
        )

        login(request, user)
        return redirect("core:fitflix")

    return render(request, "core/register.html")


# ==================
# HELPERS
# ==================


def gerar_senha_aleatoria(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return "".join(secrets.choice(caracteres) for _ in range(tamanho))


def criar_aluno_minimo(nome_aluno, personal):
    sufixo = secrets.token_hex(4)
    email = f"aluno-{sufixo}@fitflix.local"
    user = User.objects.create_user(
        username=email,
        email=email,
        password=gerar_senha_aleatoria(),
        tipo_usuario="ALUNO",
    )
    return Aluno.objects.create(
        personal=personal,
        user=user,
        nome=nome_aluno,
        data_nascimento=timezone.localdate(),
    )


# ==================
# CRIAR ALUNO
# ==================


@login_required
@apenas_personal
def criar_aluno(request):
    if request.method == "POST":
        form = CriarAlunoForm(request.POST)

        if form.is_valid():
            senha = gerar_senha_aleatoria()
            email = form.cleaned_data["email"]

            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    tipo_usuario="ALUNO",
                )
                user.set_unusable_password()
                user.save()

                aluno = form.save(commit=False)
                aluno.personal = request.user
                aluno.user = user
                aluno.save()

                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = request.build_absolute_uri(
                    reverse('core:password_reset_confirm', kwargs={
                            'uidb64': uid, 'token': token})
                )

                enviar_email_acesso_aluno(
                    nome=aluno.nome,
                    email=user.email,
                    reset_url=reset_url,
                )

            messages.success(request, "Aluno cadastrado com sucesso!")
            return redirect("core:home")

    else:
        form = CriarAlunoForm()

    return render(request, "core/criar_aluno.html", {"form": form})


# ==================
# AVALIAÇÕES (INTELIGENTE)
# ==================


@login_required
@apenas_personal
def avaliacoes(request):

    avaliacoes = AvaliacaoFisica.objects.filter(
        usuario=request.user
    ).order_by('-criado_em')

    return render(
        request,
        'core/avaliacoes.html',
        {"avaliacoes": avaliacoes}
    )


# ==================
# DETALHE AVALIAÇÃO
# ==================


@login_required
@apenas_personal
def detalhe_avaliacao(request, id):
    avaliacao = get_object_or_404(AvaliacaoFisica, id=id, usuario=request.user)

    if hasattr(avaliacao, "idoso"):
        tipo = "idoso"
    elif hasattr(avaliacao, "crianca"):
        tipo = "crianca"
    else:
        tipo = "adulto"

    return render(
        request,
        "core/detalhe_avaliacao.html",
        {
            "avaliacao": avaliacao,
            "tipo": tipo,
        },
    )


# ==================
# DASHBOARD
# ==================


@login_required
@apenas_personal
def dashboard(request, id):
    avaliacao = get_object_or_404(AvaliacaoFisica, id=id, usuario=request.user)

    composicao = calcular_composicao(avaliacao)

    avaliacao_anterior = (
        AvaliacaoFisica.objects.filter(
            usuario=avaliacao.usuario,
            criado_em__lt=avaliacao.criado_em,
        )
        .order_by("-criado_em")
        .first()
    )

    composicao = calcular_composicao(avaliacao)

    composicao_anterior = None
    comparativo = None

    if avaliacao_anterior:
        composicao_anterior = calcular_composicao(avaliacao_anterior)

    if avaliacao_anterior:
        comparativo = {
            "peso": {
                "anterior": avaliacao_anterior.peso,
                "atual": avaliacao.peso,
                "diferenca": round(
                    float(avaliacao.peso) -
                    float(avaliacao_anterior.peso),
                    2,
                ),
            },
            "percentual_gordura": {
                "anterior": composicao_anterior["percentual"]
                if composicao_anterior
                else 0,
                "atual": composicao["percentual"]
                if composicao
                else 0,
                "diferenca": round(
                    float(composicao["percentual"] if composicao else 0)
                    - float(
                        composicao_anterior["percentual"]
                        if composicao_anterior
                        else 0
                    ),
                    2,
                ),
            },
        }

    return render(
        request,
        "core/dashboard.html",
        {
            "avaliacao": avaliacao,
            "composicao": composicao,
            "comparativo": comparativo,
            "avaliacao_anterior": avaliacao_anterior,
        },
    )


# ==================
# FITFLIX (PERSONAL)
# ==================


@login_required
@apenas_personal
def fitflix(request):
    grupo_dict = defaultdict(list)

    exercicios = VideoExercicio.objects.prefetch_related("variacoes").order_by(
        "grupo_muscular", "nome"
    )

    for exercicio in exercicios:
        grupo_dict[exercicio.grupo_muscular].append(exercicio)

    grupos = [
        {
            "grupo": nome,
            "exercicios": lista,
            "total_exercicios": len(lista),
        }
        for nome, lista in grupo_dict.items()
    ]

    alunos = Aluno.objects.filter(personal=request.user).order_by("nome")
    return render(
        request,
        "core/fitflix.html",
        {"grupos": grupos, "alunos": alunos},
    )


# ==================
# PAINEL DO ALUNO
# ==================


@login_required
@apenas_aluno
def painel_aluno(request, aluno_id):
    aluno = get_object_or_404(Aluno, id=aluno_id, user=request.user)
    if aluno.personal_id is None:
        raise Http404
    treinos = Treino.objects.filter(aluno=aluno)

    return render(
        request, "core/painel_aluno.html", {"aluno": aluno, "treinos": treinos}
    )


# ==================
# CALCULAR COMPOSIÇÃO
# ==================


def calcular_composicao(avaliacao):
    adip = getattr(avaliacao, "adipometria", None)

    if not adip:
        return None

    soma = sum(
        [
            adip.tricipital or 0,
            adip.subescapular or 0,
            adip.supra_iliaca or 0,
            adip.coxa or 0,
            adip.abdominal or 0,
            adip.peito or 0,
        ]
    )

    peso = avaliacao.peso or 0

    if soma == 0:
        return None

    percentual = soma * Decimal("0.153")
    massa_gorda = (percentual / 100) * peso
    massa_magra = peso - massa_gorda
    massa_residual = peso * Decimal("0.24")

    return {
        "percentual": round(percentual, 2),
        "massa_gorda": round(massa_gorda, 2),
        "massa_magra": round(massa_magra, 2),
        "massa_residual": round(massa_residual, 2),
    }


# ==================
# CRIAR AVALIAÇÃO
# ==================


@login_required
@apenas_personal
def criar_avaliacao(request):
    if request.method == "POST":
        avaliacao_form = AvaliacaoFisicaForm(request.POST, user=request.user)
        circ_form = CircunferenciaForm(request.POST)
        adip_form = AdipometriaForm(request.POST)

        if all([avaliacao_form.is_valid(), circ_form.is_valid(), adip_form.is_valid()]):
            avaliacao = avaliacao_form.save(commit=False)
            avaliacao.usuario = request.user
            aluno = avaliacao_form.cleaned_data.get("aluno")
            if aluno is not None and aluno.personal_id != request.user.pk:
                avaliacao_form.add_error(
                    "aluno", "Aluno inválido para este personal."
                )
            else:
                avaliacao.aluno = aluno
                avaliacao.save()

                circ = circ_form.save(commit=False)
                circ.avaliacao = avaliacao
                circ.save()

                adip = adip_form.save(commit=False)
                adip.avaliacao = avaliacao
                adip.save()

                return redirect("core:avaliacoes")

    else:
        avaliacao_form = AvaliacaoFisicaForm(user=request.user)
        circ_form = CircunferenciaForm()
        adip_form = AdipometriaForm()

    return render(
        request,
        "core/criar_avaliacao.html",
        {
            "avaliacao_form": avaliacao_form,
            "circ_form": circ_form,
            "adip_form": adip_form,
        },
    )


# ==================
# EXCLUIR AVALIAÇÃO
# ==================


@login_required
@apenas_personal
@require_POST
def excluir_avaliacao(request, id):
    avaliacao = get_object_or_404(AvaliacaoFisica, id=id, usuario=request.user)
    avaliacao.delete()
    return redirect("core:avaliacoes")


# =========================
# EDITAR AVALIAÇÃO
# =========================


@login_required
@apenas_personal
def editar_avaliacao(request, id):
    avaliacao = get_object_or_404(AvaliacaoFisica, id=id, usuario=request.user)

    if request.method == "POST":
        form = AvaliacaoFisicaForm(request.POST, instance=avaliacao, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("core:avaliacoes")
    else:
        form = AvaliacaoFisicaForm(instance=avaliacao, user=request.user)

    return render(
        request, "core/editar_avaliacao.html", {
            "form": form, "avaliacao": avaliacao}
    )


# ================
# ESCOLHER TIPO
# ================


@login_required
@apenas_personal
def escolher_tipo(request):
    return render(request, "core/escolher_tipo.html")


# ====================
# AVALIAÇÃO IDOSO
# ====================


@login_required
@apenas_personal
def criar_avaliacao_idoso(request):
    avaliacao_form = AvaliacaoFisicaForm(request.POST or None, user=request.user)
    circ_form = CircunferenciaIdosoForm(request.POST or None)
    form = AvaliacaoIdosoForm(request.POST or None)

    if request.method == "POST":
        if avaliacao_form.is_valid() and circ_form.is_valid() and form.is_valid():
            aluno = avaliacao_form.cleaned_data.get("aluno")
            if aluno is not None and aluno.personal_id != request.user.pk:
                avaliacao_form.add_error(
                    "aluno", "Aluno inválido para este personal."
                )
            else:
                with transaction.atomic():
                    avaliacao = avaliacao_form.save(commit=False)
                    avaliacao.usuario = request.user
                    avaliacao.aluno = aluno
                    avaliacao.save()

                    circ = circ_form.save(commit=False)
                    circ.avaliacao = avaliacao
                    circ.save()

                    idoso = form.save(commit=False)
                    idoso.avaliacao = avaliacao
                    idoso.save()

                return redirect("core:avaliacoes")

    return render(
        request,
        "core/criar_avaliacao_idoso.html",
        {
            "avaliacao_form": avaliacao_form,
            "circ_form": circ_form,
            "form": form,
        },
    )


# =====================
# AVALIAÇÃO CRIANÇA
# =====================


@login_required
@apenas_personal
def criar_avaliacao_crianca(request):
    avaliacao_form = AvaliacaoFisicaForm(request.POST or None, user=request.user)
    form = AvaliacaoCriancaForm(request.POST or None)

    if request.method == "POST":
        if avaliacao_form.is_valid() and form.is_valid():
            aluno = avaliacao_form.cleaned_data.get("aluno")
            if aluno is not None and aluno.personal_id != request.user.pk:
                avaliacao_form.add_error(
                    "aluno", "Aluno inválido para este personal."
                )
            else:
                with transaction.atomic():
                    avaliacao = avaliacao_form.save(commit=False)
                    avaliacao.usuario = request.user
                    avaliacao.aluno = aluno
                    avaliacao.save()

                    crianca = form.save(commit=False)
                    crianca.avaliacao = avaliacao
                    crianca.save()

                return redirect("core:avaliacoes")

    return render(
        request,
        "core/criar_avaliacao_crianca.html",
        {
            "avaliacao_form": avaliacao_form,
            "form": form,
        },
    )


# =====================
# ADICIONAR EXERCICIO
# =====================


@login_required
@apenas_personal

# =====================
# CRIAR EXERCÍCIO
# =====================


@login_required
@apenas_personal
def criar_exercicio(request):
    # Tela refatorada para atuar como visualizador do catálogo injetado pela pipeline
    return render(
        request,
        "core/criar_exercicio.html",
        {
            "grupos": GrupoMuscular.objects.all(),
            "exercicios": VideoExercicio.objects.all(),
        }
    )


# ====================
# EXERCÍCIO DETALHE
# ====================


@login_required
@apenas_personal
def exercicio_detalhe(request, id):
    exercicio = get_object_or_404(VideoExercicio, id=id)
    variacoes = exercicio.variacoes.all()

    return render(
        request,
        "core/exercicio_detalhe.html",
        {"exercicio": exercicio, "variacoes": variacoes},
    )


# =================
# CRIAR TREINO
# =================


@login_required
@apenas_personal
def criar_treino(request):
    if request.method == "POST":
        form = CriarTreinoForm(request.POST, user=request.user)

        if form.is_valid():
            aluno = form.cleaned_data.get("aluno")
            nome_aluno = form.cleaned_data.get("nome_aluno")

            with transaction.atomic():
                if not aluno and nome_aluno:
                    aluno = criar_aluno_minimo(nome_aluno, request.user)

                treino = Treino.objects.create(
                    aluno=aluno,
                    nome=form.cleaned_data.get("nome"),
                    descricao="",
                )

            messages.success(request, "Treino criado com sucesso!")
            return redirect("core:editar_treino", treino_id=treino.id)
        else:
            messages.error(request, "Erro no formulário.")

    else:
        form = CriarTreinoForm(user=request.user)

    return render(
        request, "core/criar_treino.html", {"form": form, "modo_edicao": False}
    )


# ===================
# EDITA TREINO
# ===================


@login_required
@apenas_personal
def editar_treino(request, treino_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user)

    # Todas as divisões pertencentes ao treino autorizado, na ordem
    # definida no modelo (ordem, id).
    divisoes = DivisaoTreino.objects.filter(treino=treino).order_by("ordem", "id")

    # Identifica a divisão selecionada pelo parâmetro GET "divisao",
    # validando estritamente que ela pertence ao treino atual. Valores
    # inválidos (não numéricos, fora de escopo) resultam em None.
    divisao_id = request.GET.get("divisao")
    divisao_selecionada = None

    # Verifica se o parâmetro ?divisao= foi informado na URL.
    parametro_fornecido = divisao_id is not None

    if divisao_id:
        try:
            divisao_id = int(divisao_id)
        except (TypeError, ValueError):
            divisao_id = None

        if divisao_id:
            divisao_selecionada = divisoes.filter(
                id=divisao_id
            ).first()

    # Parâmetro fornecido mas inválido ou de outro treino: usar a primeira
    # divisão do treino autorizado. Quando nenhum parâmetro foi informado,
    # `divisao_selecionada` permanece None, e `exercicios_treino` fica vazio
    # (seção "Sem divisão").
    if parametro_fornecido and divisao_selecionada is None and divisoes.exists():
        divisao_selecionada = divisoes.first()
    # Exercícios do treino, opcionalmente filtrados pela divisão selecionada.
    # Quando nenhuma divisão estiver selecionada, `exercicios_treino` fica
    # vazio, de modo que exercícios sem divisão não apareçam duplicados
    # na lista principal.
    exercicios_treino = treino.exercicios.none()

    if divisao_selecionada is not None:
        exercicios_treino = (
            treino.exercicios
            .filter(divisao=divisao_selecionada)
            .select_related("exercicio", "variacao")
            .order_by("ordem")
        )

    # Exercícios que ainda não possuem divisão. Esse conjunto é sempre
    # independente do filtro acima: com divisão selecionada ele mantém
    # somente os exercícios sem divisão; sem divisão, `exercicios_treino`
    # já começa vazio, então não há sobreposição entre os dois conjuntos.
    exercicios_sem_divisao = (
        treino.exercicios
        .filter(divisao__isnull=True)
        .select_related("exercicio", "variacao")
        .order_by("ordem")
    )

    treino_url = request.build_absolute_uri(treino.get_link())
    whatsapp_message = f"💪 Seu treino está pronto! Acesse aqui: {treino_url}"
    whatsapp_url = f"https://wa.me/?{urlencode({'text': whatsapp_message})}"

    context = {
        "treino": treino,
        "divisoes": divisoes,
        "divisao_selecionada": divisao_selecionada,
        "exercicios_treino": exercicios_treino,
        "exercicios_sem_divisao": exercicios_sem_divisao,
        "treino_url": treino_url,
        "whatsapp_url": whatsapp_url,
    }

    return render(request, "core/editar_treino.html", context)


# =========================
# DIVISÕES DE TREINO
# =========================


@login_required
@apenas_personal
def criar_divisao(request, treino_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )

    if request.method == "POST":
        form = DivisaoTreinoForm(request.POST, treino=treino)
        if form.is_valid():
            form.save()
            messages.success(request, "Divisão criada com sucesso.")
            return redirect("core:editar_treino", treino_id=treino.id)
        messages.error(request, "Corrija os erros para criar a divisão.")
        return render(
            request,
            "core/editar_divisao.html",
            {"treino": treino, "form": form},
        )

    return redirect("core:editar_treino", treino_id=treino.id)


@login_required
@apenas_personal
def editar_divisao(request, treino_id, divisao_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )
    divisao = get_object_or_404(
        DivisaoTreino, id=divisao_id, treino=treino
    )

    if request.method == "POST":
        form = DivisaoTreinoForm(
            request.POST, instance=divisao, treino=treino
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Divisão atualizada com sucesso.")
            return redirect("core:editar_treino", treino_id=treino.id)
        messages.error(request, "Corrija os erros para atualizar a divisão.")

    else:
        form = DivisaoTreinoForm(instance=divisao, treino=treino)
    return render(
        request,
        "core/editar_divisao.html",
        {"treino": treino, "divisao": divisao, "form": form},
    )


@login_required
@apenas_personal
@require_POST
def excluir_divisao(request, treino_id, divisao_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )
    divisao = get_object_or_404(
        DivisaoTreino, id=divisao_id, treino=treino
    )
    divisao.delete()
    messages.success(request, "Divisão excluída.")
    return redirect("core:editar_treino", treino_id=treino.id)


@login_required
@apenas_personal
@require_POST
def reordenar_divisoes(request, treino_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )
    ordem_ids = request.POST.getlist("divisao-ordens")

    # Validação: só aceitar IDs numéricos. Valores não numéricos são
    # rejeitados sem gerar erro 500.
    try:
        ids_numeros = [int(x) for x in ordem_ids if x.strip()]
    except ValueError:
        messages.error(request, "A ordem das divisões informada é inválida.")
        return redirect("core:editar_treino", treino_id=treino.id)

    # Validação: rejeitar IDs duplicados.
    if len(ids_numeros) != len(set(ids_numeros)):
        messages.error(request, "A ordem das divisões contém IDs duplicados.")
        return redirect("core:editar_treino", treino_id=treino.id)

    # Confirmação de que todos os IDs pertencem à divisão do treino
    # autorizado (a consulta abaixo só afeta divisões do treino corrente).
    divisoes = DivisaoTreino.objects.filter(treino=treino)
    IDs_validos = set(divisoes.values_list("id", flat=True))
    if not set(ids_numeros).issubset(IDs_validos):
        messages.error(request, "Algum ID de divisão não pertence a este treino.")
        return redirect("core:editar_treino", treino_id=treino.id)

    # Atualização atômica.
    try:
        with transaction.atomic():
            for index, divisao_id in enumerate(ids_numeros, start=1):
                DivisaoTreino.objects.filter(
                    id=divisao_id, treino=treino
                ).update(ordem=index)
    except Exception:
        messages.error(request, "Não foi possível reordenar as divisões.")
        return redirect("core:editar_treino", treino_id=treino.id)

    messages.success(request, "Ordem das divisões atualizada.")
    return redirect("core:editar_treino", treino_id=treino.id)


@login_required
@apenas_personal
def adicionar_exercicio(request, treino_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )
    divisoes = DivisaoTreino.objects.filter(treino=treino)

    divisao_selecionada = None
    if request.method == "GET" and request.GET.get("divisao"):
        try:
            divisao_id = int(request.GET["divisao"])
            divisao_selecionada = divisoes.filter(id=divisao_id).first()
        except (TypeError, ValueError):
            divisao_selecionada = None

    exercicios = (
        VideoExercicio.objects
        .all()
        .prefetch_related("variacoes")
        .order_by("nome")
    )
    grupos = GrupoMuscular.objects.order_by("nome")

    if request.method == "POST":
        exercicio_id = request.POST.get("exercicio")
        variacao_id = request.POST.get("variacao")
        divisao_id = request.POST.get("divisao")
        series = request.POST.get("series") or 3
        repeticoes = request.POST.get("repeticoes") or 12
        descanso = request.POST.get("descanso") or 60
        carga = request.POST.get("carga", "").strip()

        if not exercicio_id or not variacao_id:
            messages.error(request, "Selecione um exercício e uma variação.")
            return render(
                request,
                "core/adicionar_exercicio.html",
                {
                    "treino": treino,
                    "exercicios": exercicios,
                    "grupos": grupos,
                    "divisoes": divisoes,
                    "divisao_selecionada": divisao_selecionada,
                },
            )

        exercicio = get_object_or_404(VideoExercicio, id=exercicio_id)
        variacao = get_object_or_404(
            VariacaoExercicio, id=variacao_id, exercicio=exercicio
        )

        if divisao_id:
            divisao_selecionada = divisoes.filter(id=divisao_id).first()
            if divisao_selecionada is None:
                messages.error(request, "Selecione uma divisão válida para este treino.")
                return render(
                    request,
                    "core/adicionar_exercicio.html",
                    {
                        "treino": treino,
                        "exercicios": exercicios,
                        "grupos": grupos,
                        "divisoes": divisoes,
                        "divisao_selecionada": divisao_selecionada,
                    },
                )

        # Validação dos valores numéricos (séries, repetições, descanso)
        # e dos limites permitidos. Valores inválidos ou negativos não
        # geram erro 500; retornam ao formulário com mensagem de erro.
        try:
            series_int = int(series)
            repeticoes_int = int(repeticoes)
            descanso_int = int(descanso)
        except (TypeError, ValueError):
            messages.error(request, "Séries, repetições e descanso devem ser números inteiros.")
            return render(
                request,
                "core/adicionar_exercicio.html",
                {
                    "treino": treino,
                    "exercicios": exercicios,
                    "grupos": grupos,
                    "divisoes": divisoes,
                    "divisao_selecionada": divisao_selecionada,
                    "series": series,
                    "repeticoes": repeticoes,
                    "descanso": descanso,
                    "carga": carga,
                },
            )

        if series_int < 1:
            messages.error(request, "O número de séries deve ser no mínimo 1.")
            return render(
                request,
                "core/adicionar_exercicio.html",
                {
                    "treino": treino,
                    "exercicios": exercicios,
                    "grupos": grupos,
                    "divisoes": divisoes,
                    "divisao_selecionada": divisao_selecionada,
                    "series": series,
                    "repeticoes": repeticoes,
                    "descanso": descanso,
                    "carga": carga,
                },
            )

        if repeticoes_int < 1:
            messages.error(request, "O número de repetições deve ser no mínimo 1.")
            return render(
                request,
                "core/adicionar_exercicio.html",
                {
                    "treino": treino,
                    "exercicios": exercicios,
                    "grupos": grupos,
                    "divisoes": divisoes,
                    "divisao_selecionada": divisao_selecionada,
                    "series": series,
                    "repeticoes": repeticoes,
                    "descanso": descanso,
                    "carga": carga,
                },
            )

        if descanso_int < 0:
            messages.error(request, "O descanso não pode ser negativo.")
            return render(
                request,
                "core/adicionar_exercicio.html",
                {
                    "treino": treino,
                    "exercicios": exercicios,
                    "grupos": grupos,
                    "divisoes": divisoes,
                    "divisao_selecionada": divisao_selecionada,
                    "series": series,
                    "repeticoes": repeticoes,
                    "descanso": descanso,
                    "carga": carga,
                },
            )

        ExercicioTreino.objects.create(
            treino=treino,
            exercicio=exercicio,
            variacao=variacao,
            series=series_int,
            repeticoes=repeticoes_int,
            descanso=descanso_int,
            carga=carga,
            divisao=divisao_selecionada,
            ordem=treino.exercicios.count() + 1,
        )

        messages.success(request, "Exercício adicionado à divisão.")
        return redirect("core:editar_treino", treino_id=treino.id)

    return render(
        request,
        "core/adicionar_exercicio.html",
        {
            "treino": treino,
            "exercicios": exercicios,
            "grupos": grupos,
            "divisoes": divisoes,
            "divisao_selecionada": divisao_selecionada,
        },
    )


@login_required
@apenas_personal
def editar_exercicio(request, treino_id, exercicio_id):
    treino = get_object_or_404(
        Treino, id=treino_id, aluno__personal=request.user
    )

    # Busca o ExercicioTreino dentro do treino autorizado.
    # Nunca buscamos só pelo ID recebido na URL; sempre filtramos
    # pelo treino autorizado para garantir o isolamento entre
    # personalidades.
    exercicio_treino = get_object_or_404(
        ExercicioTreino, id=exercicio_id, treino=treino
    )

    divisoes = DivisaoTreino.objects.filter(treino=treino)
    exercicios = (
        VideoExercicio.objects.order_by("nome")
    )

    # Variações do exercício atual.
    variacoes_do_exercicio = (
        VariacaoExercicio.objects.filter(exercicio=exercicio_treino.exercicio)
        .order_by("nome")
    )

    if request.method == "POST":
        form = ExercicioTreinoForm(
            request.POST, instance=exercicio_treino
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Exercício atualizado com sucesso.")
            return redirect("core:editar_treino", treino_id=treino.id)
        messages.error(request, "Corrija os erros para atualizar o exercício.")

        # Formulário inválido: manter as opções de variação do
        # exercício enviado e preservar a seleção do usuário.
        variacoes_do_exercicio = form.fields["variacao"].queryset
        selected_variacao = form.data.get("variacao")

    else:
        form = ExercicioTreinoForm(instance=exercicio_treino)
        variacoes_do_exercicio = (
            VariacaoExercicio.objects.filter(exercicio=exercicio_treino.exercicio)
            .order_by("nome")
        )
        selected_variacao = exercicio_treino.variacao.id

    return render(
        request,
        "core/editar_exercicio.html",
        {
            "treino": treino,
            "exercicio_treino": exercicio_treino,
            "form": form,
            "divisoes": divisoes,
            "exercicios": exercicios,
            "variacoes_do_exercicio": variacoes_do_exercicio,
            "selected_variacao": selected_variacao,
        },
    )


@login_required


# =====================
# LISTA DE EXERCÍCIOS
# =====================


@login_required
@apenas_personal
def lista_exercicios(request, id):
    grupo = get_object_or_404(GrupoMuscular, id=id)
    exercicios = grupo.exercicios.all()

    return render(
        request,
        "core/lista_exercicios.html",
        {"grupo": grupo, "exercicios": exercicios},
    )


# =================
# TREINO DETALHES
# =================


@login_required
def treino_detail(request, treino_id):
    treino = get_object_or_404(
        Treino,
        Q(id=treino_id, aluno__personal=request.user)
        | Q(id=treino_id, aluno__user=request.user),
    )

    itens = treino.exercicios.select_related(
        "exercicio", "variacao").order_by("ordem")

    return render(
        request, "core/treino_detail.html", {"treino": treino, "itens": itens}
    )


# ===============
# VER TREINO
# ===============


@login_required
def ver_treino(request, token):
    treino = get_object_or_404(Treino, token=token)

    # Validação de propriedade: o usuário autenticado deve ser o aluno dono
    # do treino (relação Treino -> Aluno -> User).
    aluno = treino.aluno
    if aluno.user != request.user:
        # Aluno diferente, personal ou admin: 404
        raise Http404

    # Renderizar o treino público para o aluno proprietário.
    divisoes = DivisaoTreino.objects.filter(treino=treino)

    # Identifica a divisão selecionada pelo parâmetro GET "divisao",
    # validando estritamente que ela pertence ao treino atual. Valores
    # inválidos (não numéricos, fora de escopo) resultam em None.
    divisao_id = request.GET.get("divisao")
    divisao_selecionada = None
    modo_todos = (divisao_id == "")

    if divisao_id and not modo_todos:
        try:
            divisao_id = int(divisao_id)
        except (TypeError, ValueError):
            divisao_id = None
        if divisao_id:
            divisao_selecionada = divisoes.filter(id=divisao_id).first()

    # Primeira abertura sem parâmetro ou parâmetro inválido: seleciona a
    # divisão A (case-insensitive). Caso não exista, a primeira divisão
    # conforme a ordenação do modelo (ordem, id).
    if divisao_selecionada is None and divisoes.exists() and not modo_todos:
        divisao_a = divisoes.filter(nome__iexact="a").first()
        if divisao_a is not None:
            divisao_selecionada = divisao_a
        else:
            divisao_selecionada = divisoes.first()

    # Exercícios da área principal, sem duplicação com a seção "Sem divisão".
    if divisao_selecionada is not None:
        # Cenário 1: divisão selecionada -> somente exercícios dessa divisão.
        exercicios_treino = (
            treino.exercicios
            .filter(divisao=divisao_selecionada)
            .select_related("exercicio", "variacao")
            .order_by("ordem")
        )
    else:
        # Cenário 2/3: modo "Todos" ou treino sem divisões.
        # Main: somente exercícios que possuem divisão (evita duplicar a
        # seção "Sem divisão").
        exercicios_treino = (
            treino.exercicios
            .filter(divisao__isnull=False)
            .select_related("exercicio", "variacao")
            .order_by("ordem")
        )

    # Exercícios sem divisão. Carregados independentemente de todos os
    # cenários, com divisao__isnull=True. A seção "Sem divisão" no template
    # só renderiza se não estiver vazia.
    exercicios_sem_divisao = (
        treino.exercicios
        .filter(divisao__isnull=True)
        .select_related("exercicio", "variacao")
        .order_by("ordem")
    )

    return render(
        request,
        "core/treino_publico.html",
        {
            "treino": treino,
            "link": request.build_absolute_uri(treino.get_link()),
            "divisoes": divisoes,
            "divisao_selecionada": divisao_selecionada,
            "exercicios_treino": exercicios_treino,
            "exercicios_sem_divisao": exercicios_sem_divisao,
        },
    )


# =====================
# CRIAR VIEW JSON
# =====================


def buscar_variacoes(request, exercicio_id):
    variacoes = []

    for v in VariacaoExercicio.objects.filter(exercicio_id=exercicio_id):
        # Usa .url (gerado pelo storage, ex: Cloudinary ou FileSystemStorage)
        # em vez de .name. .name retorna caminho do banco (não é URL).
        # Se o campo não possui arquivo associado, retorna string vazia.
        gif_url = ""
        if v.gif:
            try:
                gif_url = v.gif.url
            except Exception:
                # Fallback: nem toda instância de FileField expõe .url
                # corretamente em todos os backends. Se falhar, retorna
                # string vazia invisível ao navegador.
                gif_url = ""
        variacoes.append(
            {"id": v.id, "nome": v.nome, "gif": gif_url}
        )

    return JsonResponse(variacoes, safe=False)


# ==================
# WEHOOK ASAAS
# ==================

@csrf_exempt
@ratelimit(key='ip', rate='60/m', method='POST', block=True)
def asaas_webhook(request):
    """Recebe eventos de webhook enviados pelo Asaas."""

    if request.method != "POST":
        return HttpResponse(status=405)

    auth_token = os.environ.get("ASAAS_WEBHOOK_TOKEN", "").strip()
    received_token = request.headers.get("asaas-access-token", "").strip()

    if not auth_token or not constant_time_compare(received_token, auth_token):
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    try:
        WebhookHandler.process(payload)
    except ValueError:
        return HttpResponse(status=400)
    except Exception:
        # Erro interno ou banco, retorna 500 para Asaas tentar de novo
        return HttpResponse(status=500)

    return HttpResponse(status=200)


# ==========================
# ASSINATURA ASAAS
# ==========================

@login_required
def criar_assinatura(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Método não permitido."},
            status=405,
        )

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "JSON inválido."},
            status=400,
        )

    plano = payload.get("plano", "").strip().upper()
    billing_type = payload.get("billing_type", "PIX").strip().upper()

    if plano not in {"MENSAL", "ANUAL"}:
        return JsonResponse(
            {"error": "Plano inválido."},
            status=400,
        )

    try:
        service = SubscriptionService()

        assinatura, response = service.create_subscription(
            user=request.user,
            plano=plano,
            billing_type=billing_type,
            next_due_date=(
            timezone.localdate() + timedelta(days=1)
            ).strftime("%Y-%m-%d"),
        )

    except ValueError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=400,
        )

    except Exception:
        return JsonResponse(
            {"error": "Não foi possível criar a assinatura."},
            status=502,
        )

    return JsonResponse(
        {
            "success": True,
            "assinatura_id": assinatura.id,
            "asaas_subscription_id": assinatura.asaas_subscription_id,
            "plano": assinatura.plano,
            "status": assinatura.status,
        },
        status=201,
    )