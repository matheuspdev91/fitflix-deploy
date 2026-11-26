"""
Testes da conversão do trial via webhook do Asaas (Missão 03.6.17).

Cobre a política comercial aprovada:

- somente PAYMENT_RECEIVED converte um trial ATIVO em CONVERTIDO;
- a conversão preenche `convertido_em` e `finalizado_em`;
- a assinatura só fica ACTIVE mediante pagamento confirmado;
- PAYMENT_CONFIRMED não converte o trial;
- SUBSCRIPTION_CREATED / SUBSCRIPTION_UPDATED não concedem acesso pago;
- trials ENCERRADO, CANCELADO e CONVERTIDO são imutáveis;
- eventos duplicados não provocam conversões repetidas;
- pagamento posterior ao encerramento ativa a assinatura, mas não
  converte nem reabre o trial;
- a associação entre pagamento, assinatura e usuário é preservada;
- a idempotência de WebhookEvent é preservada.

Limitações de concorrência: o banco de testes é SQLite em memória
(projeto.test_settings), que serializa as escritas e ignora
`select_for_update`. Os cenários de corrida são cobertos no nível de
domínio (chamada sequencial repetida), e não por threads reais.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Assinatura, PagamentoAsaas, PerfilDeTeste, WebhookEvent


User = get_user_model()


class TrialConversaoAsaasTests(TestCase):
    """Conversão do trial a partir do webhook do Asaas."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="trial@example.com",
            email="trial@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
            asaas_customer_id="cus_trial",
        )
        self.valid_token = "whsec_token123"
        self.agora = timezone.now()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def post_webhook(self, payload, token=None):
        headers = {}
        if token:
            headers["HTTP_ASAAS_ACCESS_TOKEN"] = token
        return self.client.post(
            reverse("core:asaas_webhook"),
            data=json.dumps(payload),
            content_type="application/json",
            **headers
        )

    def criar_assinatura(self, status="PENDING", subscription_id="sub_trial"):
        return Assinatura.objects.create(
            usuario=self.user,
            asaas_subscription_id=subscription_id,
            status=status,
        )

    def criar_trial(self, status="ATIVO", expira_em=None, **extra):
        expira_em = expira_em or (self.agora + timedelta(days=3))
        campos = {
            "usuario": self.user,
            "status": status,
            "iniciado_em": self.agora - timedelta(days=1),
            "expira_em": expira_em,
            "finalizado_em": None,
            "convertido_em": None,
        }
        campos.update(extra)
        return PerfilDeTeste.objects.create(**campos)

    def payload_payment_received(self, event_id="evt_conv_001", payment_id="pay_conv_001"):
        return {
            "id": event_id,
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": payment_id,
                "customer": "cus_trial",
                "subscription": "sub_trial",
                "value": 60.00,
            },
        }

    # ------------------------------------------------------------------
    # 1. Conversão do trial ATIVO dentro do prazo
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_converte_trial_ativo_dentro_do_prazo(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        resp = self.post_webhook(
            self.payload_payment_received(), token=self.valid_token
        )

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CONVERTIDO")
        self.assertIsNotNone(perfil.convertido_em)
        self.assertIsNotNone(perfil.finalizado_em)
        self.assertEqual(perfil.convertido_em, perfil.finalizado_em)
        self.assertTrue(timezone.is_aware(perfil.convertido_em))

    # ------------------------------------------------------------------
    # 2. Trial vencido: assinatura ativa, trial encerrado (não convertido)
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_com_trial_vencido_encerra_sem_converter(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial(
            status="ATIVO",
            expira_em=self.agora - timedelta(seconds=1),
        )

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_002"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ENCERRADO")
        self.assertIsNotNone(perfil.finalizado_em)
        self.assertIsNone(perfil.convertido_em)

    # ------------------------------------------------------------------
    # 3. Estados terminais imutáveis
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_nao_reabre_trial_encerrado(self):
        assinatura = self.criar_assinatura()
        finalizado = self.agora - timedelta(days=2)
        perfil = self.criar_trial(
            status="ENCERRADO",
            expira_em=self.agora - timedelta(days=3),
            finalizado_em=finalizado,
        )

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_003"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ENCERRADO")
        self.assertEqual(perfil.finalizado_em, finalizado)
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_nao_reabre_trial_cancelado(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial(status="CANCELADO")

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_004"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CANCELADO")
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_em_trial_ja_convertido_e_idempotente(self):
        assinatura = self.criar_assinatura()
        convertido = self.agora - timedelta(hours=1)
        perfil = self.criar_trial(
            status="CONVERTIDO",
            convertido_em=convertido,
            finalizado_em=convertido,
        )

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_005"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CONVERTIDO")
        self.assertEqual(perfil.convertido_em, convertido)
        self.assertEqual(perfil.finalizado_em, convertido)

    # ------------------------------------------------------------------
    # 4. Usuário sem trial: nada é criado
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_received_sem_trial_nao_cria_perfil_de_teste(self):
        assinatura = self.criar_assinatura()

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_006"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "ACTIVE")
        self.assertFalse(
            PerfilDeTeste.objects.filter(usuario=self.user).exists()
        )

    # ------------------------------------------------------------------
    # 5. PAYMENT_CONFIRMED não converte
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_payment_confirmed_nao_converte_trial(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        payload = self.payload_payment_received(event_id="evt_conv_007")
        payload["event"] = "PAYMENT_CONFIRMED"

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertNotEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

        pagamento = PagamentoAsaas.objects.get(
            asaas_payment_id="pay_conv_001"
        )
        self.assertEqual(pagamento.status, "CONFIRMED")

    # ------------------------------------------------------------------
    # 6. SUBSCRIPTION_CREATED / UPDATED não ativam
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_subscription_created_nao_ativa_assinatura(self):
        assinatura = self.criar_assinatura(status="PENDING")
        perfil = self.criar_trial()

        payload = {
            "id": "evt_conv_008",
            "event": "SUBSCRIPTION_CREATED",
            "subscription": {
                "id": "sub_trial",
                "customer": "cus_trial",
                "status": "ACTIVE",
            },
        }

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertNotEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_subscription_updated_nao_ativa_assinatura(self):
        assinatura = self.criar_assinatura(status="PENDING")
        perfil = self.criar_trial()

        payload = {
            "id": "evt_conv_009",
            "event": "SUBSCRIPTION_UPDATED",
            "subscription": {
                "id": "sub_trial",
                "customer": "cus_trial",
                "status": "ACTIVE",
            },
        }

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertNotEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_subscription_inactivated_preserva_cancelamento(self):
        assinatura = self.criar_assinatura(status="ACTIVE")
        perfil = self.criar_trial()

        payload = {
            "id": "evt_conv_010",
            "event": "SUBSCRIPTION_INACTIVATED",
            "subscription": {
                "id": "sub_trial",
                "customer": "cus_trial",
                "status": "INACTIVE",
            },
        }

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "CANCELLED")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    # ------------------------------------------------------------------
    # 7. Idempotência
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_evento_duplicado_nao_converte_duas_vezes(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        payload = self.payload_payment_received(event_id="evt_conv_011")

        self.post_webhook(payload, token=self.valid_token)
        perfil.refresh_from_db()
        primeira_conversao = perfil.convertido_em

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            WebhookEvent.objects.filter(event_id="evt_conv_011").count(), 1
        )
        self.assertEqual(
            PagamentoAsaas.objects.filter(
                asaas_payment_id="pay_conv_001"
            ).count(),
            1,
        )

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CONVERTIDO")
        self.assertEqual(perfil.convertido_em, primeira_conversao)
        self.assertEqual(perfil.finalizado_em, primeira_conversao)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_reenvio_com_evento_distinto_nao_reconverte(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_012a"),
            token=self.valid_token,
        )
        perfil.refresh_from_db()
        primeira_conversao = perfil.convertido_em

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_012b"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CONVERTIDO")
        self.assertEqual(perfil.convertido_em, primeira_conversao)

    # ------------------------------------------------------------------
    # 8. Associação segura
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_customer_divergente_nao_converte_trial(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        payload = self.payload_payment_received(event_id="evt_conv_013")
        payload["payment"]["customer"] = "cus_outro"

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertNotEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_subscription_desconhecida_nao_converte_trial(self):
        assinatura = self.criar_assinatura()
        perfil = self.criar_trial()

        payload = self.payload_payment_received(event_id="evt_conv_014")
        payload["payment"]["subscription"] = "sub_inexistente"

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertNotEqual(assinatura.status, "ACTIVE")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_assinatura_cancelada_nao_converte_trial(self):
        assinatura = self.criar_assinatura(status="CANCELLED")
        perfil = self.criar_trial()

        resp = self.post_webhook(
            self.payload_payment_received(event_id="evt_conv_015"),
            token=self.valid_token,
        )

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "CANCELLED")

        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNone(perfil.convertido_em)

    # ------------------------------------------------------------------
    # 9. ALUNO/ADMIN não possuem trial nem são afetados
    # ------------------------------------------------------------------

    @patch.dict("os.environ", {"ASAAS_WEBHOOK_TOKEN": "whsec_token123"})
    def test_conversao_aplica_somente_a_quem_possui_trial(self):
        aluno = User.objects.create_user(
            username="aluno@example.com",
            email="aluno@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
            asaas_customer_id="cus_aluno",
        )

        assinatura = Assinatura.objects.create(
            usuario=aluno,
            asaas_subscription_id="sub_aluno",
            status="PENDING",
        )

        payload = {
            "id": "evt_conv_016",
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_conv_016",
                "customer": "cus_aluno",
                "subscription": "sub_aluno",
                "value": 60.00,
            },
        }

        resp = self.post_webhook(payload, token=self.valid_token)

        self.assertEqual(resp.status_code, 200)

        assinatura.refresh_from_db()
        self.assertEqual(assinatura.status, "ACTIVE")
        self.assertFalse(
            PerfilDeTeste.objects.filter(usuario=aluno).exists()
        )
