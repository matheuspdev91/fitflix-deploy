"""
Testes de controle de acesso do painel do aluno (core.views.painel_aluno).

Regras cobertas:
- PERSONAL acessa o painel de aluno vinculado ao próprio profissional;
- PERSONAL nao acessa o painel de aluno de outro profissional;
- ALUNO acessa somente o proprio painel;
- ALUNO nao acessa o painel de outro aluno;
- ADMIN nao recebe acesso implicito;
- a navegacao do template do profissional aponta para a rota correta.

O painel do aluno nao depende do trial nem da assinatura: o gate comercial
nao faz parte deste escopo.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Aluno, Treino


class PainelAlunoAccessControlTests(TestCase):
    """Controle de acesso e isolamento do painel do aluno."""

    def setUp(self):
        User = get_user_model()

        self.personal_a = User.objects.create_user(
            username="personal-a-painel@example.com",
            email="personal-a-painel@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            is_active=True,
        )

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

    # 4. ALUNO nao acessa o painel de outro aluno.
    def test_aluno_nao_acessa_painel_de_outro_aluno(self):
        self.client.force_login(self.aluno_a_user)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_b.id])
        )

        self.assertEqual(response.status_code, 404)

    # 5. ADMIN nao recebe acesso implicito.
    def test_admin_nao_acessa_painel(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("core:painel_aluno", args=[self.aluno_a.id])
        )

        self.assertEqual(response.status_code, 404)

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
