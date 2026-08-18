from django.contrib import admin
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa, LoteReembolso, NotificacaoConfig, ConfiguracaoFinanceira, VinculoFuncionarioCentro, DespesaGeral
from .models import PrevisaoPagamento, PrevisaoPagamentoLog

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

# admin.py
@admin.register(UsuarioPerfil)
class UsuarioPerfilAdmin(admin.ModelAdmin):
    list_display = (
        "user", "cpf", "cargo", "local_trabalho",
        "salario_base", "ativo",
        "acesso_fechamento", "acesso_siga", "acesso_siope",
        "acesso_siops", "acesso_siconf", "acesso_etcm",
    )
    search_fields = ("user__username", "user__first_name", "user__last_name", "cpf")
    list_filter = (
        "ativo", "local_trabalho",
        "acesso_fechamento", "acesso_siga", "acesso_siope",
        "acesso_siops", "acesso_siconf", "acesso_etcm",
    )
    fieldsets = (
        ("Identificação", {
            "fields": (("user", "cpf"), ("cargo", "local_trabalho"), "ativo"),
        }),
        ("Financeiro", {
            "fields": (("salario_base", "irrf_manual"), "data_admissao"),
            "description": "Salário base é usado no cálculo de rateio por município.",
        }),
        ("Acessos", {
            "fields": (
                "acesso_fechamento", "acesso_siga", "acesso_siope",
                "acesso_siops", "acesso_siconf", "acesso_etcm",
                "acesso_prestacao_contas", "perfil_pc",
            ),
            "classes": ("collapse",),
        }),
    )
    # inlines injetado abaixo (após VinculoFuncionarioCentroInline ser definido)

class UsuarioPerfilInline(admin.StackedInline):
    model = UsuarioPerfil
    fk_name = "user"
    can_delete = False
    max_num = 1
    extra = 0

    fieldsets = (
        ("Dados Pessoais", {"fields": ("cpf",)}),
        ("Acessos", {
            "fields": (
                "acesso_fechamento", "acesso_siga", "acesso_siope",
                "acesso_siops", "acesso_siconf", "acesso_etcm"
            )
        }),  # ← fechamento do dict + fechamento do tuple "Acessos"
        ('Prestação de Contas', {
            'fields': ['acesso_prestacao_contas', 'perfil_pc']
        }),
    )
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

#GERENCIAMENTO DE ATIVIDADES

# atividades/admin.py
from django.contrib import admin
from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro,
    EtapaHistorico, FilaAutomatica
)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "codigo_externo")
    search_fields = ("nome", "codigo_externo")
    list_filter = ("ativo",)

@admin.register(AssociacaoUsuarioCliente)
class AssociacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "cliente", "ativo", "criado_em")
    list_filter = ("ativo",)
    search_fields = ("usuario__username", "cliente__nome")

@admin.register(Etapa)
class EtapaAdmin(admin.ModelAdmin):
    list_display = ("nome", "nivel", "ordem", "ativa")
    list_filter = ("nivel", "ativa")
    search_fields = ("nome",)

@admin.register(EtapaRegistro)
class EtapaRegistroAdmin(admin.ModelAdmin):
    list_display = ("cliente", "etapa", "ano", "mes", "status", "ultima_alteracao_por", "modificado_em")
    list_filter = ("status", "ano", "mes", "etapa__nivel")
    search_fields = ("cliente__nome", "etapa__nome")
    readonly_fields = ("criado_em", "modificado_em")

@admin.register(EtapaHistorico)
class EtapaHistoricoAdmin(admin.ModelAdmin):
    list_display = ("registro", "alterado_por", "status_anterior", "status_novo", "criado_em")
    list_filter = ("status_novo",)

@admin.register(FilaAutomatica)
class FilaAutomaticaAdmin(admin.ModelAdmin):
    list_display = ("nome", "cliente", "nivel", "data_entrada")
    list_filter = ("nome", "nivel")

@admin.register(NotificacaoConfig)
class NotificacaoConfigAdmin(admin.ModelAdmin):
    list_display = ("chave", "descricao", "habilitado")
    list_editable = ("habilitado",)

from django.contrib import admin

# atividades/admin.py
from django.contrib import admin
from .models import NotificationMessage

@admin.register(NotificationMessage)
class NotificationMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "sent", "sent_at")
    actions = ["send_notifications"]

    @admin.action(description="Enviar esta notificação para todos os dispositivos")
    def send_notifications(self, request, queryset):
        for msg in queryset:
            msg.send_to_all()
        self.message_user(request, "Notificações enviadas com sucesso!")


# eventos/admin.py
from django.contrib import admin
from .models import Rsvp

@admin.register(Rsvp)
class RsvpAdmin(admin.ModelAdmin):
    list_display = ("nome", "vai_ir", "criado_em")
    list_filter = ("vai_ir", "criado_em")
    search_fields = ("nome",)
    ordering = ("-criado_em",)


from django.contrib import admin
from .models import FCMToken

@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    # Colunas que aparecerão na tabela
    list_display = ('user', 'get_short_token', 'created_at')

    # Campos que permitem busca (pelo nome do usuário, email ou pelo token exato)
    search_fields = ('user__username', 'user__first_name', 'user__email', 'token')

    # Filtros laterais
    list_filter = ('created_at',)

    # Impede edição acidental da data de criação
    readonly_fields = ('created_at',)

    # Função para exibir apenas o começo do token na lista e não poluir a tela
    def get_short_token(self, obj):
        if obj.token:
            return f"{obj.token[:50]}..." # Mostra apenas os primeiros 50 caracteres
        return "-"

    get_short_token.short_description = "Token (Parcial)"


# despesas/admin.py
import logging
from django.contrib import admin
from django.utils import timezone
from firebase_admin import messaging
from .models import FCMToken, NotificacaoPush

logger = logging.getLogger(__name__)

# ... seu registro do FCMTokenAdmin continua aqui ...

@admin.register(NotificacaoPush)
class NotificacaoPushAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario_alvo', 'enviado', 'criado_em')
    list_filter = ('enviado', 'criado_em')
    actions = ['enviar_notificacao_agora']

    def enviar_notificacao_agora(self, request, queryset):
        """
        Ação do admin para disparar o push para os tokens salvos.
        """
        sucesso_total = 0
        falhas_total = 0

        for notificacao in queryset:
            # 1. Definir quem vai receber
            tokens_query = FCMToken.objects.all()

            if notificacao.usuario_alvo:
                # Filtra apenas para o usuário específico
                tokens_query = tokens_query.filter(user=notificacao.usuario_alvo)

            # Extrai apenas a string dos tokens numa lista
            lista_tokens = list(tokens_query.values_list('token', flat=True))

            if not lista_tokens:
                self.message_user(request, f"Nenhum token encontrado para '{notificacao.titulo}'.", level='warning')
                continue

            # 2. Montar a mensagem
            # Nota: O Firebase permite envio em lotes de até 500 tokens.
            # Se tiver mais que isso, precisaria dividir a lista (chunking).

            mensagem = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=notificacao.titulo,
                    body=notificacao.mensagem,
                ),
                data={
                    "link": notificacao.link if notificacao.link else "/",
                    "click_action": "FLUTTER_NOTIFICATION_CLICK" # Padrão útil
                },
                tokens=lista_tokens,
            )

            # 3. Enviar via Firebase
            try:
                response = messaging.send_each_for_multicast(mensagem)

                # Atualiza status da notificação
                notificacao.enviado = True
                notificacao.data_envio = timezone.now()
                notificacao.save()

                sucesso_total += response.success_count
                falhas_total += response.failure_count

                # Opcional: Limpar tokens inválidos (que falharam)
                if response.failure_count > 0:
                    self._limpar_tokens_invalidos(response, lista_tokens)

            except Exception as e:
                logger.error(f"Erro enviando FCM: {e}")
                self.message_user(request, f"Erro ao enviar '{notificacao.titulo}': {e}", level='error')

        self.message_user(request, f"Envio concluído! Sucessos: {sucesso_total}, Falhas: {falhas_total}")

    enviar_notificacao_agora.short_description = "Enviar notificações selecionadas"

    def _limpar_tokens_invalidos(self, response, tokens_originais):
        """Remove do banco tokens que o Google disse que não existem mais."""
        tokens_para_remover = []
        for idx, resp in enumerate(response.responses):
            if not resp.success:
                # Se o erro for de registro inválido, deletamos do banco
                if resp.exception.code == 'messaging/registration-token-not-registered':
                    tokens_para_remover.append(tokens_originais[idx])

        if tokens_para_remover:
            FCMToken.objects.filter(token__in=tokens_para_remover).delete()



from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Prefeitura, QuestionarioSIOPS

@admin.register(Prefeitura)
class PrefeituraAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ver_brasao', 'link_formulario', 'ativo', 'status_resposta')
    list_filter = ('ativo',)
    search_fields = ('nome', 'slug')
    prepopulated_fields = {'slug': ('nome',)}
    readonly_fields = ('ver_brasao_grande',)

    def ver_brasao(self, obj):
        if obj.brasao:
            return format_html('<img src="{}" style="max-height: 30px;"/>', obj.brasao.url)
        return "-"
    ver_brasao.short_description = "Brasão"

    def ver_brasao_grande(self, obj):
        if obj.brasao:
            return format_html('<img src="{}" style="max-height: 150px;"/>', obj.brasao.url)
        return "Sem imagem"
    ver_brasao_grande.short_description = "Visualização do Brasão"

    def link_formulario(self, obj):
        # Cria um link clicável para testar o formulário direto do admin
        # Certifique-se que o 'name' da url em urls.py é 'questionario_siops'
        try:
            url = reverse('questionario_siops', args=[obj.slug])
            return format_html('<a href="{}" target="_blank">Abrir Formulário 🔗</a>', url)
        except:
            return "URL não configurada"
    link_formulario.short_description = "Link de Acesso"

    def status_resposta(self, obj):
        if hasattr(obj, 'questionario'):
            return format_html('<span style="color: green;">✔ Respondido</span>')
        return format_html('<span style="color: orange;">⏳ Aguardando</span>')
    status_resposta.short_description = "Status"


@admin.register(QuestionarioSIOPS)
class QuestionarioAdmin(admin.ModelAdmin):
    list_display = ('prefeitura', 'data_envio', 'prefeito_nome', 'botao_imprimir')
    list_filter = ('data_envio', 'prefeitura')
    search_fields = ('prefeitura__nome', 'prefeito_nome', 'secretario_nome')

    # CORREÇÃO AQUI: Adicione 'data_envio' aos campos somente leitura
    readonly_fields = ('botao_imprimir', 'data_envio')

    def botao_imprimir(self, obj):
        try:
            # Certifique-se que o nome da URL está correto no seu urls.py principal
            url = reverse('admin_gerar_pdf', args=[obj.id])
            return format_html(
                '<a class="button" href="{}" target="_blank" style="background-color: #1a8f9e; color: white; padding: 5px 10px; border-radius: 5px;">📄 Baixar PDF</a>',
                url
            )
        except:
            return "Salve para gerar PDF"
    botao_imprimir.short_description = "Exportar"
    botao_imprimir.allow_tags = True

    fieldsets = (
        ('Ações', {
            'fields': ('botao_imprimir',)
        }),
        ('Identificação', {
            'fields': ('prefeitura', 'data_envio') # Agora funciona pois está no readonly_fields
        }),
        ('1. Gestores (Prefeito e Secretário)', {
            'fields': (
                ('prefeito_nome', 'prefeito_telefone'),
                ('prefeito_endereco', 'prefeito_email'),
                ('secretario_nome', 'secretario_telefone'),
                ('secretario_endereco', 'secretario_email'),
            )
        }),
        ('2. Conselho de Saúde', {
            'fields': (
                ('conselho_data_criacao', 'conselho_instrumento'),
                ('conselho_endereco', 'conselho_periodicidade'),
                ('presidente_nome', 'presidente_segmento'),
                ('presidente_endereco',), # Adicionado conforme atualização anterior
                ('presidente_telefone', 'presidente_email'),
                ('responsavel_info_nome', 'responsavel_info_email', 'responsavel_info_telefone')
            )
        }),
        ('3. Atuação e Fiscalização', {
            'classes': ('collapse',),
            'description': 'Respostas de Sim/Não sobre as atividades do conselho',
            'fields': (
                'fiscaliza_fundo', 'parecer_plano', 'parecer_ppa',
                'delibera_programacao', 'delibera_loa', 'delibera_relatorio_gestao',
                'parecer_relatorio_gestao', 'parecer_contas_quadrimestre'
            )
        }),
        ('4. Fundo de Saúde', {
            'fields': (
                ('fundo_cnpj', 'fundo_tipo_gestao'),
                'fundo_endereco',
                ('banco_nome', 'banco_agencia', 'banco_conta'),
                'fundo_pleno_funcionamento',
                ('fundo_nome_gestor', 'fundo_local_administracao'),
                ('fundo_responsavel_nome', 'fundo_responsavel_email', 'fundo_responsavel_telefone')
            )
        }),
        ('5. Recursos Financeiros', {
            'fields': (
                ('recursos_proprios_aplicados', 'recursos_proprios_percentual'),
                ('recursos_sus_aplicados', 'recursos_sus_percentual'),
            )
        }),
        ('6. Consórcio', {
            'fields': ('possui_consorcio', 'consorcio_nome', 'consorcio_cnpj', 'consorcio_responsavel')
        }),
    )

from django.contrib import admin
from .models import ConfiguracaoNivel
# ============================================================================
# ADMIN.PY - CONFIGURAÇÃO CORRIGIDA PARA ConfiguracaoNivel
# ============================================================================
# Localize a classe ConfiguracaoNivelAdmin no seu admin.py e substitua por:

from django.contrib import admin
from .models import ConfiguracaoNivel

@admin.register(ConfiguracaoNivel)
class ConfiguracaoNivelAdmin(admin.ModelAdmin):
    """
    Admin para ConfiguracaoNivel com suporte ao novo campo clientes_liberados.
    """
    list_display = [
        'nivel',
        'get_nivel_display_custom',
        'liberar_preenchimento',  # IMPORTANTE: Adicionado aqui
        'get_quantidade_clientes',
        'get_status_descricao'
    ]

    list_editable = ['liberar_preenchimento']  # Agora funciona porque está em list_display

    list_filter = ['nivel', 'liberar_preenchimento']

    search_fields = ['nivel']

    filter_horizontal = ['clientes_liberados']  # Interface drag-and-drop para ManyToMany

    fieldsets = (
        ('Configuração Básica', {
            'fields': ('nivel', 'liberar_preenchimento')
        }),
        ('Clientes Específicos (Opcional)', {
            'fields': ('clientes_liberados',),
            'description': 'Se vazio e "Liberar" marcado, libera TODOS. Se tiver clientes, libera APENAS os selecionados.',
            'classes': ('collapse',)  # Colapsado por padrão
        }),
    )

    def get_nivel_display_custom(self, obj):
        """Exibe o nome amigável do nível."""
        return obj.get_nivel_display()
    get_nivel_display_custom.short_description = 'Nome do Nível'

    def get_quantidade_clientes(self, obj):
        """Mostra quantidade de clientes liberados."""
        qtd = obj.clientes_liberados.count()
        if qtd == 0:
            return "Todos" if obj.liberar_preenchimento else "-"
        return f"{qtd} cliente(s)"
    get_quantidade_clientes.short_description = 'Clientes Liberados'

    def get_status_descricao(self, obj):
        """Status visual simplificado."""
        if not obj.liberar_preenchimento:
            return "🔴 Bloqueado"
        if obj.clientes_liberados.exists():
            return "🟡 Específicos"
        return "🟢 Todos"
    get_status_descricao.short_description = 'Status'

    class Meta:
        verbose_name = "Configuração de Nível"
        verbose_name_plural = "Configurações de Níveis"


# ============================================================================
# ALTERNATIVA SIMPLES (se preferir minimalista):
# ============================================================================

# @admin.register(ConfiguracaoNivel)
# class ConfiguracaoNivelAdmin(admin.ModelAdmin):
#     list_display = ['nivel', 'liberar_preenchimento']
#     list_editable = ['liberar_preenchimento']
#     filter_horizontal = ['clientes_liberados']




from django.contrib import admin
from .models import CartaoCorporativo

# Ações personalizadas para habilitar/desabilitar em massa
@admin.action(description="Habilitar função cartão para selecionados")
def habilitar_cartoes(modeladmin, request, queryset):
    queryset.update(habilitado=True)
    # Mensagem de feedback no admin
    modeladmin.message_user(request, "Cartões selecionados foram habilitados com sucesso.")

@admin.action(description="Desabilitar função cartão para selecionados")
def desabilitar_cartoes(modeladmin, request, queryset):
    queryset.update(habilitado=False)
    modeladmin.message_user(request, "Cartões selecionados foram desabilitados.")

@admin.register(CartaoCorporativo)
class CartaoCorporativoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'limite', 'saldo_atual_admin', 'habilitado')
    list_filter = ('habilitado',)
    search_fields = ('usuario__username', 'usuario__first_name')
    actions = [habilitar_cartoes, desabilitar_cartoes]

    # Exibe o saldo calculado dinamicamente na listagem do admin
    def saldo_atual_admin(self, obj):
        return f"R$ {obj.saldo_atual:.2f}"
    saldo_atual_admin.short_description = "Saldo Atual"


from django.contrib import admin
from django.utils.html import format_html
from .models import (
    RecebimentoNota, ContratoEmail, DocumentoPadrao,
    DocumentoModelo, DocumentoModeloGerado, NotaFiscalPDF, EnvioMensal
)
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    RecebimentoNota, ContratoEmail, DocumentoPadrao,
    DocumentoModelo, DocumentoModeloGerado, NotaFiscalPDF, EnvioMensal
)

# ─────────────────────────────────────────────────────────────────────────────
#  INLINES (Para exibir dentro de outros modelos)
# ─────────────────────────────────────────────────────────────────────────────

class ContratoEmailInline(admin.TabularInline):
    model = ContratoEmail
    extra = 1

class DocumentoModeloGeradoInline(admin.TabularInline):
    model = DocumentoModeloGerado
    extra = 0
    readonly_fields = ('gerado_em', 'gerado_por')

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURAÇÕES DO ADMIN
# ─────────────────────────────────────────────────────────────────────────────

@admin.register(RecebimentoNota)
class RecebimentoNotaAdmin(admin.ModelAdmin):
    list_display = ('nota', 'confirmado', 'valor_recebido', 'data_recebimento', 'registrado_por')
    list_filter = ('confirmado', 'data_recebimento')
    search_fields = ('nota__numero_nfse', 'nota__cliente_nome')
    # Nota: autocomplete_fields exige que NotaFiscalAdmin tenha search_fields definido.
    #autocomplete_fields = ('nota',)

@admin.register(ContratoEmail)
class ContratoEmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'contrato', 'nome_contato', 'principal')
    list_filter = ('principal',)
    search_fields = ('email', 'contrato__omie_num_ctr', 'nome_contato')

@admin.register(DocumentoPadrao)
class DocumentoPadraoAdmin(admin.ModelAdmin):
    list_display = ('get_tipo_display', 'data_validade', 'status_visual', 'link_arquivo')
    list_filter = ('tipo', 'data_validade')

    def status_visual(self, obj):
        colors = {'vencido': 'red', 'alerta': 'orange', 'ok': 'green'}
        status = obj.status_validade
        return format_html(
            '<strong style="color: {};">{}</strong>',
            colors.get(status, 'black'),
            status.upper()
        )
    status_visual.short_description = 'Status'

    def link_arquivo(self, obj):
        if obj.arquivo:
            return format_html('<a href="{}" target="_blank">📄 Ver PDF</a>', obj.arquivo.url)
        return "Sem arquivo"
    link_arquivo.short_description = 'Arquivo'

@admin.register(DocumentoModelo)
class DocumentoModeloAdmin(admin.ModelAdmin):
    # Ajustado: removido municipio e tipo_entidade. Adicionado label e contrato.
    list_display = ('exibir_label', 'contrato', 'tipo', 'ativo', 'atualizado_em')
    list_filter = ('tipo', 'ativo', 'contrato')
    search_fields = ('nome_personalizado', 'contrato__omie_num_ctr', 'descricao')
    inlines = [DocumentoModeloGeradoInline]

    def exibir_label(self, obj):
        return obj.label()
    exibir_label.short_description = 'Nome do Modelo'

@admin.register(DocumentoModeloGerado)
class DocumentoModeloGeradoAdmin(admin.ModelAdmin):
    # Ajustado: contrato agora é uma property ou acessado via modelo.
    list_display = ('modelo', 'exibir_contrato', 'periodo', 'gerado_em', 'link_download')
    list_filter = ('ano', 'mes', 'modelo')
    search_fields = ('modelo__contrato__omie_num_ctr', 'modelo__nome_personalizado')

    def exibir_contrato(self, obj):
        return obj.contrato # Acessa a @property do seu model
    exibir_contrato.short_description = 'Contrato'

    def periodo(self, obj):
        return f"{obj.mes:02d}/{obj.ano}"
    periodo.short_description = 'Mês/Ano'

    def link_download(self, obj):
        if obj.arquivo:
            return format_html('<a href="{}" target="_blank">⬇️ Download</a>', obj.arquivo.url)
        return "-"
    link_download.short_description = 'Arquivo'


@admin.register(NotaFiscalPDF)
class NotaFiscalPDFAdmin(admin.ModelAdmin):
    list_display = ('nota', 'baixado_em', 'link_pdf')
    search_fields = ('numero_nfse', 'cliente_nome', 'valor_nota')

    def link_pdf(self, obj):
        if obj.arquivo:
            return format_html('<a href="{}" target="_blank">📄 Abrir Nota</a>', obj.arquivo.url)
        return "-"
    link_pdf.short_description = 'PDF'


@admin.register(EnvioMensal)
class EnvioMensalAdmin(admin.ModelAdmin):
    list_display   = ('contrato', 'periodo', 'status', 'enviado_em', 'enviado_por')
    list_filter    = ('status', 'ano', 'mes')
    search_fields  = ('contrato__omie_num_ctr', 'contrato__cliente_nome')
    readonly_fields = ('criado_em', 'primeiro_envio_em')

    def periodo(self, obj):
        return f"{obj.mes:02d}/{obj.ano}"
    periodo.short_description = 'Competência'

    actions = ['marcar_como_enviado']

    @admin.action(description="Marcar selecionados como Enviado Externo")
    def marcar_como_enviado(self, request, queryset):
        queryset.update(status='externo')

    # ← get_urls no nível da classe, fora do método acima
    def get_urls(self):
        urls = super().get_urls()
        extras = [
            path(
                'relatorio-envios/',
                self.admin_site.admin_view(view_relatorio_envio_emails),
                name='relatorio_envio_emails',
            ),
        ]
        return extras + urls

from django.contrib import admin
from .models import Contrato

@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    # --- Configurações de Exibição na Lista ---
    list_display = (
        'omie_num_ctr',
        'cliente_nome',
        'valor_mensal',
        'status_omie',
        'tipo_entidade',
        'municipio',
        'data_vigencia_final'
    )

    # Filtros laterais para facilitar a navegação
    list_filter = ('tipo_entidade', 'status_omie', 'data_vigencia_inicial')

    # Campos de busca (útil para encontrar clientes ou contratos específicos)
    search_fields = ('omie_num_ctr', 'cliente_nome', 'municipio', 'omie_cod_ctr')

    # Ordenação padrão (mais recentes primeiro)
    ordering = ('-atualizado_em',)

    # --- Configurações do Formulário de Edição (Detail View) ---
    fieldsets = (
        ('Identificadores Omie', {
            'fields': (('omie_cod_ctr', 'omie_num_ctr'),)
        }),
        ('Dados do Cliente', {
            'fields': ('cliente_id_omie', 'cliente_nome', 'municipio', 'tipo_entidade')
        }),
        ('Valores e Prazos', {
            'fields': ('valor_mensal', ('data_vigencia_inicial', 'data_vigencia_final'))
        }),
        ('Status e Controle', {
            'fields': ('status_omie', 'atualizado_em'),
        }),
    )

    # Campos que só podem ser lidos (protege dados sensíveis sincronizados da API)
    readonly_fields = ('atualizado_em', 'omie_cod_ctr')

    # Melhora a performance se você tiver milhares de registros no futuro
    show_full_result_count = False

from django.contrib import admin
from .models import NotaFiscal

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'numero_nfse',
        'omie_nfse_id',
        'cliente_nome',
        'valor_bruto',
        'valor_liquido',
        'competencia_mes',
        'competencia_ano',
        'data_emissao',
        'status',
        'contrato',
        'municipio',
        'tipo_entidade_display',
        'foi_paga',
        'valor_recebido_real',
        'atualizado_em',
        'criado_em',
    )

    list_filter = (
        'status',
        'competencia_ano',
        'competencia_mes',
        'contrato__municipio',
        'contrato__tipo_entidade',
    )

    search_fields = (
        'numero_nfse',
        'omie_nfse_id',
        'cliente_nome',
        'descricao',
        'contrato__nome',
    )

    readonly_fields = (
        'atualizado_em',
        'criado_em',
        'municipio',
        'tipo_entidade',
        'tipo_entidade_display',
        'foi_paga',
        'valor_recebido_real',
    )

    fieldsets = (
        ('Vínculo', {
            'fields': ('contrato',)
        }),
        ('Identificadores Omie', {
            'fields': ('omie_nfse_id', 'numero_nfse', 'omie_os_id')
        }),
        ('Dados da Nota', {
            'fields': ('cliente_nome', 'descricao', 'valor_bruto', 'valor_iss', 'valor_liquido')
        }),
        ('Competência', {
            'fields': ('competencia_mes', 'competencia_ano', 'data_emissao')
        }),
        ('Status / Inativação', {
            'fields': ('status', 'inativada_por', 'inativada_em', 'motivo_inativacao')
        }),
        ('Metadados', {
            'fields': ('atualizado_em', 'criado_em')
        }),
        ('Derivados do Contrato', {
            'fields': ('municipio', 'tipo_entidade', 'tipo_entidade_display', 'foi_paga', 'valor_recebido_real')
        }),
    )

    ordering = ('-competencia_ano', '-competencia_mes', '-data_emissao')
    date_hierarchy = 'data_emissao'

import csv
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.http import HttpResponse

MESES_PT_REL = {
    1:'Janeiro', 2:'Fevereiro', 3:'Março',    4:'Abril',
    5:'Maio',    6:'Junho',     7:'Julho',     8:'Agosto',
    9:'Setembro',10:'Outubro',  11:'Novembro', 12:'Dezembro',
}

def view_relatorio_envio_emails(request):
    """Relatório consolidado de envios de e-mail por competência."""
    from .models import EnvioMensal  # ajuste o import conforme seu app

    ano_sel = request.GET.get('ano', '')
    mes_sel = request.GET.get('mes', '')

    qs = (
        EnvioMensal.objects
        .filter(status='enviado', primeiro_envio_em__isnull=False)
        .select_related('contrato', 'enviado_por')
        .order_by('contrato__cliente_nome', '-ano', '-mes')
    )
    if ano_sel:
        qs = qs.filter(ano=int(ano_sel))
    if mes_sel:
        qs = qs.filter(mes=int(mes_sel))

    linhas = []
    for envio in qs:
        emails = list(
            envio.contrato.emails
            .values_list('email', flat=True)
            .order_by('principal', 'nome_contato')
        )
        linhas.append({
            'contrato':       envio.contrato.omie_num_ctr,
            'tomador':        envio.contrato.cliente_nome or '—',
            'municipio':      envio.contrato.municipio or '—',
            'competencia':    f'{MESES_PT_REL[envio.mes]}/{envio.ano}',
            'primeiro_envio': envio.primeiro_envio_em,
            'ultimo_envio':   envio.enviado_em,
            'enviado_por':    envio.enviado_por.get_full_name() or envio.enviado_por.username if envio.enviado_por else '—',
            'emails':         emails,
            'qtd_emails':     len(emails),
        })

    # ── Export CSV ────────────────────────────────────────────
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="relatorio_envios_email.csv"'
        w = csv.writer(response, delimiter=';')
        w.writerow([
            'Contrato', 'Tomador', 'Município', 'Competência',
            'Primeiro Envio', 'Último Envio', 'Enviado Por', 'E-mails',
        ])
        for l in linhas:
            w.writerow([
                l['contrato'],
                l['tomador'],
                l['municipio'],
                l['competencia'],
                l['primeiro_envio'].strftime('%d/%m/%Y %H:%M') if l['primeiro_envio'] else '',
                l['ultimo_envio'].strftime('%d/%m/%Y %H:%M')   if l['ultimo_envio']   else '',
                l['enviado_por'],
                ', '.join(l['emails']),
            ])
        return response

    # ── Anos disponíveis para filtro ──────────────────────────
    anos = (
        EnvioMensal.objects
        .filter(status='enviado')
        .values_list('ano', flat=True)
        .distinct()
        .order_by('-ano')
    )

    context = {
        **admin.site.each_context(request),
        'title':    'Relatório de Envio de E-mails',
        'linhas':   linhas,
        'anos':     anos,
        'meses':    MESES_PT_REL,
        'ano_sel':  ano_sel,
        'mes_sel':  mes_sel,
        'total':    len(linhas),
    }
    return render(request, 'admin/relatorio_envio_emails.html', context)


from .models import PrestacaoContas, PCItem, PCAnexo, PCHistorico

@admin.register(PrestacaoContas)
class PrestacaoContasAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'etapa_atual', 'cliente', 'modificado_em']
    list_filter   = ['etapa_atual']
    search_fields = ['cliente__nome', 'nome_unidade_pdf', 'numero_processo']

@admin.register(PCItem)
class PCItemAdmin(admin.ModelAdmin):
    list_display  = ['numero', 'descricao', 'tem_inconsistencia', 'prestacao']
    list_filter   = ['tem_inconsistencia']

admin.site.register(PCAnexo)
admin.site.register(PCHistorico)



from django.contrib import admin


# ── ConfiguracaoFinanceira ───────────────────────────────────────────────────

@admin.register(ConfiguracaoFinanceira)
class ConfiguracaoFinanceiraAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Impostos sobre Notas Fiscais", {
            "fields": ("percentual_imposto_nota",),
            "description": (
                "Define o percentual de imposto (ex.: ISS) descontado do valor das "
                "notas fiscais na análise detalhada por município."
            ),
        }),
    )

    def has_add_permission(self, request):
        # Bloqueia criação de um segundo registro
        return not ConfiguracaoFinanceira.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ── VinculoFuncionarioCentro ─────────────────────────────────────────────────

class VinculoFuncionarioCentroInline(admin.TabularInline):
    model = VinculoFuncionarioCentro
    extra = 1
    autocomplete_fields = ["centro"]          # exige search_fields em CentroDeCustoAdmin
    verbose_name = "Centro de Custo vinculado"
    verbose_name_plural = "Centros de Custo vinculados (rateio de salário)"




# Injeta o inline em UsuarioPerfilAdmin (definido antes, mas inline depende de VinculoFuncionarioCentroInline)
UsuarioPerfilAdmin.inlines = [VinculoFuncionarioCentroInline]


@admin.register(VinculoFuncionarioCentro)
class VinculoFuncionarioCentroAdmin(admin.ModelAdmin):
    """
    Gerencia todos os vínculos Funcionário × Centro de Custo.
    Use para verificação/correção em massa ou quando precisar vincular
    vários funcionários ao mesmo centro de uma só vez.
    """
    list_display   = ("perfil", "get_cargo", "centro")
    list_filter    = ("centro",)
    search_fields  = (
        "perfil__user__first_name", "perfil__user__last_name",
        "perfil__user__username", "centro__nome",
    )
    autocomplete_fields = ["perfil", "centro"]
    ordering = ("perfil__user__first_name", "perfil__user__last_name", "centro")

    def get_cargo(self, obj):
        return obj.perfil.cargo or "—"
    get_cargo.short_description = "Cargo"


from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django import forms
from django.contrib.admin import helpers

# Certifique-se de importar seus models corretamente
# from .models import DespesaGeral, Municipio, Entidade

# ── Formulário Intermediário para Edição em Lote ─────────────────────────────
class EdicaoEmLoteDespesaForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)

    # Substitua pelas importações corretas de Municipio e Entidade
    # municipio = forms.ModelChoiceField(queryset=Municipio.objects.all(), required=False, label="Novo Município")
    # entidade = forms.ModelChoiceField(queryset=Entidade.objects.all(), required=False, label="Nova Entidade")

    valor = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, label="Novo Valor Geral",
        help_text="Deixe em branco se não quiser alterar o valor das despesas selecionadas."
    )


# ── DespesaGeral ─────────────────────────────────────────────────────────────
@admin.register(DespesaGeral)
class DespesaGeralAdmin(admin.ModelAdmin):
    list_display = (
        "descricao", "get_classificacao", "valor", "mes_referencia",
        "status", "municipio", "recorrente", "data_vencimento", "get_urgencia",
    )
    list_filter  = (
        "classificacao", "status", "recorrente",
        "mes_referencia", "municipio",
    )
    search_fields = (
        "descricao", "observacao", "classificacao_custom",
        "municipio", "criado_por__username",
    )
    date_hierarchy  = "mes_referencia"
    ordering        = ("-mes_referencia", "classificacao", "descricao")
    readonly_fields = ("criado_em", "atualizado_em", "criado_por")
    list_editable   = ("status",)

    # REGISTRANDO A NOVA ACTION
    actions = ['editar_em_lote']

    fieldsets = (
        ("Identificação", {
            "fields": (
                ("classificacao", "classificacao_custom"),
                "descricao",
                "municipio",
                # "entidade", # Supondo que você tenha este campo no model
            ),
        }),
        ("Valor", {
            "fields": (
                ("valor_unitario", "quantidade"),
                "valor",
            ),
            "description": "Para classificação Transporte, preencha Valor Unitário e Quantidade — "
                           "o Valor total é calculado automaticamente.",
        }),
        ("Referência e Vencimento", {
            "fields": (
                "mes_referencia",
                ("data_vencimento", "lembrete_antecedencia"),
                "recorrente",
            ),
        }),
        ("Status e Observação", {
            "fields": ("status", "observacao"),
        }),
        ("Auditoria", {
            "fields": ("criado_por", "criado_em", "atualizado_em"),
            "classes": ("collapse",),
        }),
    )

    def get_classificacao(self, obj):
        return obj.label_classificacao
    get_classificacao.short_description = "Classificação"
    get_classificacao.admin_order_field = "classificacao"

    def get_urgencia(self, obj):
        urgencia = obj.urgencia
        cores = {
            "vencida":  ("🔴", "Vencida"),
            "urgente":  ("🟠", "Urgente"),
            "proximo":  ("🟡", "Próximo"),
            "ok":       ("🟢", "OK"),
        }
        if urgencia is None:
            return "—"
        ico, label = cores.get(urgencia, ("⚪", urgencia))
        return f"{ico} {label}"
    get_urgencia.short_description = "Vencimento"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)

    # ── Action de Edição em Lote ──────────────────────────────────────────────
    @admin.action(description="Editar Valores, Município e Entidade em lote")
    def editar_em_lote(self, request, queryset):
        # Se o usuário clicou em "Aplicar" na página intermediária
        if 'apply' in request.POST:
            form = EdicaoEmLoteDespesaForm(request.POST)

            if form.is_valid():
                # Coleta apenas os campos que foram preenchidos
                update_kwargs = {}

                # Descomente abaixo quando importar os models de Município e Entidade no Form
                # municipio = form.cleaned_data.get('municipio')
                # entidade = form.cleaned_data.get('entidade')
                # if municipio: update_kwargs['municipio'] = municipio
                # if entidade: update_kwargs['entidade'] = entidade

                valor = form.cleaned_data.get('valor')
                if valor is not None:
                    update_kwargs['valor'] = valor

                # Se houver algo para atualizar, executa a query em lote (.update)
                if update_kwargs:
                    updated_count = queryset.update(**update_kwargs)
                    self.message_user(request, f"{updated_count} despesas foram atualizadas com sucesso.", messages.SUCCESS)
                else:
                    self.message_user(request, "Nenhuma alteração foi realizada. Os campos estavam em branco.", messages.WARNING)

                return HttpResponseRedirect(request.get_full_path())

        # Se o usuário acabou de selecionar os itens na lista, mostra o formulário vazio
        else:
            form = EdicaoEmLoteDespesaForm(initial={
                helpers.ACTION_CHECKBOX_NAME: request.POST.getlist(helpers.ACTION_CHECKBOX_NAME)
            })

        # Renderiza a página intermediária
        context = {
            'title': "Edição em Lote de Despesas",
            'form': form,
            'items': queryset,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }

        return render(request, 'despesageral_editar_lote.html', context)



#PREVISAO

# ─────────────────────────────────────────────────────────────────
# ADMIN DAS PREVISÕES DE PAGAMENTO
# ─────────────────────────────────────────────────────────────────
@admin.register(PrevisaoPagamento)
class PrevisaoPagamentoAdmin(admin.ModelAdmin):
    list_display = (
        'municipio',
        'tipo_entidade',
        'competencia_mes',
        'competencia_ano',
        'data_prevista',
        'valor_previsto',
        'status'
    )
    list_filter = ('status', 'tipo_entidade', 'competencia_ano', 'competencia_mes', 'municipio')
    search_fields = ('municipio',)
    readonly_fields = ('criado_em', 'atualizado_em')


@admin.register(PrevisaoPagamentoLog)
class PrevisaoPagamentoLogAdmin(admin.ModelAdmin):
    list_display = (
        'previsao',
        'tipo_evento',
        'data_prevista_snapshot',
        'valor_previsto_snapshot',
        'usuario',
        'criado_em'
    )
    list_filter = ('tipo_evento', 'criado_em')
    search_fields = ('previsao__municipio',)

    # Logs não devem ser editados pelo painel, então deixamos tudo readonly
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    # Desabilitar a opção de criar um log manualmente pelo Admin
    def has_add_permission(self, request):
        return False