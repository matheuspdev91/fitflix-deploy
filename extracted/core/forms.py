from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from .models import (
    Adipometria,
    Aluno,
    AvaliacaoCrianca,
    AvaliacaoFisica,
    AvaliacaoIdoso,
    Circunferencia,
    ExercicioTreino,
    Treino,
    VariacaoExercicio,
    VideoExercicio,
)

User = get_user_model()


class AvaliacaoFisicaForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoFisica
        fields = [
            "nome",
            "sexo",
            "data_nascimento",
            "altura",
            "peso",
            "objetivo",
            "percentual_gordura",
        ]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
        }


class CircunferenciaForm(forms.ModelForm):
    class Meta:
        model = Circunferencia
        fields = [
            "ombros",
            "torax",
            "cintura",
            "abdome",
            "quadril",
            "braco_direito",
            "braco_esquerdo",
            "coxa_direita",
            "coxa_esquerda",
            "panturrilha_direita",
            "panturrilha_esquerda",
        ]
        labels = {
            "ombros": "Ombros",
            "torax": "Tórax",
            "cintura": "Cintura",
            "abdome": "Abdome",
            "quadril": "Quadril",
            "braco_direito": "Braço direito",
            "braco_esquerdo": "Braço esquerdo",
            "coxa_direita": "Coxa direita",
            "coxa_esquerda": "Coxa esquerda",
            "panturrilha_direita": "Panturrilha direita",
            "panturrilha_esquerda": "Panturrilha esquerda",
        }


class AdipometriaForm(forms.ModelForm):
    class Meta:
        model = Adipometria
        fields = [
            "tricipital",
            "subescapular",
            "supra_iliaca",
            "abdominal",
            "coxa",
            "peito",
            "axilar_media",
        ]


class AvaliacaoCriancaForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoCrianca
        fields = [
            "coordenacao",
            "equilibrio_segundos",
            "flexoes",
            "agilidade_tempo",
            "salto_horizontal",
        ]


class AvaliacaoIdosoForm(forms.ModelForm):
    class Meta:
        model = AvaliacaoIdoso
        fields = [
            "sentar_levantar",
            "tug_tempo",
            "equilibrio_segundos",
            "caminhada_6min",
        ]


class TreinoForm(forms.ModelForm):
    aluno = forms.ModelChoiceField(
        queryset=Aluno.objects.none(),
        required=False,
        label="Aluno existente",
        empty_label="Selecione um aluno",
    )

    nome_aluno = forms.CharField(
        label="Nome do aluno (novo)",
        required=False,
        max_length=100,
    )

    class Meta:
        model = Treino
        fields = ["nome"]

        labels = {
            "nome": "Nome do treino",
        }

        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Ex: Treino A - Hipertrofia"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        alunos = Aluno.objects.none()
        if user is not None and user.is_authenticated:
            alunos = Aluno.objects.filter(personal=user)

        self.fields["aluno"].queryset = alunos.order_by("nome")

        field_classes = "treino-input"

        for field_name, field in self.fields.items():
            existing_class = field.widget.attrs.get(
                "class",
                "",
            ).strip()

            field.widget.attrs["class"] = (
                f"{existing_class} {field_classes}".strip()
            )

        self.fields["nome_aluno"].widget.attrs.update(
            {
                "placeholder": "Digite o nome do novo aluno",
            }
        )

    def clean(self):
        cleaned_data = super().clean()

        aluno = cleaned_data.get("aluno")

        nome_aluno = (
            cleaned_data.get("nome_aluno") or ""
        ).strip()

        cleaned_data["nome_aluno"] = nome_aluno

        if not aluno and not nome_aluno:
            raise forms.ValidationError(
                "Selecione um aluno ou crie um novo."
            )

        return cleaned_data

CriarTreinoForm = TreinoForm


# ===================
# CRIAR ALUNO FORM
# ===================


class CriarAlunoForm(forms.ModelForm):

    email = forms.EmailField(label="Email")

    class Meta:
        model = Aluno
        fields = [
            "nome",
            "email",
            "telefone",
            "data_nascimento",
            "objetivo",
            "observacoes",
        ]
        labels = {
            "nome": "Nome",
            "telefone": "Telefone",
            "data_nascimento": "Data de nascimento",
            "objetivo": "Objetivo",
            "observacoes": "Observacoes",
        }
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}),
            "objetivo": forms.TextInput(
                attrs={"placeholder": "Ex: Ganho de massa muscular"}
            ),
            "observacoes": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Informacoes adicionais"}
            ),
        }



     # =================
     # CRIAR TREINO
     # =================   

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["telefone"].required = False
        self.fields["objetivo"].required = False
        self.fields["observacoes"].required = False
        self.fields["nome"].widget.attrs.update(
            {
                "placeholder": "Ex: Matheus Silva",
            }
        )
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "aluno@fitflix.com",
            }
        )
        self.fields["telefone"].widget.attrs.update(
            {
                "placeholder": "(11) 99999-9999",
            }
        )
        self.fields["data_nascimento"].widget.attrs.update(
            {
                "max": "2099-12-31",
            }
        )

        field_classes = "input-field"
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{existing_class} {field_classes}".strip()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ja existe um usuario cadastrado com este email."
            )
        return email



# ==================
# VARIAÇÕES
# ==================

class ExercicioTreinoForm(forms.ModelForm):

    class Meta:
        model = ExercicioTreino

        fields = [
            "exercicio",
            "variacao",
        ]

        labels = {
            "exercicio": "Exercício",
            "variacao": "Variação",
            "series": "Séries",
            "repeticoes": "Repetições",
            "descanso": "Descanso (segundos)",
            "carga": "Carga",
        }

        widgets = {
            "exercicio": forms.Select(),
            "variacao": forms.Select(),
            "series": forms.NumberInput(attrs={"min": 1}),
            "repeticoes": forms.NumberInput(attrs={"min": 1}),
            "descanso": forms.NumberInput(attrs={"min": 0}),
            "carga": forms.TextInput(
                attrs={"placeholder": "Ex: 20kg"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["exercicio"].queryset = (
            VideoExercicio.objects.order_by("nome")
        )

        self.fields["variacao"].queryset = (
            VariacaoExercicio.objects.none()
        )

        if "exercicio" in self.data:

            try:
                exercicio_id = int(
                    self.data.get("exercicio")
                )

                self.fields["variacao"].queryset = (
                    VariacaoExercicio.objects.filter(
                        exercicio_id=exercicio_id
                    ).order_by("nome")
                )

            except (ValueError, TypeError):
                pass

        elif (
            self.instance.pk
            and self.instance.exercicio
        ):

            self.fields["variacao"].queryset = (
                VariacaoExercicio.objects.filter(
                    exercicio=self.instance.exercicio
                ).order_by("nome")
            )

ExercicioTreinoFormSet = inlineformset_factory(
Treino,
ExercicioTreino,
form=ExercicioTreinoForm,
extra=1,
can_delete=True,
)

# ======================
# AVALIAÇÃO PARA IDOSO
# =====================


class CircunferenciaIdosoForm(forms.ModelForm):
    class Meta:
        model = Circunferencia
        fields = [
            "cintura",
            "quadril",
            "braco_direito",
            "braco_esquerdo",
            "panturrilha_direita",
            "panturrilha_esquerda",
        ]

        labels = {
            "cintura": "Cintura",
            "quadril": "Quadril",
            "braco_direito": "Braço Direito",
            "braco_esquerdo": "Braço Esquerdo",
            "panturrilha_direita": "Panturrilha Direita",
            "panturrilha_esquerda": "Panturrilha Esquerda",
        }
