from django.contrib import admin
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa, LoteReembolso

@admin.register(CentroDeCusto)
class CentroDeCustoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)

@admin.register(AssociacaoCentroCusto)
class AssociacaoCentroCustoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "centro", "ativo", "criado_em")
    list_filter = ("ativo", "centro")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "centro__nome")

@admin.register(Despesa)
class DespesaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "usuario", "centro", "valor", "status", "data_fato", "criado_em")
    list_filter = ("status", "centro")
    date_hierarchy = "criado_em"
    search_fields = ("titulo", "descricao", "usuario__username")

@admin.register(LoteReembolso)
class LoteReembolsoAdmin(admin.ModelAdmin):
    list_display = ("id", "centro", "periodo_ref", "pago_em", "criado_por", "criado_em")
    list_filter = ("centro", "pago_em")
    search_fields = ("periodo_ref", "centro__nome")
    filter_horizontal = ("despesas",)
