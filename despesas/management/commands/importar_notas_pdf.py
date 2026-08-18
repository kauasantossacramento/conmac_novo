"""
Importa NFS-e em PDF (layout nacional DANFSe v2.0) para o model NotaFiscal.

Uso:
    python manage.py importar_notas_pdf --mes 7 --ano 2026
    python manage.py importar_notas_pdf --mes 7 --ano 2026 --pasta /caminho/pdfs --dry-run

Os PDFs são lidos da pasta deste command (padrão) ou de --pasta. Cada PDF processado
com sucesso é renomeado para "nfse_<numero>.pdf" e movido para MEDIA_ROOT/docs_nfse/.

Como os dados são importados manualmente (fora do Omie), omie_nfse_id e omie_os_id
são gerados aleatoriamente (negativos, para nunca colidir com IDs reais sincronizados
via API). A competência (mês/ano) não é extraída do PDF: é informada pelo usuário e
aplicada a todas as notas encontradas na execução.

O contrato é vinculado automaticamente por proximidade de nome (TOMADOR do PDF vs.
Contrato.cliente_nome), usando difflib. Abaixo do limiar (--limiar-fuzzy), a nota é
criada sem contrato vinculado, para revisão manual.

Dependências:
    pip install pdfplumber pymupdf
    apt install tesseract-ocr tesseract-ocr-por   (usado só quando o PDF não tem texto nativo)
"""
import os
import random
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from despesas.models import Contrato, NotaFiscal, NotaFiscalPDF

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


TESSERACT_CMD = getattr(settings, 'TESSERACT_CMD', 'tesseract')

# Mapa de acentuação -> ASCII, 1:1 em quantidade de caracteres. Isso permite rodar os
# regexes de rótulo no texto normalizado e, com as mesmas posições, fatiar o texto
# original (mantendo acentos/caixa) para valores como nome do tomador.
_ACCENT_MAP = str.maketrans(
    'ÁÀÂÃÄáàâãäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇçÑñ',
    'AAAAAaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCcNn',
)

RE_NUMERO_DATA = re.compile(
    r'(?m)^\s*(\d{1,6})\s+(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}:\d{2}\s+'
    r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})'
)
RE_MUNICIPIO_INCIDENCIA = re.compile(
    r'(?m)\d{6,7}\s*/\s*([A-Z][A-Z\s\.\-]*?)\s*/\s*([A-Z]{2})\s*$'
)
RE_CEP_SUFIXO = re.compile(r'\d{6,7}\s*/\s*[\d\-]{8,9}\s*$')
RE_CNPJ = re.compile(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')
RE_MONEY = re.compile(r'R\$\s*([\d\.]+,\d{2})')


def normalizar(texto):
    return texto.translate(_ACCENT_MAP).upper()


def para_decimal(valor_str):
    if not valor_str:
        return None
    limpo = valor_str.replace('.', '').replace(',', '.')
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def extrair_texto_via_ocr(caminho_pdf):
    if fitz is None:
        return ''
    partes = []
    try:
        documento = fitz.open(caminho_pdf)
        for pagina in documento:
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(3, 3))
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                caminho_png = tmp.name
            try:
                pixmap.save(caminho_png)
                resultado = subprocess.run(
                    [TESSERACT_CMD, caminho_png, 'stdout', '-l', 'por', '--psm', '6'],
                    capture_output=True, encoding='utf-8', errors='replace', timeout=60,
                )
                partes.append(resultado.stdout or '')
            finally:
                os.unlink(caminho_png)
    except Exception:
        return ''
    return '\n'.join(partes)


def extrair_texto_pdf(caminho_pdf):
    """Tenta texto nativo (pdfplumber); se vier vazio/insuficiente (PDF "protegido",
    comum em algumas prefeituras que renderizam o DANFSe como vetor), cai para OCR."""
    texto = ''
    if pdfplumber is not None:
        try:
            with pdfplumber.open(caminho_pdf) as pdf:
                texto = '\n'.join((pagina.extract_text() or '') for pagina in pdf.pages)
        except Exception:
            texto = ''

    if len(texto.strip()) < 200 or 'NFS-E' not in normalizar(texto):
        texto_ocr = extrair_texto_via_ocr(caminho_pdf)
        if len(texto_ocr.strip()) > len(texto.strip()):
            texto = texto_ocr

    return texto


def _valores_apos_label(padrao_label, texto_norm):
    """Valores 'R$ x,xx' logo após um rótulo: na própria linha ou, quando o rótulo faz
    parte de uma linha de cabeçalho de tabela, na linha seguinte (linha de dados)."""
    m = re.search(padrao_label, texto_norm)
    if not m:
        return []

    # Verifica a própria linha do rótulo e, se vazia, as próximas linhas não-vazias
    # (o OCR às vezes insere uma linha em branco entre o rótulo e a linha de valores).
    resto = texto_norm[m.end():]
    for linha in resto.split('\n')[:6]:
        valores = RE_MONEY.findall(linha)
        if valores:
            return valores
    return []


def _detectar_sufixo_duplicado(linha_norm):
    """Fallback para quando a linha "Município Incidência" não foi localizada (ou não
    bate) e a linha do tomador ainda termina em "/UF": detecta se as últimas k palavras
    antes do "/UF" repetem as k palavras imediatamente anteriores (ex. "...CAMPO ALEGRE
    DE LOURDES CAMPO ALEGRE DE LOURDES/BA") e retorna (posição de corte, frase repetida)
    usando a posição real na própria linha_norm — não por contagem de palavras — para
    não perder alinhamento por espaçamento irregular do OCR."""
    m_uf = re.search(r'/([A-Z]{2})\s*$', linha_norm)
    if not m_uf:
        return None, None

    texto_sem_uf = linha_norm[:m_uf.start()].rstrip()
    palavras = texto_sem_uf.split()
    n = len(palavras)
    for k in range(min(6, n // 2), 0, -1):
        if palavras[n - k:] == palavras[n - 2 * k:n - k]:
            padrao_frase = re.compile(r'\s+'.join(re.escape(p) for p in palavras[n - k:]))
            ocorrencias = list(padrao_frase.finditer(texto_sem_uf))
            if ocorrencias:
                return ocorrencias[-1].start(), ' '.join(palavras[n - k:])
    return None, None


def _extrair_tomador(texto, norm):
    """Retorna (cliente_nome, cnpj_tomador, municipio_tomador) a partir do bloco
    TOMADOR / ADQUIRENTE. municipio_tomador vem da linha "Município Incidência do ISSQN",
    que nos testes corresponde ao município do próprio tomador — mais confiável para
    associar o Contrato do que o nome (que às vezes vem com a cidade antes da razão
    social, ex. "RAFAEL JAMBEIRO CAMARA MUNICIPAL")."""
    m_tomador = re.search(r'TOMADOR\s*/\s*ADQUIRENTE', norm)
    if not m_tomador:
        return None, None, None

    m_servico = re.search(r'SERVICO\s+PRESTADO', norm[m_tomador.end():])
    fim = m_tomador.end() + m_servico.start() if m_servico else len(norm)
    bloco_norm = norm[m_tomador.end():fim]
    bloco_orig = texto[m_tomador.end():fim]

    m_cnpj = RE_CNPJ.search(bloco_orig)
    cnpj_tomador = m_cnpj.group(0) if m_cnpj else None

    m_municipio = RE_MUNICIPIO_INCIDENCIA.search(norm)
    municipio_tomador = m_municipio.group(1).strip() if m_municipio else None

    cliente_nome = None
    m_nome_label = re.search(r'NOME\s*/\s*NOME\s+EMPRESARIAL[^\n]*\n', bloco_norm)
    if m_nome_label:
        linhas_norm = bloco_norm[m_nome_label.end():].split('\n')
        linhas_orig = bloco_orig[m_nome_label.end():].split('\n')
        linha_norm = linha_orig = ''
        for ln, lo in zip(linhas_norm, linhas_orig):
            if ln.strip():
                linha_norm, linha_orig = ln, lo
                break

        if linha_orig:
            m_cep = RE_CEP_SUFIXO.search(linha_norm)
            if m_cep:
                linha_norm = linha_norm[:m_cep.start()]
                linha_orig = linha_orig[:m_cep.start()]

            if m_municipio:
                municipio_uf_norm = f'{municipio_tomador}/{m_municipio.group(2)}'
                if linha_norm.rstrip().endswith(municipio_uf_norm):
                    corte = len(linha_norm.rstrip()) - len(municipio_uf_norm)
                    linha_norm = linha_norm[:corte]
                    linha_orig = linha_orig[:corte]

            corte_fallback, frase_repetida = _detectar_sufixo_duplicado(linha_norm)
            if corte_fallback is not None:
                linha_orig = linha_orig[:corte_fallback]
                if not municipio_tomador:
                    municipio_tomador = frase_repetida

            # letra solta remanescente de ruído de OCR no fim da linha (ex.: "... BARBARA B")
            linha_orig = re.sub(r'\s+[A-Za-zÀ-ú]\s*$', '', linha_orig)
            cliente_nome = linha_orig.strip() or None

    return cliente_nome, cnpj_tomador, municipio_tomador


def _extrair_descricao(texto, norm):
    m_desc = re.search(r'DESCRICAO\s+DO\s+SERVICO\s*\n', norm)
    if not m_desc:
        return None
    m_fim = re.search(r'TRIBUTACAO\s+MUNICIPAL', norm[m_desc.end():])
    fim_idx = m_desc.end() + m_fim.start() if m_fim else len(norm)
    descricao = texto[m_desc.end():fim_idx].strip()
    return descricao or None


def extrair_dados_nfse(texto, nome_arquivo=''):
    norm = normalizar(texto)
    dados = {
        'numero_nfse': None,
        'data_emissao': None,
        'competencia_pdf': None,
        'cliente_nome': None,
        'cnpj_tomador': None,
        'municipio_tomador': None,
        'descricao': None,
        'valor_bruto': None,
        'valor_iss': None,
        'valor_liquido': None,
    }

    m_num = RE_NUMERO_DATA.search(norm)
    if m_num:
        dados['numero_nfse'] = m_num.group(1)
        try:
            dados['competencia_pdf'] = datetime.strptime(m_num.group(2), '%d/%m/%Y').date()
            dados['data_emissao'] = datetime.strptime(m_num.group(3), '%d/%m/%Y').date()
        except ValueError:
            pass
    else:
        m_arquivo = re.search(r'(\d{3,6})', nome_arquivo)
        if m_arquivo:
            dados['numero_nfse'] = m_arquivo.group(1)

    dados['cliente_nome'], dados['cnpj_tomador'], dados['municipio_tomador'] = _extrair_tomador(texto, norm)
    dados['descricao'] = _extrair_descricao(texto, norm)

    valores_bruto = _valores_apos_label(r'VALOR\s+TOTAL\s+DA\s+NFS-E', norm)
    if valores_bruto:
        dados['valor_bruto'] = para_decimal(valores_bruto[0])

    valores_iss = _valores_apos_label(r'ISSQN\s+APURADO', norm)
    if valores_iss:
        dados['valor_iss'] = para_decimal(valores_iss[-1])

    valores_liquido = _valores_apos_label(r'VALOR\s+LIQUIDO\s+DA\s+NFS-E(?!\s*\+)', norm)
    if len(valores_liquido) > 1:
        dados['valor_liquido'] = para_decimal(valores_liquido[1])
    elif valores_liquido:
        dados['valor_liquido'] = para_decimal(valores_liquido[0])

    return dados


def gerar_omie_nfse_id_aleatorio():
    while True:
        candidato = -random.randint(10 ** 9, 10 ** 12)
        if not NotaFiscal.objects.filter(omie_nfse_id=candidato).exists():
            return candidato


def _chave_comparacao(texto):
    """Palavras normalizadas e ordenadas alfabeticamente, para comparar nomes
    independente da ordem em que as palavras aparecem (o TOMADOR do PDF às vezes vem
    com a cidade antes da razão social, ex. "RAFAEL JAMBEIRO CAMARA MUNICIPAL" em vez
    de "CAMARA MUNICIPAL DE RAFAEL JAMBEIRO" — SequenceMatcher.ratio() puro penaliza
    muito essa inversão e favorece nomes errados que só compartilham texto de boilerplate
    como "CAMARA MUNICIPAL DE VEREADORES")."""
    palavras = re.findall(r'[A-Z0-9]+', normalizar(texto))
    return ' '.join(sorted(palavras))


def _inferir_tipo_entidade(nome_tomador_norm):
    """Câmara ou prefeitura/município, a partir de palavras-chave no nome do tomador —
    complementa o filtro por município quando a mesma cidade tem contratos dos dois
    tipos de entidade."""
    if 'CAMARA' in nome_tomador_norm or 'VEREADOR' in nome_tomador_norm:
        return 'camara'
    if 'PREFEITURA' in nome_tomador_norm or 'MUNICIPIO' in nome_tomador_norm:
        return 'municipio'
    return None


# Diferença de pontuação (0-1) dentro da qual dois contratos são tratados como empate
# de nome e o desempate passa a considerar o valor mensal do contrato.
TOLERANCIA_EMPATE_NOME = 0.03


def encontrar_contrato(nome_tomador, municipio_tomador, valor_bruto, limiar):
    """Associa o Contrato pelo TOMADOR extraído do PDF.

    1) Restringe a busca aos contratos do mesmo município (quando identificado) e,
       dentro deles, ao mesmo tipo de entidade (câmara/prefeitura) inferido do nome —
       resolve a ambiguidade entre cidades com nomes de órgão parecidos.
    2) Pontua o nome com uma chave insensível à ordem das palavras.
    3) Se dois ou mais contratos empatarem no nome (ex. duas "CAMARA MUNICIPAL DE
       APORA" com valores/atividades diferentes), só vincula automaticamente se o
       valor mensal de um deles for claramente mais próximo do valor faturado na nota;
       caso contrário devolve None (ambíguo) para revisão manual — nunca adivinha.

    Retorna (contrato_ou_none, melhor_pontuacao, motivo), onde motivo é um de
    'nome', 'nome+valor', 'ambiguo' ou None (nenhum candidato acima do limiar).
    """
    candidatos = list(Contrato.objects.exclude(cliente_nome__isnull=True).exclude(cliente_nome=''))

    if municipio_tomador:
        alvo_municipio = normalizar(municipio_tomador)
        mesmo_municipio = [
            c for c in candidatos if c.municipio and normalizar(c.municipio) == alvo_municipio
        ]
        if mesmo_municipio:
            candidatos = mesmo_municipio

    tipo_inferido = _inferir_tipo_entidade(normalizar(nome_tomador))
    if tipo_inferido:
        mesmo_tipo = [c for c in candidatos if c.tipo_entidade == tipo_inferido]
        if mesmo_tipo:
            candidatos = mesmo_tipo

    if not candidatos:
        return None, 0.0, None

    alvo_nome = _chave_comparacao(nome_tomador)
    pontuados = sorted(
        ((c, SequenceMatcher(None, alvo_nome, _chave_comparacao(c.cliente_nome)).ratio()) for c in candidatos),
        key=lambda item: item[1], reverse=True,
    )
    melhor_contrato, melhor_pontuacao = pontuados[0]
    if melhor_pontuacao < limiar:
        return None, melhor_pontuacao, None

    empatados = [c for c, p in pontuados if melhor_pontuacao - p <= TOLERANCIA_EMPATE_NOME]
    if len(empatados) == 1:
        return melhor_contrato, melhor_pontuacao, 'nome'

    if valor_bruto is None:
        return None, melhor_pontuacao, 'ambiguo'

    com_valor = sorted(
        ((c, abs(c.valor_mensal - valor_bruto)) for c in empatados if c.valor_mensal),
        key=lambda item: item[1],
    )
    if len(com_valor) == 1:
        return com_valor[0][0], melhor_pontuacao, 'nome+valor'
    if len(com_valor) > 1 and com_valor[0][1] <= com_valor[1][1] / 2:
        return com_valor[0][0], melhor_pontuacao, 'nome+valor'

    return None, melhor_pontuacao, 'ambiguo'


class Command(BaseCommand):
    help = (
        'Importa NFS-e em PDF (layout nacional DANFSe v2.0) de uma pasta, criando '
        'NotaFiscal + NotaFiscalPDF. IDs do Omie são gerados aleatoriamente (importação manual).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--mes', type=int, required=True,
                             help='Mês de competência (1-12) aplicado a todas as notas encontradas.')
        parser.add_argument('--ano', type=int, required=True,
                             help='Ano de competência aplicado a todas as notas encontradas.')
        parser.add_argument('--pasta', type=str, default=None,
                             help='Pasta com os PDFs. Padrão: a pasta deste command.')
        parser.add_argument('--limiar-fuzzy', type=float, default=0.55,
                             help='Similaridade mínima (0-1) para vincular o Contrato pelo nome do tomador.')
        parser.add_argument('--dry-run', action='store_true',
                             help='Só mostra o que seria extraído/importado, sem gravar no banco nem mover arquivos.')
        parser.add_argument('--limpar', action='store_true',
                             help='Desfaz a importação de --mes/--ano: apaga as NotaFiscal (e PDFs) e devolve '
                                  'os arquivos para --pasta, para permitir corrigir e rodar de novo. '
                                  'Sem --confirmar, só mostra o que seria removido.')
        parser.add_argument('--confirmar', action='store_true',
                             help='Confirma a execução de --limpar (sem essa flag, --limpar é só um preview).')

    def handle(self, *args, **options):
        mes = options['mes']
        ano = options['ano']
        if not (1 <= mes <= 12):
            raise CommandError('--mes deve estar entre 1 e 12.')

        pasta_origem = Path(options['pasta']) if options['pasta'] else Path(__file__).resolve().parent
        pasta_destino = Path(settings.MEDIA_ROOT) / 'docs_nfse'
        dry_run = options['dry_run']
        limiar = options['limiar_fuzzy']

        if not pasta_origem.is_dir():
            raise CommandError(f'Pasta não encontrada: {pasta_origem}')

        if options['limpar']:
            self._limpar_competencia(mes, ano, pasta_origem, options['confirmar'])
            return

        pdfs = sorted(pasta_origem.glob('*.pdf'))
        if not pdfs:
            self.stdout.write(self.style.WARNING(f'Nenhum PDF encontrado em {pasta_origem}'))
            return

        if not dry_run:
            pasta_destino.mkdir(parents=True, exist_ok=True)

        total_importadas = total_puladas = total_erros = 0

        for caminho_pdf in pdfs:
            self.stdout.write(f'\n→ {caminho_pdf.name}')
            try:
                texto = extrair_texto_pdf(str(caminho_pdf))
                if len(texto.strip()) < 50:
                    self.stdout.write(self.style.ERROR(
                        '  Não foi possível extrair texto (nem nativo, nem OCR). Pulando.'))
                    total_erros += 1
                    continue
                dados = extrair_dados_nfse(texto, caminho_pdf.name)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  Falha ao processar: {exc}'))
                total_erros += 1
                continue

            if not dados['numero_nfse']:
                self.stdout.write(self.style.ERROR(
                    '  Não foi possível identificar o número da NFS-e. Pulando.'))
                total_erros += 1
                continue

            numero_nfse = dados['numero_nfse']
            nome_destino = f'nfse_{numero_nfse}.pdf'
            caminho_final = pasta_destino / nome_destino

            self.stdout.write(f'  Número NFS-e: {numero_nfse}')
            self.stdout.write(f'  Tomador: {dados["cliente_nome"] or "-"}  (CNPJ: {dados["cnpj_tomador"] or "-"})')
            self.stdout.write(f'  Município tomador: {dados["municipio_tomador"] or "-"}')
            self.stdout.write(
                f'  Valor bruto: {dados["valor_bruto"]}  |  ISS: {dados["valor_iss"]}  |  '
                f'Líquido: {dados["valor_liquido"]}')
            self.stdout.write(f'  Data emissão: {dados["data_emissao"] or "-"}')

            if dados['competencia_pdf'] and (
                dados['competencia_pdf'].month != mes or dados['competencia_pdf'].year != ano
            ):
                self.stdout.write(self.style.WARNING(
                    f'  Competência no PDF ({dados["competencia_pdf"].month:02d}/'
                    f'{dados["competencia_pdf"].year}) difere da informada '
                    f'({mes:02d}/{ano}). Mantendo a informada.'))

            contrato = None
            if dados['cliente_nome']:
                contrato, pontuacao, motivo = encontrar_contrato(
                    dados['cliente_nome'], dados['municipio_tomador'], dados['valor_bruto'], limiar)
                if contrato:
                    sufixo = ' — desempatado pelo valor mensal' if motivo == 'nome+valor' else ''
                    self.stdout.write(self.style.SUCCESS(
                        f'  Contrato vinculado: {contrato} (similaridade {pontuacao:.0%}){sufixo}'))
                    if contrato.valor_mensal and dados['valor_bruto']:
                        delta = abs(contrato.valor_mensal - dados['valor_bruto'])
                        if delta / contrato.valor_mensal > Decimal('0.3'):
                            self.stdout.write(self.style.WARNING(
                                f'  Aviso: valor da nota (R$ {dados["valor_bruto"]}) diverge do valor '
                                f'mensal do contrato (R$ {contrato.valor_mensal}). Confira antes de aceitar.'))
                elif motivo == 'ambiguo':
                    self.stdout.write(self.style.WARNING(
                        f'  Nome bate com mais de um contrato (similaridade {pontuacao:.0%}) e o valor '
                        f'da nota não permite desempatar com segurança. Nota será criada sem vínculo.'))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  Nenhum contrato com similaridade >= {limiar:.0%} '
                        f'(melhor: {pontuacao:.0%}). Nota será criada sem vínculo.'))
            else:
                self.stdout.write(self.style.WARNING('  Nome do tomador não identificado.'))

            ja_existe = NotaFiscal.objects.filter(
                numero_nfse=numero_nfse, competencia_mes=mes, competencia_ano=ano,
            ).exists()

            if ja_existe:
                self.stdout.write(self.style.WARNING(
                    f'  Já existe NotaFiscal {numero_nfse} para {mes:02d}/{ano}. Não será duplicada.'))
                total_puladas += 1
                if not dry_run:
                    self._mover_pdf(caminho_pdf, caminho_final)
                continue

            if dry_run:
                self.stdout.write(self.style.NOTICE('  [dry-run] Nada foi gravado.'))
                continue

            movido = False
            try:
                with transaction.atomic():
                    nota = NotaFiscal.objects.create(
                        contrato=contrato,
                        omie_nfse_id=gerar_omie_nfse_id_aleatorio(),
                        numero_nfse=numero_nfse,
                        omie_os_id=-random.randint(10 ** 9, 10 ** 12),
                        cliente_nome=dados['cliente_nome'] or '',
                        descricao=dados['descricao'] or '',
                        valor_bruto=dados['valor_bruto'] or Decimal('0'),
                        valor_iss=dados['valor_iss'] or Decimal('0'),
                        valor_liquido=dados['valor_liquido'] or dados['valor_bruto'] or Decimal('0'),
                        competencia_mes=mes,
                        competencia_ano=ano,
                        data_emissao=dados['data_emissao'],
                        status='emitida',
                    )
                    self._mover_pdf(caminho_pdf, caminho_final)
                    movido = True
                    NotaFiscalPDF.objects.create(nota=nota, arquivo=f'docs_nfse/{nome_destino}')
            except Exception as exc:
                if movido and caminho_final.exists():
                    shutil.move(str(caminho_final), str(caminho_pdf))
                self.stdout.write(self.style.ERROR(f'  Erro ao salvar: {exc}'))
                total_erros += 1
                continue

            self.stdout.write(self.style.SUCCESS(
                f'  Importada como NotaFiscal #{nota.pk} e PDF movido para {caminho_final}'))
            total_importadas += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nConcluído: {total_importadas} importadas, {total_puladas} já existentes, '
            f'{total_erros} com erro.'))

    @staticmethod
    def _mover_pdf(origem: Path, destino: Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origem), str(destino))

    def _limpar_competencia(self, mes, ano, pasta_origem, confirmar):
        """Desfaz a importação de --mes/--ano: apaga as NotaFiscal (e, em cascata, o
        NotaFiscalPDF) e devolve o PDF físico para pasta_origem, para permitir corrigir
        a lógica e rodar a importação de novo do zero. Sem --confirmar, só lista o que
        seria removido."""
        notas = list(NotaFiscal.objects.filter(competencia_mes=mes, competencia_ano=ano))
        if not notas:
            self.stdout.write(self.style.WARNING(f'Nenhuma NotaFiscal encontrada para {mes:02d}/{ano}.'))
            return

        self.stdout.write(f'{len(notas)} NotaFiscal(is) encontrada(s) para {mes:02d}/{ano}:')
        for nota in notas:
            self.stdout.write(
                f'  #{nota.pk}  nfse_{nota.numero_nfse}  {nota.cliente_nome or "-"}  '
                f'R$ {nota.valor_bruto}  contrato={nota.contrato_id or "-"}')

        if not confirmar:
            self.stdout.write(self.style.WARNING(
                f'\n[preview] Nada foi removido. Rode de novo com --limpar --confirmar para excluir '
                f'essas NotaFiscal e devolver os PDFs para {pasta_origem}'))
            return

        removidas = devolvidos = 0
        for nota in notas:
            pdf_local = getattr(nota, 'pdf_local', None)
            if pdf_local and pdf_local.arquivo:
                origem = Path(pdf_local.arquivo.path)
                if origem.exists():
                    pasta_origem.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(origem), str(pasta_origem / origem.name))
                    devolvidos += 1
            nota.delete()
            removidas += 1

        self.stdout.write(self.style.SUCCESS(
            f'{removidas} NotaFiscal(is) removida(s), {devolvidos} PDF(s) devolvido(s) para {pasta_origem}.'))
