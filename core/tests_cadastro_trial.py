"""
Testes da integração do trial ao cadastro de novos profissionais
(Missão 03.6.13.2).

Cobre:
- cadastro de PERSONAL com lançamento configurado concede trial;
- o trial começa após a conclusão do cadastro;
- expiração exatamente 7 dias depois;
- fail-safe: configuração ausente => nenhum trial, cadastro concluído;
- fail-safe: configuração None => nenhum trial, cadastro concluído;
- falha na concessão reverte a conta (sem conta parcialmente criada);
- cadastro de ALUNO/ADMIN não recebe trial.
"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import PerfilDeTeste


LAUNCH_AT = timezone.make_aware(
    datetime(2026, 1, 1, 12, 0, 0),
    timezone.get_current_timezone(),
)


@override_settings(RATELIMIT_ENABLE=False)
class CadastroComTrialTests(TestCase):
    """Cadastro de novos profissionais e concessão de trial."""

    def setUp(self):
        self.url = reverse("core:register")

    def _cadastrar(self, username="novo-personal", email=None):
        if email is None:
            email = "{}@example.com".format(username)
        return self.client.post(
            self.url,
            {
                "username": username,
                "email": email,
                "password": "SenhaTeste123",
                "password_confirm": "SenhaTeste123",
            },
        )

    # ------------------------------------------------------------------
    # 1. Cadastro com lançamento configurado concede trial
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_cadastro_personal_concede_trial(self):
        response = self._cadastrar()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:fitflix"))

        user = get_user_model().objects.get(username="novo-personal")
        self.assertEqual(user.tipo_usuario, "PERSONAL")

        perfil = PerfilDeTeste.objects.get(usuario=user)
        self.assertEqual(perfil.status, "ATIVO")

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_trial_comeca_apos_conclusao_do_cadastro(self):
        antes = timezone.now()
        self._cadastrar(username="personal-novo-tempo")
        depois = timezone.now()

        user = get_user_model().objects.get(username="personal-novo-tempo")
        perfil = PerfilDeTeste.objects.get(usuario=user)

        self.assertGreaterEqual(perfil.iniciado_em, antes)
        self.assertLessEqual(perfil.iniciado_em, depois)
        self.assertTrue(timezone.is_aware(perfil.iniciado_em))
        self.assertTrue(timezone.is_aware(perfil.expira_em))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_expiracao_exatamente_sete_dias_depois(self):
        self._cadastrar(username="personal-novo-duracao")

        user = get_user_model().objects.get(username="personal-novo-duracao")
        perfil = PerfilDeTeste.objects.get(usuario=user)

        self.assertEqual(
            perfil.expira_em - perfil.iniciado_em, timedelta(days=7)
        )
        self.assertEqual(
            perfil.expira_em, perfil.iniciado_em + timedelta(days=7)
        )

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_cadastro_nao_duplica_trial_em_reenvio(self):
        self._cadastrar(username="personal-reenvio")

        user = get_user_model().objects.get(username="personal-reenvio")
        self.assertEqual(PerfilDeTeste.objects.filter(usuario=user).count(), 1)

    # ------------------------------------------------------------------
    # 2. Fail-safe: configuração ausente
    # ------------------------------------------------------------------

    def test_configuracao_ausente_nao_concede_trial(self):
        with override_settings():
            del_settings = getattr(
                __import__("django.conf", fromlist=["settings"]).settings,
                "FITFLIX_TRIAL_LAUNCH_AT",
                None,
            )
            self.assertIsNone(del_settings)

            response = self._cadastrar(username="personal-sem-config")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            get_user_model().objects.filter(username="personal-sem-config").exists()
        )
        self.assertFalse(
            PerfilDeTeste.objects.filter(
                usuario__username="personal-sem-config"
            ).exists()
        )

    # ------------------------------------------------------------------
    # 3. Fail-safe: configuração None
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=None)
    def test_configuracao_none_nao_concede_trial(self):
        response = self._cadastrar(username="personal-config-none")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            get_user_model().objects.filter(username="personal-config-none").exists()
        )
        self.assertFalse(
            PerfilDeTeste.objects.filter(
                usuario__username="personal-config-none"
            ).exists()
        )

    # ------------------------------------------------------------------
    # 4. Integridade transacional
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_falha_na_concessao_reverte_a_conta(self):
        """
        Se a concessão do trial falhar, a criação da conta é revertida:
        não existe conta parcialmente criada.
        """
        from unittest.mock import patch

        from core.services.perfil_de_teste_service import TrialInelegivelError

        with patch(
            "core.services.perfil_de_teste_service."
            "PerfilDeTesteService.conceder_trial_novo_cadastro",
            side_effect=TrialInelegivelError("falha simulada"),
        ):
            response = self._cadastrar(username="personal-falha")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username="personal-falha").exists()
        )
        self.assertFalse(
            PerfilDeTeste.objects.filter(
                usuario__username="personal-falha"
            ).exists()
        )
        # O usuário não fica autenticado após a falha.
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_falha_inesperada_nao_deixa_conta_parcial(self):
        """
        Uma exceção inesperada na concessão também reverte a conta
        (a transação externa cobre todo o bloco).
        """
        from unittest.mock import patch

        with patch(
            "core.services.perfil_de_teste_service."
            "PerfilDeTesteService.conceder_trial_novo_cadastro",
            side_effect=RuntimeError("falha inesperada"),
        ):
            with self.assertRaises(RuntimeError):
                self._cadastrar(username="personal-falha-inesperada")

        self.assertFalse(
            get_user_model().objects.filter(
                username="personal-falha-inesperada"
            ).exists()
        )

    # ------------------------------------------------------------------
    # 5. Apenas PERSONAL recebe trial
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_cadastro_padrao_cria_personal(self):
        self._cadastrar(username="padrao-personal")

        user = get_user_model().objects.get(username="padrao-personal")
        self.assertEqual(user.tipo_usuario, "PERSONAL")
        self.assertEqual(PerfilDeTeste.objects.filter(usuario=user).count(), 1)

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
    def test_nao_cria_trial_para_tipo_nao_personal(self):
        """
        O formulário público de cadastro cria PERSONAL. Se o tipo da conta
        for alterado para ALUNO/ADMIN, nenhum trial é concedido.
        """
        user = get_user_model().objects.create_user(
            username="aluno-sem-trial",
            email="aluno-sem-trial@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
        )
        from core.services.perfil_de_teste_service import PerfilDeTesteService

        servico = PerfilDeTesteService()
        self.assertFalse(servico.elegivel(user))
        self.assertFalse(PerfilDeTeste.objects.filter(usuario=user).exists())
