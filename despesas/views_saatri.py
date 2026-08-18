# ═══════════════════════════════════════════════════════════════════════
# Emissão de NFS-e via SAATRI Direto (bypassa a Omie) — caminho alternativo
# ao faturamento pela Omie (ver faturar_lote_view em views.py).
#
# Reaproveita, por contrato selecionado:
#   - valor / descrição / competência ATUAIS do contrato na Omie
#     (ConsultarContrato — já teria sido ajustado por editar_lote_modal)
#   - dados fiscais do tomador ao vivo da Omie (ConsultarCliente)
# e envia direto pro Web Service SAATRI, sem a Omie no meio.
# ═══════════════════════════════════════════════════════════════════════
import json
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from time import sleep

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Contrato, NotaFiscal, NotaFiscalPDF, RpsSaatri, SaatriNumeracao
from .omie_service import OmieService
from .saatri import client as saatri_client
from .saatri import config as saatri_config

logger = logging.getLogger(__name__)


def _fmt_msg(msg):
    texto = f"[{msg['codigo']}] {msg['mensagem']}"
    if msg.get('correcao'):
        texto += f" — Correção: {msg['correcao']}"
    return texto


def _throttle(idx, total):
    if idx < total - 1:
        sleep(1.0)


def _num_dec(valor, default='0'):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def _dados_emissao_do_contrato(contrato, service, fonte='omie'):
    """
    Extrai valor/descrição/NBS/alíquota pra emissão. `fonte='local'` lê só
    do cache do Contrato (nenhuma chamada à Omie — rápido, sem risco de
    REDUNDANT); `fonte='omie'` consulta ao vivo (comportamento original).
    Retorna None se não conseguir montar os dados.
    """
    if fonte == 'local':
        if not contrato.descricao_servico or not contrato.valor_mensal:
            return None
        return {
            'valor':         _num_dec(contrato.valor_mensal),
            'discriminacao': contrato.descricao_servico,
            'aliquota':      _num_dec(contrato.aliquota_iss or saatri_config.ALIQUOTA_ISS_PADRAO),
            'codigo_nbs':    contrato.codigo_nbs or saatri_config.CODIGO_NBS_PADRAO,
        }

    dados_api = service.consultar_contrato_completo(contrato.omie_cod_ctr)
    if not dados_api or 'contratoCadastro' not in dados_api:
        return None

    ctr   = dados_api['contratoCadastro']
    cab   = ctr.get('cabecalho', {})
    itens = ctr.get('itensContrato', [])
    item0 = itens[0] if itens else {}

    item_cab  = item0.get('itemCabecalho', {})
    item_desc = item0.get('itemDescrServ', {})
    item_imp  = item0.get('itemImpostos', {})

    valor = item_cab.get('valorTotal') or cab.get('nValTotMes') or contrato.valor_mensal
    discriminacao = (item_desc.get('descrCompleta') or '').strip()
    aliquota = item_imp.get('aliqISS') or saatri_config.ALIQUOTA_ISS_PADRAO
    codigo_nbs = item_cab.get('codNBS') or saatri_config.CODIGO_NBS_PADRAO

    if not discriminacao or not valor:
        return None

    return {
        'valor':         _num_dec(valor),
        'discriminacao': discriminacao,
        'aliquota':      _num_dec(aliquota),
        'codigo_nbs':    str(codigo_nbs).strip() if codigo_nbs else saatri_config.CODIGO_NBS_PADRAO,
    }


def _tomador_do_contrato(contrato, service, fonte='omie'):
    """Idem, mas pros dados fiscais do tomador (CNPJ/CPF, endereço...)."""
    if fonte == 'local':
        dados = contrato.dados_tomador
        if not dados or not dados.get('cpf_cnpj') or not dados.get('codigo_municipio'):
            return None
        return dados
    return service.consultar_cliente_completo(contrato.cliente_id_omie)


def _salvar_nota_saatri(contrato, rps_saatri, nota_data):
    """Cria/atualiza a NotaFiscal (origem='saatri') a partir do retorno do WS
    e baixa o PDF (DANFSe) automaticamente para uso no envio de dossiê."""
    data_str = nota_data.get('data_emissao', '')
    try:
        data_emissao = datetime.fromisoformat(data_str).date()
    except (ValueError, TypeError):
        data_emissao = date.today()

    if rps_saatri.nota_fiscal_id:
        nota = rps_saatri.nota_fiscal
    else:
        nota = NotaFiscal(origem='saatri', contrato=contrato)

    nota.contrato            = contrato
    nota.cliente_nome        = contrato.cliente_nome
    nota.descricao           = rps_saatri.discriminacao
    nota.numero_nfse         = nota_data.get('numero', '')
    nota.codigo_verificacao  = nota_data.get('codigo_verificacao', '')
    nota.valor_bruto         = nota_data.get('base_calculo') or rps_saatri.valor_servicos
    nota.valor_iss           = nota_data.get('valor_iss') or rps_saatri.valor_iss
    nota.valor_liquido       = nota_data.get('valor_liquido') or rps_saatri.valor_servicos
    nota.competencia_mes     = rps_saatri.competencia_mes
    nota.competencia_ano     = rps_saatri.competencia_ano
    nota.data_emissao        = data_emissao
    nota.status              = 'emitida'
    nota.xml_completo        = nota_data.get('xml_completo', '')
    nota.save()

    rps_saatri.nota_fiscal   = nota
    rps_saatri.status        = 'convertido'
    rps_saatri.mensagem_erro = ''
    rps_saatri.save(update_fields=['nota_fiscal', 'status', 'mensagem_erro'])

    # Baixa o DANFSe (PDF) automaticamente — o envio de dossiê por e-mail já
    # usa NotaFiscalPDF pra anexar a nota (ver enviar_lote_dashboard).
    if not NotaFiscalPDF.objects.filter(nota=nota).exists():
        try:
            pdf_bytes = saatri_client.baixar_pdf_nfse(nota.numero_nfse, nota.codigo_verificacao)
            if pdf_bytes:
                NotaFiscalPDF.objects.create(
                    nota=nota,
                    arquivo=ContentFile(pdf_bytes, name=f'nfse_saatri_{nota.numero_nfse}.pdf'),
                )
        except Exception:
            logger.exception('Falha ao baixar PDF da NFS-e SAATRI %s', nota.numero_nfse)

    return nota


@login_required
@require_POST
def faturar_lote_saatri_view(request):
    """
    POST /receitas/contratos/faturar-lote-saatri/

    Body JSON: { "ids": [1,2,3], "competencia": {"mes_num": 8, "ano": 2026} }
    (mesmo shape de faturar_lote_view, pra reaproveitar o JS do dashboard)
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    ids = data.get('ids', [])
    if not ids:
        return JsonResponse({'ok': False, 'erro': 'Nenhum contrato informado'}, status=400)

    # fonte='local' lê tudo do cache do Contrato (rápido, zero chamada à
    # Omie — evita o throttling REDUNDANT em lotes grandes). fonte='omie'
    # consulta ao vivo, como antes.
    fonte = data.get('fonte') or 'omie'
    if fonte not in ('local', 'omie'):
        fonte = 'omie'

    competencia = data.get('competencia') or {}
    hoje = date.today()
    mes_comp = int(competencia.get('mes_num') or hoje.month)
    ano_comp = int(competencia.get('ano') or hoje.year)

    contratos = list(Contrato.objects.filter(id__in=ids))
    service   = OmieService()
    numeracao = SaatriNumeracao.obter()
    prestador = saatri_config.PRESTADOR

    sucessos, erros, msgs_erro = 0, 0, []
    total = len(contratos)

    logger.info('--- Faturar Lote SAATRI | total=%s fonte=%s ---', total, fonte)

    for idx, contrato in enumerate(contratos):
        num_ctr = contrato.omie_num_ctr or str(contrato.omie_cod_ctr)

        dados_emissao = _dados_emissao_do_contrato(contrato, service, fonte)
        if not dados_emissao:
            erros += 1
            fonte_txt = 'no cache local' if fonte == 'local' else 'na Omie'
            msgs_erro.append(
                f"<b>Ctr {num_ctr}:</b> Não foi possível obter valor/descrição do contrato {fonte_txt}."
                + (" Sincronize este contrato com a Omie pelo menos uma vez." if fonte == 'local' else "")
            )
            if fonte == 'omie':
                _throttle(idx, total)
            continue

        tomador = _tomador_do_contrato(contrato, service, fonte)
        if not tomador or not tomador.get('cpf_cnpj') or not tomador.get('codigo_municipio'):
            erros += 1
            fonte_txt = 'no cache local' if fonte == 'local' else 'na Omie'
            msgs_erro.append(
                f"<b>Ctr {num_ctr}:</b> Cadastro fiscal do cliente incompleto {fonte_txt} "
                f"(falta CNPJ/CPF ou município — necessário pro SAATRI)."
            )
            if fonte == 'omie':
                _throttle(idx, total)
            continue

        valor_iss = (dados_emissao['valor'] * dados_emissao['aliquota'] / 100).quantize(Decimal('0.01'))
        numero = numeracao.incrementar()

        rps_saatri = RpsSaatri.objects.create(
            contrato=contrato, numero=numero, serie=prestador['serie_rps'],
            competencia_mes=mes_comp, competencia_ano=ano_comp,
            valor_servicos=dados_emissao['valor'], aliquota=dados_emissao['aliquota'],
            valor_iss=valor_iss, discriminacao=dados_emissao['discriminacao'],
            item_lista_servico=saatri_config.ITEM_LISTA_SERVICO_PADRAO,
            codigo_nbs=dados_emissao['codigo_nbs'],
        )

        competencia_dt = date(ano_comp, mes_comp, 1)
        rps_dict = {
            'numero': rps_saatri.numero, 'serie': rps_saatri.serie, 'tipo': '1', 'status_rps': '1',
            'data_emissao': hoje.isoformat(), 'competencia': competencia_dt.isoformat(),
            'valor_servicos': rps_saatri.valor_servicos, 'aliquota': rps_saatri.aliquota,
            'valor_iss': rps_saatri.valor_iss, 'iss_retido': '2', 'responsavel_retencao': '1',
            'item_lista_servico': rps_saatri.item_lista_servico, 'codigo_nbs': rps_saatri.codigo_nbs,
            'discriminacao': rps_saatri.discriminacao, 'exigibilidade_iss': '1',
        }

        try:
            resultado = saatri_client.gerar_nfse(rps_dict, tomador)
        except Exception as e:
            logger.exception('Erro inesperado no GerarNfse SAATRI (RPS %s)', numero)
            rps_saatri.status = 'erro'
            rps_saatri.mensagem_erro = f'Erro de comunicação: {e}'
            rps_saatri.save(update_fields=['status', 'mensagem_erro'])
            erros += 1
            msgs_erro.append(f"<b>Ctr {num_ctr}:</b> {rps_saatri.mensagem_erro}")
            _throttle(idx, total)
            continue

        if resultado.get('notas'):
            _salvar_nota_saatri(contrato, rps_saatri, resultado['notas'][0])
            sucessos += 1
        elif resultado.get('info'):
            # Ambiente Nacional (Reforma Tributária): DPS aceita, a NFS-e
            # sai minutos depois pela SEFIN — sincronizar_saatri_pendentes_view
            # busca o resultado depois.
            rps_saatri.status = 'enviado'
            rps_saatri.mensagem_erro = ''
            rps_saatri.save(update_fields=['status', 'mensagem_erro'])
            sucessos += 1
        else:
            rps_saatri.status = 'erro'
            erros_msg = resultado.get('erros', [])
            rps_saatri.mensagem_erro = '; '.join(_fmt_msg(e) for e in erros_msg) or 'Erro desconhecido na resposta.'
            rps_saatri.save(update_fields=['status', 'mensagem_erro'])
            erros += 1
            msgs_erro.append(f"<b>Ctr {num_ctr}:</b> {rps_saatri.mensagem_erro}")

        _throttle(idx, total)

    logger.info('--- Faturar Lote SAATRI End | sucessos=%s erros=%s ---', sucessos, erros)

    return JsonResponse({
        'ok': True, 'total': total, 'sucessos': sucessos, 'erros': erros,
        'msgs_erro': msgs_erro[:8],
    })


def sincronizar_saatri_pendentes():
    """
    Para todo RpsSaatri com status='enviado' (aceito pela DPS, aguardando a
    SEFIN gerar a NFS-e no Ambiente Nacional — leva ~5min), consulta de novo
    e, se já saiu, salva a NotaFiscal + baixa o PDF (DANFSe) automaticamente
    — o mesmo PDF que o envio de dossiê por e-mail (enviar_lote_dashboard)
    depois anexa via NotaFiscalPDF.

    Chamada tanto pela sincronização manual do SAATRI quanto embutida nas
    views de sincronizar NFS-e da Omie (sincronizar_nfse / sincronizar_nfse_ajax),
    pra ficar tudo num clique só, igual já funcionava só com a Omie.

    Retorna (total, resolvidos, ainda_pendentes).
    """
    pendentes = list(RpsSaatri.objects.filter(status='enviado'))
    total = len(pendentes)
    resolvidos = 0
    ainda_pendentes = 0

    for idx, rps_saatri in enumerate(pendentes):
        try:
            resultado = saatri_client.consultar_nfse_por_rps(rps_saatri.numero, rps_saatri.serie, rps_saatri.tipo)
        except Exception:
            logger.exception('Erro ao consultar RPS SAATRI pendente %s', rps_saatri.numero)
            ainda_pendentes += 1
            _throttle(idx, total)
            continue

        if resultado.get('notas'):
            _salvar_nota_saatri(rps_saatri.contrato, rps_saatri, resultado['notas'][0])
            resolvidos += 1
        else:
            ainda_pendentes += 1
        _throttle(idx, total)

    return total, resolvidos, ainda_pendentes


@login_required
def sincronizar_saatri_pendentes_view(request):
    """GET /receitas/contratos/saatri/sincronizar-pendentes/ — versão standalone (debug/manual)."""
    total, resolvidos, ainda_pendentes = sincronizar_saatri_pendentes()
    return JsonResponse({
        'ok': True, 'total': total, 'resolvidos': resolvidos, 'ainda_pendentes': ainda_pendentes,
    })
