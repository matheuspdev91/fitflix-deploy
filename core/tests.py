from datetime import datetime, date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import CriarAlunoForm, DivisaoTreinoForm
from .models import (
    Aluno,
    AvaliacaoFisica,
    ExercicioTreino,
    GrupoMuscular,
    Treino,
    VariacaoExercicio,
    VideoExercicio,
    DivisaoTreino,
)
from .services.perfil_de_teste_service import PerfilDeTesteService
from .views import gerar_senha_aleatoria

FITFLIX_TRIAL_LAUNCH_AT_FIXED = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.get_fixed_timezone(0))


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


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=FITFLIX_TRIAL_LAUNCH_AT_FIXED)
class IsolamentoMultiTenantTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.personal_a = self.user_model.objects.create_user(
            username="personal-a@example.com",
            email="personal-a@example.com",
            password="Senha123",
            date_joined=timezone.now(),
        )
        from core.services.perfil_de_teste_service import PerfilDeTesteService
        PerfilDeTesteService().iniciar_trial(self.personal_a)
        self.personal_b = self.user_model.objects.create_user(
            username="personal-b@example.com",
            email="personal-b@example.com",
            password="Senha123",
            date_joined=timezone.now(),
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

        self.aluno_c_user = self.user_model.objects.create_user(
            username="aluno-c@example.com",
            email="aluno-c@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno_c = Aluno.objects.create(
            personal=self.personal_b,
            user=self.aluno_c_user,
            nome="Aluno C",
            data_nascimento="2000-01-01",
        )
        self.treino_c = Treino.objects.create(
            aluno=self.aluno_c,
            nome="Treino C",
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
                if url == reverse("core:excluir_avaliacao", args=[self.avaliacao_b.id]):
                    response = self.client.post(url)
                else:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

    def test_treino_de_outro_personal_retorna_404(self):
            # Personal com trial válido, sem assinatura ACTIVE: 404 em treino_detail.
            self.client.force_login(self.personal_a)
            response = self.client.get(reverse("core:treino_detail", args=[self.treino_b.id]))
            self.assertEqual(response.status_code, 404)

            # Outras rotas mantêm a proteção de 404 (editar_treino, adicionar_exercicio, painel_aluno).
            self.client.force_login(self.personal_a)
            urls = [
                reverse("core:editar_treino", args=[self.treino_b.id]),
                reverse("core:adicionar_exercicio", args=[self.treino_b.id]),
                reverse("core:painel_aluno", args=[self.aluno_b.id]),
            ]
            for url in urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 404)

            # ALUNO: acesso ao PRÓPRIO treino depende da regra comercial do personal.
            # Personal B não tem trial válido nem assinatura ACTIVE -> 403.
            self.client.force_login(self.aluno_b_user)
            response = self.client.get(reverse("core:treino_detail", args=[self.treino_b.id]))
            self.assertEqual(response.status_code, 403)

            # ALUNO: acesso a treino de OUTRO aluno (mesmo personal) é bloqueado com 404.
            self.client.force_login(self.aluno_b_user)
            response = self.client.get(reverse("core:treino_detail", args=[self.treino_c.id]))
            self.assertEqual(response.status_code, 404)

    def test_personal_com_trial_acessa_proprio_treino(self):
            # Personal com trial válido, sem assinatura ACTIVE: acesso ao PROPRIO treino permitido.
            # personal_a já tem trial do setUp()
            self.client.force_login(self.personal_a)

            aluno_user = self.user_model.objects.create_user(
                username="aluno-proprio@example.com",
                email="aluno-proprio@example.com",
                password="Senha123",
                tipo_usuario="ALUNO",
            )
            aluno = Aluno.objects.create(
                personal=self.personal_a,
                user=aluno_user,
                nome="Aluno Proprio",
                data_nascimento="2000-01-01",
            )
            treino_proprio = Treino.objects.create(
                aluno=aluno,
                nome="Treino Proprio",
                descricao="",
            )

            response = self.client.get(reverse("core:treino_detail", args=[treino_proprio.id]))
            self.assertEqual(response.status_code, 200)

    def test_personal_com_assinatura_ativa_acessa_proprio_treino(self):
        # Personal com assinatura ACTIVE: acesso ao PROPRIO treino permitido.
        self.client.force_login(self.personal_a)
        from core.models import Assinatura

        Assinatura.objects.create(
            usuario=self.personal_a,
            status="ACTIVE",
            plano="MENSAL",
        )
        aluno_user = self.user_model.objects.create_user(
            username="aluno-proprio-ativa@example.com",
            email="aluno-proprio-ativa@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        aluno = Aluno.objects.create(
            personal=self.personal_a,
            user=aluno_user,
            nome="Aluno Proprio Ativa",
            data_nascimento="2000-01-01",
        )
        treino = Treino.objects.create(
            aluno=aluno,
            nome="Treino Proprio Ativa",
            descricao="",
        )
        response = self.client.get(reverse("core:treino_detail", args=[treino.id]))
        self.assertEqual(response.status_code, 200)

    def test_personal_com_assinatura_ativa_nao_acessa_treino_outro(self):
        # Personal com assinatura ACTIVE: protege o acesso ao treino de
        # outro profissional (consulta de propriedade, não só o trial).
        self.client.force_login(self.personal_a)
        from core.models import Assinatura

        Assinatura.objects.create(
            usuario=self.personal_a,
            status="ACTIVE",
            plano="MENSAL",
        )
        response = self.client.get(reverse("core:treino_detail", args=[self.treino_b.id]))
        self.assertEqual(response.status_code, 404)

    def test_personal_sem_trial_assinatura_nao_acessa_treino_outro(self):
            # Personal sem trial/assinatura: 403 em treino_detail.
            user_model = get_user_model()
            personal_sem_acesso = user_model.objects.create_user(
                username="personal-sem-acesso-treino@example.com",
                email="personal-sem-acesso-treino@example.com",
                password="Senha123",
                date_joined=timezone.now(),
            )
            self.client.force_login(personal_sem_acesso)

            response = self.client.get(
                reverse("core:treino_detail", args=[self.treino_b.id])
            )

            self.assertEqual(response.status_code, 403)

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

    def test_painel_fitflix_lista_apenas_alunos_do_personal_logado(self):
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

        response = self.client.get(reverse("core:fitflix"))

        self.assertEqual(response.status_code, 200)
        alunos = response.context["alunos"]
        self.assertIn(aluno_a, alunos)
        self.assertNotIn(self.aluno_b, alunos)
        self.assertContains(response, "Aluno A")
        self.assertNotContains(response, "Aluno B")

    def test_aluno_nao_acessa_rotas_exclusivas_de_personal(self):
        self.client.force_login(self.aluno_b_user)

        for name in ("criar_aluno", "criar_treino", "criar_exercicio"):
            with self.subTest(name=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 403)

    def test_post_idor_nao_edita_treino_de_outro_personal(self):
        self.client.force_login(self.personal_a)

        response = self.client.post(
            reverse("core:editar_treino", args=[self.treino_b.id]),
            data={"nome": "Alterado", "descricao": "Alterado"},
        )

        self.assertEqual(response.status_code, 404)
        self.treino_b.refresh_from_db()
        self.assertEqual(self.treino_b.nome, "Treino B")

    def test_get_nao_exclui_avaliacao(self):
            from core.services.perfil_de_teste_service import PerfilDeTesteService
            PerfilDeTesteService().iniciar_trial(self.personal_b)
            self.client.force_login(self.personal_b)

            response = self.client.get(
                reverse("core:excluir_avaliacao", args=[self.avaliacao_b.id])
            )

            self.assertEqual(response.status_code, 405)
            self.assertTrue(AvaliacaoFisica.objects.filter(pk=self.avaliacao_b.pk).exists())

    def test_token_inexistente_nao_revela_treino(self):
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:ver_treino", args=["00000000-0000-0000-0000-000000000000"])
        )

        self.assertEqual(response.status_code, 404)

    def test_probe_force_login_authenticates(self):
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        resp = response.wsgi_request
        print("PROBE_STATUS:", response.status_code)
        print("PROBE_URL:", response.url)
        print("PROBE_USER_IS_AUTHENTICATED:", resp.user.is_authenticated)
        print("PROBE_USER_ID:", getattr(resp.user, "id", None))
        print("PROBE_USER_IS_PERSONAL:", getattr(resp.user, "tipo_usuario", None))
        print("PROBE_SESSION:", dict(self.client.session.items()))

    def test_aluno_nao_acessa_painel_de_outro_aluno(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a@example.com", email="aluno-a@example.com",
            password="Senha123", tipo_usuario="ALUNO",
        )
        Aluno.objects.create(
            personal=self.personal_a, user=aluno_a_user, nome="Aluno A",
            data_nascimento="2000-01-01",
        )
        self.client.force_login(aluno_a_user)

        response = self.client.get(reverse("core:painel_aluno", args=[self.aluno_b.id]))

        self.assertEqual(response.status_code, 404)

    def test_aluno_nao_acessa_treino_de_outro_aluno(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a@example.com", email="aluno-a@example.com",
            password="Senha123", tipo_usuario="ALUNO",
        )
        Aluno.objects.create(
            personal=self.personal_a, user=aluno_a_user, nome="Aluno A",
            data_nascimento="2000-01-01",
        )
        self.client.force_login(aluno_a_user)

        response = self.client.get(reverse("core:treino_detail", args=[self.treino_b.id]))

        self.assertEqual(response.status_code, 404)

    def test_aluno_nao_acessa_operacoes_de_avaliacao(self):
        self.client.force_login(self.aluno_b_user)
        get_names = (
            "avaliacoes", "escolher_tipo", "criar_avaliacao",
            "criar_avaliacao_idoso", "criar_avaliacao_crianca",
            "detalhe_avaliacao", "dashboard", "editar_avaliacao",
        )
        for name in get_names:
            args = [self.avaliacao_b.id] if name in {
                "detalhe_avaliacao", "dashboard", "editar_avaliacao"
            } else []
            with self.subTest(name=name):
                response = self.client.get(reverse(f"core:{name}", args=args))
                self.assertEqual(response.status_code, 403)

    def test_aluno_nao_cria_avaliacao_por_post(self):
        self.client.force_login(self.aluno_b_user)

        response = self.client.post(reverse("core:criar_avaliacao"), data={})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(AvaliacaoFisica.objects.filter(usuario=self.aluno_b_user).exists())

    def test_aluno_nao_edita_ou_exclui_avaliacao_por_post(self):
        avaliacao = AvaliacaoFisica.objects.create(
            usuario=self.aluno_b_user, nome="Avaliação aluno", sexo="M",
            data_nascimento="2000-01-01", altura="1.80", peso="80.00",
        )
        self.client.force_login(self.aluno_b_user)

        edit_response = self.client.post(
            reverse("core:editar_avaliacao", args=[avaliacao.id]),
            data={"nome": "Alterado", "sexo": "M", "data_nascimento": "2000-01-01",
                  "altura": "1.80", "peso": "80.00"},
        )
        delete_response = self.client.post(
            reverse("core:excluir_avaliacao", args=[avaliacao.id])
        )

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        avaliacao.refresh_from_db()
        self.assertEqual(avaliacao.nome, "Avaliação aluno")
        self.assertTrue(AvaliacaoFisica.objects.filter(pk=avaliacao.pk).exists())

    def test_personal_nao_cria_treino_com_aluno_de_outro_personal(self):
        self.client.force_login(self.personal_a)

        response = self.client.post(
            reverse("core:criar_treino"),
            data={"nome": "Treino inválido", "aluno": self.aluno_b.id,
                  "nome_aluno": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Treino.objects.filter(nome="Treino inválido").exists())

    def test_personal_nao_adiciona_variacao_de_outro_exercicio(self):
        grupo = GrupoMuscular.objects.create(nome="Grupo")
        exercicio_a = VideoExercicio.objects.create(
            nome="Exercício A", grupo_muscular=grupo, gif="a.gif",
        )
        exercicio_b = VideoExercicio.objects.create(
            nome="Exercício B", grupo_muscular=grupo, gif="b.gif",
        )
        variacao_b = VariacaoExercicio.objects.create(
            exercicio=exercicio_b, nome="Variação B",
        )
        treino_a = Treino.objects.create(aluno=self.aluno_b, nome="Treino A", descricao="")
        self.client.force_login(self.personal_b)

        response = self.client.post(
            reverse("core:adicionar_exercicio", args=[treino_a.id]),
            data={"exercicio": exercicio_a.id, "variacao": variacao_b.id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ExercicioTreino.objects.filter(treino=treino_a).exists())

    def test_aluno_sem_personal_nao_acessa_proprio_painel(self):
        sem_personal = self.user_model.objects.create_user(
            username="sem-personal@example.com", email="sem-personal@example.com",
            password="Senha123", tipo_usuario="ALUNO",
        )
        aluno = Aluno.objects.create(
            personal=None, user=sem_personal, nome="Sem Personal",
            data_nascimento="2000-01-01",
        )
        self.client.force_login(sem_personal)

        response = self.client.get(reverse("core:painel_aluno", args=[aluno.id]))

        self.assertEqual(response.status_code, 404)

    def test_personal_acessa_proprio_aluno_e_treino(self):
        aluno_user = self.user_model.objects.create_user(
            username="aluno-a@example.com", email="aluno-a@example.com",
            password="Senha123", tipo_usuario="ALUNO",
        )
        aluno = Aluno.objects.create(
            personal=self.personal_a, user=aluno_user, nome="Aluno A",
            data_nascimento="2000-01-01",
        )
        treino = Treino.objects.create(aluno=aluno, nome="Treino A", descricao="")
        self.client.force_login(self.personal_a)

        panel_response = self.client.get(reverse("core:fitflix"))
        treino_response = self.client.get(reverse("core:editar_treino", args=[treino.id]))

        self.assertEqual(panel_response.status_code, 200)
        self.assertContains(panel_response, "Aluno A")
        self.assertEqual(treino_response.status_code, 200)

    def test_aluno_nao_acessa_cada_operacao_avaliacao(self):
        self.client.force_login(self.aluno_b_user)
        get_names = (
            "avaliacoes",
            "escolher_tipo",
            "criar_avaliacao",
            "criar_avaliacao_idoso",
            "criar_avaliacao_crianca",
        )
        for name in get_names:
            with self.subTest(operacao=name):
                response = self.client.get(reverse(f"core:{name}"))
                self.assertEqual(response.status_code, 403)

        for name in ("detalhe_avaliacao", "dashboard", "editar_avaliacao"):
            with self.subTest(operacao=name):
                response = self.client.get(
                    reverse(f"core:{name}", args=[self.avaliacao_b.id])
                )
                self.assertEqual(response.status_code, 403)

    def test_aluno_cria_avaliacao_por_post_rejeitada(self):
        self.client.force_login(self.aluno_b_user)
        response = self.client.post(reverse("core:criar_avaliacao"), data={})
        self.assertEqual(response.status_code, 403)

    def test_personal_a_nao_veja_avaliacoes_outra_pessoa_listagem(self):
        self.client.force_login(self.personal_a)
        response = self.client.get(reverse("core:avaliacoes"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.avaliacao_b, response.context["avaliacoes"])

    def test_personal_a_edita_exclui_avaliacao_outra_pessoa(self):
        self.client.force_login(self.personal_a)
        for name in ("editar_avaliacao", "excluir_avaliacao"):
            with self.subTest(operacao=name):
                url = reverse(f"core:{name}", args=[self.avaliacao_b.id])
                if name == "excluir_avaliacao":
                    response = self.client.post(url)
                else:
                    response = self.client.post(url, data={})
                self.assertEqual(response.status_code, 404)
                self.assertTrue(
                    AvaliacaoFisica.objects.filter(pk=self.avaliacao_b.pk).exists()
                )

    def test_personal_a_acessa_avaliacao_proprio_aluno(self):
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
        avaliacao = AvaliacaoFisica.objects.create(
            usuario=self.personal_a,
            aluno=aluno_a,
            nome="Aluno A",
            sexo="M",
            data_nascimento="2000-01-01",
            altura="1.80",
            peso="80.00",
        )
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:detalhe_avaliacao", args=[avaliacao.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aluno A")

    def test_personal_acessando_avaliacao_legada_sem_aluno_criador(self):
        avaliacao = AvaliacaoFisica.objects.create(
            usuario=self.personal_a,
            aluno=None,
            nome="Legado",
            sexo="M",
            data_nascimento="2000-01-01",
            altura="1.80",
            peso="80.00",
        )
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:detalhe_avaliacao", args=[avaliacao.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_personal_nao_acessa_avaliacao_legada_outra_pessoa(self):
        avaliacao = AvaliacaoFisica.objects.create(
            usuario=self.personal_b,
            aluno=None,
            nome="Legado B",
            sexo="M",
            data_nascimento="2000-01-01",
            altura="1.80",
            peso="80.00",
        )
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:detalhe_avaliacao", args=[avaliacao.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_usuario_nao_autenticado_acessa_rotas_privadas(self):
        urls = [
            reverse("core:avaliacoes"),
            reverse("core:escolher_tipo"),
            reverse("core:criar_avaliacao"),
            reverse("core:detalhe_avaliacao", args=[self.avaliacao_b.id]),
            reverse("core:editar_avaliacao", args=[self.avaliacao_b.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.url)

    def test_ver_treino_anonimo_redireciona_para_login(self):
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)
        self.assertIn("next", response.url)

    def test_ver_treino_aluno_proprietario_retorna_200(self):
        self.client.force_login(self.aluno_b_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/treino_publico.html")
        self.assertEqual(response.context["treino"], self.treino_b)
        self.assertContains(response, self.treino_b.nome)

    def test_ver_treino_aluno_diferente_retorna_404(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a-different@example.com",
            email="aluno-a-different@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.client.force_login(aluno_a_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 404)

    def test_ver_treino_aluno_outro_personal_retorna_404(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a-outro-personal@example.com",
            email="aluno-a-outro-personal@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        aluno_a = Aluno.objects.create(
            personal=self.personal_a,
            user=aluno_a_user,
            nome="Aluno A (outro personal)",
            data_nascimento="2000-01-01",
        )
        treino_a = Treino.objects.create(
            aluno=aluno_a,
            nome="Treino A (outro personal)",
            descricao="",
        )
        self.client.force_login(aluno_a_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[treino_a.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_ver_treino_personal_retorna_404(self):
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 404)

    def test_ver_treino_admin_retorna_404(self):
        admin_user = self.user_model.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="Senha123",
            tipo_usuario="ADMIN",
        )
        self.client.force_login(admin_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 404)

    def test_probe_session_after_login(self):
        self.client.force_login(self.personal_a)
        from django.conf import settings
        cookie = self.client.cookies.get(settings.SESSION_COOKIE_NAME)
        print("PROBE_COOKIE:", cookie)
        print("PROBE_COOKIE_VALUE:", cookie.value if cookie else None)
        print("PROBE_SESSION_KEY:", self.client.session.session_key)
        print("PROBE_SESSION_ITEMS:", dict(self.client.session.items()))
        self.assertIsNotNone(self.client.session.session_key)

    def test_ver_treino_token_inexistente_retorna_404(self):
        self.client.force_login(self.personal_a)
        response = self.client.get(
            reverse("core:ver_treino", args=["00000000-0000-0000-0000-000000000000"])
        )
        self.assertEqual(response.status_code, 404)

    def test_ver_treino_apos_login_retorna_ao_treino_correto(self):
        self.client.force_login(self.aluno_b_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/treino_publico.html")
        self.assertEqual(response.context["treino"], self.treino_b)
        self.assertContains(response, self.treino_b.nome)

    def test_ver_treino_aluno_outro_personal_retorna_404(self):
        aluno_a_user = self.user_model.objects.create_user(
            username="aluno-a-outro-personal@example.com",
            email="aluno-a-outro-personal@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        aluno_a = Aluno.objects.create(
            personal=self.personal_a,
            user=aluno_a_user,
            nome="Aluno A (outro personal)",
            data_nascimento="2000-01-01",
        )
        self.client.force_login(aluno_a_user)
        response = self.client.get(
            reverse("core:ver_treino", args=[self.treino_b.token])
        )
        self.assertEqual(response.status_code, 404)

    def test_personal_acesso_administracao_continua_funcionando(self):
        self.client.force_login(self.personal_a)
        response = self.client.get(reverse("core:criar_treino"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/criar_treino.html")

class EditarTreinoDivisaoTests(TestCase):
    """Verifica a navegação e o contexto da view editar_treino com divisões."""

    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal-divisao@example.com",
            email="personal-divisao@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno_user = self.user_model.objects.create_user(
            username="aluno-divisao@example.com",
            email="aluno-divisao@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_user,
            nome="Aluno Divisao",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino Divisao",
            descricao="",
        )

        self.divisao_a = DivisaoTreino.objects.create(
            treino=self.treino,
            nome="Treino A",
            ordem=1,
        )
        self.divisao_b = DivisaoTreino.objects.create(
            treino=self.treino,
            nome="Treino B",
            ordem=2,
        )

        # Divisão de outro treino, para validar que não é aceita.
        outro_user = self.user_model.objects.create_user(
            username="outro-divisao@example.com",
            email="outro-divisao@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.outro_aluno = Aluno.objects.create(
            personal=self.personal,
            user=outro_user,
            nome="Outro Aluno",
            data_nascimento="2000-01-01",
        )
        self.outro_treino = Treino.objects.create(
            aluno=self.outro_aluno,
            nome="Treino Outro",
            descricao="",
        )
        self.outro_divisao = DivisaoTreino.objects.create(
            treino=self.outro_treino,
            nome="Outro Treino",
            ordem=1,
        )

        self.grupo = GrupoMuscular.objects.create(nome="Teste")
        self.exercicio = VideoExercicio.objects.create(
            nome="Exercício Teste",
            grupo_muscular=self.grupo,
            gif="",
        )
        self.variacao = VariacaoExercicio.objects.create(
            exercicio=self.exercicio,
            nome="Variação 1",
            gif="",
        )

        self.exercicio_sem_divisao = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=1,
        )
        self.exercicio_na_divisao_a = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=2,
            divisao=self.divisao_a,
        )
        self.exercicio_na_divisao_b = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=3,
            divisao=self.divisao_b,
        )

    def test_contexto_inclui_divisoes_e_exercicios_sem_divisao(self):
        self.client.force_login(self.personal)
        response = self.client.get(
            reverse("core:editar_treino", args=[self.treino.id])
        )
        self.assertEqual(response.status_code, 200)

        context = response.context
        self.assertIn("divisoes", context)
        self.assertIn("divisao_selecionada", context)
        self.assertIn("exercicios_treino", context)
        self.assertIn("exercicios_sem_divisao", context)

        self.assertQuerySetEqual(
            context["divisoes"].order_by("id"),
            [self.divisao_a, self.divisao_b],
            transform=lambda d: d,
        )
        self.assertIn(self.exercicio_sem_divisao, context["exercicios_sem_divisao"])

    def test_divisao_selecionada_filtra_exercicios(self):
        self.client.force_login(self.personal)
        response = self.client.get(
            reverse("core:editar_treino", args=[self.treino.id])
            + f"?divisao={self.divisao_a.id}"
        )
        self.assertEqual(response.status_code, 200)

        exercicios_treino = response.context["exercicios_treino"]
        self.assertQuerySetEqual(
            exercicios_treino.order_by("id"),
            [self.exercicio_na_divisao_a],
            transform=lambda e: e,
        )

    def test_divisao_de_outro_treino_nao_filtra_exercicios(self):
        self.client.force_login(self.personal)
        response = self.client.get(
            reverse("core:editar_treino", args=[self.treino.id])
            + f"?divisao={self.outro_divisao.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
        response.context["divisao_selecionada"],
        self.divisao_a,
    )
        self.assertQuerySetEqual(
        response.context["exercicios_treino"],
        [self.exercicio_na_divisao_a],
        transform=lambda e: e,
    )

    def test_parametro_divisao_invalido_nao_filtra_exercicios(self):
        self.client.force_login(self.personal)

        response = self.client.get(
            reverse("core:editar_treino", args=[self.treino.id])
            + "?divisao=abc"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["divisao_selecionada"],
            self.divisao_a,
        )

        self.assertQuerySetEqual(
            response.context["exercicios_treino"],
            [self.exercicio_na_divisao_a],
            transform=lambda e: e,
        )

class TestEditarTreinoSemDuplicacaoExercicio(TestCase):
    """Verifica que os conjuntos exercicios_treino e exercicios_sem_divisao são
    disjuntos, respeitando o comportamento esperado conforme divisão selecionada."""

    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal-duplicacao@example.com",
            email="personal-duplicacao@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno_user = self.user_model.objects.create_user(
            username="aluno-duplicacao@example.com",
            email="aluno-duplicacao@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_user,
            nome="Aluno Duplicacao",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino Duplicacao",
            descricao="",
        )

        self.divisao_a = DivisaoTreino.objects.create(
            treino=self.treino,
            nome="Treino A",
            ordem=1,
        )
        self.divisao_b = DivisaoTreino.objects.create(
            treino=self.treino,
            nome="Treino B",
            ordem=2,
        )

        self.exercicio = VideoExercicio.objects.create(
            nome="Exercício Teste",
            grupo_muscular=GrupoMuscular.objects.create(nome="Teste"),
            gif="",
        )
        self.variacao = VariacaoExercicio.objects.create(
            exercicio=self.exercicio,
            nome="Variação 1",
            gif="",
        )

        # Sem divisão.
        self.sem_divisao = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=1,
        )
        # Com divisão A.
        self.com_divisao_a = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=2,
            divisao=self.divisao_a,
        )
        # Com divisão B.
        self.com_divisao_b = ExercicioTreino.objects.create(
            treino=self.treino,
            exercicio=self.exercicio,
            variacao=self.variacao,
            series=3,
            repeticoes=10,
            descanso=60,
            ordem=3,
            divisao=self.divisao_b,
        )

    def _get(self, divisao=None):
        url = reverse("core:editar_treino", args=[self.treino.id])
        if divisao is not None:
            url += f"?divisao={divisao.id}"
        self.client.force_login(self.personal)
        return self.client.get(url)

    def test_sem_divisao_selecionada_exercicios_treino_vazio(self):
        response = self._get()
        self.assertEqual(len(response.context["exercicios_treino"]), 0)

    def test_sem_divisao_exercicios_sem_divisao_apenas_aqui(self):
        response = self._get()
        context = response.context
        self.assertIn(self.sem_divisao, context["exercicios_sem_divisao"])
        self.assertNotIn(self.sem_divisao, context["exercicios_treino"])
        self.assertNotIn(self.com_divisao_a, context["exercicios_sem_divisao"])
        self.assertNotIn(self.com_divisao_b, context["exercicios_sem_divisao"])

    def test_com_divisao_selecionada_apenas_divisao_filtra(self):
        response = self._get(divisao=self.divisao_a)
        self.assertQuerySetEqual(
            response.context["exercicios_treino"].order_by("id"),
            [self.com_divisao_a],
            transform=lambda e: e,
        )
        self.assertNotIn(self.sem_divisao, response.context["exercicios_treino"])

    def test_exercicios_sem_divisao_sempre_separados(self):
        # Sem divisão.
        response = self._get()
        self.assertNotIn(self.com_divisao_a, response.context["exercicios_sem_divisao"])
        self.assertNotIn(self.com_divisao_b, response.context["exercicios_sem_divisao"])
        # Com divisão A.
        response = self._get(divisao=self.divisao_a)
        self.assertNotIn(self.com_divisao_a, response.context["exercicios_sem_divisao"])
        self.assertNotIn(self.com_divisao_b, response.context["exercicios_sem_divisao"])
        self.assertIn(self.sem_divisao, response.context["exercicios_sem_divisao"])

    def test_nenhum_exercicio_em_ambos_conjuntos(self):
        response = self._get()
        treino = set(response.context["exercicios_treino"])
        sem = set(response.context["exercicios_sem_divisao"])
        self.assertEqual(treino & sem, set())

        response = self._get(divisao=self.divisao_a)
        treino = set(response.context["exercicios_treino"])
        sem = set(response.context["exercicios_sem_divisao"])
        self.assertEqual(treino & sem, set())


class LoginNextFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal@example.com",
            email="personal@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno_user = self.user_model.objects.create_user(
            username="aluno@example.com",
            email="aluno@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_user,
            nome="Aluno Teste",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino de Teste",
            descricao="",
        )

    def test_anonimo_acessando_treino_redireciona_para_login_com_next(self):
        resposta = self.client.get(
            reverse("core:ver_treino", args=[self.treino.token])
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/login", resposta.url)
        self.assertIn("next", resposta.url)

    def test_login_valido_com_next_retorna_ao_endereco_original(self):
        destino = reverse("core:ver_treino", args=[self.treino.token])
        resposta = self.client.post(
            reverse("core:login"),
            {
                "email": "aluno@example.com",
                "password": "Senha123",
                "next": destino,
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, destino)

    def test_next_externo_ignored_nao_redireciona_para_outro_dominio(self):
        resposta = self.client.post(
            reverse("core:login"),
            {
                "email": "aluno@example.com",
                "password": "Senha123",
                "next": "https://evil.example/",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertNotIn("evil.example", resposta.url)
        self.assertTrue(
            resposta.url.startswith("/aluno/") or resposta.url.startswith("/fitflix")
        )

    def test_login_sem_next_mantem_comportamento_atual(self):
        resposta = self.client.post(
            reverse("core:login"),
            {
                "email": "aluno@example.com",
                "password": "Senha123",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, reverse("core:painel_aluno", args=[self.aluno.id]))

    def test_senha_incorreta_continua_exibindo_erro(self):
        resposta = self.client.post(
            reverse("core:login"),
            {
                "email": "aluno@example.com",
                "password": "SenhaErrada",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.wsgi_request.user.is_authenticated)
        mensagens = [m.message for m in get_messages(resposta.wsgi_request)]
        self.assertIn("Email ou senha inválidos", mensagens)


class TreinoSharingFlowTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal@example.com",
            email="personal@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno_user = self.user_model.objects.create_user(
            username="aluno@example.com",
            email="aluno@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_user,
            nome="Aluno Proprietario",
            data_nascimento="2000-01-01",
        )
        self.aluno_outro_user = self.user_model.objects.create_user(
            username="outro@example.com",
            email="outro@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno_outro = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_outro_user,
            nome="Outro Aluno",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino Compartilhado",
            descricao="",
        )

    def test_url_gerada_corresponde_ao_token(self):
        self.assertEqual(self.treino.get_link(), "/treino/%s" % self.treino.token)
        self.assertEqual(
            reverse("core:ver_treino", args=[self.treino.token]),
            "/treino/%s/" % self.treino.token,
        )

    def test_pagina_de_edicao_preserva_botoes(self):
        self.client.force_login(self.personal)
        resposta = self.client.get(
            reverse("core:editar_treino", args=[self.treino.id])
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="copiar-link"')
        conteudo = resposta.content.decode()
        self.assertIn('data-link="', conteudo)
        self.assertIn(str(self.treino.token), conteudo)
        self.assertIn("https://wa.me", conteudo)


class TestDivisaoCrudTests(TestCase):
    """Verifica o CRUD completo de divisões: criar, editar e excluir."""

    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal-crud@example.com",
            email="personal-crud@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno_user = self.user_model.objects.create_user(
            username="aluno-crud@example.com",
            email="aluno-crud@example.com",
            password="Senha123",
            tipo_usuario="ALUNO",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.aluno_user,
            nome="Aluno CRUD",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino CRUD",
            descricao="",
        )

    def test_criar_divisao(self):
        self.client.force_login(self.personal)
        resposta = self.client.post(
            reverse("core:nova_divisao", args=[self.treino.id]),
            {"nome": "Treino X", "descricao": "Descrição", "ordem": 1},
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            DivisaoTreino.objects.filter(
                treino=self.treino, nome="Treino X"
            ).exists()
        )

    def test_editar_divisao(self):
        divisao = DivisaoTreino.objects.create(
            treino=self.treino, nome="Treino Original", ordem=1
        )
        self.client.force_login(self.personal)
        resposta = self.client.post(
            reverse("core:editar_divisao", args=[self.treino.id, divisao.id]),
            {
                "nome": "Treino Renomeado",
                "descricao": "Nova descrição",
                "ordem": 1,
            },
        )
        self.assertEqual(resposta.status_code, 302)
        divisao.refresh_from_db()
        self.assertEqual(divisao.nome, "Treino Renomeado")

    def test_excluir_divisao(self):
        divisao = DivisaoTreino.objects.create(
            treino=self.treino, nome="Excluir", ordem=1
        )
        self.client.force_login(self.personal)
        resposta = self.client.post(
            reverse("core:excluir_divisao", args=[self.treino.id, divisao.id])
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(DivisaoTreino.objects.filter(pk=divisao.pk).exists())

    def test_form_rejeita_divisao_duplicada(self):
        DivisaoTreino.objects.create(
            treino=self.treino, nome="Treino Existente", ordem=1
        )
        form = DivisaoTreinoForm(
            data={
                "nome": "TREINO EXISTENTE",
                "descricao": "Duplicado",
                "ordem": 1,
            },
            treino=self.treino,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("nome", form.errors)


class TestAdicionarExercicioDivisaoTests(TestCase):
    """Verifica o fluxo de adicionar exercício a uma divisão e a restrição de
    associar exercício a divisão de outro treino."""

    def setUp(self):
        self.user_model = get_user_model()
        self.personal = self.user_model.objects.create_user(
            username="personal-aderexemplo@example.com",
            email="personal-aderexemplo@example.com",
            password="Senha123",
            tipo_usuario="PERSONAL",
        )
        self.aluno = Aluno.objects.create(
            personal=self.personal,
            user=self.user_model.objects.create_user(
                username="aluno-aderexemplo@example.com",
                email="aluno-aderexemplo@example.com",
                password="Senha123",
                tipo_usuario="ALUNO",
            ),
            nome="Aluno AddEx",
            data_nascimento="2000-01-01",
        )
        self.treino = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino AddEx",
            descricao="",
        )
        self.treino_outro = Treino.objects.create(
            aluno=self.aluno,
            nome="Treino Outro",
            descricao="",
        )
        self.grupo = GrupoMuscular.objects.create(nome="Pernas")
        self.exercicio = VideoExercicio.objects.create(
            nome="Agachamento",
            grupo_muscular=self.grupo,
            gif="",
        )
        self.variacao = VariacaoExercicio.objects.create(
            exercicio=self.exercicio,
            nome="Musculação",
            gif="",
        )
        self.divisao = DivisaoTreino.objects.create(
            treino=self.treino, nome="Div A", ordem=1
        )

    def test_adicionar_exercicio_a_divisao(self):
        self.client.force_login(self.personal)
        resposta = self.client.post(
            reverse("core:adicionar_exercicio", args=[self.treino.id]),
            {
                "exercicio": self.exercicio.id,
                "variacao": self.variacao.id,
                "divisao": self.divisao.id,
                "series": 3,
                "repeticoes": 12,
                "descanso": 60,
                "carga": "20kg",
            },
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(
            ExercicioTreino.objects.filter(
                treino=self.treino,
                divisao=self.divisao,
                exercicio=self.exercicio,
                variacao=self.variacao,
            ).exists()
        )

    def test_nao_associar_exercicio_divisao_treino_diferente(self):
        self.client.force_login(self.personal)
        self.client.post(
            reverse("core:adicionar_exercicio", args=[self.treino_outro.id]),
            {
                "exercicio": self.exercicio.id,
                "variacao": self.variacao.id,
                "divisao": self.divisao.id,
                "series": 3,
                "repeticoes": 12,
                "descanso": 60,
                "carga": "20kg",
            },
        )
        self.assertFalse(
            ExercicioTreino.objects.filter(
                treino=self.treino_outro, divisao=self.divisao
            ).exists()
        )
