from datetime import date, timedelta
from decimal import Decimal


from django.db import transaction

from .client import AsaasClient
from core.models import Assinatura


PLANOS = {
    "MENSAL": {
        "value": Decimal("60.00"),
        "cycle": "MONTHLY",
        "description": "Fitflix - Plano Mensal",
    },
    "ANUAL": {
        "value": Decimal("500.00"),
        "cycle": "YEARLY",
        "description": "Fitflix - Plano Anual",
    },
}


class SubscriptionService:
    """
    Orquestra a criação de assinaturas do Fitflix no Asaas.

    Responsabilidades:
    - validar o plano;
    - garantir que o usuário tenha Customer no Asaas;
    - criar a assinatura recorrente;
    - salvar o ID retornado pelo Asaas;
    - manter a assinatura do Fitflix como PENDING.
    """

    def __init__(self, client=None):
        self.client = client or AsaasClient()

    @transaction.atomic
    def create_subscription(
        self,
        user,
        plano,
        customer_data=None,
        billing_type="PIX",
        next_due_date=None,
    ):
        plano = plano.upper()

        if plano not in PLANOS:
            raise ValueError(
                f"Plano inválido: {plano}"
            )

        config = PLANOS[plano]

        if config["value"] is None:
            raise ValueError(
                f"O plano {plano} ainda não possui preço configurado."
            )

        # Não permite criar outra assinatura enquanto
        # já existe uma assinatura pendente ou ativa.
        assinatura = (
            Assinatura.objects
            .filter(usuario=user)
            .first()
        )

        if assinatura and assinatura.status in (
            "PENDING",
            "ACTIVE",
        ):
            raise ValueError(
                "Usuário já possui uma assinatura ativa "
                "ou pendente."
            )

        # --------------------------------------------------
        # CUSTOMER ASAAS
        # --------------------------------------------------

        customer_id = getattr(
            user,
            "asaas_customer_id",
            None,
        )

        if not customer_id:
            if not customer_data:
                raise ValueError(
                    "customer_data é obrigatório para criar "
                    "um novo cliente no Asaas."
                )

            customer_payload = dict(customer_data)

            customer_payload.setdefault(
                "externalReference",
                str(user.pk),
            )

            customer = self.client.create_customer(
                customer_payload
            )

            customer_id = customer.get("id")

            if not customer_id:
                raise ValueError(
                    "Asaas não retornou o ID do cliente."
                )

            user.asaas_customer_id = customer_id
            user.save(
                update_fields=["asaas_customer_id"]
            )

        # --------------------------------------------------
        # DATA DA PRIMEIRA COBRANÇA
        # --------------------------------------------------

        if next_due_date is None:
            next_due_date = date.today() + timedelta(
                days=1
            )

        if isinstance(next_due_date, date):
            next_due_date = next_due_date.isoformat()

        # --------------------------------------------------
        # ASSINATURA ASAAS
        # --------------------------------------------------

        subscription_payload = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": float(config["value"]),
            "cycle": config["cycle"],
            "nextDueDate": next_due_date,
            "description": config["description"],
            "externalReference": f"fitflix-user-{user.pk}",
        }

        response = self.client.create_subscription(
            subscription_payload
        )

        subscription_id = response.get("id")

        if not subscription_id:
            raise ValueError(
                "Asaas não retornou o ID da assinatura."
            )

        # --------------------------------------------------
        # FITFLIX
        # --------------------------------------------------

        if assinatura:
            assinatura.asaas_subscription_id = (
                subscription_id
            )
            assinatura.plano = plano
            assinatura.status = "PENDING"

            assinatura.save(
                update_fields=[
                    "asaas_subscription_id",
                    "plano",
                    "status",
                    "atualizado_em",
                ]
            )

        else:
            assinatura = Assinatura.objects.create(
                usuario=user,
                asaas_subscription_id=subscription_id,
                plano=plano,
                status="PENDING",
            )

        return assinatura, response
