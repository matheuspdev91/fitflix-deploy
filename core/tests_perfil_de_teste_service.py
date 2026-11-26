from datetime import timedelta, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from core.models import Assinatura, PerfilDeTeste
from core.services.perfil_de_teste_service import PerfilDeTesteService

service = PerfilDeTesteService()


TEST_LAUNCH_AT_PAST = timezone.make_aware(
    datetime(2020, 1, 1, 0, 0, 0),
    timezone.get_current_timezone(),
)


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=TEST_LAUNCH_AT_PAST)
class PerfilDeTesteServiceElegibilidadeTests(TestCase):
    """Cenários de elegibilidade."""

    def setUp(self):
        self.usuario_personal = get_user_model().objects.create_user(
            username="personal_teste@example.com",
            email="personal_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        self.usuario_aluno = get_user_model().objects.create_user(
            username="aluno_teste@example.com",
            email="aluno_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
        )
        self.usuario_admin = get_user_model().objects.create_user(
            username="admin_teste@example.com",
            email="admin_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
        )

    def test_personal_elegivel(self):
        """1. PERSONAL elegível."""
        self.assertTrue(service.elegivel(self.usuario_personal))

    def test_aluno_nao_elegivel(self):
        """2. ALUNO não elegível."""
        self.assertFalse(service.elegivel(self.usuario_aluno))

    def test_admin_nao_elegivel(self):
        """3. ADMIN não elegível."""
        self.assertFalse(service.elegivel(self.usuario_admin))

    def test_usuario_inativo_nao_elegivel(self):
        """4. Usuário inativo não elegível."""
        usuario = get_user_model().objects.create_user(
            username="inativo@example.com",
            email="inativo@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        usuario.is_active = False
        usuario.save(update_fields=["is_active"])
        self.assertFalse(service.elegivel(usuario))

    def test_personal_com_perfil_anterior_nao_elegivel(self):
        """5. PERSONAL com PerfilDeTeste anterior não elegível."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=timezone.now() - timedelta(days=2),
            expira_em=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(service.elegivel(self.usuario_personal))
        perfil.delete()

    def test_personal_com_assinatura_active_nao_elegivel(self):
        """6. PERSONAL com assinatura ACTIVE não elegível."""
        Assinatura.objects.create(
            usuario=self.usuario_personal,
            asaas_subscription_id="sub_test",
            plano="MENSAL",
            status="ACTIVE",
        )
        self.assertFalse(service.elegivel(self.usuario_personal))


@override_settings(FITFLIX_TRIAL_LAUNCH_AT=TEST_LAUNCH_AT_PAST)
class PerfilDeTesteServiceInicioTests(TestCase):
    """Cenários de início do trial."""

    def setUp(self):
        self.usuario_personal = get_user_model().objects.create_user(
            username="personal_teste@example.com",
            email="personal_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )

    def test_criacao_correta_do_teste(self):
        """7. Criação correta do teste."""
        perfil = service.iniciar_trial(self.usuario_personal)
        self.assertIsNotNone(perfil.pk)
        self.assertEqual(perfil.usuario, self.usuario_personal)
        self.assertEqual(perfil.status, "ATIVO")
        self.assertIsNotNone(perfil.iniciado_em)
        self.assertIsNotNone(perfil.expira_em)
        self.assertIsNone(perfil.finalizado_em)
        self.assertIsNone(perfil.convertido_em)

    def test_duracao_exata_de_sete_dias(self):
        """8. Duração exata de sete dias."""
        perfil = service.iniciar_trial(self.usuario_personal)
        duracao = perfil.expira_em - perfil.iniciado_em
        self.assertEqual(duracao, timedelta(days=7))

    def test_campos_de_encerramento_inicialmente_nulos(self):
        """9. Campos de encerramento inicialmente nulos."""
        perfil = service.iniciar_trial(self.usuario_personal)
        self.assertIsNone(perfil.finalizado_em)
        self.assertIsNone(perfil.convertido_em)

    def test_segunda_tentativa_de_iniciar_rejeitada(self):
        """10. Segunda tentativa de iniciar teste rejeitada."""
        service.iniciar_trial(self.usuario_personal)
        with self.assertRaises(Exception):
            service.iniciar_trial(self.usuario_personal)

    def test_tentativa_com_usuario_nao_elegivel_rejeitada(self):
        """11. Tentativa com usuário não elegível rejeitada."""
        usuario_aluno = get_user_model().objects.create_user(
            username="aluno_exemplo@example.com",
            email="aluno_exemplo@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
        )
        with self.assertRaises(Exception):
            service.iniciar_trial(usuario_aluno)


class PerfilDeTesteServiceValidacaoAcessoTests(TestCase):
    """Cenários de validação de acesso."""

    def setUp(self):
        self.usuario_personal = get_user_model().objects.create_user(
            username="personal_teste@example.com",
            email="personal_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        agora = timezone.now()
        self.agora_dentro = agora - timedelta(hours=1)
        self.agora_expiracao = agora + timedelta(hours=1)
        self.agora_fora = agora + timedelta(days=10)

    def test_ativo_dentro_do_prazo_permite_acesso(self):
        """12. Teste ATIVO dentro do prazo permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora_dentro - timedelta(days=2),
            expira_em=self.agora_dentro + timedelta(days=7),
        )
        self.assertTrue(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_dentro)
        )

    def test_exato_instante_expiracao_nao_permita_acesso(self):
        """13. Teste exatamente no instante da expiração não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora_expiracao - timedelta(days=2),
            expira_em=self.agora_expiracao,
        )
        self.assertFalse(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_expiracao)
        )

    def test_expirado_nao_permita_acesso_mesmo_status_ativo(self):
        """14. Teste expirado não permite acesso mesmo que o status still esteja ATIVO."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora_fora - timedelta(days=2),
            expira_em=self.agora_fora - timedelta(hours=1),
        )
        self.assertFalse(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_fora)
        )

    def test_encerrado_nao_permita_acesso(self):
        """15. Teste ENCERRADO não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ENCERRADO",
            iniciado_em=self.agora_dentro - timedelta(days=2),
            expira_em=self.agora_dentro + timedelta(days=7),
        )
        self.assertFalse(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_dentro)
        )

    def test_cancelado_nao_permita_acesso(self):
        """16. Teste CANCELADO não permite acesso."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CANCELADO",
            iniciado_em=self.agora_dentro - timedelta(days=2),
            expira_em=self.agora_dentro + timedelta(days=7),
        )
        self.assertFalse(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_dentro)
        )

    def test_convertido_nao_conceda_acesso_gratuito(self):
        """17. Teste CONVERTIDO não concede acesso gratuito."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CONVERTIDO",
            iniciado_em=self.agora_dentro - timedelta(days=2),
            expira_em=self.agora_dentro + timedelta(days=7),
        )
        self.assertFalse(
            service.tem_acesso_trial(self.usuario_personal, agora=self.agora_dentro)
        )


class PerfilDeTesteServiceEncerramentoTests(TestCase):
    """Cenários de encerramento."""

    def setUp(self):
        self.usuario_personal = get_user_model().objects.create_user(
            username="personal_teste@example.com",
            email="personal_teste@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        self.agora = timezone.now()

    def test_expirado_encerrado(self):
        """18. Teste expirado é encerrado."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora - timedelta(hours=1),
        )
        resultado = service.encerrar_trial_expirado(
            self.usuario_personal, agora=self.agora
        )
        self.assertEqual(resultado.status, "ENCERRADO")
        self.assertIsNotNone(resultado.finalizado_em)
        self.assertEqual(resultado.iniciado_em, perfil.iniciado_em)
        self.assertEqual(resultado.expira_em, perfil.expira_em)

    def test_valido_nao_encerrado(self):
        """19. Teste ainda válido não é encerrado."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora + timedelta(hours=1),
        )
        with self.assertRaises(Exception):
            service.encerrar_trial_expirado(
                self.usuario_personal, agora=self.agora
            )
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ATIVO")

    def test_convertido_nao_alterado(self):
        """20. Teste CONVERTIDO não é alterado."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CONVERTIDO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora + timedelta(hours=1),
        )
        with self.assertRaises(Exception):
            service.encerrar_trial_expirado(
                self.usuario_personal, agora=self.agora
            )
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CONVERTIDO")

    def test_cancelado_não_alterado(self):
        """21. Teste CANCELADO não é alterado."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="CANCELADO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora + timedelta(hours=1),
        )
        with self.assertRaises(Exception):
            service.encerrar_trial_expirado(
                self.usuario_personal, agora=self.agora
            )
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "CANCELADO")

    def test_execucao_repetida_não_duplica_encerramentos(self):
        """22. Execução repetida não duplica encerramentos."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora - timedelta(hours=1),
        )
        service.encerrar_trial_expirado(
            self.usuario_personal, agora=self.agora
        )
        # Nova execução deve falhar (já está ENCERRADO)
        with self.assertRaises(Exception):
            service.encerrar_trial_expirado(
                self.usuario_personal, agora=self.agora
            )
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ENCERRADO")

    def test_finalizado_em_preenchido_corretamente(self):
        """23. finalizado_em é preenchido corretamente."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora - timedelta(hours=1),
        )
        service.encerrar_trial_expirado(
            self.usuario_personal, agora=self.agora
        )
        perfil.refresh_from_db()
        self.assertIsNotNone(perfil.finalizado_em)
        self.assertLessEqual(perfil.finalizado_em, self.agora)

    def test_expira_em_e_iniciado_em_preservados(self):
        """24. expira_em e iniciado_em permanecem preservados."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario_personal,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora - timedelta(hours=1),
        )
        service.encerrar_trial_expirado(
            self.usuario_personal, agora=self.agora
        )
        perfil.refresh_from_db()
        self.assertEqual(perfil.iniciado_em, self.agora - timedelta(days=2))
        self.assertEqual(perfil.expira_em, self.agora - timedelta(hours=1))

    def test_lote_encerra_somente_expirados(self):
        """Encerramento em lote só aplica a registros elegíveis."""
        usuario_valido = get_user_model().objects.create_user(
            username="personal_validos@example.com",
            email="personal_validos@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        usuario_expirado = get_user_model().objects.create_user(
            username="personal_expirados@example.com",
            email="personal_expirados@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        perfil_valido = PerfilDeTeste.objects.create(
            usuario=usuario_valido,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=2),
            expira_em=self.agora + timedelta(hours=1),
        )
        perfil_expirado = PerfilDeTeste.objects.create(
            usuario=usuario_expirado,
            status="ATIVO",
            iniciado_em=self.agora - timedelta(days=10),
            expira_em=self.agora - timedelta(hours=1),
        )
        encerrados = service.encerrar_trials_expirados(agora=self.agora)

        self.assertEqual(encerrados, 1)
        perfil_valido.refresh_from_db()
        perfil_expirado.refresh_from_db()
        self.assertEqual(perfil_valido.status, "ATIVO")
        self.assertEqual(perfil_expirado.status, "ENCERRADO")

class PerfilDeTesteServiceElegibilidadeComDataCorteTests(TestCase):
    """Cenários de elegibilidade aplicando FITFLIX_TRIAL_LAUNCH_AT."""

    FIXTURE_LAUNCH_AT = timezone.make_aware(
        datetime(2030, 1, 1, 12, 0, 0),
        timezone.get_current_timezone(),
    )

    def setUp(self):
        self.service = PerfilDeTesteService()
        self.personal = get_user_model().objects.create_user(
            username="personal-corte",
            email="personal-corte@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        self.aluno = get_user_model().objects.create_user(
            username="aluno-corte",
            email="aluno-corte@example.com",
            password="SenhaTeste123",
            tipo_usuario="ALUNO",
        )
        self.admin = get_user_model().objects.create_user(
            username="admin-corte",
            email="admin-corte@example.com",
            password="SenhaTeste123",
            tipo_usuario="ADMIN",
        )

    def _make_personal(self, date_joined):
        user = get_user_model().objects.create_user(
            username="personal-{}".format(date_joined.timestamp()),
            email="personal-{}@example.com".format(date_joined.timestamp()),
            password="SenhaTeste123",
        )
        user.date_joined = date_joined
        user.save(update_fields=["date_joined"])
        return user

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_personal_antes_da_data_de_corte_e_elegivel_para_concessao_oficial(self):
        """
        Política aprovada (Missão 03.6.13.1): contas antigas TAMBÉM podem
        receber o primeiro trial, mediante a concessão oficial de
        ativação do lançamento. A data de corte deixou de excluir a conta.
        """
        user = self._make_personal(self.FIXTURE_LAUNCH_AT - timedelta(days=30))
        self.assertTrue(self.service.elegivel(user))
        self.assertEqual(
            self.service.classificar_conta(user),
            PerfilDeTesteService.CONTA_ANTIGA,
        )

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_personal_no_instante_corte_aceito(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT)
        self.assertTrue(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_personal_depois_da_data_de_corte_aceito(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT + timedelta(days=30))
        self.assertTrue(self.service.elegivel(user))

    def test_configuracao_ausente_rejeitado(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT)
        self.assertFalse(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_personal_com_trial_anterior_rejeitado(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT + timedelta(days=30))
        PerfilDeTeste.objects.create(
            usuario=user,
            status="ATIVO",
            iniciado_em=timezone.now() - timedelta(days=5),
            expira_em=timezone.now() + timedelta(days=2),
        )
        self.assertFalse(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_personal_com_assinatura_active_rejeitado(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT + timedelta(days=30))
        Assinatura.objects.create(
            usuario=user,
            asaas_subscription_id="sub_test",
            plano="MENSAL",
            status="ACTIVE",
        )
        self.assertFalse(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_admin_nao_elegivel(self):
        user = self.admin
        self.assertFalse(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_aluno_nao_elegivel(self):
        user = self.aluno
        self.assertFalse(self.service.elegivel(user))

    @override_settings(FITFLIX_TRIAL_LAUNCH_AT=FIXTURE_LAUNCH_AT)
    def test_usuario_inativo_rejeitado(self):
        user = self._make_personal(self.FIXTURE_LAUNCH_AT + timedelta(days=30))
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertFalse(self.service.elegivel(user))