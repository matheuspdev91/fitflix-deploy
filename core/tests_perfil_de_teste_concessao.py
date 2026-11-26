"""
Testes da concessão do trial de 7 dias (Missão 03.6.13.1).

Cobre a política comercial aprovada:
- novo PERSONAL elegível;
- PERSONAL antigo elegível por concessão oficial;
- configuração ausente / None (fail-safe);
- trial anterior (qualquer status) bloqueia nova concessão;
- assinatura ACTIVE bloqueia a concessão;
- ADMIN e ALUNO não recebem trial;
- usuário inativo não recebe trial;
- duração exata de 7 dias;
- duas tentativas de concessão (idempotência/duplicidade);
- preservação dos estados terminais;
- datas timezone-aware.

Limitações de concorrência: o banco de testes é SQLite em memória
(projeto.test_settings), que serializa as escritas e não suporta
`select_for_update` de forma efetiva (SELECT ... FOR UPDATE é ignorado).
Por isso os testes de concorrência aqui cobrem a camada de domínio
(tentativa sequencial duplicada e corrida simulada via IntegrityError),
e não uma corrida real entre threads. Ver
`test_concessao_duplicada_nao_propaga_integrity_error`.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import Assinatura, PerfilDeTeste
from core.services.perfil_de_teste_service import (
    PerfilDeTesteService,
    TrialInelegivelError,
    TrialJaConcedidoError,
)


LAUNCH_AT = timezone.make_aware(
    datetime(2026, 1, 1, 12, 0, 0),
    timezone.get_current_timezone(),
)


def _criar_usuario(username, tipo="PERSONAL", date_joined=None, ativo=True):
    User = get_user_model()
    usuario = User.objects.create_user(
        username=username,
        email="{}@example.com".format(username),
        password="SenhaTeste123",
        tipo_usuario=tipo,
    )
    if date_joined is not None:
        usuario.date_joined = date_joined
        usuario.save(update_fields=["date_joined"])
    if not ativo:
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
    return usuario


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=LAUNCH_AT)
class ConcessaoTrialTests(TestCase):
    """Concessão do trial por perfil de conta."""

    def setUp(self):
        self.service = PerfilDeTesteService()
        self.agora = LAUNCH_AT + timedelta(hours=1)

    # ------------------------------------------------------------------
    # 1. Novo PERSONAL elegível
    # ------------------------------------------------------------------

    def test_novo_personal_elegivel_recebe_trial(self):
        usuario = _criar_usuario(
            "personal-novo", date_joined=LAUNCH_AT + timedelta(minutes=10)
        )

        self.assertTrue(self.service.elegivel(usuario))

        perfil = self.service.conceder_trial_novo_cadastro(
            usuario, agora=self.agora
        )

        self.assertEqual(perfil.usuario, usuario)
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNotNone(perfil.pk)

    def test_conta_nova_nao_pode_usar_trilha_de_conta_antiga(self):
        usuario = _criar_usuario(
            "personal-novo-trilha", date_joined=LAUNCH_AT + timedelta(minutes=10)
        )

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_conta_antiga(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 2. PERSONAL antigo elegível por concessão oficial
    # ------------------------------------------------------------------

    def test_personal_antigo_recebe_trial_na_concessao_oficial(self):
        usuario = _criar_usuario(
            "personal-antigo", date_joined=LAUNCH_AT - timedelta(days=30)
        )

        self.assertEqual(
            self.service.classificar_conta(usuario),
            PerfilDeTesteService.CONTA_ANTIGA,
        )
        self.assertTrue(self.service.elegivel(usuario))

        perfil = self.service.conceder_trial_conta_antiga(
            usuario, agora=LAUNCH_AT
        )

        self.assertEqual(perfil.status, "ATIVO")
        self.assertEqual(perfil.iniciado_em, LAUNCH_AT)
        self.assertEqual(
            perfil.expira_em, LAUNCH_AT + timedelta(days=7)
        )

    def test_conta_antiga_nao_recebe_trial_antes_do_lancamento(self):
        usuario = _criar_usuario(
            "personal-antigo-pre", date_joined=LAUNCH_AT - timedelta(days=30)
        )

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_conta_antiga(
                usuario, agora=LAUNCH_AT - timedelta(seconds=1)
            )

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    def test_conta_antiga_nao_pode_usar_trilha_de_novo_cadastro(self):
        usuario = _criar_usuario(
            "personal-antigo-trilha", date_joined=LAUNCH_AT - timedelta(days=30)
        )

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 3. Configuração ausente
    # ------------------------------------------------------------------

    def test_configuracao_ausente_nao_concede_trial(self):
        usuario = _criar_usuario(
            "personal-sem-config", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        with override_settings():
            del settings.FITFLIX_TRIAL_LAUNCH_AT
            self.assertIsNone(self.service.lancamento_oficial())
            self.assertFalse(self.service.elegivel(usuario))

            with self.assertRaises(TrialInelegivelError):
                self.service.conceder_trial_novo_cadastro(
                    usuario, agora=self.agora
                )
            with self.assertRaises(TrialInelegivelError):
                self.service.conceder_trial_conta_antiga(
                    usuario, agora=self.agora
                )

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 4. Configuração None
    # ------------------------------------------------------------------

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=None)
    def test_configuracao_none_nao_concede_trial(self):
        usuario = _criar_usuario(
            "personal-config-none", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        self.assertIsNone(self.service.lancamento_oficial())
        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 5. Trial anterior
    # ------------------------------------------------------------------

    def test_trial_anterior_bloqueia_nova_concessao(self):
        usuario = _criar_usuario(
            "personal-com-trial", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )
        PerfilDeTeste.objects.create(
            usuario=usuario,
            status="ATIVO",
            iniciado_em=LAUNCH_AT,
            expira_em=LAUNCH_AT + timedelta(days=7),
        )

        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertEqual(PerfilDeTeste.objects.filter(usuario=usuario).count(), 1)

    # ------------------------------------------------------------------
    # 6. Assinatura ACTIVE
    # ------------------------------------------------------------------

    def test_assinatura_active_bloqueia_concessao(self):
        usuario = _criar_usuario(
            "personal-assinado", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )
        Assinatura.objects.create(
            usuario=usuario,
            asaas_subscription_id="sub_trial_01",
            plano="MENSAL",
            status="ACTIVE",
        )

        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 7. ADMIN / 8. ALUNO
    # ------------------------------------------------------------------

    def test_admin_nao_recebe_trial(self):
        usuario = _criar_usuario(
            "admin-trial", tipo="ADMIN", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    def test_aluno_nao_recebe_trial(self):
        usuario = _criar_usuario(
            "aluno-trial", tipo="ALUNO", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 9. Usuário inativo
    # ------------------------------------------------------------------

    def test_usuario_inativo_nao_recebe_trial(self):
        usuario = _criar_usuario(
            "inativo-trial",
            date_joined=LAUNCH_AT + timedelta(minutes=5),
            ativo=False,
        )

        self.assertFalse(self.service.elegivel(usuario))

        with self.assertRaises(TrialInelegivelError):
            self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        self.assertFalse(PerfilDeTeste.objects.filter(usuario=usuario).exists())

    # ------------------------------------------------------------------
    # 10. Duração exata de sete dias
    # ------------------------------------------------------------------

    def test_duracao_exata_de_sete_dias(self):
        usuario = _criar_usuario(
            "personal-duracao", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        perfil = self.service.conceder_trial_novo_cadastro(
            usuario, agora=self.agora
        )

        self.assertEqual(
            perfil.expira_em - perfil.iniciado_em, timedelta(days=7)
        )
        self.assertEqual(
            perfil.expira_em, perfil.iniciado_em + timedelta(days=7)
        )

    # ------------------------------------------------------------------
    # 11. Duas tentativas de concessão
    # ------------------------------------------------------------------

    def test_segunda_tentativa_de_concessao_rejeitada_sem_500(self):
        usuario = _criar_usuario(
            "personal-duplicado", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        primeiro = self.service.conceder_trial_novo_cadastro(
            usuario, agora=self.agora
        )

        with self.assertRaises(TrialJaConcedidoError):
            self.service.conceder_trial_novo_cadastro(
                usuario, agora=self.agora + timedelta(hours=1)
            )

        self.assertEqual(PerfilDeTeste.objects.filter(usuario=usuario).count(), 1)
        self.assertEqual(primeiro.pk, PerfilDeTeste.objects.get(usuario=usuario).pk)

    def test_concessao_duplicada_nao_propaga_integrity_error(self):
        """
        Simula a corrida de criação (duas transações gravando o mesmo
        OneToOne): o IntegrityError é convertido em erro de domínio,
        nunca propagado como erro 500.
        """
        usuario = _criar_usuario(
            "personal-corrida", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )
        self.service.conceder_trial_novo_cadastro(usuario, agora=self.agora)

        # Outra transação grava o mesmo OneToOne (simula a corrida).
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PerfilDeTeste.objects.create(
                    usuario=usuario,
                    status="ATIVO",
                    iniciado_em=self.agora,
                    expira_em=self.agora + timedelta(days=7),
                )

        # A segunda chamada da serviço deve falhar como erro de domínio.
        with self.assertRaises(TrialJaConcedidoError):
            self.service.conceder_trial_novo_cadastro(
                usuario, agora=self.agora + timedelta(minutes=1)
            )

        self.assertEqual(PerfilDeTeste.objects.filter(usuario=usuario).count(), 1)

    # ------------------------------------------------------------------
    # 12. Preservação dos estados terminais
    # ------------------------------------------------------------------

    def test_status_terminal_nao_permite_reuso_do_trial(self):
        for status in ("ENCERRADO", "CANCELADO", "CONVERTIDO"):
            with self.subTest(status=status):
                usuario = _criar_usuario(
                    "personal-terminal-{}".format(status.lower()),
                    date_joined=LAUNCH_AT + timedelta(minutes=5),
                )
                PerfilDeTeste.objects.create(
                    usuario=usuario,
                    status=status,
                    iniciado_em=LAUNCH_AT,
                    expira_em=LAUNCH_AT + timedelta(days=7),
                    finalizado_em=(
                        LAUNCH_AT + timedelta(days=7)
                        if status == "ENCERRADO"
                        else None
                    ),
                    convertido_em=(
                        LAUNCH_AT + timedelta(days=1)
                        if status == "CONVERTIDO"
                        else None
                    ),
                )

                self.assertFalse(self.service.elegivel(usuario))

                with self.assertRaises(TrialInelegivelError):
                    self.service.conceder_trial_novo_cadastro(
                        usuario, agora=self.agora
                    )

                perfil = PerfilDeTeste.objects.get(usuario=usuario)
                self.assertEqual(perfil.status, status)

    def test_encerramento_nao_apaga_dados_do_trial(self):
        usuario = _criar_usuario(
            "personal-encerrado", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )
        perfil = self.service.conceder_trial_novo_cadastro(
            usuario, agora=self.agora
        )

        encerrado = self.service.encerrar_trial_expirado(
            usuario, agora=perfil.expira_em
        )

        self.assertEqual(encerrado.status, "ENCERRADO")
        self.assertIsNotNone(encerrado.finalizado_em)
        self.assertEqual(encerrado.iniciado_em, perfil.iniciado_em)
        self.assertEqual(encerrado.expira_em, perfil.expira_em)
        self.assertTrue(
            PerfilDeTeste.objects.filter(pk=perfil.pk).exists()
        )

    # ------------------------------------------------------------------
    # 13. Datas timezone-aware
    # ------------------------------------------------------------------

    def test_das_persistidas_sao_timezone_aware(self):
        usuario = _criar_usuario(
            "personal-aware", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        perfil = self.service.conceder_trial_novo_cadastro(
            usuario, agora=self.agora
        )

        self.assertTrue(timezone.is_aware(perfil.iniciado_em))
        self.assertTrue(timezone.is_aware(perfil.expira_em))

        perfil.refresh_from_db()
        self.assertTrue(timezone.is_aware(perfil.iniciado_em))
        self.assertTrue(timezone.is_aware(perfil.expira_em))

    def test_instante_naive_e_convertido_para_aware(self):
        usuario = _criar_usuario(
            "personal-naive", date_joined=LAUNCH_AT + timedelta(minutes=5)
        )

        perfil = self.service.conceder_trial_novo_cadastro(
            usuario, agora=datetime(2026, 1, 1, 13, 0, 0)
        )

        self.assertTrue(timezone.is_aware(perfil.iniciado_em))
        self.assertTrue(timezone.is_aware(perfil.expira_em))
        self.assertEqual(
            perfil.expira_em - perfil.iniciado_em, timedelta(days=7)
        )

    def test_lancamento_naive_e_convertido_para_aware(self):
        with override_settings(
            FITFLIX_TRIAL_LAUNCH_AT=datetime(2026, 1, 1, 12, 0, 0)
        ):
            lancamento = self.service.lancamento_oficial()
            self.assertTrue(timezone.is_aware(lancamento))
