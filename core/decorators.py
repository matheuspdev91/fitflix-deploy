from functools import wraps
from django.shortcuts import redirect


def apenas_personal(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("core:login")

        if hasattr(request.user, "aluno"):
            return redirect("core:painel_aluno", aluno_id=request.user.aluno.id)

        return view_func(request, *args, **kwargs)

    return wrapper
