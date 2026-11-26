"""
Serviço de concessão do trial de 7 dias para profissionais (PERSONAL).

Política comercial implementada:

- Cada profissional PERSONAL elegível recebe apenas um trial;
- duração exata de 7 dias (expira_em = iniciado_em + timedelta(days=7));
- contas novas (cadastradas a partir do lançamento oficial) recebem o trial
  na conclusão do cadastro;
- contas antigas (cadastradas antes do lançamento oficial) recebem o primeiro
  trial durante a ativação oficial do lançamento;
- contas com trial anterior (qualquer status) não recebem outro trial;
- usuários com assinatura ACTIVE não recebem trial;
- ADMIN e ALUNO não recebem trial;
- usuários inativos não recebem trial;
- o encerramento do trial nunca apaga dados.

Fail-safe de configuração:
- `settings.FITFLIX_TRIAL_LAUNCH_AT` ausente ou None => ninguém recebe trial.
- A data oficial de lançamento NÃO é definida por este módulo.

Todas as datas persistidas e comparadas são timezone-aware.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import Assinatura, PerfilDeTeste


class ErroTrial(ValueError):
    """Base dos erros de domínio do serviço de trial."""


class TrialInelegivelError(ErroTrial):
    """O usuário não cumpre os requisitos de elegibilidade."""


class TrialAindaNaoLiberadoError(TrialInelegivelError):
    """
    O lançamento oficial ainda não ocorreu: o cadastro é permitido, mas a
    concessão do trial só poderá acontecer a partir da ativação oficial.

    Diferente de uma falha técnica, este erro NÃO invalida a criação da
    conta: o profissional conclude o cadastro normalmente e receberá o
    primeiro trial na concessão oficial (trilha de conta antiga).
    """


class TrialJaConcedidoError(TrialInelegivelError):
    """O usuário já possui um PerfilDeTeste; nenhum novo trial é criado."""


class PerfilDeTesteService:
    """
    Gestão do período de teste gratuito de 7 dias para profissionais
    (tipo_usuario=PERSONAL).

    Responsabilidades:
    - validar a elegibilidade do usuário;
    - criar e iniciar o trial de forma atômica;
    - verificar se o profissional possui acesso durante o trial;
    - encerrar trials expirados individualmente ou em lote.
    """

    DURACAO_DIAS = 7

    STATUS_ATIVO = "ATIVO"
    STATUS_CONVERTIDO = "CONVERTIDO"
    STATUS_ENCERRADO = "ENCERRADO"
    STATUS_CANCELADO = "CANCELADO"

    STATUS_CHOICES = (
        (STATUS_ATIVO, "Ativo"),
        (STATUS_CONVERTIDO, "Convertido"),
        (STATUS_ENCERRADO, "Encerrado"),
        (STATUS_CANCELADO, "Cancelado"),
    )

    # Status terminais: o trial não pode ser reutilizado.
    STATUS_TERMINAIS = (STATUS_ENCERRADO, STATUS_CANCELADO, STATUS_CONVERTIDO)

    # Classificação de conta em relação ao lançamento oficial.
    CONTA_NOVA = "NOVA"
    CONTA_ANTIGA = "ANTIGA"

    def __init__(self, modelo=PerfilDeTeste):
        self.modelo = modelo

    # ------------------------------------------------------------------
    # CONFIGURAÇÃO / LANÇAMENTO OFICIAL
    # ------------------------------------------------------------------

    @staticmethod
    def lancamento_oficial():
        """
        Retorna o instante (timezone-aware) do lançamento oficial do trial,
        ou None quando o lançamento ainda não foi oficialmente ativado.

        Fail-safe: chave ausente ou None => lançamento inativo.
        """
        launch_at = getattr(settings, "FITFLIX_TRIAL_LAUNCH_AT", None)
        if launch_at is None:
            return None
        if timezone.is_naive(launch_at):
            launch_at = timezone.make_aware(launch_at)
        return launch_at

    # ------------------------------------------------------------------
    # ELEGIBILIDADE (regra única, centralizada)
    # ------------------------------------------------------------------

    def elegivel(self, usuario):
        """
        Verifica se o usuário pode receber o período de teste.

        Regras:
        - usuário autenticado;
        - tipo_usuario == PERSONAL;
        - conta ativa (is_active=True);
        - lançamento oficial ativado (FITFLIX_TRIAL_LAUNCH_AT definido);
        - nenhum PerfilDeTeste existente para o usuário (trial anterior,
          encerrado, cancelado ou convertido bloqueia nova concessão);
        - nenhuma assinatura ACTIVE.

        A data de cadastro do usuário NÃO exclui a conta: contas antigas
        podem receber o primeiro trial na ativação oficial.
        """
        if not usuario or not getattr(usuario, "is_authenticated", False):
            return False

        if getattr(usuario, "tipo_usuario", None) != "PERSONAL":
            return False

        if not usuario.is_active:
            return False

        if self.lancamento_oficial() is None:
            return False

        if self.modelo.objects.filter(usuario=usuario).exists():
            return False

        assinatura = Assinatura.objects.filter(usuario=usuario).first()
        if assinatura and assinatura.status == "ACTIVE":
            return False

        return True

    def classificar_conta(self, usuario):
        """
        Classifica a conta em relação ao lançamento oficial:

        - NOVA: cadastrada no instante do lançamento ou depois;
        - ANTIGA: cadastrada antes do lançamento oficial.

        Sem lançamento oficial ativado, a classificação é indefinida e
        retorna None.
        """
        launch_at = self.lancamento_oficial()
        if launch_at is None:
            return None

        date_joined = getattr(usuario, "date_joined", None)
        if date_joined is None:
            return None
        if timezone.is_naive(date_joined):
            date_joined = timezone.make_aware(date_joined)

        if date_joined < launch_at:
            return self.CONTA_ANTIGA
        return self.CONTA_NOVA

    # ------------------------------------------------------------------
    # CONCESSÃO
    # ------------------------------------------------------------------

    def conceder_trial_novo_cadastro(self, usuario, agora=None):
        """
        Concede o trial a um profissional recém-cadastrado (conta NOVA).

        Regras:
        - o lançamento oficial precisa estar ativado;
        - a conta precisa ser NOVA (cadastrada no lançamento ou depois);
        - a concessão só acontece a partir do instante do lançamento;
        - o usuário precisa ser elegível (regra única de elegibilidade);
        - não pode existir trial anterior;
        - duração exata de 7 dias, com datas timezone-aware.
        """
        agora = self._agora(agora)
        launch_at = self.lancamento_oficial()

        if launch_at is None:
            raise TrialInelegivelError(
                "Lançamento oficial do trial não ativado "
                "(FITFLIX_TRIAL_LAUNCH_AT ausente ou None)."
            )

        if agora < launch_at:
            raise TrialAindaNaoLiberadoError(
                "A concessão de trial só é permitida a partir do "
                "lançamento oficial."
            )

        if self.classificar_conta(usuario) != self.CONTA_NOVA:
            raise TrialInelegivelError(
                "Conta não é nova; use a concessão de conta antiga."
            )

        return self._conceder(usuario, agora)

    def conceder_trial_conta_antiga(self, usuario, agora=None):
        """
        Concede o primeiro trial a uma conta ANTIGA durante a ativação
        oficial do lançamento.

        Regras:
        - o lançamento oficial precisa estar ativado;
        - a conta precisa ser ANTIGA (cadastrada antes do lançamento);
        - a concessão só acontece a partir do instante do lançamento;
        - o usuário precisa ser elegível (regra única de elegibilidade);
        - não pode existir trial anterior;
        - duração exata de 7 dias, com datas timezone-aware.

        O trial começa no instante da concessão (na ativação oficial, esse
        instante coincide com o lançamento). A expiração é sempre
        iniciado_em + timedelta(days=7).
        """
        agora = self._agora(agora)
        launch_at = self.lancamento_oficial()

        if launch_at is None:
            raise TrialInelegivelError(
                "Lançamento oficial do trial não ativado "
                "(FITFLIX_TRIAL_LAUNCH_AT ausente ou None)."
            )

        if agora < launch_at:
            raise TrialAindaNaoLiberadoError(
                "A concessão de trial só é permitida a partir do "
                "lançamento oficial."
            )

        if self.classificar_conta(usuario) != self.CONTA_ANTIGA:
            raise TrialInelegivelError(
                "Conta não é antiga; use a concessão de novo cadastro."
            )

        return self._conceder(usuario, agora)

    def conceder_trial(self, usuario, agora=None):
        """
        Concede o trial conforme a classificação da conta: contas NOVA
        seguem a trilha de novo cadastro; contas ANTIGA seguem a trilha
        de ativação oficial.
        """
        agora = self._agora(agora)
        classificacao = self.classificar_conta(usuario)

        if classificacao == self.CONTA_NOVA:
            return self.conceder_trial_novo_cadastro(usuario, agora=agora)
        if classificacao == self.CONTA_ANTIGA:
            return self.conceder_trial_conta_antiga(usuario, agora=agora)

        raise TrialInelegivelError(
            "Não foi possível classificar a conta em relação ao lançamento "
            "oficial do trial."
        )

    def iniciar_trial(self, usuario):
        """
        Mantido por compatibilidade com as chamadas existentes: concede o
        trial conforme a classificação da conta. Para chamadas explícitas,
        prefira `conceder_trial_novo_cadastro` ou
        `conceder_trial_conta_antiga`.
        """
        return self.conceder_trial(usuario)

    # ------------------------------------------------------------------
    # RELÓGIO (indireção testável)
    # ------------------------------------------------------------------

    @staticmethod
    def instante_referencia():
        """
        Instante atual usado como referência de tempo pelo serviço.

        Existe como ponto único de indireção para que os testes possam
        fixar o relógio sem alterar globalmente `django.utils.timezone`
        (o que afetaria, por exemplo, a expiração de sessões do Django).
        """
        return timezone.now()

    # ------------------------------------------------------------------
    # INTERNOS
    # ------------------------------------------------------------------

    @staticmethod
    def _agora(agora=None):
        """Retorna um instante timezone-aware."""
        if agora is None:
            return PerfilDeTesteService.instante_referencia()
        if timezone.is_naive(agora):
            return timezone.make_aware(agora)
        return agora

    def _conceder(self, usuario, agora):
        """
        Cria o PerfilDeTeste de forma segura.

        - a elegibilidade é avaliada uma única vez, aqui;
        - a linha do usuário é bloqueada (select_for_update) para
          serializar concessões concorrentes do mesmo usuário;
        - a criação usa get_or_create, que trata a corrida de criação
          de registro inexistente capturando o IntegrityError do OneToOne;
        - uma tentativa duplicada nunca propaga IntegrityError bruto
          (que viraria erro 500 em uma view), e sim TrialJaConcedidoError.
        """
        if self.modelo.objects.filter(usuario=usuario).exists():
            # Um trial anterior (ATIVO, ENCERRADO, CANCELADO ou CONVERTIDO)
            # impede qualquer nova concessão.
            raise TrialJaConcedidoError(
                "O usuário já possui um teste; nenhum novo trial é "
                "concedido."
            )

        if not self.elegivel(usuario):
            raise TrialInelegivelError(
                "Não é possível iniciar o teste: o usuário não é elegível."
            )

        expira_em = agora + timedelta(days=self.DURACAO_DIAS)

        with transaction.atomic():
            # Bloqueia a conta do usuário (registro existente): serializa
            # duas concessões simultâneas para o mesmo profissional.
            usuario_pk = getattr(usuario, "pk", None)
            if usuario_pk is not None:
                get_user_model().objects.select_for_update().filter(
                    pk=usuario_pk
                ).first()

            # Reavalia a elegibilidade dentro da transação: o trial pode
            # ter sido criado por outra transação entre a checagem e o lock.
            if self.modelo.objects.filter(usuario=usuario).exists():
                raise TrialJaConcedidoError(
                    "O usuário já possui um teste; nenhum novo trial é "
                    "concedido."
                )

            try:
                # Savepoint próprio: um IntegrityError aqui não invalida a
                # transação externa.
                with transaction.atomic():
                    perfil, criado = self.modelo.objects.get_or_create(
                        usuario=usuario,
                        defaults={
                            "status": self.STATUS_ATIVO,
                            "iniciado_em": agora,
                            "expira_em": expira_em,
                            "finalizado_em": None,
                            "convertido_em": None,
                        },
                    )
            except IntegrityError:
                # Corrida de criação: outra transação gravou o registro
                # OneToOne. Recupera o perfil existente e sinaliza a
                # duplicidade como erro de domínio, nunca como 500.
                existente = self.modelo.objects.filter(usuario=usuario).first()
                if existente is not None:
                    raise TrialJaConcedidoError(
                        "O usuário já possui um teste; nenhum novo trial é "
                        "concedido."
                    )
                raise

            if not criado:
                raise TrialJaConcedidoError(
                    "O usuário já possui um teste; nenhum novo trial é "
                    "concedido."
                )

        return perfil

    # ------------------------------------------------------------------
    # VALIDAÇÃO DE ACESSO
    # ------------------------------------------------------------------

    def tem_acesso_trial(self, usuario, agora=None):
        """
        Verifica se o profissional possui acesso gratuito no instante
        indicado.

        Acesso permitido quando:
        - existe PerfilDeTeste;
        - status == ATIVO;
        - agora < expira_em.

        Parâmetros:
        - agora: instante opcional para testes determinísticos.
        """
        if agora is None:
            agora = timezone.now()

        perfil = self.modelo.objects.filter(usuario=usuario).first()
        if perfil is None:
            return False

        if perfil.status != self.STATUS_ATIVO:
            return False

        if agora >= perfil.expira_em:
            return False

        return True

    # ------------------------------------------------------------------
    # ENCERRAMENTO INDIVIDUAL
    # ------------------------------------------------------------------

    @transaction.atomic
    def encerrar_trial_expirado(self, usuario, agora=None):
        """
        Encerra um trial expirado.

        Regras:
        - somente status ATIVO pode ser encerrado;
        - agora >= expira_em;
        - define status para ENCERRADO;
        - define finalizado_em;
        - preserva iniciado_em e expira_em.
        """
        if agora is None:
            agora = timezone.now()

        perfil = self.modelo.objects.select_for_update().filter(
            usuario=usuario,
            status=self.STATUS_ATIVO,
        ).first()

        if perfil is None:
            raise ValueError(
                "Não há trial ATIVO para o usuário para encerrar."
            )

        if agora < perfil.expira_em:
            raise ValueError(
                "O trial ainda não expirou; não é possível encerrar."
            )

        perfil.status = self.STATUS_ENCERRADO
        perfil.finalizado_em = agora
        perfil.save(update_fields=["status", "finalizado_em"])

        return perfil

    # ------------------------------------------------------------------
    # CONVERSÃO POR PAGAMENTO
    # ------------------------------------------------------------------

    @transaction.atomic
    def converter_por_pagamento(self, usuario, agora=None):
        """
        Converte o trial do profissional em uma assinatura paga.

        Chamado exclusivamente a partir do fluxo de webhook
        `PAYMENT_RECEIVED` (ver core/services/asaas/webhook_handler.py).

        Regras de transição:

        - não existe PerfilDeTeste => nada acontece (o trial não é
          criado por esta via);
        - status ATIVO e agora < expira_em => status = CONVERTIDO,
          com `convertido_em` e `finalizado_em` iguais ao instante de
          referência;
        - status ATIVO e agora >= expira_em => status = ENCERRADO,
          com `finalizado_em` igual ao instante de referência e
          `convertido_em` preservado (não preenchido). O trial não é
          reaberto;
        - status ENCERRADO, CANCELADO ou CONVERTIDO => o registro é
          imutável e nada é alterado.

        O método é idempotente por estado: chamadas repetidas não
        provocam nova conversão nem alteram os carimbos de tempo.

        Retorna o PerfilDeTeste resultante ou None quando o usuário
        não possui trial.
        """
        agora = self._agora(agora)

        # O PerfilDeTeste é a chave primária (OneToOne): quando existe,
        # select_for_update serializa conversões concorrentes do mesmo
        # usuário. Quando não existe, nada é criado.
        perfil = (
            self.modelo.objects
            .select_for_update()
            .filter(usuario=usuario)
            .first()
        )

        if perfil is None:
            return None

        # Estados terminais são imutáveis.
        if perfil.status != self.STATUS_ATIVO:
            return perfil

        if agora < perfil.expira_em:
            perfil.status = self.STATUS_CONVERTIDO
            perfil.convertido_em = agora
            perfil.finalizado_em = agora
            perfil.save(
                update_fields=[
                    "status",
                    "convertido_em",
                    "finalizado_em",
                ]
            )
            return perfil

        # Trial vencido: encerra sem converter e sem reabrir.
        perfil.status = self.STATUS_ENCERRADO
        perfil.finalizado_em = agora
        perfil.save(
            update_fields=[
                "status",
                "finalizado_em",
            ]
        )
        return perfil

    # ------------------------------------------------------------------
    # ENCERRAMENTO EM LOTE
    # ------------------------------------------------------------------

    @transaction.atomic
    def encerrar_trials_expirados(self, agora=None):
        """
        Encerra todos os trials ATIVOS com expira_em <= agora.

        A operação é idempotente: registros que já estavam ENCERRADOS
        ou CONVERTIDOS/CANCELADOS não são alterados.

        Retorna a quantidade de registros efetivamente encerrados.
        """
        if agora is None:
            agora = timezone.now()

        queryset = self.modelo.objects.filter(
            status=self.STATUS_ATIVO,
            expira_em__lte=agora,
        )

        updated = queryset.update(
            status=self.STATUS_ENCERRADO,
            finalizado_em=agora,
        )

        return updated