import logging

from django.db import transaction
from django.contrib.auth import get_user_model

from core.models import (
    Assinatura,
    PagamentoAsaas,
    WebhookEvent,
)


logger = logging.getLogger(__name__)
User = get_user_model()


class WebhookHandler:

    @classmethod
    def process(cls, payload):
        event_id = payload.get("id")
        event_type = payload.get("event")

        if not event_id or not event_type:
            raise ValueError(
                "Payload inválido: faltando id ou event"
            )

        payment = payload.get("payment") or {}
        subscription = payload.get("subscription") or {}

        payment_id = payment.get("id", "")

        with transaction.atomic():

            # Idempotência
            existing_event = (
                WebhookEvent.objects
                .select_for_update()
                .filter(event_id=event_id)
                .first()
            )

            if existing_event:
                logger.info(
                    f"Evento {event_id} já processado anteriormente."
                )
                return True

            event = WebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                payment_id=payment_id,
                payload=payload,
                status="PROCESSED",
            )

            try:
                handled = cls._handle_event(
                    event_type=event_type,
                    payment=payment,
                    subscription=subscription,
                )

                if not handled:
                    event.status = "IGNORED"
                    event.save(update_fields=["status"])

            except Exception as exc:
                logger.error(
                    f"Erro ao processar webhook {event_id}: {exc}"
                )
                raise

            return True

    @classmethod
    def _handle_event(
        cls,
        event_type,
        payment,
        subscription,
    ):
        # Eventos financeiros
        if event_type.startswith("PAYMENT_"):
            return cls._handle_payment(
                event_type,
                payment,
            )

        # Eventos do ciclo de vida da assinatura
        if event_type.startswith("SUBSCRIPTION_"):
            return cls._handle_subscription(
                event_type,
                subscription,
            )

        return False

    # ==========================================================
    # PAGAMENTOS
    # ==========================================================

    @classmethod
    def _handle_payment(cls, event_type, payment):
        payment_id = payment.get("id")

        if not payment_id:
            return False

        assinatura = cls._get_assinatura_from_payment(payment)

        if not assinatura:
            logger.warning(
                "Pagamento recebido sem assinatura "
                f"identificável: {payment_id}"
            )
            return False

        status_map = {
            "PAYMENT_CREATED": "PENDING",
            "PAYMENT_CONFIRMED": "CONFIRMED",
            "PAYMENT_RECEIVED": "RECEIVED",
            "PAYMENT_OVERDUE": "OVERDUE",
            "PAYMENT_REFUNDED": "REFUNDED",
            "PAYMENT_DELETED": "DELETED",
        }

        status = status_map.get(event_type)

        if not status:
            return False

        defaults = {
            "assinatura": assinatura,
            "status": status,
        }

        if payment.get("value") is not None:
            defaults["valor"] = payment["value"]

        if payment.get("dueDate"):
            defaults["data_vencimento"] = payment["dueDate"]

        # Se o pagamento foi recebido, guarda também a data.
        if event_type == "PAYMENT_RECEIVED":
            defaults["recebido_em"] = payment.get(
                "paymentDate"
            ) or payment.get(
                "confirmedDate"
            )

        PagamentoAsaas.objects.update_or_create(
            asaas_payment_id=payment_id,
            defaults=defaults,
        )

        # Somente RECEIVED torna a assinatura ACTIVE.
        #
        # OVERDUE, REFUNDED e DELETED são estados da cobrança,
        # não cancelamento automático da assinatura.
        if event_type == "PAYMENT_RECEIVED":
            cls._activate_subscription(assinatura)

        return True

    @classmethod
    def _get_assinatura_from_payment(cls, payment):
        subscription_id = payment.get("subscription")

        # Caminho preferencial:
        # payment.subscription → Assinatura
        if subscription_id:
            assinatura = (
                Assinatura.objects
                .select_for_update()
                .filter(
                    asaas_subscription_id=subscription_id
                )
                .first()
            )

            if assinatura:
                return assinatura

        # Fallback para pagamentos antigos ou payloads
        # que não tragam subscription.
        customer_id = payment.get("customer")

        if not customer_id:
            return None

        usuario = (
            User.objects
            .filter(asaas_customer_id=customer_id)
            .first()
        )

        if not usuario:
            logger.warning(
                "Usuário não encontrado para "
                f"asaas_customer_id={customer_id}"
            )
            return None

        assinatura, _ = (
            Assinatura.objects
            .select_for_update()
            .get_or_create(usuario=usuario)
        )

        return assinatura

    @classmethod
    def _activate_subscription(cls, assinatura):
        # Uma assinatura cancelada não é ressuscitada
        # por um evento de pagamento.
        if assinatura.status == "CANCELLED":
            return

        assinatura.status = "ACTIVE"
        assinatura.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

    # ==========================================================
    # ASSINATURAS
    # ==========================================================

    @classmethod
    def _handle_subscription(
        cls,
        event_type,
        subscription,
    ):
        subscription_id = subscription.get("id")

        if not subscription_id:
            return False

        customer_id = subscription.get("customer")

        usuario = None

        if customer_id:
            usuario = (
                User.objects
                .filter(
                    asaas_customer_id=customer_id
                )
                .first()
            )

        if not usuario:
            logger.warning(
                "Usuário não encontrado para assinatura "
                f"{subscription_id}"
            )
            return False

        assinatura, _ = (
            Assinatura.objects
            .select_for_update()
            .get_or_create(
                usuario=usuario,
                defaults={
                    "asaas_subscription_id": subscription_id,
                },
            )
        )

        # Garante que o ID da assinatura esteja sincronizado.
        if (
            assinatura.asaas_subscription_id
            != subscription_id
        ):
            assinatura.asaas_subscription_id = (
                subscription_id
            )

        # Cancelamento explícito da assinatura.
        if event_type in (
            "SUBSCRIPTION_INACTIVATED",
            "SUBSCRIPTION_DELETED",
        ):
            assinatura.status = "CANCELLED"

        # Criação/atualização:
        # usamos o status informado pelo próprio Asaas,
        # quando ele existir e for compatível.
        elif event_type in (
            "SUBSCRIPTION_CREATED",
            "SUBSCRIPTION_UPDATED",
        ):
            asaas_status = subscription.get("status")

            if asaas_status == "ACTIVE":
                assinatura.status = "ACTIVE"

            elif asaas_status in (
                "INACTIVE",
                "CANCELLED",
            ):
                assinatura.status = "CANCELLED"

        assinatura.save(
            update_fields=[
                "asaas_subscription_id",
                "status",
                "atualizado_em",
            ]
        )

        return True
