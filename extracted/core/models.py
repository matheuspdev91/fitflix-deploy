from django.contrib.auth import models
from datetime import date
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


# ========================
# USUÁRIO
# ========================
class Usuario(AbstractUser):

    TIPO_CHOICES = (
        ("ADMIN", "Administrador"),
        ("PERSONAL", "Personal"),
        ("ALUNO", "Aluno"),
    )

    email = models.EmailField(unique=True)
    cref = models.CharField(max_length=20, blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    asaas_customer_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )

    tipo_usuario = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="PERSONAL",
)

    


# ========================
# AVALIAÇÃO BASE
# ========================
class AvaliacaoFisica(models.Model):
    SEXO_CHOICES = (
        ("M", "Masculino"),
        ("F", "Feminino"),
    )

    data = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    nome = models.CharField(max_length=100)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    data_nascimento = models.DateField()

    altura = models.DecimalField(max_digits=4, decimal_places=2)
    peso = models.DecimalField(max_digits=5, decimal_places=2)

    objetivo = models.TextField(blank=True)
    percentual_gordura = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - {self.criado_em.strftime('%d/%m/%Y')}"

    @property
    def idade(self):
        hoje = date.today()
        return (
            hoje.year
            - self.data_nascimento.year
            - (
                (hoje.month, hoje.day)
                < (self.data_nascimento.month, self.data_nascimento.day)
            )
        )

    @property
    def imc(self):
        try:
            return round(float(self.peso) / (float(self.altura) ** 2), 2)
        except:
            return None


# ========================
# CIRCUNFERÊNCIAS
# ========================
class Circunferencia(models.Model):
    avaliacao = models.OneToOneField(
        AvaliacaoFisica, on_delete=models.CASCADE, related_name="circunferencias"
    )

    ombros = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    torax = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    cintura = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    abdome = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    quadril = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    braco_direito = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    braco_esquerdo = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    coxa_direita = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    coxa_esquerda = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    panturrilha_direita = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    panturrilha_esquerda = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )


# ========================
# ADIPOMETRIA
# ========================
class Adipometria(models.Model):
    avaliacao = models.OneToOneField(
        AvaliacaoFisica, on_delete=models.CASCADE, related_name="adipometria"
    )

    tricipital = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    subescapular = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    supra_iliaca = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    abdominal = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    coxa = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    peito = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    axilar_media = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"Adipometria - Avaliação {self.avaliacao.id}"


# ========================
# CRIANÇA
# ========================
class AvaliacaoCrianca(models.Model):
    avaliacao = models.OneToOneField(
        AvaliacaoFisica, on_delete=models.CASCADE, related_name="crianca"
    )

    coordenacao = models.CharField(max_length=20)
    equilibrio_segundos = models.FloatField()
    flexoes = models.IntegerField()
    agilidade_tempo = models.FloatField()
    salto_horizontal = models.FloatField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Criança - {self.avaliacao.nome}"


# ========================
# IDOSO
# ========================
class AvaliacaoIdoso(models.Model):
    avaliacao = models.OneToOneField(
        AvaliacaoFisica, on_delete=models.CASCADE, related_name="idoso"
    )

    sentar_levantar = models.IntegerField()
    tug_tempo = models.FloatField()
    equilibrio_segundos = models.FloatField()
    caminhada_6min = models.IntegerField()

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Idoso - {self.avaliacao.nome}"


# ========================
# ALUNO
# ========================
class Aluno(models.Model):
    personal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alunos",
        null=True,
        blank=True,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField()
    objetivo = models.CharField(max_length=255, blank=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    @property
    def idade(self):
        hoje = date.today()
        return (
            hoje.year
            - self.data_nascimento.year
            - (
                (hoje.month, hoje.day)
                < (self.data_nascimento.month, self.data_nascimento.day)
            )
        )


# ========================
# FITFLIX (VERSÃO ORIGINAL)
# ========================


class GrupoMuscular(models.Model):
    nome = models.CharField(max_length=50)

    def __str__(self):
        return self.nome


class VideoExercicio(models.Model):
    nome = models.CharField(max_length=100)
    grupo_muscular = models.ForeignKey(
    GrupoMuscular, on_delete=models.CASCADE, related_name="exercicios"
    )
    gif = models.FileField(upload_to='gifs/', max_length=300)
    descricao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class VariacaoExercicio(models.Model):
    exercicio = models.ForeignKey(
    VideoExercicio, 
    on_delete=models.CASCADE, related_name="variacoes"
    )
    nome = models.CharField(max_length=300)
    gif = models.FileField(
        upload_to='gifs/', 
        max_length=300,
        null=True,
        blank=True)

    grupo_muscular = models.ForeignKey(
    GrupoMuscular, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.exercicio.nome} - {self.nome}"


# ========================
# TREINO
# ========================


class Treino(models.Model):
    aluno = models.ForeignKey(Aluno, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    descricao = models.TextField()
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def get_link(self):
        return f"/treino/{self.token}"

    def __str__(self):
        return f"{self.nome} - {self.aluno.nome}"


class ExercicioTreino(models.Model):
    treino = models.ForeignKey(
        Treino, on_delete=models.CASCADE, related_name="exercicios"
    )
    exercicio = models.ForeignKey(VideoExercicio, on_delete=models.CASCADE)
    variacao = models.ForeignKey(VariacaoExercicio, on_delete=models.CASCADE)

    series = models.IntegerField()
    repeticoes = models.IntegerField()
    descanso = models.IntegerField(help_text="em segundos")
    carga = models.CharField(max_length=50, blank=True)

    ordem = models.IntegerField()

    def __str__(self):
        return f"{self.treino.nome} - {self.exercicio.nome}"


# ============
# Exercício
# ===========


class Exercicio(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome


# =======================
# USUÁRIO
# =======================


# =======================
# ASSINATURA E PAGAMENTOS
# =======================

class Assinatura(models.Model):
    STATUS_CHOICES = (
        ("ACTIVE", "Ativa"),
        ("OVERDUE", "Inadimplente"),
        ("CANCELLED", "Cancelada"),
        ("PENDING", "Pendente"),
    )

    PLANO_CHOICES = (
        ("MENSAL", "Plano Mensal"),
        ("ANUAL", "Plano Anual"),
    )

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assinatura",
    )

    asaas_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    plano = models.CharField(
        max_length=20,
        choices = PLANO_CHOICES,
        default = "MENSAL"
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def esta_ativa(self):
        return self.status == "ACTIVE"

    def __str__(self):
        return f"{self.usuario.email} - {self.status}"


class WebhookEvent(models.Model):
    STATUS_CHOICES = (
        ("PROCESSED", "Processado"),
        ("IGNORED", "Ignorado"),
        ("FAILED", "Falhou"),
    )

    event_id = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
    )

    event_type = models.CharField(max_length=100)

    payment_id = models.CharField(
        max_length=100,
        blank=True,
    )

    payload = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} - {self.status}"


# ==================
# PAGAMENTO ASAAS
# ==================

class PagamentoAsaas(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pendente"),
        ("CONFIRMED", "Confirmado"),
        ("RECEIVED", "Recebido"),
        ("OVERDUE", "Inadimplente"),
        ("REFUNDED", "Estornado"),
        ("DELETED", "Removido"),
    )

    assinatura = models.ForeignKey(
        Assinatura,
        on_delete=models.CASCADE,
        related_name="pagamentos",
    )

    asaas_payment_id = models.CharField(
        max_length=100,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    data_vencimento = models.DateField(
        null=True,
        blank=True,
    )

    recebido_em = models.DateTimeField(
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.asaas_payment_id} - {self.status}"