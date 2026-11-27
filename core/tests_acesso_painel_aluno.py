"""
Testes de controle de acesso do painel do aluno (core.views.painel_aluno).

Regras cobertas:
- PERSONAL acessa o painel de aluno vinculado ao próprio profissional;
- PERSONAL nao acessa o painel de aluno de outro profissional;
- ALUNO acessa somente o proprio painel;
- ALUNO nao acessa o painel de outro aluno;
- ADMIN nao recebe acesso implicito;
- a navegacao do template do profissional aponta para a rota correta.

O acesso do painel do aluno é controlado pelo decorator
@acesso_profissional_ou_aluno: PERSONAL só acessa se tiver trial ATIVO
dentro do prazo ou assinatura ACTIVE; ALUNO sempre passa. O isolamento de
propriedade (quem pode ver qual painel) é validado pela view.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Aluno, Treino, Assinatura, PerfilDeTeste
from core.services.perfil_de_teste_service import PerfilDeTesteService

LAUNCH_AT = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.get_fixed_timezone(0))


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
class PainelAlunoAccessControlTests(TestCase):
    """Controle de acesso e isolamento do painel do aluno."""

    def setUp(self):
        User = get_user_model()

        self.service = PerfilDeTesteService()
        self.personal_a = User.objects.create_user(
            username="personal-a-painel@example.com",
            email="personal-a-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )
        self.service.iniciar_trial(self.personal_a)

        self.personal_b = User.objects.create_user(
            username="personal-b-painel@example.com",
            email="personal-b-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )

        self.admin = User.objects.create_user(
            username="admin-painel@example.com",
            email="admin-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
            is_active=True,
        )

        self.aluno_a_user = User.objects.create_user(
            username="aluno-a-painel@example.com",
            email="aluno-a-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            is_active=True,
        )

        self.aluno_b_user = User.objects.create_user(
            username="aluno-b-painel@example.com",
            email="aluno-b-painel@example.com",
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

        self.aluno_b = Aluno.objects.create(
            personal=self.personal_b,
            user=self.aluno_b_user,
            nome="Aluno B",
            data_nascimento="2000-01-01",
        )

        self.treino_a = Treino.objects.create(
            aluno=self.aluno_a,
            nome="Treino do Aluno A",
            descricao="",
        )

    # 1. PERSONAL acessa painel de aluno proprio.
    def test_personal_acessa_painel_de_aluno_proprio(self):
        self.client.force_login(self.personal_a)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_a.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluno A")
        self.assertEqual(response.context["aluno"].id, self.aluno_a.id)
        self.assertIn(
            self.treino_a,
            list(response.context["treinos"]),
        )

    # 2. PERSONAL nao acessa painel de aluno de outro profissional.
    def test_personal_nao_acessa_painel_de_aluno_de_outro_profissional(self):
        self.client.force_login(self.personal_a)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_b.id])
        )

        self.assertEqual(response.status_code, 404)

    # 3. ALUNO acessa o proprio painel.
    def test_aluno_acessa_proprio_painel(self):
        self.client.force_login(self.aluno_a_user)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_a.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["aluno"].id, self.aluno_a.id)

    # 3b. ALUNO acessa o proprio painel ainda que o personal nao tenha
    # acesso comercial (trial vencido, encerrado ou assinatura nao ACTIVE).
    def test_aluno_acessa_proprio_painel_sem_acesso_comercial_personal(self):
        # personal_a sem trial, sem assinatura -> sem acesso comercial.
        PerfilDeTeste.objects.filter(usuario=self.personal_a).delete()
        Assinatura.objects.filter(usuario=self.personal_a).delete()

        self.client.force_login(self.aluno_a_user)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_a.id])
        )

        # O painel do aluno permanece acessivel: a regra comercial nao bloqueia
        # o acesso do aluno ao proprio painel.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["aluno"].id, self.aluno_a.id)

    # 4. ALUNO nao acessa o painel de outro aluno.
    def test_aluno_nao_acessa_painel_de_outro_aluno(self):
        self.client.force_login(self.aluno_a_user)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_b.id])
        )

        self.assertEqual(response.status_code, 404)

    # 5. ADMIN nao recebe acesso implicito (decorator retorna 403).
    def test_admin_nao_acessa_painel(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("core:painel_aluno", args=[self.aluno_a.id]))

        self.assertEqual(response.status_code, 403)

    # Complemento: usuario nao autenticado e redirecionado ao login.
    def test_usuario_nao_autenticado_redireciona_para_login(self):
        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_a.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    # Complemento: aluno sem personal vinculado nao acessa o proprio painel.
    def test_aluno_sem_personal_nao_acessa_proprio_painel(self):
        sem_personal = get_user_model().objects.create_user(
            username="sem-personal-painel@example.com",
            email="sem-personal-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            is_active=True,
        )
        aluno = Aluno.objects.create(
            personal=None,
            user=sem_personal,
            nome="Sem Personal",
            data_nascimento="2000-01-01",
        )
        self.client.force_login(sem_personal)

        response = self.client.get(
            reverse("core:painel_aluno", args=[aluno.id])
        )

        self.assertEqual(response.status_code, 404)

    # 6. A navegacao do template do profissional aponta para a rota correta.
    def test_navegacao_do_profissional_aponta_para_painel_do_aluno(self):
        self.client.force_login(self.personal_a)

        response = self.client.get(reverse("core:fitflix"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("core:painel_aluno", args=[self.aluno_a.id]),
        )
        # O link do painel do aluno próprio não pode levar a um 403.
        self.assertNotContains(
            response,
            reverse("core:painel_aluno", args=[self.aluno_b.id]),
        )

    # PERSONAL — acesso comercial no painel (sem trial, apenas assinatura ACTIVE)
    def test_personal_com_assinatura_active_sem_trial_acessa_painel(self):
        User = get_user_model()
        personal_ativo = User.objects.create_user(
            username="personal-assinatura@example.com",
            email="personal-assinatura@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )
        aluno_assinatura = Aluno.objects.create(
            personal=personal_ativo,
            user=User.objects.create_user(
                username="aluno-assinatura@example.com",
                email="aluno-assinatura@example.com",
                password="SenhaTeste123",
                tipo_usuario="ALUNO",
                is_active=True,
            ),
            nome="Aluno Assinatura",
            data_nascimento="2000-01-01",
        )
        Assinatura.objects.create(
            usuario=personal_ativo,
            asaas_subscription_id="sub-painel-1",
            plano="MENSAL",
            status="ACTIVE",
        )
        self.client.force_login(personal_ativo)

        resposta = self.client.get(reverse("core:painel_aluno", args=[aluno_assinatura.id]))

        self.assertEqual(resposta.status_code, 200)

    # PERSONAL — sem trial e sem assinatura -> bloqueado
    def test_personal_sem_trial_e_sem_assinatura_nao_acessa_painel(self):
        User = get_user_model()
        personal_sem_acesso = User.objects.create_user(
            username="personal-sem-acesso@example.com",
            email="personal-sem-acesso@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )
        self.client.force_login(personal_sem_acesso)

        resposta = self.client.get(reverse("core:painel_aluno", args=[self.aluno_a.id]))

        self.assertEqual(resposta.status_code, 403)

    # PERSONAL — trial vencido -> bloqueado
    def test_personal_trial_expirado_nao_acessa_painel(self):
        perfil = PerfilDeTeste.objects.get(usuario=self.personal_a)
        perfil.expira_em = timezone.now() - timedelta(seconds=1)
        perfil.save(update_fields=["expira_em"])

        self.client.force_login(self.personal_a)

        resposta = self.client.get(reverse("core:painel_aluno", args=[self.aluno_a.id]))

        self.assertEqual(resposta.status_code, 403)

    # PERSONAL — assinatura PENDING sem trial -> bloqueado
    def test_personal_assinatura_pending_sem_trial_nao_acessa_painel(self):
        User = get_user_model()
        personal_pending = User.objects.create_user(
            username="personal-pending@example.com",
            email="personal-pending@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )
        Assinatura.objects.create(
            usuario=personal_pending,
            asaas_subscription_id="sub-painel-pending",
            plano="MENSAL",
            status="PENDING",
        )
        self.client.force_login(personal_pending)

        resposta = self.client.get(reverse("core:painel_aluno", args=[self.aluno_a.id]))

        self.assertEqual(resposta.status_code, 403)
