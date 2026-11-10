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
