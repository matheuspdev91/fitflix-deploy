"""
Testes do decorator @acesso_profissional_ou_aluno (Missão 03.6.20).

Cobre a matriz de acesso comercial para views compartilhadas entre
PERSONAL e ALUNO:

- PERSONAL com trial ATIVO dentro do prazo: permitido;
- PERSONAL com trial ATIVO vencido: bloqueado;
- PERSONAL com trial ENCERRADO: bloqueado;
- PERSONAL com trial CANCELADO: bloqueado;
- PERSONAL com trial CONVERTIDO: bloqueado;
- PERSONAL com assinatura ACTIVE: permitido;
- PERSONAL com assinatura PENDING: bloqueado;
- PERSONAL sem trial e sem assinatura: bloqueado;
- ALUNO (inclusive cujo profissional não tem assinatura): permitido;
- ADMIN e demais perfis: bloqueado;
- usuário anônimo: redirecionado para login;
- usuário inativo: bloqueado (o Django bloqueia no login; o decorator
  também nega o acesso).

O decorator NÃO é aplicado a nenhuma view nesta etapa: os testes usam
views sintéticas para validar o comportamento isolado.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.utils import timezone

from core.decorators import acesso_profissional_ou_aluno
from core.models import Assinatura, PerfilDeTeste

User = get_user_model()

LAUNCH_AT = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.get_fixed_timezone(0))


def _request_for(user):
    """Cria um request sintético com o usuário informado."""
    return type(
        "Request",
        (),
        {"user": user},
    )()


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
class AcessoProfissionalOuAlunoDecoratorTests(TestCase):
    """Matriz de acesso do decorator misto."""

    def setUp(self):
        self.personal = User.objects.create_user(
            username="personal_misto@example.com",
            email="personal_misto@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            date_joined=timezone.now(),
        )
        self.aluno = User.objects.create_user(
            username="aluno_misto@example.com",
            email="aluno_misto@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            date_joined=timezone.now(),
        )
        self.admin = User.objects.create_user(
            username="admin_misto@example.com",
            email="admin_misto@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
            date_joined=timezone.now(),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _view(self):
        """View sintética que devolve um marcador de execução."""
        return acesso_profissional_ou_aluno(lambda request: "executado")

    def _criar_trial(self, status="ATIVO", expira_em=None, usuario=None):
        usuario = usuario or self.personal
        if expira_em is None:
            expira_em = timezone.now() + timedelta(days=3)
        return PerfilDeTeste.objects.create(
            usuario=usuario,
            status=status,
            iniciado_em=timezone.now() - timedelta(days=1),
            expira_em=expira_em,
        )

    def _criar_assinatura(self, status="ACTIVE", usuario=None):
        usuario = usuario or self.personal
        return Assinatura.objects.create(
            usuario=usuario,
            asaas_subscription_id="sub_misto_{}".format(usuario.pk),
            status=status,
        )

    # ------------------------------------------------------------------
    # PERSONAL — trial
    # ------------------------------------------------------------------

    def test_personal_com_trial_valido_e_permitido(self):
        self._criar_trial()

        resultado = self._view()(_request_for(self.personal))

        self.assertEqual(resultado, "executado")

    def test_personal_com_trial_ativo_mas_vencido_e_bloqueado(self):
        self._criar_trial(expira_em=timezone.now() - timedelta(seconds=1))

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_trial_encerrado_e_bloqueado(self):
        self._criar_trial(status="ENCERRADO")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_trial_cancelado_e_bloqueado(self):
        self._criar_trial(status="CANCELADO")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_trial_convertido_e_bloqueado(self):
        self._criar_trial(status="CONVERTIDO")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    # ------------------------------------------------------------------
    # PERSONAL — assinatura
    # ------------------------------------------------------------------

    def test_personal_com_assinatura_active_e_permitido(self):
        self._criar_assinatura(status="ACTIVE")

        resultado = self._view()(_request_for(self.personal))

        self.assertEqual(resultado, "executado")

    def test_personal_com_assinatura_pending_e_bloqueado(self):
        self._criar_assinatura(status="PENDING")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_assinatura_overdue_e_bloqueado(self):
        self._criar_assinatura(status="OVERDUE")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_assinatura_cancelled_e_bloqueado(self):
        self._criar_assinatura(status="CANCELLED")

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    def test_personal_com_trial_vencido_e_assinatura_active_e_permitido(self):
        self._criar_trial(expira_em=timezone.now() - timedelta(days=1))
        self._criar_assinatura(status="ACTIVE")

        resultado = self._view()(_request_for(self.personal))

        self.assertEqual(resultado, "executado")

    def test_personal_sem_trial_e_sem_assinatura_e_bloqueado(self):
        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    # ------------------------------------------------------------------
    # ALUNO
    # ------------------------------------------------------------------

    def test_aluno_e_permitido_sem_trial_do_profissional(self):
        resultado = self._view()(_request_for(self.aluno))

        self.assertEqual(resultado, "executado")

    def test_aluno_e_permitido_com_profissional_sem_assinatura(self):
        # O profissional do aluno não possui assinatura nem trial.
        self.assertFalse(
            Assinatura.objects.filter(usuario=self.personal).exists()
        )

        resultado = self._view()(_request_for(self.aluno))

        self.assertEqual(resultado, "executado")

    def test_aluno_com_profissional_sem_acesso_comercial_e_permitido(self):
        self._criar_trial(status="ENCERRADO")

        resultado = self._view()(_request_for(self.aluno))

        self.assertEqual(resultado, "executado")

    # ------------------------------------------------------------------
    # ADMIN e outros perfis
    # ------------------------------------------------------------------

    def test_admin_e_bloqueado(self):
        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.admin))

    def test_perfil_desconhecido_e_bloqueado(self):
        usuario = User.objects.create_user(
            username="outro_misto@example.com",
            email="outro_misto@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            date_joined=timezone.now(),
        )
        usuario.tipo_usuario = "OUTRO"
        usuario.save(update_fields=["tipo_usuario"])

        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(usuario))

    # ------------------------------------------------------------------
    # Anônimo e inativo
    # ------------------------------------------------------------------

    def test_usuario_anonimo_redireciona_para_login(self):
        request = type(
            "Request",
            (),
            {
                "user": type(
                    "User",
                    (),
                    {"is_authenticated": False, "tipo_usuario": "PERSONAL"},
                )(),
            },
        )()

        resposta = self._view()(request)

        self.assertIsInstance(resposta, HttpResponseRedirect)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login/", resposta.url)

    def test_usuario_inativo_nao_acessa(self):
        self._criar_trial()
        self.personal.is_active = False
        self.personal.save(update_fields=["is_active"])

        # O Django recusa a sessão de usuário inativo no login; o
        # decorator nega o acesso mesmo que a sessão exista.
        with self.assertRaises(PermissionDenied):
            self._view()(_request_for(self.personal))

    # ------------------------------------------------------------------
    # Comportamento do decorator
    # ------------------------------------------------------------------

    def test_decorator_preserva_metadados_da_view(self):
        def view_original(request):
            return "executado"

        decorada = acesso_profissional_ou_aluno(view_original)

        self.assertEqual(decorada.__name__, "view_original")

    def test_decorator_nao_altera_decorator_existente(self):
        # `precisa_acesso_profissional` continua existindo e com o mesmo
        # comportamento (não removido nesta etapa).
        from core.decorators import precisa_acesso_profissional

        self.assertTrue(callable(precisa_acesso_profissional))
