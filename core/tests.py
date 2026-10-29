from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .forms import CriarAlunoForm
from .models import Aluno, AvaliacaoFisica, Treino
from .views import gerar_senha_aleatoria


class CriarAlunoFormTests(TestCase):
    def test_form_rejeita_email_duplicado(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="duplicado@example.com",
            email="duplicado@example.com",
            password="Senha123",
        )

        form = CriarAlunoForm(
            data={
                "nome": "Aluno Duplicado",
                "email": "duplicado@example.com",
                "telefone": "",
                "data_nascimento": "2000-01-01",
                "objetivo": "",
                "observacoes": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class CriarAlunoViewTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.professor = self.user_model.objects.create_user(
            username="professor@example.com",
            email="professor@example.com",
            password="Senha123",
        )

    def test_view_exige_login(self):
        response = self.client.get(reverse("core:criar_aluno"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    @patch("core.views.enviar_email_acesso_aluno")
    def test_cadastro_valido_cria_usuario_aluno_envia_email_e_redireciona(
        self, mock_enviar_email
    ):
        self.client.force_login(self.professor)

        response = self.client.post(
            reverse("core:criar_aluno"),
            data={
                "nome": "Maria Silva",
                "email": "maria@example.com",
                "telefone": "",
                "data_nascimento": "2001-04-15",
                "objetivo": "",
                "observacoes": "",
            },
        )

        self.assertRedirects(
            response, reverse("core:home"), fetch_redirect_response=False
        )

        usuario = self.user_model.objects.get(email="maria@example.com")
        aluno = Aluno.objects.get(user=usuario)

        self.assertEqual(usuario.username, "maria@example.com")
        self.assertEqual(aluno.nome, "Maria Silva")
        self.assertEqual(aluno.telefone, "")
        self.assertEqual(aluno.objetivo, "")
        self.assertEqual(aluno.observacoes, "")

        mock_enviar_email.assert_called_once()
        self.assertEqual(mock_enviar_email.call_count, 1)
        self.assertEqual(mock_enviar_email.call_args.kwargs["email"], "maria@example.com")
        self.assertEqual(mock_enviar_email.call_args.kwargs["nome"], "Maria Silva")
        self.assertIn("password-reset-confirm", mock_enviar_email.call_args.kwargs["reset_url"])

        mensagens = [message.message for message in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("Aluno cadastrado com sucesso" in mensagem for mensagem in mensagens)
        )

    @patch("core.views.enviar_email_acesso_aluno")
    def test_email_duplicado_nao_cria_aluno(self, mock_enviar_email):
        self.user_model.objects.create_user(
            username="maria@example.com",
            email="maria@example.com",
            password="Senha123",
        )
        self.client.force_login(self.professor)

        response = self.client.post(
            reverse("core:criar_aluno"),
            data={
                "nome": "Maria Silva",
                "email": "maria@example.com",
                "telefone": "",
                "data_nascimento": "2001-04-15",
                "objetivo": "",
                "observacoes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ja existe um usuario cadastrado com este email.")
        self.assertEqual(Aluno.objects.count(), 0)
        mock_enviar_email.assert_not_called()


class AlunoModelTests(TestCase):
    def test_idade_e_calculada_corretamente(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="aluno@example.com",
            email="aluno@example.com",
            password="Senha123",
        )

        hoje = date.today()
        data_nascimento = hoje.replace(year=hoje.year - 20)
        if hoje.month == 1 and hoje.day == 1:
            data_nascimento = date(hoje.year - 20, 12, 31)

        aluno = Aluno.objects.create(
            user=user,
            nome="Aluno Teste",
            data_nascimento=data_nascimento,
        )

        idade_esperada = (
            hoje.year
            - data_nascimento.year
            - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
        )
        self.assertEqual(aluno.idade, idade_esperada)


class SenhaAleatoriaTests(TestCase):
    def test_senha_gerada_tem_o_formato_esperado(self):
        senha = gerar_senha_aleatoria()
        self.assertRegex(senha, r"^[A-Za-z0-9]{8}$")


class IsolamentoMultiTenantTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.personal_a = self.user_model.objects.create_user(
            username="personal-a@example.com",
            email="personal-a@example.com",
            password="Senha123",
        )
        self.personal_b = self.user_model.objects.create_user(
            username="personal-b@example.com",
            email="personal-b@example.com",
            password="Senha123",
        )

        self.avaliacao_b = AvaliacaoFisica.objects.create(
            usuario=self.personal_b,
            nome="Aluno B",
            sexo="M",
            data_nascimento="2000-01-01",
            altura="1.80",
            peso="80.00",
        )

        self.aluno_b_user = self.user_model.objects.create_user(
            username="aluno-b@example.com",
            email="aluno-b@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno_b = Aluno.objects.create(
            personal=self.personal_b,
            user=self.aluno_b_user,
            nome="Aluno B",
            data_nascimento="2000-01-01",
        )
        self.treino_b = Treino.objects.create(
            aluno=self.aluno_b,
            nome="Treino B",
            descricao="",
        )

    def test_avaliacao_de_outro_usuario_retorna_404(self):
        self.client.force_login(self.personal_a)

        urls = [
            reverse("core:detalhe_avaliacao", args=[self.avaliacao_b.id]),
            reverse("core:dashboard", args=[self.avaliacao_b.id]),
            reverse("core:editar_avaliacao", args=[self.avaliacao_b.id]),
            reverse("core:excluir_avaliacao", args=[self.avaliacao_b.id]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_treino_de_outro_personal_retorna_404(self):
        self.client.force_login(self.personal_a)

        urls = [
            reverse("core:treino_detail", args=[self.treino_b.id]),
            reverse("core:editar_treino", args=[self.treino_b.id]),
            reverse("core:adicionar_exercicio", args=[self.treino_b.id]),
            reverse("core:painel_aluno", args=[self.aluno_b.id]),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_form_treino_lista_apenas_alunos_do_personal_logado(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a@example.com",
            email="aluno-a@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        aluno_a = Aluno.objects.create(
            personal=self.personal_a,
            user=aluno_a_user,
            nome="Aluno A",
            data_nascimento="2000-01-01",
        )

        self.client.force_login(self.personal_a)
        response = self.client.get(reverse("core:criar_treino"))

        alunos = response.context["form"].fields["aluno"].queryset
        self.assertIn(aluno_a, alunos)
        self.assertNotIn(self.aluno_b, alunos)
