from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView



urlpatterns = [
    # auth
    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),

    # home + rotas do módulo
    path("", views.home, name="home"),
    path("viagens/", views.viagens_lista, name="viagens_lista"),
    path("despesas/nova/", views.despesa_create, name="despesa_create"),
    path("despesas/<int:pk>/", views.despesa_detail, name="despesa_detail"),

    # admin
    path("admin-centros/", views.admin_centros, name="admin_centros"),
    path("admin-centros/<int:centro_id>/", views.admin_centro_detail, name="admin_centro_detail"),
    path("admin-despesas/<int:pk>/aprovar/", views.aprovar_despesa, name="aprovar_despesa"),
    path("admin-despesas/<int:pk>/reprovar/", views.reprovar_despesa, name="reprovar_despesa"),

    # reembolso
    path("admin-reembolso/lote/novo/", views.lote_create, name="lote_create"),
    path("admin-reembolso/lote/<int:pk>/", views.lote_detail, name="lote_detail"),

    # relatório / placeholders
    path("relatorio/", views.relatorio, name="relatorio"),
    path("notificacoes/", views.notificacoes_placeholder, name="notificacoes"),
    path("links/", views.links_placeholder, name="links"),

    # checklist
    path("checklist/adicionar/", views.checklist_add, name="checklist_add"),
    path("checklist/<int:pk>/done/", views.checklist_done, name="checklist_done"),
    path("despesas/<int:pk>/modal/", views.despesa_modal, name="despesa_modal"),
    path("despesas/<int:pk>/editar/", views.despesa_update, name="despesa_update"),
    path("centros/", views.centros_index, name="centros_index"),
    path("centros/modal/novo/", views.centro_novo_modal, name="centro_novo_modal"),
    path("centros/modal/associar/<int:centro_id>/", views.associar_analista_modal, name="associar_analista_modal"),
    path("centros/relatorio/", views.centros_relatorio_redirect, name="centros_relatorio"),
    # despesas/urls.py
    path("centros/associacao/<int:assoc_id>/remover/", views.centro_associacao_remover, name="centro_associacao_remover"),
    # despesas/urls.py
    path("relatorio-colaborador/", views.relatorio_colaborador, name="relatorio_colaborador"),

    path("usuarios/novo/", views.usuario_create_modal, name="usuario_create_modal"),
    path("relatorio/", views.relatorio_usuario, name="relatorio"),  # <-- relatório do usuário (mantém o nome atual)
    path("relatorio-centro/", views.relatorio_centro, name="relatorio_centro"),  # <-- relatório admin por centro
    path("centros/relatorio/", views.centros_relatorio_redirect, name="centros_relatorio"),  # redirect do filtro admin
        path(
        "centros/despesa/<int:pk>/",
        views.despesa_modal_admin,
        name="despesa_modal_admin",
    ),
    path("viagens/centros/", views.viagens_centros, name="viagens_centros"),
    path("despesas/<int:pk>/editar/", views.despesa_edit, name="despesa_edit"),
    path("despesas/<int:pk>/editar/", views.despesa_edit, name="despesa_editar"),

    path("despesas/lote-modal/", views.despesas_lote_modal, name="despesas_lote_modal"),
    path("centros/despesa/<int:pk>/", views.despesa_modal_admin, name="despesa_modal_admin"),
    path("centros/despesa/<int:pk>/nav/", views.despesa_modal_nav, name="despesa_modal_nav"),
    path("despesas/<int:pk>/excluir/", views.despesa_delete, name="despesa_delete"),
    path("despesas/api/pendentes-ultimas5-duplicadas/", views.api_pendentes_ultimas5_duplicadas,
         name="api_pendentes_ultimas5_duplicadas"),
    path('manifest.json', TemplateView.as_view(template_name="manifest.json", content_type='application/json')),
    path("centros/pendentes-summary/", views.centros_pendentes_summary, name="centros_pendentes_summary"),
    #path("fechamento/", views.fechamento_clientes_list, name="fechamento_clientes_list"),
    path("fechamento/cliente/<int:cliente_id>/", views.fechamento_cliente_detail, name="fechamento_cliente_detail"),
    path("fechamento/registro/<int:registro_id>/alterar/", views.etapa_alterar_status, name="etapa_alterar_status"),
    #path("fechamento/", views.fechamento_clientes_list, name="fechamento_clients_list"),
    path("fechamento/registro/<int:registro_id>/alterar/", views.etapa_alterar_status, name="etapa_alterar_status"),
    # nova rota:
    path("fechamento/registro/criar/", views.etapa_criar_registro, name="etapa_criar_registro"),
    path('fechamento/registro/<int:registro_id>/historico/', views.etapa_historico_list, name='etapa_historico_list'),
    path('api/push/register/', views.push_register_device, name='push_register_device'),
    path("sw.js/", views.service_worker, name="service_worker"),
    path("vapid.js/", views.vapid_js, name="vapid_js"),
    path("push/register/", views.push_register_device, name="push_register_device"),
    path('atividades/', views.atividades_home, name='atividades_home'),
    path('liberar_competencia', views.liberar_competencia, name='liberar_competencia'),
    path("conmacfest2025/", views.rsvp_create, name="rsvp_create"),
    path(
        "firebase-messaging-sw.js",
        TemplateView.as_view(
            template_name="firebase-messaging-sw.js",
            content_type="application/javascript",
        ),
        name="firebase-messaging-sw.js",
    ),
    path('api/salvar-fcm-token/', views.salvar_fcm_token, name='salvar_fcm_token'),
    path('api/disparar-notificacoes/', views.api_disparar_notificacoes, name='api_disparar_notificacoes'),
    path('relatorio/administrativo/', views.relatorio_administrativo, name='relatorio_administrativo'),
    path('etapa/salvar/', views.etapa_salvar, name='etapa_salvar'),
    path('etapa/excluir/<int:etapa_id>/', views.etapa_excluir, name='etapa_excluir'),
    path('etapa/atualizar/', views.atualizar_etapa_registro, name='atualizar_etapa_registro'),
    path('fechamento/cliente/<int:cliente_id>/', views.fechamento_cliente_detail, name='fechamento_cliente_detail'),

    path('etapa/solicitar-reabertura/<int:registro_id>/', views.solicitar_reabertura, name='solicitar_reabertura'),
    path('solicitacoes/gerenciar/', views.gerenciar_solicitacao, name='gerenciar_solicitacao'),

    path('siops/<slug:slug_prefeitura>/', views.preencher_questionario, name='questionario_siops'),
    path('painel/', views.painel_acompanhamento_view, name='painel_acompanhamento'),
    path('api/painel-data/', views.api_painel_data, name='api_painel_data'),
    path('salvar-config-nivel/', views.salvar_configuracao_nivel, name='salvar_configuracao_nivel'),
    path('receitas/', views.receitas_dashboard, name='receitas_dashboard'),
    path('receitas/sincronizar/', views.sincronizar_receitas_view, name='sincronizar_receitas'),
    path('receitas/editar-lote/', views.editar_lote_modal, name='receitas_editar_lote'),
    path('rh/', views.rh_dashboard, name='rh_dashboard'),
    path('rh/atualizar-salario/', views.rh_atualizar_dados, name='rh_atualizar_dados'),
    path('receitas/notas/',                       views.notas_competencia,    name='notas_competencia'),
    path('receitas/notas/<int:nota_id>/confirmar/', views.confirmar_recebimento, name='confirmar_recebimento'),
    path('receitas/notas/sincronizar/',            views.sincronizar_nfse,     name='sincronizar_nfse'),
    path('receitas/relatorio/',                    views.relatorio_receitas,    name='relatorio_receitas'),
    path('receitas/notas/<int:nota_id>/inativar/', views.inativar_nota, name='inativar_nota'),
    path('receitas/contratos/<int:contrato_id>/municipio/', views.editar_municipio_contrato,  name='editar_municipio_contrato'),
    path('receitas/documentos/', views.gestao_documentos, name='gestao_documentos'),
    path('receitas/documentos/padrao/salvar/', views.salvar_documento_padrao, name='salvar_documento_padrao'),
    path('receitas/documentos/padrao/<int:pk>/excluir/', views.excluir_documento_padrao, name='excluir_documento_padrao'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/salvar/', views.salvar_documento_modelo, name='salvar_documento_modelo'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/<int:pk>/excluir/', views.excluir_documento_modelo, name='excluir_documento_modelo'),
    path('receitas/contratos/<int:contrato_id>/documentos/', views.documentos_contrato, name='documentos_contrato'),
    path('receitas/contratos/<int:contrato_id>/emails/', views.gerenciar_emails, name='gerenciar_emails'),
    path('receitas/contratos/<int:contrato_id>/emails/<int:pk>/excluir/', views.excluir_email, name='excluir_email'),
    path('receitas/documentos/modelo/gerar/', views.gerar_documento_modelo, name='gerar_documento_modelo'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/<int:pk>/excluir/', views.excluir_documento_modelo, name='excluir_documento_modelo'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/gerar-lote/', views.gerar_modelos_lote, name='gerar_modelos_lote'),
    path('receitas/notas/<int:nota_id>/baixar-pdf/', views.baixar_nfse_pdf, name='baixar_nfse_pdf'),
    path('receitas/notas/<int:nota_id>/baixar-pdf-saatri/', views.baixar_nfse_pdf_saatri, name='baixar_nfse_pdf_saatri'),
    path('receitas/envio/<int:envio_id>/enviar/', views.enviar_dossie, name='enviar_dossie'),
    path('receitas/envio/<int:envio_id>/status/', views.alterar_status_envio, name='alterar_status_envio'),
    path('receitas/lote/competencias/', views.competencias_lote, name='competencias_lote'),
    path('receitas/lote/gerar/', views.gerar_lote_dashboard, name='gerar_lote_dashboard'),
    path('receitas/lote/enviar/', views.enviar_lote_dashboard, name='enviar_lote_dashboard'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/gerados-status/', views.gerados_status, name='gerados_status'),
    path('receitas/contratos/<int:contrato_id>/documentos/modelo/gerados-status/', views.gerados_status, name='gerados_status'),
    path('receitas/sincronizar-nfse/', views.sincronizar_nfse_ajax, name='sincronizar_nfse_ajax'),
    path('relatorio/municipios-pivot/', views.relatorio_municipios_pivot, name='relatorio_municipios_pivot'),
    path('ferramentas/pdf-ocr/',
         views.ocr_compress_page,       name='ocr_compress_page'),

    path('ferramentas/pdf-ocr/iniciar/',
         views.ocr_iniciar,             name='ocr_iniciar'),

    path('ferramentas/pdf-ocr/chunk/',
         views.ocr_processar_chunk,     name='ocr_processar_chunk'),

    path('ferramentas/pdf-ocr/finalizar/',
         views.ocr_finalizar,           name='ocr_finalizar'),

    path('confronto-balanco/', views.processar_balanco_pdf, name='processar_balanco_pdf'),
        path(
        'contratos/email-municipio/',
        views.adicionar_email_municipio,
        name='adicionar_email_municipio',
    ),
    path('receitas/contratos/faturar-lote/', views.faturar_lote_view, name='faturar_lote'),
    path('receitas/contratos/status-faturamento/', views.status_faturamento_contratos, name='status_faturamento_contratos'),
    path('receitas/contratos/faturar-lote-saatri/', views.faturar_lote_saatri_view, name='faturar_lote_saatri'),
    path('receitas/contratos/saatri/sincronizar-pendentes/', views.sincronizar_saatri_pendentes_view, name='sincronizar_saatri_pendentes'),
    path('receitas/contratos/saatri/pendentes/', views.saatri_pendentes_listar, name='saatri_pendentes_listar'),
    path('receitas/contratos/saatri/resolver-chunk/', views.saatri_pendentes_resolver_chunk, name='saatri_pendentes_resolver_chunk'),

    path('envios/<int:envio_id>/prefetch-nfse/',
         views.prefetch_nfse_pdf,
         name='prefetch_nfse_pdf'),

    path('monitor-boletos/', views.boleto_monitor, name='monitor_boletos'),
    path('tcm/',      views.tcm_monitor, name='tcm_monitor'),

    #MÓDULO DE PRESTAÇÃO DE CONTAS:

    path(
    'prestacao-contas/',
    views.prestacao_contas_monitor,
    name='prestacao_contas_monitor',
    ),

    # ── Cadastrar nova PC ─────────────────────────────────────────────────
    path(
        'prestacao-contas/nova/',
        views.prestacao_contas_nova,
        name='prestacao_contas_nova',
    ),

    # ── Detalhe / Trabalho por PC ─────────────────────────────────────────
    path(
        'prestacao-contas/<int:pk>/',
        views.prestacao_contas_detalhe,
        name='prestacao_contas_detalhe',
    ),

    # ── Actions (POST) ────────────────────────────────────────────────────
    path(
        'prestacao-contas/<int:pk>/avancar/',
        views.pc_avancar_etapa,
        name='pc_avancar_etapa',
    ),
    path(
        'prestacao-contas/<int:pk>/item/<int:item_pk>/toggle/',
        views.pc_item_toggle_inconsistencia,
        name='pc_item_toggle',
    ),
    path(
        'prestacao-contas/<int:pk>/item/<int:item_pk>/obs/',
        views.pc_item_salvar_obs,
        name='pc_item_salvar_obs',
    ),
    path(
        'prestacao-contas/<int:pk>/upload-anexo/',
        views.pc_upload_anexo,
        name='pc_upload_anexo',
    ),
    path(
        'prestacao-contas/<int:pk>/upload-comprovante/',
        views.pc_upload_comprovante,
        name='pc_upload_comprovante',
    ),
    path(
        'prestacao-contas/<int:pk>/vincular-cliente/',
        views.pc_vincular_cliente,
        name='pc_vincular_cliente',
    ),

    # ── APIs JSON ─────────────────────────────────────────────────────────
    path(
        'prestacao-contas/api/identificar-cliente/',
        views.api_identificar_cliente_pc,
        name='api_identificar_cliente_pc',
    ),
    path(
        'prestacao-contas/api/data/',
        views.api_pc_data,
        name='api_pc_data',
    ),

    # Retorno de etapa (SIGA → Análise)
    path('prestacao-contas/<int:pk>/solicitar-retorno/',
         views.pc_solicitar_retorno, name='pc_solicitar_retorno'),

    # Confirmação de item pelo SIGA
    path('prestacao-contas/<int:pk>/item/<int:item_pk>/confirmar-siga/',
         views.pc_item_confirmar_siga, name='pc_item_confirmar_siga'),

    # OK do Jurídico em item
    path('prestacao-contas/<int:pk>/item/<int:item_pk>/ok-juridico/',
         views.pc_item_ok_juridico, name='pc_item_ok_juridico'),

    # Anotações por item
    path('prestacao-contas/<int:pk>/item/<int:item_pk>/anotar/',
         views.pc_item_anotar, name='pc_item_anotar'),
    path('prestacao-contas/<int:pk>/item/<int:item_pk>/anotacoes/',
         views.pc_item_anotacoes, name='pc_item_anotacoes'),

    # Prazos
    path('prestacao-contas/<int:pk>/prazos/',
         views.pc_prazos, name='pc_prazos'),
    path('prestacao-contas/<int:pk>/prazos/salvar/',
         views.pc_prazo_salvar, name='pc_prazo_salvar'),
    path('prestacao-contas/<int:pk>/prazos/<int:prazo_pk>/concluir/',
         views.pc_prazo_concluir, name='pc_prazo_concluir'),
    path('prestacao-contas/<int:pk>/prazos/<int:prazo_pk>/excluir/',
         views.pc_prazo_excluir, name='pc_prazo_excluir'),


   #DESPESAS GERAIS
    path("despesas-gerais/",                  views.despesas_gerais,           name="despesas_gerais"),
    path("despesas-gerais/criar/",            views.despesa_geral_create,      name="despesa_geral_create"),
    path("despesas-gerais/lote/",             views.despesa_geral_lote_create, name="despesa_geral_lote_create"),
    path("despesas-gerais/<int:pk>/editar/",  views.despesa_geral_update,      name="despesa_geral_update"),
    path("despesas-gerais/<int:pk>/excluir/", views.despesa_geral_delete,      name="despesa_geral_delete"),
    path("raio-x/",                           views.raio_x,                    name="raio_x"),
    path("verificar-senha/",                  views.verificar_senha,           name="verificar_senha"),
    path("toggle-sync-pagamento/",            views.toggle_sync_pagamento,     name="toggle_sync_pagamento"),
    path('prestacao-contas/<int:pk>/salvar-periodo/', views.pc_salvar_periodo, name='pc_salvar_periodo'),
    path('raio-x/municipio-detalhe/', views.api_municipio_detalhe, name='raio_x_municipio_detalhe'),
    path('previsao/salvar/', views.previsao_salvar, name='previsao_salvar'),
    path('previsao/marcar/', views.previsao_marcar, name='previsao_marcar'),


    path('rh/contracheques/upload/', views.rh_contracheque_upload,
         name='rh_contracheque_upload'),
    path('rh/contracheques/<int:lote_id>/status/', views.rh_contracheque_status,
         name='rh_contracheque_status'),
    path('rh/contracheques/<int:lote_id>/pendencias/', views.rh_contracheque_pendencias,
         name='rh_contracheque_pendencias'),
    path('rh/contracheques/confirmar/', views.rh_contracheque_confirmar,
         name='rh_contracheque_confirmar'),
    path('rh/contracheques/ignorar/', views.rh_contracheque_ignorar,
         name='rh_contracheque_ignorar'),

    # ── Colaborador ──
    path('meus-contracheques/', views.colaborador_contracheques,
         name='colaborador_contracheques'),
    path('meus-contracheques/<int:contracheque_id>/arquivo/', views.colaborador_contracheque_arquivo,
         name='colaborador_contracheque_arquivo'),
]

