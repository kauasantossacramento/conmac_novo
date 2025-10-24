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

class AdminReembolsoForm(forms.ModelForm):
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
        # (opcional) reforça o label via código, caso prefira:
        self.fields["observacao_admin"].label = "Observação"
        # (opcional) aceita dd/mm/yyyy também
        self.fields["pago_em"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]
        # (opcional) aceitação de tipos no upload
        if "comprovante_pagamento" in self.fields:
            self.fields["comprovante_pagamento"].widget.attrs.update({"accept": ".pdf,image/*"})

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
        # título · data · valor [+ usuário se show_user=True]
        base = f"{d.titulo} · {d.data_fato.strftime('%d/%m/%Y')} · R$ {d.valor:.2f}"
        if self.show_user:
            nome = (d.usuario.get_full_name() or d.usuario.username).upper()
            return f"{base} · {nome}"
        return base


class AdminLoteReembolsoForm(forms.Form):
    status = forms.ChoiceField(choices=Despesa.Status.choices, label="Novo status")
    comprovante_pagamento = forms.FileField(required=False, label="Comprovante de Pagamento (lote)")
    pago_em = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    # 'despesas' será definido no __init__ usando DespesaCheckboxes

    def __init__(self, *args, **kwargs):
        centro = kwargs.pop("centro", None)
        ano = kwargs.pop("ano", None)
        mes = kwargs.pop("mes", None)
        super().__init__(*args, **kwargs)

        qs = Despesa.objects.filter(centro=centro, data_fato__year=ano)
        if mes:
            qs = qs.filter(data_fato__month=mes)

        qs = qs.select_related("usuario").order_by("-data_fato", "-criado_em", "-id")

        # Mostra o nome do usuário somente se houver mais de um distinto
        multi_usuarios = qs.values("usuario_id").distinct().count() > 1

        self.fields["despesas"] = DespesaCheckboxes(
            queryset=qs,
            widget=forms.CheckboxSelectMultiple(attrs={"class": "chk-lote"}),
            label="Despesas a alterar",
            show_user=multi_usuarios,
            required=True,
        )

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

        # 1) status / pago_em
        update_kwargs = {"status": status}
        if pago_em is not None:
            update_kwargs["pago_em"] = pago_em
        Despesa.objects.filter(pk__in=ids).update(**update_kwargs)

        # 2) comprovante (salva 1x e usa a mesma path em todas)
        if comp:
            folder = timezone.now().strftime("reembolsos/%Y/%m/")
            filename = f"lote_{uuid4().hex}_{comp.name}"
            saved_path = default_storage.save(folder + filename, comp)

            instancias = list(Despesa.objects.filter(pk__in=ids))
            for d in instancias:
                d.comprovante_pagamento.name = saved_path
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

class DespesaForm(forms.ModelForm):
    """
    Formulário do COLABORADOR (criar/editar).
    - Não mostra nem aceita campos administrativos.
    - Usa FileInput simples para 'comprovante' (sem "Modificar/Limpar").
    - Oferece um checkbox opcional para remover o comprovante atual.
    """
    #remover_comprovante = forms.BooleanField(
    #    required=False, label="Remover comprovante atual"
    #)

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

        # nunca mostre campos administrativos (por segurança)
        for admin_field in ("pago_em", "comprovante_pagamento", "status", "observacao_admin"):
            if admin_field in self.fields:
                self.fields.pop(admin_field)

        # só mostra o checkbox de remover se já existe arquivo
        if not (self.instance and getattr(self.instance, "comprovante")):
            self.fields.pop("remover_comprovante", None)

        # estiliza e simplifica o input de arquivo do comprovante (sem "limpar/modificar")
        self.fields["comprovante"].widget = forms.FileInput(
            attrs={"accept": ".pdf,image/*"}
        )

    def clean(self):
        cleaned = super().clean()
        data_fato = cleaned.get("data_fato")

        if data_fato and not inserir_permitido_para_data_fato(data_fato):
            raise ValidationError("Lançamentos para o mês selecionado estão encerrados.")

        if self.instance and self.instance.pk:
            if not despesa_editavel(self.instance.criado_em) and not (self._user and self._user.is_superuser):
                raise ValidationError("Esta despesa não pode mais ser editada após o fechamento do mês.")

        # blindagem: mesmo se postarem campos admin, ignore
        for admin_field in ("pago_em", "comprovante_pagamento", "status", "observacao_admin"):
            cleaned.pop(admin_field, None)

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)

        # remove o arquivo atual se marcado
        if "remover_comprovante" in self.cleaned_data and self.cleaned_data["remover_comprovante"]:
            if obj.comprovante:
                # exclui o arquivo do storage (sem salvar ainda)
                obj.comprovante.delete(save=False)
            obj.comprovante = None

        if commit:
            obj.save()
        return obj

    class Meta:
        model = Despesa
        fields = ["centro", "titulo", "data_fato", "valor", "descricao", "comprovante"]
        widgets = {
            "data_fato": BRDateInput(),
            # 'comprovante' é substituído em __init__ por FileInput simples
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

