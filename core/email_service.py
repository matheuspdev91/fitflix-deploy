from django.conf import settings
from django.core.mail import send_mail


def enviar_email_acesso_aluno(
    *, nome, email, reset_url
):
    assunto = "Ative sua conta no FitFlix"
    mensagem = (
        f"Ola, {nome}!\n\n"
        "Seu perfil no FitFlix foi criado.\n"
        "Para ativar sua conta e definir sua senha, clique no link abaixo:\n\n"
        f"{reset_url}\n\n"
        "Se o link expirar, você pode solicitar um novo na página de login.\n"
        "Se precisar de ajuda, entre em contato."
    )

    send_mail(
        subject=assunto,
        message=mensagem,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
