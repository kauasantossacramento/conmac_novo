from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

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

]
