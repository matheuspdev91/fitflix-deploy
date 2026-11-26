"""
Auditoria do cadastro de novos profissionais com data de lançamento
futura (Missão 03.6.13.3).

Todos os cenários usam instantes controlados (sem depender do relógio
real): o instante de referência do cadastro é fixado por mock de
`core.views.timezone.now`, e a configuração FITFLIX_TRIAL_LAUNCH_AT é
controlada por `override_settings`.

Cobre:
- data futura: cadastro concluído, sem trial prematuro;
- data passada: cadastro concluído com trial de 7 dias;
- data exatamente igual ao instante de referência: comportamento
  determinístico (o trial é concedido, pois a concessão é permitida a
  partir do instante do lançamento, inclusive);
- configuração None: cadastro concluído sem trial;
- configuração ausente: cadastro concluído sem trial;
- falha técnica na concessão: rollback da criação da conta;
- reenvio de cadastro: nenhuma duplicação de trial.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import PerfilDeTeste


# Instante de referência controlado (fixo, timezone-aware).
INSTANTE_REFERENCIA = timezone.make_aware(
    datetime(2026, 6, 15, 12, 0, 0),
    timezone.get_current_timezone(),
)

LAUNCH_PASSADO = INSTANTE_REFERENCIA - timedelta(days=1)
LAUNCH_FUTURO = INSTANTE_REFERENCIA + timedelta(days=1)


@override_settings(RATELIMIT_ENABLE=False)
class CadastroComLancamentoFuturoTests(TestCase):
    """Comportamento do cadastro conforme a data oficial de lançamento."""

    def setUp(self):
        self.url = reverse("core:register")

    def _cadastrar(self, username, email=None):
        if email is None:
            email = "{}@example.com".format(username)
        with patch(
            "core.services.perfil_de_teste_service."
            "PerfilDeTesteService.instante_referencia",
            return_value=INSTANTE_REFERENCIA,
        ):
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
    # 1. Data futura: cadastro concluído sem trial prematuro
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_data_futura_cadastro_concluido_sem_trial(self):
        response = self._cadastrar("personal-futuro")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:fitflix"))

        user = get_user_model().objects.get(username="personal-futuro")
        self.assertEqual(user.tipo_usuario, "PERSONAL")

        # Nenhum trial concedido antes da ativação oficial.
        self.assertFalse(PerfilDeTeste.objects.filter(usuario=user).exists())

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_data_futura_nao_cria_conta_parcial(self):
        self._cadastrar("personal-futuro-parcial")

        user = get_user_model().objects.get(username="personal-futuro-parcial")
        # Conta completa e funcional (não há rollback indevido).
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("SenhaTeste123"))
        self.assertFalse(PerfilDeTeste.objects.filter(usuario=user).exists())

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_data_futura_autentica_o_usuario(self):
        response = self._cadastrar("personal-futuro-login")

        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_data_futura_nao_cria_registro_de_trial_em_nenhum_cenario(self):
        self._cadastrar("personal-futuro-a")
        self._cadastrar("personal-futuro-b")

        self.assertEqual(PerfilDeTeste.objects.count(), 0)

    # ------------------------------------------------------------------
    # 2. Data passada: cadastro concluído com trial de 7 dias
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_PASSADO)
    def test_data_passada_cadastro_concluido_com_trial(self):
        response = self._cadastrar("personal-passado")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:fitflix"))

        user = get_user_model().objects.get(username="personal-passado")
        perfil = PerfilDeTeste.objects.get(usuario=user)

        self.assertEqual(perfil.status, "ATIVO")
        self.assertEqual(perfil.iniciado_em, INSTANTE_REFERENCIA)
        self.assertEqual(
            perfil.expira_em, INSTANTE_REFERENCIA + timedelta(days=7)
        )
        self.assertEqual(
            perfil.expira_em - perfil.iniciado_em, timedelta(days=7)
        )

    # ------------------------------------------------------------------
    # 3. Data exatamente igual ao instante de referência
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=INSTANTE_REFERENCIA)
    def test_data_igual_ao_instante_de_referencia_concede_trial(self):
        """
        A concessão é permitida a partir do instante do lançamento
        (inclusive). Com `agora == launch_at`, o cadastro conclui e o trial
        é concedido: comportamento determinístico, sem ambiguidade.
        """
        response = self._cadastrar("personal-igual")

        self.assertEqual(response.status_code, 302)

        user = get_user_model().objects.get(username="personal-igual")
        perfil = PerfilDeTeste.objects.get(usuario=user)

        self.assertEqual(perfil.status, "ATIVO")
        self.assertEqual(perfil.iniciado_em, INSTANTE_REFERENCIA)
        self.assertEqual(
            perfil.expira_em, INSTANTE_REFERENCIA + timedelta(days=7)
        )

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=INSTANTE_REFERENCIA)
    def test_data_igual_ao_instante_de_referencia_e_repetivel(self):
        """
        Duas contas cadastradas exatamente no instante do lançamento
        recebem, ambas, trial de 7 dias — sem ambiguidade de relógio.
        """
        self._cadastrar("personal-igual-a")
        self._cadastrar("personal-igual-b")

        self.assertEqual(PerfilDeTeste.objects.count(), 2)
        for perfil in PerfilDeTeste.objects.all():
            self.assertEqual(perfil.iniciado_em, INSTANTE_REFERENCIA)
            self.assertEqual(
                perfil.expira_em - perfil.iniciado_em, timedelta(days=7)
            )

    # ------------------------------------------------------------------
    # 4. Configuração None
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=None)
    def test_configuracao_none_cadastro_concluido_sem_trial(self):
        response = self._cadastrar("personal-none")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:fitflix"))

        user = get_user_model().objects.get(username="personal-none")
        self.assertTrue(user.is_active)
        self.assertFalse(PerfilDeTeste.objects.filter(usuario=user).exists())

    # ------------------------------------------------------------------
    # 5. Configuração ausente
    # ------------------------------------------------------------------

    def test_configuracao_ausente_cadastro_concluido_sem_trial(self):
        with override_settings():
            del settings.FITFLIX_TRIAL_LAUNCH_AT

            response = self._cadastrar("personal-ausente")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core:fitflix"))

        user = get_user_model().objects.get(username="personal-ausente")
        self.assertTrue(user.is_active)
        self.assertFalse(PerfilDeTeste.objects.filter(usuario=user).exists())

    # ------------------------------------------------------------------
    # 6. Falha técnica na concessão: rollback da criação da conta
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_PASSADO)
    def test_falha_tecnica_reverte_a_conta(self):
        from core.services.perfil_de_teste_service import TrialInelegivelError

        with patch(
            "core.services.perfil_de_teste_service."
            "PerfilDeTesteService.conceder_trial_novo_cadastro",
            side_effect=TrialInelegivelError("falha técnica simulada"),
        ):
            response = self._cadastrar("personal-falha-tecnica")

        # A falha técnica invalida o cadastro: nada é gravado.
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username="personal-falha-tecnica").exists()
        )
        self.assertFalse(
            PerfilDeTeste.objects.filter(
                usuario__username="personal-falha-tecnica"
            ).exists()
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_falha_tecnica_com_lancamento_futuro_tambem_reverte(self):
        """
        Uma falha técnica real (e não o 'ainda não liberado') reverte a
        conta mesmo com lançamento futuro.
        """
        from core.services.perfil_de_teste_service import TrialInelegivelError

        with patch(
            "core.services.perfil_de_teste_service."
            "PerfilDeTesteService.conceder_trial_novo_cadastro",
            side_effect=TrialInelegivelError("falha técnica simulada"),
        ):
            response = self._cadastrar("personal-falha-futuro")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(
                username="personal-falha-futuro"
            ).exists()
        )

    # ------------------------------------------------------------------
    # 7. Reenvio de cadastro: nenhuma duplicação de trial
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_PASSADO)
    def test_reenvio_nao_duplica_trial(self):
        self._cadastrar("personal-reenvio")

        user = get_user_model().objects.get(username="personal-reenvio")
        self.assertEqual(PerfilDeTeste.objects.filter(usuario=user).count(), 1)
        perfil = PerfilDeTeste.objects.get(usuario=user)

        # Segundo envio com o mesmo username é rejeitado pela view.
        response = self._cadastrar("personal-reenvio")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PerfilDeTeste.objects.filter(usuario=user).count(), 1)
        perfil.refresh_from_db()
        self.assertEqual(perfil.iniciado_em, INSTANTE_REFERENCIA)
        self.assertEqual(perfil.status, "ATIVO")

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_FUTURO)
    def test_reenvio_com_lancamento_futuro_nao_duplica_nada(self):
        self._cadastrar("personal-reenvio-futuro")

        response = self._cadastrar("personal-reenvio-futuro")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PerfilDeTeste.objects.count(), 0)
        self.assertEqual(
            get_user_model().objects.filter(
                username="personal-reenvio-futuro"
            ).count(),
            1,
        )
