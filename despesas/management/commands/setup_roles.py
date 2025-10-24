from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from despesas.models import Despesa, LoteReembolso, CentroDeCusto, AssociacaoCentroCusto
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Cria grupos Admin do Módulo e Colaborador com permissões básicas."

    def handle(self, *args, **kwargs):
        # Colaborador: pode adicionar/alterar/apenas SUAS despesas; ver centros atribuídos
        colaborador, _ = Group.objects.get_or_create(name="Colaborador")
        admin_modulo, _ = Group.objects.get_or_create(name="AdminModulo")

        # Permissões por modelo
        for model in [Despesa, CentroDeCusto, AssociacaoCentroCusto, LoteReembolso]:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            # AdminModulo recebe todas
            admin_modulo.permissions.add(*perms)

        # Colaborador: apenas add/change own despesas (controle fino no view)
        # Concede add_despesa e change_despesa; listar centros/associações
        for codename in ["add_despesa", "change_despesa", "view_centrodecusto", "view_associacaocentrocusto", "view_despesa"]:
            p = Permission.objects.get(codename=codename)
            colaborador.permissions.add(p)

        self.stdout.write(self.style.SUCCESS("Grupos e permissões configurados."))
