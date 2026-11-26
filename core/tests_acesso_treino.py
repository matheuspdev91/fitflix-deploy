from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Assinatura, PerfilDeTeste, Treino, Aluno
from core.services.perfil_de_teste_service import PerfilDeTesteService
from core.views import treino_detail

FITFLIX_TRIAL_LAUNCH_AT_FIXED = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.get_fixed_timezone(0))


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=FITFLIX_TRIAL_LAUNCH_AT_FIXED)
class TreinoDetailAccessControlTests(TestCase):
    """Testes de controle de acesso para treino_detail."""

    def _logar(self, user):
        self.client.force_login(user)

    def _cria_usuarios_e_treinos(self):
        User = get_user_model()
        # Personal A
        self.personal_a = User.objects.create_user(
            username="personal-a@example.com",
            email="personal-a@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
            date_joined=timezone.now(),
        )
        # Personal B
        self.personal_b = User.objects.create_user(
            username="personal-b@example.com",
            email="personal-b@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
            date_joined=timezone.now(),
        )
        # Aluno A
        self.aluno_a_user = User.objects.create_user(
            username="aluno-a@example.com",
            email="aluno-a@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            is_active=True,
        )
        self.aluno_a = Aluno.objects.create(
            personal=self.personal_a,
            user=self.aluno_a_user,
            nome="Aluno A",
            data_nascimento="2000-01-01",
        )
        # Aluno B
        self.aluno_b_user = User.objects.create_user(
            username="aluno-b@example.com",
            email="aluno-b@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            is_active=True,
        )
        self.aluno_b = Aluno.objects.create(
            personal=self.personal_b,
            user=self.aluno_b_user,
            nome="Aluno B",
            data_nascimento="2000-01-01",
        )

        # Treinos
        self.treino_owns = Treino.objects.create(
            aluno=self.aluno_a, nome="Treino Próprio", descricao=""
        )
        self.treino_other_personal = Treino.objects.create(
            aluno=self.aluno_b, nome="Treino de outro personal", descricao=""
        )
        self.treino_outro_aluno = Treino.objects.create(
            aluno=self.aluno_b, nome="Treino de outro aluno", descricao=""
        )

    def setUp(self):
        self.now = timezone.now()
        self._cria_usuarios_e_treinos()

    def test_personal_trial_valido_acessa_own_treino(self):
        PerfilDeTesteService().iniciar_trial(self.personal_a)
        self._logar(self.personal_a)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 200)

    def test_personal_assinatura_active_acessa_own_treino(self):
        Assinatura.objects.create(
            usuario=self.personal_a,
            asaas_subscription_id="sub-1",
            plano="MENSAL",
            status="ACTIVE",
        )
        self._logar(self.personal_a)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 200)

    def test_personal_trial_expirado_sem_assinatura_nao_acessa(self):
        PerfilDeTesteService().iniciar_trial(self.personal_a)
        perfil = PerfilDeTeste.objects.get(usuario=self.personal_a)
        perfil.expira_em = self.now - timedelta(hours=1)
        perfil.save(update_fields=["expira_em"])

        self._logar(self.personal_a)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 403)

    def test_personal_trial_expirado_com_assinatura_active_acessa(self):
        PerfilDeTesteService().iniciar_trial(self.personal_a)
        perfil = PerfilDeTeste.objects.get(usuario=self.personal_a)
        perfil.expira_em = self.now - timedelta(hours=1)
        perfil.save(update_fields=["expira_em"])

        Assinatura.objects.create(
            usuario=self.personal_a,
            asaas_subscription_id="sub-2",
            plano="MENSAL",
            status="ACTIVE",
        )
        self._logar(self.personal_a)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 200)

    def test_personal_nao_acessa_treino_de_outro_profissional(self):
        PerfilDeTesteService().iniciar_trial(self.personal_a)
        self._logar(self.personal_a)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_other_personal.id]))
        self.assertEqual(response.status_code, 404)

    def test_aluno_acessa_proprio_treino_mesmo_sem_assinatura(self):
        self._logar(self.aluno_a_user)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 200)

    def test_aluno_acessa_proprio_treino_mesmo_trial_profissional_expirado(self):
        perfil = PerfilDeTesteService().iniciar_trial(self.personal_a)
        perfil.expira_em = self.now - timedelta(hours=1)
        perfil.save(update_fields=["expira_em"])

        self._logar(self.aluno_a_user)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 200)

    def test_aluno_nao_acessa_treino_de_outro_aluno(self):
        # Aluno A tenta acessar o treino de Aluno B -> deve retornar 404.
        self._logar(self.aluno_a_user)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_outro_aluno.id]))
        self.assertEqual(response.status_code, 404)

    def test_usuario_nao_autenticado_redireciona_para_login(self):
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_admin_nao_recebe_acesso(self):
        admin = get_user_model().objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
            is_active=True,
        )
        self._logar(admin)
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_owns.id]))
        self.assertEqual(response.status_code, 404)
