from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import PerfilDeTeste


class PerfilDeTesteModelTests(TestCase):
    """Testes unitários do modelo PerfilDeTeste."""

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="professor01",
            email="professor@example.com",
            password="SenhaTeste123",
            tipo_usuario="PERSONAL",
        )
        self.now = timezone.now()
        self.iniciado_em = self.now - timedelta(days=2)

    def test_criacao_de_perfil_de_teste(self):
        """1. Criação de PerfilDeTeste."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertIsNotNone(perfil.pk)
        self.assertEqual(perfil.usuario, self.usuario)
        self.assertEqual(perfil.status, "ATIVO")
        self.assertEqual(perfil.iniciado_em, self.iniciado_em)
        self.assertEqual(perfil.expira_em, self.iniciado_em + timedelta(days=7))

    def test_associacao_correta_com_usuario(self):
        """2. Associação correta com Usuario."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertEqual(perfil.usuario, self.usuario)
        self.assertEqual(perfil.usuario_id, self.usuario.pk)

    def test_valores_validos_de_status(self):
        """3. Valores válidos de status."""
        for status in ["ATIVO", "CONVERTIDO", "ENCERRADO", "CANCELADO"]:
            usuario = get_user_model().objects.create_user(
                username=f"professor_status_{status}",
                email=f"{status.lower()}@example.com",
                password="SenhaTeste123",
                tipo_usuario="PERSONAL",
            )
            perfil = PerfilDeTeste.objects.create(
                usuario=usuario,
                status=status,
                iniciado_em=self.iniciado_em,
                expira_em=self.iniciado_em + timedelta(days=7),
            )
            self.assertEqual(perfil.status, status)

    def test_campos_opcionais_inicialmente_nulos(self):
        """4. Campos opcionais inicialmente nulos."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertIsNone(perfil.finalizado_em)
        self.assertIsNone(perfil.convertido_em)

    def test_expiracao_calculada_corretamente_em_relacao_ao_inicio(self):
        """5. Expiração calculada corretamente em relação ao início."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertEqual(
            perfil.expira_em,
            self.iniciado_em + timedelta(days=7),
        )

    def test_impedimento_de_dois_perfis_de_teste_para_o_mesmo_usuario(self):
        """6. Impedimento de dois perfis de teste para o mesmo usuário."""
        PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        with self.assertRaises(Exception):
            PerfilDeTeste.objects.create(
                usuario=self.usuario,
                status="ATIVO",
                iniciado_em=self.iniciado_em,
                expira_em=self.iniciado_em + timedelta(days=7),
            )

    def test_protecao_contra_exclusao_do_usuario_com_historico(self):
        """7. Proteção contra exclusão do usuário com histórico de teste."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertTrue(PerfilDeTeste.objects.filter(pk=perfil.pk).exists())
        with self.assertRaises(Exception):
            self.usuario.delete()
        self.assertTrue(PerfilDeTeste.objects.filter(pk=perfil.pk).exists())

    def test_preservacao_do_registro_apos_mudanca_de_status(self):
        """8. Preservação do registro após mudança de status."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        perfil.status = "ENCERRADO"
        perfil.save()
        perfil.refresh_from_db()
        self.assertEqual(perfil.status, "ENCERRADO")
        self.assertTrue(PerfilDeTeste.objects.filter(pk=perfil.pk).exists())

    def test_relacionamento_reverso_usuario_perfil_de_teste(self):
        """9. Relacionamento reverso usuario.perfil_de_teste."""
        perfil = PerfilDeTeste.objects.create(
            usuario=self.usuario,
            status="ATIVO",
            iniciado_em=self.iniciado_em,
            expira_em=self.iniciado_em + timedelta(days=7),
        )
        self.assertEqual(self.usuario.perfil_de_teste, perfil)
        self.assertEqual(perfil.usuario.perfil_de_teste, perfil)