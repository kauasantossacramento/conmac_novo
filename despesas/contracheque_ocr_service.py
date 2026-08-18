# ═══════════════════════════════════════════════════════════════════════════
#  contracheque_ocr_service.py
#
#  Serviço de OCR e reconciliação de contracheques (recibos de pagamento).
#
#  FLUXO
#  ──────
#  1. RH envia o PDF da folha do mês (uma folha, várias páginas — no padrão
#     observado no arquivo de exemplo da CONMAC, cada página física traz
#     2 vias idênticas do MESMO colaborador, empilhadas uma sobre a outra).
#
#  2. Para cada página: renderiza em imagem (PyMuPDF) e roda OCR (Tesseract,
#     idioma 'por') separadamente na metade de cima e na metade de baixo.
#     Os contracheques da CONMAC não têm camada de texto (o texto é
#     desenhado como curvas vetoriais) — por isso o OCR é obrigatório,
#     não dá para usar extração de texto direta (`page.extract_text()`
#     retorna vazio nesse layout).
#
#  3. Se o nome das duas metades coincide → 1 colaborador por página (caso
#     padrão, validado nas 43 páginas do arquivo de exemplo). Se
#     divergem → a página tem 2 colaboradores diferentes (outro layout de
#     folha) e é dividida em 2 PDFs de 1 página cada.
#
#  4. Tenta casar automaticamente com um UsuarioPerfil cadastrado:
#       a) por CPF, se o layout do recibo trouxer esse campo (nem todo
#          software de folha imprime CPF no recibo — o da CONMAC, por
#          exemplo, não traz) → match de 100%;
#       b) por nome, com comparação "fuzzy" (SequenceMatcher) contra o
#          nome completo de cada colaborador ativo.
#
#  5. Grava um Contracheque por colaborador identificado:
#       score >= SCORE_AUTO_CONFIRMA   → status CONFIRMADO (já aparece pro
#                                         colaborador; RH só audita depois)
#       score >= SCORE_MINIMO_SUGESTAO → status PENDENTE, com perfil_sugerido
#                                         preenchido (RH confirma no modal)
#       caso contrário                 → status SEM_CORRESPONDENCIA
#
#  DEPENDÊNCIAS (pip):
#      pymupdf  pypdf  pytesseract  Pillow
#
#  DEPENDÊNCIA DE SISTEMA:
#      tesseract-ocr  +  pacote de idioma português (tesseract-ocr-por)
#      Ex. Ubuntu/Debian:
#          apt-get install tesseract-ocr tesseract-ocr-por
# ═══════════════════════════════════════════════════════════════════════════
import os
import re
import io
import logging
import unicodedata
import difflib
from decimal import Decimal, InvalidOperation

import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from pypdf import PdfReader, PdfWriter
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import UsuarioPerfil, LoteContracheque, Contracheque

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────────────────────────────────────
# DPI e faixas de recorte abaixo foram validados empiricamente contra as 43
# páginas do lote real da CONMAC (0 falhas de leitura). Propositalmente NÃO
# fazemos OCR na meia-página inteira: a área da tabela de itens é, na
# prática, quase toda em branco (1-3 linhas preenchidas num espaço para
# ~20), então recortar só o cabeçalho + a faixa de totais reduz o tempo de
# OCR por página em ~3x. Isso é a causa mais provável de o modal "travar":
# em hospedagens mais lentas (ex. planos como PythonAnywhere), o tempo de
# OCR de um chunk inteiro podia facilmente estourar o timeout do worker —
# o mesmo tipo de limite que já apareceu no pipeline de OCR/compressão de
# PDF do sistema.
OCR_DPI = 200
OCR_LANG = 'por'
OCR_CONFIG = '--psm 6'

# frações de altura da PÁGINA INTEIRA (não da meia-página) onde ficam os
# campos que interessam, na via de CIMA:
FAIXA_CABECALHO = (0.0, 0.135)   # nome, cargo, código, competência
FAIXA_TOTAIS    = (0.25, 0.50)   # total vencimentos/descontos, salário base…
# a via de BAIXO é uma cópia idêntica, deslocada exatamente +0.5 da página
OFFSET_VIA_BAIXO = 0.5

# score (0-100) a partir do qual o vínculo é confirmado automaticamente,
# sem esperar clique do RH. Ajuste conforme a confiança desejada.
SCORE_AUTO_CONFIRMA = Decimal('92.0')
# score mínimo para SEQUER sugerir um colaborador (abaixo disso, vai
# direto para "sem correspondência").
SCORE_MINIMO_SUGESTAO = Decimal('60.0')

MESES_NOME_PARA_NUM = {
    'JANEIRO': 1, 'FEVEREIRO': 2, 'MARCO': 3, 'ABRIL': 4, 'MAIO': 5, 'JUNHO': 6,
    'JULHO': 7, 'AGOSTO': 8, 'SETEMBRO': 9, 'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12,
}
MESES_NUM_PARA_NOME = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


def normalizar_nome(texto: str) -> str:
    """Maiúsculas, sem acento, espaços colapsados — para comparação robusta."""
    if not texto:
        return ''
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'\s+', ' ', texto).strip().upper()


def _to_decimal(valor_str):
    """Converte '5.000,00' (formato BR) em Decimal('5000.00')."""
    if not valor_str:
        return None
    try:
        limpo = valor_str.strip().replace('.', '').replace(',', '.')
        return Decimal(limpo)
    except (InvalidOperation, AttributeError):
        return None


# ──────────────────────────────────────────────────────────────────────────
# OCR + parsing de UM bloco (meia página = 1 via do recibo)
# ──────────────────────────────────────────────────────────────────────────
from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor

_OCR_POOL = None


def _obter_pool_ocr():
    global _OCR_POOL
    if _OCR_POOL is None:
        # Substituído ProcessPoolExecutor por ThreadPoolExecutor para
        # evitar travamentos de memória (OOM Killer) no PythonAnywhere.
        _OCR_POOL = _ThreadPoolExecutor(max_workers=2)
    return _OCR_POOL


def _ocr_worker(imagem_bytes, largura, altura, lang, config):
    """Extrai texto da imagem via Tesseract. Importações locais mantidas
    por segurança em relação ao design isolado anterior."""
    from PIL import Image as _Image
    import pytesseract as _pytesseract
    img = _Image.frombytes('RGB', (largura, altura), imagem_bytes)
    return _pytesseract.image_to_string(img, lang=lang, config=config)


def _ocr_bloco(imagem_pil) -> str:
    pool = _obter_pool_ocr()
    largura, altura = imagem_pil.size
    future = pool.submit(_ocr_worker, imagem_pil.tobytes(), largura, altura, OCR_LANG, OCR_CONFIG)
    return future.result(timeout=30)  # nunca mais trava pra sempre — no máximo 30s e levanta erro


def parse_texto_recibo(texto: str) -> dict:
    """
    Extrai os campos estruturados do texto OCR de UMA via do recibo.
    Testado e validado contra o layout de folha da CONMAC (43/43 páginas
    de um lote real lidas corretamente). Os regexes são propositalmente
    tolerantes a pequenos erros de OCR (ex.: espaçamento extra).
    """
    dados = {}

    # Competência: "Julho de 2026"
    m = re.search(r'([A-Za-zçÇãÃéÉóÓ]+)\s+de\s+(\d{4})', texto)
    if m:
        nome_mes = normalizar_nome(m.group(1))
        dados['mes'] = MESES_NOME_PARA_NUM.get(nome_mes)
        dados['ano'] = int(m.group(2))

    # Código + Nome do funcionário
    # Linha típica: "27  ADEILTON LUIZ NASCIMENTO   252210   4   1"
    #                cod         nome               CBO    depto filial
    m = re.search(
        r'\n\s*(\d{1,5})\s+([A-ZÀ-Ú][A-ZÀ-Ú \.\-]{4,60}?)\s+(\d{5,6})\s+(\d{1,3})\s+(\d{1,3})\s*\n',
        texto,
    )
    if not m:
        # fallback mais permissivo (CBO/depto/filial não lidos pelo OCR)
        m = re.search(r'\n\s*(\d{1,5})\s+([A-ZÀ-Ú][A-ZÀ-Ú \.\-]{4,60})', texto)
    if m:
        dados['codigo_funcionario'] = m.group(1).strip()
        dados['nome'] = re.sub(r'\s+', ' ', m.group(2)).strip()

    # Cargo — linha seguinte ao nome, logo antes de "Admissão:"
    m = re.search(r'\n\s*([A-ZÀ-Ú][A-ZÀ-Ú \.\-]{3,60})\s*\n\s*Admiss', texto)
    if m:
        dados['cargo'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    # Data de admissão (opcional, útil para preencher UsuarioPerfil.data_admissao)
    m = re.search(r'Admiss[ãa]o[:\s]*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
    if m:
        dados['data_admissao'] = m.group(1)

    # CPF — nem todo layout traz, mas quando existe é o match mais forte
    m = re.search(r'CPF[:\s]*([\d\.\-]{11,14})', texto, re.IGNORECASE)
    if m:
        dados['cpf'] = re.sub(r'\D', '', m.group(1))

    # Totais: "Total de Vencimentos   Total de Descontos" seguido dos valores
    m = re.search(
        r'Total de Vencimentos\s+Total de Descontos.*?\n\s*([\d\.,]+)\s+([\d\.,]+)',
        texto, re.DOTALL,
    )
    if m:
        dados['valor_bruto'] = _to_decimal(m.group(1))
        dados['valor_descontos'] = _to_decimal(m.group(2))
        if dados['valor_bruto'] is not None and dados['valor_descontos'] is not None:
            dados['valor_liquido'] = dados['valor_bruto'] - dados['valor_descontos']

    return dados


def _recortar(imagem, y0_frac: float, y1_frac: float):
    largura, altura = imagem.size
    return imagem.crop((0, int(altura * y0_frac), largura, int(altura * y1_frac)))


def extrair_dados_pagina(doc_fitz, indice_pagina: int) -> dict:
    """
    Renderiza a página `indice_pagina` (0-based) e faz OCR só nas faixas
    que realmente importam (cabeçalho + bloco de totais) de cada via —
    não na meia-página inteira. Retorna os dados de cada via e um flag
    indicando se pertencem ao MESMO colaborador (caso padrão observado)
    ou a colaboradores DIFERENTES (layout com 2 pessoas por folha física
    — tratado como fallback).

    Caminho comum (99% dos casos, ambas as vias são do mesmo colaborador):
      · via de cima  → OCR do cabeçalho + totais (dados completos)
      · via de baixo → OCR só do cabeçalho (o suficiente pra comparar o
        nome e confirmar que é cópia da mesma pessoa) — os totais da via
        de baixo NÃO são lidos de novo, evitando OCR desnecessário.
    Só quando os nomes DIVERGEM é que o bloco de totais da via de baixo
    também é lido, para montar os dados do segundo colaborador.
    """
    page = doc_fitz[indice_pagina]
    pix = page.get_pixmap(dpi=OCR_DPI)
    imagem = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)

    cab_sup = _recortar(imagem, *FAIXA_CABECALHO)
    tot_sup = _recortar(imagem, *FAIXA_TOTAIS)
    cab_inf = _recortar(imagem, OFFSET_VIA_BAIXO + FAIXA_CABECALHO[0], OFFSET_VIA_BAIXO + FAIXA_CABECALHO[1])

    texto_sup = _ocr_bloco(cab_sup) + '\n' + _ocr_bloco(tot_sup)
    texto_cab_inf = _ocr_bloco(cab_inf)

    dados_sup = parse_texto_recibo(texto_sup)
    nome_inf_preliminar = parse_texto_recibo(texto_cab_inf).get('nome', '')

    mesmo_colaborador = normalizar_nome(dados_sup.get('nome', 'A')) == normalizar_nome(nome_inf_preliminar)

    if mesmo_colaborador:
        dados_inf = dados_sup  # via de baixo é cópia idêntica — não precisa reler os totais
    else:
        tot_inf = _recortar(imagem, OFFSET_VIA_BAIXO + FAIXA_TOTAIS[0], OFFSET_VIA_BAIXO + FAIXA_TOTAIS[1])
        texto_inf = texto_cab_inf + '\n' + _ocr_bloco(tot_inf)
        dados_inf = parse_texto_recibo(texto_inf)

    return {'superior': dados_sup, 'inferior': dados_inf, 'mesma_pessoa': mesmo_colaborador}


# ──────────────────────────────────────────────────────────────────────────
# Casamento (matching) com UsuarioPerfil cadastrado
# ──────────────────────────────────────────────────────────────────────────
def encontrar_perfil_correspondente(dados: dict, perfis_ativos=None):
    """
    Tenta casar os dados extraídos de UMA via com um UsuarioPerfil.
      1. CPF exato (quando o layout do recibo traz CPF)      → score 100.
      2. Nome — fuzzy match (SequenceMatcher) contra o nome
         completo de cada colaborador ativo                  → 0-100.
    Retorna (perfil_ou_None, score_decimal).
    """
    if perfis_ativos is None:
        perfis_ativos = UsuarioPerfil.objects.filter(ativo=True).select_related('user')

    cpf_extraido = dados.get('cpf')
    if cpf_extraido:
        perfil_cpf = next((p for p in perfis_ativos if p.cpf and re.sub(r'\D', '', p.cpf) == cpf_extraido), None)
        if perfil_cpf:
            return perfil_cpf, Decimal('100.0')

    nome_extraido = normalizar_nome(dados.get('nome', ''))
    if not nome_extraido:
        return None, Decimal('0.0')

    melhor_perfil, melhor_score = None, 0.0
    for perfil in perfis_ativos:
        nome_cadastro = normalizar_nome(perfil.user.get_full_name() or perfil.user.username)
        if not nome_cadastro:
            continue
        score = difflib.SequenceMatcher(None, nome_extraido, nome_cadastro).ratio() * 100
        if score > melhor_score:
            melhor_perfil, melhor_score = perfil, score

    if melhor_perfil is None:
        return None, Decimal('0.0')
    return melhor_perfil, Decimal(str(round(melhor_score, 2)))


# ──────────────────────────────────────────────────────────────────────────
# Recorte do PDF (separação automática por colaborador)
# ──────────────────────────────────────────────────────────────────────────
def _pagina_completa_pdf(pdf_bytes: bytes, indice_pagina: int) -> bytes:
    """PDF de 1 página com a página inteira (as 2 vias juntas — caso padrão)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    writer.add_page(reader.pages[indice_pagina])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _metade_pagina_pdf(pdf_bytes: bytes, indice_pagina: int, metade: str) -> bytes:
    """
    PDF de 1 página contendo apenas a metade 'superior' ou 'inferior' da
    página original — usado quando 2 colaboradores diferentes dividem a
    mesma folha física (fallback para layouts fora do padrão CONMAC).
    """
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    pagina_original = doc[indice_pagina]
    rect = pagina_original.rect
    meio = rect.y0 + (rect.height / 2)

    novo_doc = fitz.open()
    nova_pagina = novo_doc.new_page(width=rect.width, height=rect.height / 2)
    origem = fitz.Rect(rect.x0, rect.y0, rect.x1, meio) if metade == 'superior' \
        else fitz.Rect(rect.x0, meio, rect.x1, rect.y1)
    nova_pagina.show_pdf_page(nova_pagina.rect, doc, indice_pagina, clip=origem)

    saida = novo_doc.tobytes()
    novo_doc.close()
    doc.close()
    return saida


# ──────────────────────────────────────────────────────────────────────────
# Orquestração — processa UMA página do lote (chamado em chunks pela view)
# ──────────────────────────────────────────────────────────────────────────
def processar_pagina_do_lote(lote: LoteContracheque, indice_pagina: int):
    """
    Processa UMA página do PDF original do lote: OCR, parsing, matching,
    recorte e criação/atualização do(s) registro(s) de Contracheque.
    Se já existir um Contracheque CONFIRMADO para aquele colaborador
    naquela competência (re-sincronização/correção de um mês já
    processado antes), o arquivo e os valores são ATUALIZADOS em vez de
    criar um registro duplicado.
    Retorna a lista de Contracheque criados/atualizados nesta página.
    """
    import time as _time  # diagnóstico temporário — remover depois de achar o gargalo
    _t0 = _time.time()
    def _log(msg):
        print(f'[DIAG-SERVICO {_time.time()-_t0:.2f}s] {msg}', flush=True)

    _log('lendo bytes do arquivo original…')
    pdf_bytes = lote.arquivo_original.read()
    lote.arquivo_original.seek(0)
    _log('bytes lidos, abrindo com fitz…')

    doc_fitz = fitz.open(lote.arquivo_original.path)
    _log('fitz abriu, extraindo dados da página (OCR)…')
    info = extrair_dados_pagina(doc_fitz, indice_pagina)
    doc_fitz.close()
    _log('OCR concluído, consultando UsuarioPerfil no banco…')

    perfis_ativos = list(UsuarioPerfil.objects.filter(ativo=True).select_related('user'))
    _log(f'{len(perfis_ativos)} perfis ativos carregados')
    criados = []

    def _salvar(dados, arquivo_bytes, sufixo_nome):
        _log('_salvar: iniciando match…')
        mes = dados.get('mes') or lote.mes
        ano = dados.get('ano') or lote.ano
        perfil, score = encontrar_perfil_correspondente(dados, perfis_ativos)
        _log(f'_salvar: match concluído (perfil={perfil}, score={score})')

        if perfil and score >= SCORE_AUTO_CONFIRMA:
            status = Contracheque.Status.CONFIRMADO
        elif perfil and score >= SCORE_MINIMO_SUGESTAO:
            status = Contracheque.Status.PENDENTE
        else:
            status = Contracheque.Status.SEM_CORRESPONDENCIA

        nome_arquivo = f"contracheque_{ano}_{mes:02d}_pag{indice_pagina + 1}{sufixo_nome}.pdf"

        # Re-sincronização: já existe um contracheque CONFIRMADO para esse
        # colaborador nessa competência (ex.: RH reenviou o PDF com uma
        # correção) → atualiza o registro existente em vez de duplicar.
        registro = None
        if status == Contracheque.Status.CONFIRMADO and perfil:
            _log('_salvar: checando se já existe contracheque pra essa competência…')
            registro = Contracheque.objects.filter(perfil=perfil, mes=mes, ano=ano).first()
            _log(f'_salvar: checagem concluída (existente={registro})')

        if registro is None:
            registro = Contracheque(mes=mes, ano=ano)
        else:
            registro.arquivo.delete(save=False)

        registro.lote = lote
        registro.perfil = perfil if status == Contracheque.Status.CONFIRMADO else None
        registro.perfil_sugerido = perfil if status != Contracheque.Status.CONFIRMADO else None
        registro.numero_pagina = indice_pagina + 1
        registro.nome_extraido = dados.get('nome', '')
        registro.cargo_extraido = dados.get('cargo', '')
        registro.codigo_funcionario = dados.get('codigo_funcionario', '')
        registro.valor_bruto = dados.get('valor_bruto')
        registro.valor_descontos = dados.get('valor_descontos')
        registro.valor_liquido = dados.get('valor_liquido')
        registro.score_match = score
        registro.status = status
        if status == Contracheque.Status.CONFIRMADO:
            registro.confirmado_em = timezone.now()

        _log('_salvar: gravando arquivo PDF recortado em disco…')
        registro.arquivo.save(nome_arquivo, ContentFile(arquivo_bytes), save=False)
        _log('_salvar: arquivo gravado, salvando registro no banco (INSERT/UPDATE)…')
        registro.save()
        _log('_salvar: registro.save() concluído')
        return registro

    if info['mesma_pessoa']:
        _log('mesma pessoa nas 2 vias — montando PDF da página completa…')
        arquivo_bytes = _pagina_completa_pdf(pdf_bytes, indice_pagina)
        _log('PDF montado, chamando _salvar…')
        criados.append(_salvar(info['superior'], arquivo_bytes, ''))
    else:
        _log('vias de pessoas diferentes — separando em 2 PDFs…')
        bytes_sup = _metade_pagina_pdf(pdf_bytes, indice_pagina, 'superior')
        bytes_inf = _metade_pagina_pdf(pdf_bytes, indice_pagina, 'inferior')
        criados.append(_salvar(info['superior'], bytes_sup, '_a'))
        criados.append(_salvar(info['inferior'], bytes_inf, '_b'))

    _log('processar_pagina_do_lote: FIM, retornando')
    return criados