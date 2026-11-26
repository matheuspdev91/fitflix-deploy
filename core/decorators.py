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

        from core.services.perfil_de_teste_service import PerfilDeTesteService

        service = PerfilDeTesteService()

        if service.tem_acesso_trial(user):
            return view_func(request, *args, **kwargs)

        # Verifica assinatura ativa como segunda via de acesso.
        from core.models import Assinatura

        if Assinatura.objects.filter(usuario=user, status="ACTIVE").exists():
            return view_func(request, *args, **kwargs)

        # Nenhum dos critérios foi satisfeito: acesso negado.
        raise PermissionDenied

    return wrapper
