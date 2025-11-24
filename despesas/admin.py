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


# despesas/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model
from .models import UsuarioPerfil

User = get_user_model()

@admin.register(UsuarioPerfil)
class UsuarioPerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "cpf")
    search_fields = ("user__username", "user__first_name", "user__last_name", "cpf")

class UsuarioPerfilInline(admin.StackedInline):
    model = UsuarioPerfil
    fk_name = "user"
    can_delete = False
    max_num = 1
    extra = 0                 # <<< não apresenta formulário em branco
    fields = ("cpf",)         # <<< mostra CPF no inline
    verbose_name = "Usuário Perfil"
    verbose_name_plural = "Usuário Perfil"

class UserAdmin(DjangoUserAdmin):
    inlines = [UsuarioPerfilInline]

    # No add_view (sem obj) não mostra inline. No change_view mostra.
    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

# Registrar o User com o inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
