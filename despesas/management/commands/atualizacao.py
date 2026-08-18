from django.core.management.base import BaseCommand
from despesas.models import DespesaGeral, Contrato

class Command(BaseCommand):
    help = 'Normaliza o campo tipo_orgao de todas as despesas gerais baseado nos contratos'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando normalização da base de dados...")

        # 1. Pega todos os municípios que são Câmaras
        camaras_nomes = list(
            Contrato.objects
            .filter(status_omie='10', tipo_entidade='camara')
            .values_list('municipio', flat=True)
            .distinct()
        )

        count = 0
        # 2. Corrige todas as despesas
        for dg in DespesaGeral.objects.filter(municipio__isnull=False).exclude(municipio=''):
            novo_tipo = 'camara' if dg.municipio in camaras_nomes else 'prefeitura'
            
            # Só salva se houver mudança para evitar processamento desnecessário
            if dg.tipo_orgao != novo_tipo:
                dg.tipo_orgao = novo_tipo
                dg.save()
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"Base normalizada com sucesso! {count} despesas foram atualizadas.")
        )