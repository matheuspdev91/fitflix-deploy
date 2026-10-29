class AsaasError(Exception):
    """Erro base da integração com o Asaas."""


class AsaasAuthenticationError(AsaasError):
    """Erro de autenticação com a API do Asaas."""


class AsaasAPIError(AsaasError):
    """Erro retornado pela API do Asaas."""