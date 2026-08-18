# ═══════════════════════════════════════════════════════════════════════════
#  processar_lotes_contracheque.py
#
#  Worker que processa os LoteContracheque pendentes (OCR + matching).
#  Roda FORA do ciclo de request do Django — como Always-on Task ou
#  Scheduled Task do PythonAnywhere — porque o Tesseract é chamado via
#  subprocess (por baixo do pytesseract), e subprocessos disparados de
#  dentro do worker web (uWSGI) são mortos de forma imprevisível pelo
#  próprio PythonAnywhere. Doc oficial:
#  https://help.pythonanywhere.com/pages/AsyncInWebApps/
#
#  ONDE COLOCAR ESTE ARQUIVO (confirmado a partir do seu projeto):
#      despesas/management/commands/processar_lotes_contracheque.py
#
#  Precisa também destes dois arquivos vazios (se ainda não existirem):
#      despesas/management/__init__.py
#      despesas/management/commands/__init__.py
#
#  COMO USAR
#  ─────────
#  1) Teste manual — roda uma vez, processa o que estiver pendente, e sai:
#         python manage.py processar_lotes_contracheque
#
#  2) Always-on Task (RECOMENDADO — você está em plano pago, tem direito
#     a pelo menos 1). Na aba "Tasks" do PythonAnywhere, em "Always-on
#     tasks", cadastre o comando:
#         python /home/conmac/gestao-inteligente-conmac/manage.py processar_lotes_contracheque --loop
#     Isso deixa o worker rodando continuamente, verificando novos lotes
#     a cada poucos segundos.
#
#  3) Alternativa sem Always-on — Scheduled Task rodando a cada poucos
#     minutos (planos pagos permitem granularidade de hora em hora, em
#     um minuto específico — ex.: configure 5 tasks, uma a cada 10-12min,
#     pra reduzir a latência entre o upload e o processamento começar):
#         python /home/conmac/gestao-inteligente-conmac/manage.py processar_lotes_contracheque
# ═══════════════════════════════════════════════════════════════════════════
import time
import logging

from django.core.management.base import BaseCommand

from despesas.models import LoteContracheque, Contracheque
from despesas.contracheque_ocr_service import processar_pagina_do_lote

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Processa (OCR) os lotes de contracheques pendentes. Rodar como Always-on Task ou Scheduled Task — nunca a partir de uma view web.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop', action='store_true',
            help='Roda continuamente, verificando novos lotes a cada --intervalo segundos (uso com Always-on Task).',
        )
        parser.add_argument(
            '--intervalo', type=int, default=5,
            help='Segundos entre verificações no modo --loop (padrão: 5).',
        )

    def handle(self, *args, **options):
        if options['loop']:
            self.stdout.write(self.style.SUCCESS(
                'Worker de contracheques iniciado em modo contínuo (Always-on Task). '
                f'Verificando a cada {options["intervalo"]}s.'
            ))
            while True:
                try:
                    self._processar_pendentes()
                except Exception:
                    # nunca deixa o loop morrer por causa de um lote com problema
                    logger.exception('Erro inesperado no loop do worker de contracheques')
                time.sleep(options['intervalo'])
        else:
            self._processar_pendentes()

    def _processar_pendentes(self):
        lotes = LoteContracheque.objects.filter(status=LoteContracheque.Status.PROCESSANDO)

        for lote in lotes:
            if lote.paginas_processadas >= lote.total_paginas:
                # nada a fazer (ex.: total_paginas ainda não foi calculado)
                continue

            self.stdout.write(
                f'Lote #{lote.pk}: continuando do zero {lote.paginas_processadas}/{lote.total_paginas}…'
            )

            deu_erro = False
            while lote.paginas_processadas < lote.total_paginas:
                indice = lote.paginas_processadas
                try:
                    processar_pagina_do_lote(lote, indice)
                except Exception as exc:
                    logger.exception('Falha ao processar página %s do lote #%s', indice + 1, lote.pk)
                    lote.status = LoteContracheque.Status.ERRO
                    lote.log_erro = f'Erro na página {indice + 1}: {exc}'
                    lote.save(update_fields=['status', 'log_erro'])
                    self.stdout.write(self.style.ERROR(
                        f'  Lote #{lote.pk} marcado como ERRO na página {indice + 1}: {exc}'
                    ))
                    deu_erro = True
                    break

                lote.paginas_processadas = indice + 1
                lote.save(update_fields=['paginas_processadas'])

            if not deu_erro:
                pendencias = lote.contracheques.filter(status=Contracheque.Status.PENDENTE).count()
                sem_match = lote.contracheques.filter(status=Contracheque.Status.SEM_CORRESPONDENCIA).count()
                lote.status = (
                    LoteContracheque.Status.CONCLUIDO if pendencias == 0 and sem_match == 0
                    else LoteContracheque.Status.AGUARDANDO_CONFIRMACAO
                )
                lote.save(update_fields=['status'])
                self.stdout.write(self.style.SUCCESS(
                    f'  Lote #{lote.pk} concluído — {lote.total_paginas} páginas '
                    f'({pendencias} pendentes de revisão, {sem_match} sem correspondência).'
                ))
