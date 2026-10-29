import os
import requests

from .exceptions import AsaasAPIError, AsaasAuthenticationError


class AsaasClient:
    """Client HTTP para comunicação com API do Asaas"""

    def __init__(self):
        self.environment = os.environ.get("ASAAS_ENVIRONMENT", "sandbox")

        if self.environment == "production":
            self.api_key = os.environ.get("ASAAS_PRODUCTION_API_KEY")
            self.base_url = "https://api.asaas.com/v3"
        else:
            self.api_key = os.environ.get("ASAAS_SANDBOX_API_KEY")
            self.base_url = "https://api-sandbox.asaas.com/v3"

        if not self.api_key:
            raise RuntimeError(
                f"API KEY do Asaas não configurada para o ambiente: "
                f"{self.environment}"
            )

        self.headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Fitflix/1.0",
        }

    def _request(self, method, endpoint, **kwargs):
        """Wrapper interno para tratar erros da API e requests."""
        kwargs.setdefault("timeout", 10)
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            if response.status_code == 401:
                raise AsaasAuthenticationError("Não autorizado. Verifique a API Key.")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, "response") and e.response is not None:
                raise AsaasAPIError(f"Erro na API do Asaas: {e.response.text}")
            raise AsaasAPIError(f"Erro de comunicação com Asaas: {str(e)}")

    def get_account(self):
        """Retorna os dados da conta autenticada no Asaas"""
        return self._request("GET", "/myAccount")

    def create_customer(self, data):
        """Cria um cliente no Asaas"""
        return self._request("POST", "/customers", json=data)

    def create_payment(self, data):
        """Cria uma cobrança no Asaas"""
        return self._request("POST", "/payments", json=data)

    def create_subscription(self, data):
        """Cria uma assinatura recorrente no Asaas."""
        return self._request("POST", "/subscriptions", json=data)

    def get_payment(self, payment_id):
        """Retorna detalhes de um pagamento pelo ID."""
        return self._request("GET", f"/payments/{payment_id}")
