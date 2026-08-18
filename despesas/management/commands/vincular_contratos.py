from django.core.management.base import BaseCommand
from django.db.models import Q

# Ajuste o import conforme o seu app
from despesas.models import CentroDeCusto, Contrato, VinculoCentroCustoContrato

class Command(BaseCommand):
    help = 'Recria vínculos entre Centros de Custo e Contratos, classificando por PM, CM ou AUT.'

    def handle(self, *args, **options):
        # ── 1. Ferramenta de Exclusão ─────────────────────────────────────────
        self.stdout.write(self.style.WARNING("Gerenciador de Vínculos Contratuais"))
        
        resp = input("Deseja excluir TODOS os vínculos atuais antes de recriar? (s/N): ")
        if resp.strip().lower() == 's':
            apagados, _ = VinculoCentroCustoContrato.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"  [-] {apagados} vínculos antigos foram excluídos.\n"))
        else:
            self.stdout.write(self.style.WARNING("  [!] Vínculos antigos mantidos. Apenas atualizando/criando novos.\n"))

        self.stdout.write(self.style.WARNING("Iniciando varredura de municípios..."))

        # ── 2. Regra 1: Somente Ativos ────────────────────────────────────────
        centros_ativos = CentroDeCusto.objects.filter(ativo=True)
        
        contratos_validos = Contrato.objects.exclude(
            Q(municipio__isnull=True) | Q(municipio__exact='')
        )

        vinculos_criados = 0
        vinculos_atualizados = 0

        for cc in centros_ativos:
            nome_cc_upper = cc.nome.upper()
            palavras_cc = nome_cc_upper.split() # Para isolar "CM" e evitar "PACMAN"
            
            for contrato in contratos_validos:
                municipio_upper = contrato.municipio.upper().strip()
                
                if municipio_upper in nome_cc_upper:
                    
                    # ── 3. Classificação (Regras 2, 3 e 4 + Contrato) ──────────
                    # Verifica o nome do Centro de Custo e cruza com a info do Omie
                    if "CIRSP" in nome_cc_upper:
                        tipo_classificacao = 'AUT'
                    elif "CM" in palavras_cc or contrato.tipo_entidade == 'camara':
                        tipo_classificacao = 'CM'
                    else:
                        tipo_classificacao = 'PM'
                    
                    # ── 4. Gravação (update_or_create) ─────────────────────────
                    obj, created = VinculoCentroCustoContrato.objects.update_or_create(
                        centro_de_custo=cc,
                        contrato=contrato,
                        defaults={
                            'criado_automaticamente': True,
                            'tipo_entidade': tipo_classificacao
                        }
                    )
                    
                    if created:
                        vinculos_criados += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  [+] NOVO ({tipo_classificacao}): {cc.nome} <-> Contrato {contrato.omie_num_ctr}")
                        )
                    else:
                        vinculos_atualizados += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  [*] ATUALIZADO ({tipo_classificacao}): {cc.nome} <-> Contrato {contrato.omie_num_ctr}")
                        )

        # Resumo
        self.stdout.write("\n")
        self.stdout.write(self.style.SUCCESS(
            f'Concluído! {vinculos_criados} novos vínculos criados e {vinculos_atualizados} atualizados.'
        ))