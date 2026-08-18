"""
Management command: backfill_recorrencia_id
===========================================
Despesas recorrentes criadas antes do campo `recorrencia_id` existir
ficam com esse campo NULL. Este comando agrupa essas despesas pelo par
(classificacao, descricao) e atribui um UUID compartilhado para cada
grupo, permitindo edição/exclusão em lote por recorrência.

Uso:
    python manage.py backfill_recorrencia_id
    python manage.py backfill_recorrencia_id --dry-run
"""

import uuid
from django.core.management.base import BaseCommand
from despesas.models import DespesaGeral


class Command(BaseCommand):
    help = (
        'Backfill recorrencia_id para despesas recorrentes sem UUID de grupo. '
        'Agrupa por (classificacao, descricao) e atribui um UUID compartilhado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas exibe o que seria feito, sem salvar no banco.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('⚠  Modo DRY-RUN — nenhuma alteração será salva.\n'))

        # Pares (classificacao, descricao) que ainda têm registros sem recorrencia_id
        grupos = (
            DespesaGeral.objects
            .filter(recorrente=True, recorrencia_id__isnull=True)
            .values('classificacao', 'descricao')
            .distinct()
            .order_by('classificacao', 'descricao')
        )

        if not grupos.exists():
            self.stdout.write(self.style.SUCCESS(
                '✔ Nenhuma despesa recorrente sem recorrencia_id encontrada. Tudo certo!'
            ))
            return

        total_registros = 0
        total_grupos    = 0

        for grupo in grupos:
            cls  = grupo['classificacao']
            desc = grupo['descricao']

            # Reusar UUID já existente no grupo (caso parte já tenha sido preenchida)
            existing_id = (
                DespesaGeral.objects
                .filter(classificacao=cls, descricao=desc, recorrente=True)
                .exclude(recorrencia_id__isnull=True)
                .values_list('recorrencia_id', flat=True)
                .first()
            )
            novo_id = existing_id or uuid.uuid4()

            qs = DespesaGeral.objects.filter(
                classificacao=cls,
                descricao=desc,
                recorrente=True,
                recorrencia_id__isnull=True,
            )
            count = qs.count()

            action = 'Aproveitaria UUID existente' if existing_id else 'Novo UUID'
            self.stdout.write(
                f'  [{cls}] "{desc}": {count} registro(s) → {novo_id}  ({action})'
            )

            if not dry_run:
                qs.update(recorrencia_id=novo_id)

            total_registros += count
            total_grupos    += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\n⚠  DRY-RUN: {total_registros} despesa(s) em {total_grupos} grupo(s) '
                f'seriam atualizadas.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✔ {total_registros} despesa(s) atualizadas em {total_grupos} grupo(s).'
            ))