from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect


def apenas_personal(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("core:login")

        if request.user.tipo_usuario != "PERSONAL":
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


def apenas_aluno(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("core:login")
        if request.user.tipo_usuario != "ALUNO":
            raise Http404
        return view_func(request, *args, **kwargs)

    return wrapper


def _profissional_tem_acesso_comercial(user):
    """
    Regra única de acesso comercial do profissional (PERSONAL).

    O acesso é liberado quando:
    - possui PerfilDeTeste com status ATIVO e prazo ainda válido; OU
    - possui Assinatura com status ACTIVE.

    Fonte de verdade:
    - trial: PerfilDeTesteService.tem_acesso_trial(usuario);
    - assinatura: Assinatura.objects.filter(usuario=..., status="ACTIVE").

    Retorna True quando há acesso pago ou gratuito válido.
    """
    from core.services.perfil_de_teste_service import PerfilDeTesteService

    service = PerfilDeTesteService()

    if service.tem_acesso_trial(user):
        return True

    # Verifica assinatura ativa como segunda via de acesso.
    from core.models import Assinatura

    return Assinatura.objects.filter(
        usuario=user,
        status="ACTIVE",
    ).exists()


def precisa_acesso_profissional(view_func):
    """
    Decorator de acesso centralizado para funcionalidades comerciais.

    O acesso do profissional (PERSONAL) é permitido quando:
    - Possui PerfilDeTeste com status ATIVO e prazo ainda válido; OU
    - Possui Assinatura com status ACTIVE.

    Regras de validação:
    - Exige usuário autenticado;
    - Exige tipo_usuario == PERSONAL;
    - Consulta PerfilDeTesteService.tem_acesso_trial(usuario);
    - Consulta assinatura ativa do profissional;
    - Libera o acesso quando pelo menos uma condição for verdadeira;
    - Nega o acesso quando nenhuma condição for satisfeita.

    Comportamento:
    - Usuário não autenticado: redireciona para login;
    - Usuário não PERSONAL: PermissionDenied;
    - Sem trial válido e sem assinatura ACTIVE: PermissionDenied.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect("core:login")

        if getattr(user, "tipo_usuario", None) != "PERSONAL":
            raise PermissionDenied

        if _profissional_tem_acesso_comercial(user):
            return view_func(request, *args, **kwargs)

        # Nenhum dos critérios foi satisfeito: acesso negado.
        raise PermissionDenied

    return wrapper


def acesso_profissional_ou_aluno(view_func):
    """
    Decorator de acesso para views compartilhadas entre PERSONAL e ALUNO.

    PERSONAL:
    - trial ATIVO dentro do prazo: permitido;
    - assinatura ACTIVE: permitido;
    - trial vencido, ENCERRADO ou CANCELADO sem assinatura ACTIVE:
      bloqueado;
    - assinatura PENDING: bloqueado.

    ALUNO:
    - sempre passa pelo decorator; o acesso NÃO depende do trial nem da
      assinatura do profissional. A view protegida continua responsável
      por validar a propriedade do aluno e do treino.

    Comportamento:
    - Usuário não autenticado: redireciona para login;
    - ADMIN e demais perfis: PermissionDenied;
    - PERSONAL sem acesso comercial: PermissionDenied.

    A regra comercial do profissional é compartilhada com
    `precisa_acesso_profissional` via `_profissional_tem_acesso_comercial`,
    evitando duplicação.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return redirect("core:login")

        # Conta desativada não mantém acesso, ainda que uma sessão
        # antiga exista no banco.
        if not getattr(user, "is_active", True):
            raise PermissionDenied

        tipo_usuario = getattr(user, "tipo_usuario", None)

        if tipo_usuario == "ALUNO":
            return view_func(request, *args, **kwargs)

        if tipo_usuario == "PERSONAL":
            if _profissional_tem_acesso_comercial(user):
                return view_func(request, *args, **kwargs)

            raise PermissionDenied

        # ADMIN e demais perfis não recebem acesso implícito.
        raise PermissionDenied

    return wrapper
