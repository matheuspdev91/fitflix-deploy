from django.contrib.auth import get_user_model
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings
from django.urls import reverse

from core.decorators import precisa_acesso_profissional
from core.models import Assinatura, PerfilDeTeste
from core.services.perfil_de_teste_service import PerfilDeTesteService

FITFLIX_TRIAL_LAUNCH_AT_FIXED = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.get_fixed_timezone(0))


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=FITFLIX_TRIAL_LAUNCH_AT_FIXED)
class PrecisaAcessoProfissionalDecoratorTests(TestCase):
    """Testes do decorator @precisa_acesso_profissional."""

    def setUp(self):
        self.usuario_personal = get_user_model().objects.create_user(
            username="personal_teste@example.com",
            email="personal_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            date_joined=timezone.now(),
        )
        self.usuario_aluno = get_user_model().objects.create_user(
            username="aluno_teste@example.com",
            email="aluno_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
        )
        self.usuario_admin = get_user_model().objects.create_user(
            username="admin_teste@example.com",
            email="admin_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
        )
        self.service = PerfilDeTesteService()

    def test_nao_autenticado_redireciona_login(self):
        """Acesso não autenticado redireciona para login."""
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {
                "user": type("User", (), {"is_authenticated": False, "tipo_usuario": "PERSONAL"})(),
            },
        )()
        response = view(request)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_nao_personal_lanca_permission_denied(self):
        """Usuário não PERSONAL lança PermissionDenied."""
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {
                "user": self.usuario_aluno,
            },
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_ativo_dentro_do_prazo_permite_acesso(self):
        """Trial ATIVO dentro do prazo permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        # Acesso liberado sem exceção
        resultado = view(request)
        self.assertIsNone(resultado)

    def test_trial_expirado_nao_permita_acesso_sem_assinatura(self):
        """Trial expirado não permite acesso sem assinatura ativa."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self._agora(10),
            expira_em=self._agora(1),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_encerrado_nao_permita_acesso(self):
        """Trial ENCERRADO não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ENCERRADO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_cancelado_nao_permita_acesso(self):
        """Trial CANCELADO não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CANCELADO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_convertido_nao_permita_acesso(self):
        """Trial CONVERTIDO não concede acesso gratuito."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CONVERTIDO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_converteu_apos_expiracao_nao_permita_acesso(self):
        """Trial CONVERTIDO após expiração não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CONVERTIDO",
            iniciado_em=self._agora(10),
            expira_em=self._agora(1),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_assinatura_active_permite_acesso_mesmo_trial_expirado(self):
        """Assinatura ACTIVE permite acesso mesmo com trial expirado."""
        PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self._agora(10),
            expira_em=self._agora(1),
        )
        Assinatura.objects.create(
            usuario=self.usuario_personal,
            asaas_subscription_id="sub_teste",
            plano="MENSAL",
            status="ACTIVE",
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        # Acesso liberado sem exceção
        resultado = view(request)
        self.assertIsNone(resultado)

    def test_aluno_nao_pode_acessar_funcionalidades_comerciais(self):
        """ALUNO não pode acessar funcionalidades comerciais."""
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_aluno},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_admin_nao_pode_acessar_funcionalidades_comerciais(self):
        """ADMIN não pode acessar funcionalidades comerciais."""
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_admin},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_valido_com_status_ativo_por_extenso(self):
        """Trial ATIVO dentro do prazo permite acesso."""
        self.service.iniciar_trial(self.usuario_personal)
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        # Acesso liberado sem exceção
        view(request)
        # Verifica que o trial está ativo
        perfil = PerfilDeTeste.objects.get(usuario=self.usuario_personal)
        self.assertEqual(perfil.status, "ATIVO")

    def test_trial_valido_com_status_convertido_nao_permita(self):
        """Trial CONVERTIDO não concede acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CONVERTIDO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_valido_com_status_encerrado_nao_permita(self):
        """Trial ENCERRADO não concede acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ENCERRADO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_trial_valido_com_status_cancelado_nao_permita(self):
        """Trial CANCELADO não concede acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CANCELADO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_assinatura_inativa_nao_permita_acesso(self):
        """Assinatura inativa (não ACTIVE) não concede acesso."""
        # Trial com status ENCERRADO (não ATIVO), então o trial não
        # concede acesso. A assinatura inativa (não ACTIVE) também não
        # concede acesso.
        PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ENCERRADO",
            iniciado_em=self._agora(2),
            expira_em=self._agora(-6),
        )
        Assinatura.objects.create(
            usuario=self.usuario_personal,
            asaas_subscription_id="sub_inativa",
            plano="MENSAL",
            status="PENDING",
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    def test_personal_com_trial_em_andamento_e_assinatura_active_permite(self):
        """Personal com trial ativo e assinatura ACTIVE permite acesso."""
        self.service.iniciar_trial(self.usuario_personal)
        Assinatura.objects.create(
            usuario=self.usuario_personal,
            asaas_subscription_id="sub_teste",
            plano="MENSAL",
            status="ACTIVE",
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        # Acesso liberado sem exceção
        resultado = view(request)
        self.assertIsNone(resultado)

    def test_trial_valido_mesmo_instante_expiracao_nao_permita(self):
        """Trial exatamente no instante de expiração não permite acesso."""
        agora = self._agora()
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self._agora(10),
            expira_em=agora,
        )
        view = precisa_acesso_profissional(lambda r: None)
        request = type(
            "Request",
            (),
            {"user": self.usuario_personal},
        )()
        with self.assertRaises(PermissionDenied):
            view(request)

    @staticmethod
    def _agora(hours_offset=0):
        from datetime import timedelta

        from django.utils import timezone

        return timezone.now() - timedelta(hours=hours_offset)
