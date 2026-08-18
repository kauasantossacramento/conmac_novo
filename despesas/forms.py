# despesas/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Despesa, LoteReembolso, AssociacaoCentroCusto
from .services.fechamento import despesa_editavel, inserir_permitido_para_data_fato
from .models import ChecklistItem
from django import forms
from django.db import transaction           # ← precisa disso
from .models import Despesa                 # ← e do model correto


from django.forms.widgets import ClearableFileInput


from django import forms
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from uuid import uuid4


from django import forms

# despesas/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa

User = get_user_model()
# ---------- helpers ----------
_POSSIVEIS_CAMPOS_COMPROVANTE = (
    "comprovante_pagamento",  # preferido
    "comprovante_reembolso",
    "comprovante_pgto",
)

# util que você já usa
def _descobrir_attr_comprovante(instance):
    """
    Descobre o nome do atributo de comprovante de pagamento no model.
    Ajuste se no seu model o campo tiver outro nome.
    """
    for cand in ("comprovante_pagamento", "comprovante_reembolso"):
        if hasattr(instance, cand):
            return cand
    return None
'''
class AdminReembolsoForm(forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["status", "comprovante_pagamento", "pago_em", "observacao_admin"]
        widgets = {
            "pago_em": forms.DateInput(attrs={"type": "date"}),
            "observacao_admin": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pago_em"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        self.fields["comprovante_pagamento"].widget.attrs.update({"accept": ".pdf,image/*"})

'''
#este é um form que é usado para alterar status de despesa

# despesas/forms.py
class AdminReembolsoForm(forms.ModelForm):
    marcar_analisada = forms.BooleanField(required=False, label="Marcar como analisada")  # NOVO

    class Meta:
        model = Despesa
        fields = ["status", "comprovante_pagamento", "pago_em", "observacao_admin"]
        widgets = {
            "pago_em": forms.DateInput(attrs={"type": "date"}),
            "observacao_admin": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "observacao_admin": "Observação",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["observacao_admin"].label = "Observação"
        self.fields["pago_em"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        if "comprovante_pagamento" in self.fields:
            self.fields["comprovante_pagamento"].widget.attrs.update({"accept": ".pdf,image/*"})
        # pré-marca se já foi avaliada
        self.fields["marcar_analisada"].initial = bool(self.instance and self.instance.foi_avaliada)

    def save(self, commit=True):
        obj = super().save(commit=False)

        # Se o admin marcou como analisada, garante flags/ts
        if self.cleaned_data.get("marcar_analisada"):
            if not obj.foi_avaliada:
                obj.foi_avaliada = True
            if not obj.primeira_analise_em:
                obj.primeira_analise_em = timezone.now()

        # OBS: você pode usar o status "PENDENTE_PAGTO" como etapa intermediária do fluxo:
        # - Ex.: ao analisar mas ainda não pagar: setar status = PENDENTE_PAGTO
        # Isso fica a seu critério de UX; mantive a decisão por quem usa o form (via select).

        if self.cleaned_data.get("marcar_analisada") and obj.status == Despesa.Status.PENDENTE:
            obj.status = Despesa.Status.PENDENTE_PAGTO

        if commit:
            obj.save()
        return obj



'''
class AdminLoteReembolsoForm(forms.Form):
    status = forms.ChoiceField(choices=Despesa.Status.choices, label="Novo status")
    comprovante_pagamento = forms.FileField(required=False, label="Comprovante de Pagamento (lote)")
    pago_em = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    despesas = forms.ModelMultipleChoiceField(
        queryset=Despesa.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Despesas a alterar"
    )

    def __init__(self, *args, **kwargs):
        centro = kwargs.pop("centro", None)
        ano = kwargs.pop("ano", None)
        mes = kwargs.pop("mes", None)
        super().__init__(*args, **kwargs)

        qs = Despesa.objects.filter(centro=centro, data_fato__year=ano)
        if mes:
            qs = qs.filter(data_fato__month=mes)
        self.fields["despesas"].queryset = qs.order_by("-data_fato", "-criado_em", "-id")
        self.fields["pago_em"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        self.fields["comprovante_pagamento"].widget.attrs.update({"accept": ".pdf,image/*"})

    def clean_despesas(self):
        qs = self.cleaned_data.get("despesas")
        if not qs or not qs.exists():
            raise forms.ValidationError("Selecione ao menos uma despesa para aplicar em lote.")
        return qs

    @transaction.atomic
    def aplicar(self) -> int:
        """
        Aplica:
          - novo 'status' (update em lote)
          - 'pago_em' (se informado)
          - mesmo 'comprovante_pagamento' para todas (se enviado)
        Retorna a quantidade de despesas atualizadas.
        """
        despesas = list(self.cleaned_data["despesas"])
        status = self.cleaned_data["status"]
        pago_em = self.cleaned_data.get("pago_em")
        comp = self.cleaned_data.get("comprovante_pagamento")

        ids = [d.pk for d in despesas]

        # 1) status e pago_em via update no queryset
        update_kwargs = {"status": status}
        if pago_em is not None:
            update_kwargs["pago_em"] = pago_em
        Despesa.objects.filter(pk__in=ids).update(**update_kwargs)

        # 2) comprovante: salvar UMA vez no storage e setar o caminho em todas
        if comp:
            folder = timezone.now().strftime("reembolsos/%Y/%m/")
            filename = f"lote_{uuid4().hex}_{comp.name}"
            saved_path = default_storage.save(folder + filename, comp)  # grava o arquivo 1x

            # carregar instâncias e atualizar o campo FileField com o caminho salvo
            instancias = list(Despesa.objects.filter(pk__in=ids))
            for d in instancias:
                d.comprovante_pagamento.name = saved_path
            Despesa.objects.bulk_update(instancias, ["comprovante_pagamento"])

        return len(ids)
'''

from django import forms
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from uuid import uuid4

from .models import Despesa

class DespesaCheckboxes(forms.ModelMultipleChoiceField):
    """Checkboxes com label customizado para cada despesa."""
    def __init__(self, *args, show_user=False, **kwargs):
        self.show_user = show_user
        super().__init__(*args, **kwargs)

    def label_from_instance(self, d: Despesa) -> str:
        # Formata valor para PT-BR: 1.234,56
        valor_fmt = f"{d.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # título · data · valor
        base = f"{d.titulo} · {d.data_fato.strftime('%d/%m/%Y')} · R$ {valor_fmt}"

        if self.show_user:
            nome = (d.usuario.get_full_name() or d.usuario.username).upper()
            return f"{base} · {nome}"
        return base

# despesas/forms.py
from django import forms
from django.db import transaction
from django.utils import timezone

# ... seus imports existentes ...

class AdminLoteReembolsoForm(forms.Form):
    status = forms.ChoiceField(choices=Despesa.Status.choices, label="Novo status")
    comprovante_pagamento = forms.FileField(required=False, label="Comprovante de Pagamento (lote)")
    pago_em = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    # campos “decorativos”/compat com o template
    centro = forms.CharField(required=False, disabled=True)
    periodo_ref = forms.CharField(required=False, disabled=True)

    def __init__(self, *args, **kwargs):
        centro = kwargs.pop("centro", None)
        ano    = kwargs.pop("ano", None)
        mes    = kwargs.pop("mes", None)
        user   = kwargs.pop("user", None)       # pode ser instância
        user_id = kwargs.pop("user_id", None)   # ...ou id
        super().__init__(*args, **kwargs)

        # resolve user se vier somente id
        if user is None and user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                user = None

        # Base: apenas PENDENTE_DE_PAGAMENTO
        qs = Despesa.objects.filter(
            data_fato__year=ano,
            status=Despesa.Status.PENDENTE_PAGTO,
        )
        if mes:
            qs = qs.filter(data_fato__month=mes)
        if centro:
            qs = qs.filter(centro=centro)
        if user:
            qs = qs.filter(usuario=user)

        qs = qs.select_related("usuario").order_by("-data_fato", "-criado_em", "-id")

        multi_usuarios = qs.values("usuario_id").distinct().count() > 1

        self.fields["despesas"] = DespesaCheckboxes(
            queryset=qs,
            widget=forms.CheckboxSelectMultiple(attrs={"class": "chk-lote"}),
            label="Despesas a alterar (apenas PENDENTE DE PAGAMENTO)",
            show_user=multi_usuarios,
            required=True,
        )

        self.fields["pago_em"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        self.fields["comprovante_pagamento"].widget.attrs.update({"accept": ".pdf,image/*"})

        # Apenas pode ir para APROVADA (paga) ou REPROVADA
        self.fields["status"].choices = [
            (Despesa.Status.APROVADA, "Aprovada (paga)"),
            (Despesa.Status.REPROVADA, "Reprovada"),
        ]

        # Preenche campos “decorativos” do template (sem mudar nada de lógica)
        self.fields["centro"].initial = centro.nome if centro else ""
        if ano and mes:
            from datetime import date
            try:
                ref = date(int(ano), int(mes), 1)
                self.fields["periodo_ref"].initial = ref.strftime("%m/%Y")
            except Exception:
                self.fields["periodo_ref"].initial = ""

    def clean_despesas(self):
        qs = self.cleaned_data.get("despesas")
        if not qs or not qs.exists():
            raise forms.ValidationError("Selecione ao menos uma despesa (pendente de pagamento) para aplicar em lote.")
        # Garante que permanecem PENDENTE_PAGTO
        if qs.exclude(status=Despesa.Status.PENDENTE_PAGTO).exists():
            raise forms.ValidationError("A seleção contém itens que não estão mais PENDENTES DE PAGAMENTO. Atualize a página.")
        return qs

    @transaction.atomic
    def aplicar(self) -> int:
        despesas = list(self.cleaned_data["despesas"])
        novo_status = self.cleaned_data["status"]
        pago_em = self.cleaned_data.get("pago_em")
        comp = self.cleaned_data.get("comprovante_pagamento")

        ids = [d.pk for d in despesas]

        # Revalida no banco (evita race)
        alvo_qs = Despesa.objects.filter(pk__in=ids, status=Despesa.Status.PENDENTE_PAGTO)
        if alvo_qs.count() != len(ids):
            raise forms.ValidationError("Algumas despesas não estão mais PENDENTES DE PAGAMENTO. Recarregue a lista.")

        update_kwargs = {
            "status": novo_status,
            "foi_avaliada": True,
        }

        # Se for aprovada (paga), aceita 'pago_em'; se reprovada, ignora 'pago_em'
        if novo_status == Despesa.Status.APROVADA and pago_em is not None:
            update_kwargs["pago_em"] = pago_em
        else:
            update_kwargs["pago_em"] = None  # evita data de pagamento em reprovadas

        # aplica status/pagamento
        alvo_qs.update(**update_kwargs)

        # 1ª análise (se ainda não tinha)
        from django.utils import timezone
        Despesa.objects.filter(pk__in=ids, primeira_analise_em__isnull=True)\
                       .update(primeira_analise_em=timezone.now())

        # Comprovante em lote: só faz sentido se APROVADA
        if comp and novo_status == Despesa.Status.APROVADA:
            from django.core.files.storage import default_storage
            from uuid import uuid4
            folder = timezone.now().strftime("reembolsos/%Y/%m/")
            filename = f"lote_{uuid4().hex}_{comp.name}"
            saved_path = default_storage.save(folder + filename, comp)
            instancias = list(Despesa.objects.filter(pk__in=ids))
            for d in instancias:
                d.comprovante_pagamento.name = saved_path
            Despesa.objects.bulk_update(instancias, ["comprovante_pagamento"])
        elif novo_status == Despesa.Status.REPROVADA:
            # limpa comprovante se por acaso tinha algo
            instancias = list(Despesa.objects.filter(pk__in=ids))
            any_change = False
            for d in instancias:
                if d.comprovante_pagamento:
                    d.comprovante_pagamento.delete(save=False)
                    d.comprovante_pagamento = None
                    any_change = True
            if any_change:
                Despesa.objects.bulk_update(instancias, ["comprovante_pagamento"])

        return len(ids)


# despesas/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Despesa, AssociacaoCentroCusto
from .services.fechamento import despesa_editavel, inserir_permitido_para_data_fato

class BRDateInput(forms.DateInput):
    input_type = "text"
    format = "%d/%m/%Y"
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("format", self.format)
        attrs = kwargs.setdefault("attrs", {})
        attrs.update({
            "placeholder": "dd/mm/aaaa",
            "inputmode": "numeric",
            "maxlength": "10",
            "class": (attrs.get("class", "") + " mask-date").strip(),
            "autocomplete": "off",
        })
        super().__init__(*args, **kwargs)

from django import forms
from django.core.exceptions import ValidationError

class DespesaForm(forms.ModelForm):
    """
    Formulário do COLABORADOR (criar/editar).
    Campos obrigatórios: valor, data_fato e comprovante*.
    * comprovante é obrigatório quando a despesa ainda não possui arquivo.
    """

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

        # limitar centros ao vínculo do usuário
        centros_ids = (AssociacaoCentroCusto.objects
                       .filter(usuario=user, ativo=True)
                       .values_list("centro_id", flat=True))
        self.fields["centro"].queryset = self.fields["centro"].queryset.filter(id__in=centros_ids)

        # aceita dd/mm/aaaa e yyyy-mm-dd
        self.fields["data_fato"].input_formats = ["%d/%m/%Y", "%Y-%m-%d"]

        # reforça obrigatoriedade
        self.fields["valor"].required = True
        self.fields["data_fato"].required = True

        # input simplificado de arquivo
        self.fields["comprovante"].widget = forms.FileInput(attrs={"accept": ".pdf,image/*"})

        # comprovante obrigatório se ainda não existe um salvo
        ja_tem_comprovante = bool(self.instance and getattr(self.instance, "comprovante"))
        self.fields["comprovante"].required = not ja_tem_comprovante

        # nunca mostre/aceite campos administrativos
        for admin_field in ("pago_em", "comprovante_pagamento", "status", "observacao_admin"):
            if admin_field in self.fields:
                self.fields.pop(admin_field)

    def clean(self):
        cleaned = super().clean()

        # fechamento de período
        data_fato = cleaned.get("data_fato")
        if data_fato and not inserir_permitido_para_data_fato(data_fato):
            raise ValidationError("Lançamentos para o mês selecionado estão encerrados.")

        # trava edição após fechamento (exceto superuser)
        if self.instance and self.instance.pk:
            if not despesa_editavel(self.instance.criado_em) and not (self._user and self._user.is_superuser):
                raise ValidationError("Esta despesa não pode mais ser editada após o fechamento do mês.")

        # reforça obrigatório do comprovante quando não há arquivo ainda
        tem_arquivo_banco = bool(self.instance and getattr(self.instance, "comprovante"))
        arquivo_novo = cleaned.get("comprovante")
        if not tem_arquivo_banco and not arquivo_novo:
            self.add_error("comprovante", "Envie o comprovante (obrigatório).")

        # blindagem: ignora campos admin se vierem no POST
        for admin_field in ("pago_em", "comprovante_pagamento", "status", "observacao_admin"):
            cleaned.pop(admin_field, None)

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        if commit:
            obj.save()
        return obj

    class Meta:
        model = Despesa
        fields = ["centro", "titulo", "data_fato", "valor", "descricao", "comprovante"]
        widgets = {
            "data_fato": BRDateInput(),
        }



class LoteReembolsoForm(forms.ModelForm):
    class Meta:
        model = LoteReembolso
        fields = ["centro", "periodo_ref", "despesas", "comprovante_reembolso", "pago_em"]


class ChecklistForm(forms.ModelForm):
    class Meta:
        model = ChecklistItem
        fields = ["texto"]
        widgets = {
            "texto": forms.TextInput(attrs={"placeholder": "insira a tarefa aqui"})
        }




class CentroForm(forms.ModelForm):
    class Meta:
        model = CentroDeCusto
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome do centro de custo/cliente"})
        }

class AssociaAnalistaForm(forms.Form):
    usuario = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="Analista/Colaborador"
    )

    def __init__(self, *args, **kwargs):
        centro = kwargs.pop("centro")
        super().__init__(*args, **kwargs)
        # sugere usuários que AINDA não estão associados a este centro
        associados = AssociacaoCentroCusto.objects.filter(centro=centro, ativo=True)\
                       .values_list("usuario_id", flat=True)
        self.fields["usuario"].queryset = User.objects.exclude(id__in=associados).order_by("first_name","last_name")



#conmacfest2025

# eventos/forms.py
from django import forms
from .models import Rsvp

class RsvpForm(forms.ModelForm):
    class Meta:
        model = Rsvp
        fields = ["nome", "vai_ir"]
        widgets = {
            "nome": forms.TextInput(attrs={
                "placeholder": "nome completo",
                "class": "form-control",
                "autocomplete": "name",
            }),
            "vai_ir": forms.RadioSelect(choices=[(True, "eu vou para CONMAC FEST 2025."), (False, "não poderei ir.")]),
        }
        labels = {
            "nome": "",
            "vai_ir": "",
        }


#--------------------


from django import forms
from .models import Etapa, NivelChoices

# despesas/forms.py

class EtapaForm(forms.ModelForm):
    class Meta:
        model = Etapa
        fields = [
            'nivel', 'nome', 'descricao', 'ordem', 'ativa', 'exige_anexo',
            'obrigatoria_para_fila_siga', 'obrigatoria_para_fila_etcm',
            'obrigatoria_para_fila_siope', 'obrigatoria_para_fila_siops',
            'obrigatoria_para_fila_siconf'
        ]
        widgets = {
            'nivel': forms.Select(attrs={'class': 'conmac-input', 'id': 'id_etapa_nivel'}), # Adicionei ID para facilitar o JS
            'nome': forms.TextInput(attrs={'class': 'conmac-input', 'placeholder': 'Nome da Etapa'}),
            'descricao': forms.Textarea(attrs={'class': 'conmac-input', 'rows': 3, 'placeholder': 'Descrição breve...'}),
            'ordem': forms.NumberInput(attrs={'class': 'conmac-input', 'style': 'width: 80px;'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        nivel_selecionado = cleaned_data.get('nivel')

        # Mapeamento: Nivel -> Nome do Campo de Obrigatoriedade
        mapa_conflito = {
            'SIGA': 'obrigatoria_para_fila_siga',
            'E-TCM': 'obrigatoria_para_fila_etcm', # Ajuste se no model a choice for 'E_TCM' ou 'E-TCM'
            'SIOPE': 'obrigatoria_para_fila_siope',
            'SIOPS': 'obrigatoria_para_fila_siops',
            'SICONF': 'obrigatoria_para_fila_siconf',
        }

        # Se o nível selecionado tiver um campo de obrigatoriedade correspondente
        campo_proibido = mapa_conflito.get(nivel_selecionado)

        if campo_proibido and cleaned_data.get(campo_proibido):
            # Opção A: Auto-corrigir (Definir como False silenciosamente) - Recomendado para UX
            cleaned_data[campo_proibido] = False

            # Opção B: Levantar erro (Se preferir travar o salvamento)
            # self.add_error(campo_proibido, f"Uma etapa do {nivel_selecionado} não pode ser pré-requisito para ele mesmo.")

        return cleaned_data




from django import forms
from .models import QuestionarioSIOPS

# Variável definida fora da classe para estar disponível no escopo dos widgets
CHOICES_SIM_NAO = [
    (True, 'Sim'),
    (False, 'Não')
]

from django import forms
from .models import QuestionarioSIOPS

CHOICES_SIM_NAO = [
    (True, 'Sim'),
    (False, 'Não')
]

class QuestionarioForm(forms.ModelForm):
    class Meta:
        model = QuestionarioSIOPS
        exclude = ['prefeitura', 'data_envio']

        widgets = {
            'conselho_data_criacao': forms.DateInput(attrs={'type': 'date'}),
            'prefeito_endereco': forms.TextInput(attrs={'placeholder': 'Rua, Número, Bairro, CEP'}),
            'fiscaliza_fundo': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'parecer_plano': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'parecer_ppa': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'delibera_programacao': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'delibera_loa': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'delibera_relatorio_gestao': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'parecer_relatorio_gestao': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'parecer_contas_quadrimestre': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'fundo_pleno_funcionamento': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'recursos_proprios_aplicados': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'recursos_sus_aplicados': forms.RadioSelect(choices=CHOICES_SIM_NAO),
            'possui_consorcio': forms.RadioSelect(choices=CHOICES_SIM_NAO),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            # 1. Limpeza agressiva do
            # Se o label existir, pega tudo antes do primeiro '[' e remove espaços extras
            if field.label:
                if '[' in field.label:
                    field.label = field.label.split('[')[0].strip()

                # Remove também se estiver no help_text, por garantia
                if field.help_text and '[' in field.help_text:
                    field.help_text = field.help_text.split('[')[0].strip()

            # 2. Classes CSS
            if isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control input-conmac'})

from django import forms
from .models import Contrato, ServicoExtra

from django import forms
from datetime import date
# Mantenha as importações existentes

class EdicaoLoteContratoForm(forms.Form):
    ids_selecionados = forms.CharField(widget=forms.HiddenInput())

    valor_mensal = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        label="Novo Valor Mensal (R$)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Manter valor atual'})
    )

    codigo_nbs = forms.CharField(
        max_length=20, required=False, label="Novo Código NBS",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Manter NBS atual'})
    )

    # --- NOVOS CAMPOS PARA COMPETÊNCIA ---
    MESES = [
        ('', '--- Manter Mês Atual ---'),
        ('JANEIRO', 'JANEIRO'), ('FEVEREIRO', 'FEVEREIRO'), ('MARÇO', 'MARÇO'),
        ('ABRIL', 'ABRIL'), ('MAIO', 'MAIO'), ('JUNHO', 'JUNHO'),
        ('JULHO', 'JULHO'), ('AGOSTO', 'AGOSTO'), ('SETEMBRO', 'SETEMBRO'),
        ('OUTUBRO', 'OUTUBRO'), ('NOVEMBRO', 'NOVEMBRO'), ('DEZEMBRO', 'DEZEMBRO')
    ]

    # Pega ano atual e próximo para opções
    ano_atual = date.today().year
    ANOS = [('', '---')] + [(str(y), str(y)) for y in range(ano_atual-1, ano_atual+2)]

    nova_competencia_mes = forms.ChoiceField(
        choices=MESES, required=False, label="Alterar Mês de Referência",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    nova_competencia_ano = forms.ChoiceField(
        choices=ANOS, required=False, label="Alterar Ano",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

class ServicoExtraForm(forms.ModelForm):
    class Meta:
        model = ServicoExtra
        fields = ['descricao', 'valor', 'data_servico', 'contrato']
        widgets = {
            'data_servico': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'contrato': forms.Select(attrs={'class': 'form-control'}),
        }



# forms.py

from django import forms
from .models import EmailMunicipio, Contrato

class EmailMunicipioForm(forms.ModelForm):

    # Popula o select de municípios com os que já existem nos contratos
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        municipios = (
            Contrato.objects
            .exclude(municipio__isnull=True).exclude(municipio='')
            .values_list('municipio', flat=True)
            .distinct().order_by('municipio')
        )
        choices = [('', '---------')] + [(m, m) for m in municipios]
        self.fields['municipio'].widget = forms.Select(choices=choices)
        self.fields['municipio'].widget.attrs.update({'class': 'form-select'})
        for field in self.fields.values():
            if not field.widget.attrs.get('class'):
                field.widget.attrs['class'] = 'form-control'

    class Meta:
        model  = EmailMunicipio
        fields = ['municipio', 'tipo_entidade', 'email', 'nome_contato', 'principal']
        widgets = {
            'tipo_entidade': forms.Select(attrs={'class': 'form-select'}),
            'principal':     forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'municipio':     'Município',
            'tipo_entidade': 'Tipo de Entidade',
            'email':         'E-mail',
            'nome_contato':  'Nome do Contato',
            'principal':     'Marcar como e-mail principal nos contratos',
        }