# ═══════════════════════════════════════════════════════════════════════
# ADICIONAR AO FINAL DE: pc/views.py
# Ou cole em pc/views_pc.py e importe no views.py principal
# ═══════════════════════════════════════════════════════════════════════
#
# DEPENDÊNCIAS ADICIONAIS (pip install):
#   pdfplumber   → extração de texto de PDF
#   difflib      → já incluso na stdlib Python
#
# pip install pdfplumber
# ═══════════════════════════════════════════════════════════════════════

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Prefetch
from django.shortcuts import redirect, render

import io
import re
import unicodedata
import difflib
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

# Importações dos models PC (assumindo que foram adicionados a models.py)
from .models import (
    Cliente,
    NotificacaoPush,
    PCAnexo,
    PCHistorico,
    PCItem,
    PrestacaoContas,
    EtapaPC,
    FLUXO_PC,
    PERMISSAO_AVANCO,
)
'''
try:
    from .models import UsuarioPerfil
except ImportError:
    UsuarioPerfil = None
'''

# ── Tentativa de importar pdfplumber ─────────────────────────────────────
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False


# ═══════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ═══════════════════════════════════════════════════════════════════════

'''
def _get_perfil(user):
    """Retorna o UsuarioPerfil do usuário, ou None."""
    if UsuarioPerfil is None:
        return None
    try:
        return user.perfil
    except Exception:
        return None
'''
def _get_perfil(user):
    """Retorna o perfil do usuário de forma segura, usando ORM."""
    try:
        return getattr(user, 'perfil', None)
    except Exception:
        return None

def _pode_acessar_pc(user):
    if user.is_staff or user.is_superuser:
        return True
    perfil = _get_perfil(user)
    return perfil and getattr(perfil, 'acesso_prestacao_contas', False)


def _perfil_pc(user):
    """Retorna 'JURIDICO', 'ANALISE', 'SIGA' ou '' para o módulo PC."""
    if user.is_staff or user.is_superuser:
        return 'ADMIN'
    perfil = _get_perfil(user)
    if not perfil:
        return ''
    if getattr(perfil, 'acesso_siga', False):
        return 'SIGA'
    return getattr(perfil, 'perfil_pc', '') or ''


def _normalizar_nome(nome: str) -> str:
    """
    Normaliza um nome de cliente para comparação fuzzy.
    Ex.: 'PM Glória' → 'GLORIA'
         'Prefeitura Municipal de GLORIA' → 'GLORIA'
    """
    if not nome:
        return ''
    # Remove acentos (NFD → filtra Mn)
    nome = unicodedata.normalize('NFD', nome)
    nome = ''.join(c for c in nome if unicodedata.category(c) != 'Mn')
    nome = nome.upper()
    # Remove prefixos comuns
    prefixos = [
        r'^PREFEITURA MUNICIPAL DE\s+',
        r'^PREFEITURA DE\s+',
        r'^MUNICIPIO DE\s+',
        r'^MUNICIPIO\s+',
        r'^PM\s+',
        r'^PREF\.\s+',
        r'^PREF\s+',
        r'^CAMARA MUNICIPAL DE\s+',
        r'^CM\s+',
    ]
    for p in prefixos:
        nome = re.sub(p, '', nome, flags=re.IGNORECASE)
    # Remove caracteres especiais
    nome = re.sub(r'[^A-Z0-9\s]', ' ', nome)
    return re.sub(r'\s+', ' ', nome).strip()


def _tentar_identificar_cliente(texto_pdf: str):
    """
    Tenta identificar o cliente (Prefeitura) a partir do texto extraído do PDF.
    Retorna (Cliente | None, confiança_float 0-1, nome_extraido_str).
    """
    if not texto_pdf:
        return None, 0.0, ''

    # Padrão: "UNIDADE: Prefeitura Municipal de GLORIA"
    match = re.search(
        r'UNIDADE[:\s]+(.+?)(?:\n|INSPETORIA|$)',
        texto_pdf,
        re.IGNORECASE,
    )
    nome_extraido = match.group(1).strip() if match else ''

    if not nome_extraido:
        return None, 0.0, ''

    nome_normalizado = _normalizar_nome(nome_extraido)

    # Carrega todos os clientes ativos
    clientes = list(Cliente.objects.filter(ativo=True))
    if not clientes:
        return None, 0.0, nome_extraido

    # Gera lista de (cliente, score)
    scores = []
    for c in clientes:
        nome_c_norm = _normalizar_nome(c.nome)
        ratio = difflib.SequenceMatcher(
            None, nome_normalizado, nome_c_norm
        ).ratio()
        scores.append((c, ratio))

    scores.sort(key=lambda x: x[1], reverse=True)
    melhor_cliente, melhor_score = scores[0]

    if melhor_score >= 0.70:
        return melhor_cliente, melhor_score, nome_extraido

    return None, melhor_score, nome_extraido


def _extrair_texto_pdf(arquivo_field) -> str:
    """Extrai texto completo de um FileField PDF usando pdfplumber."""
    if not PDFPLUMBER_OK or not arquivo_field:
        return ''
    try:
        arquivo_field.seek(0)
        with pdfplumber.open(arquivo_field) as pdf:
            partes = []
            for page in pdf.pages[:10]:  # Limita às 10 primeiras páginas
                t = page.extract_text()
                if t:
                    partes.append(t)
            return '\n'.join(partes)
    except Exception as e:
        logger.warning('Falha ao extrair texto do PDF: %s', e)
        return ''


def _extrair_itens_pdf(texto: str):
    """
    Extrai a lista de seções/itens do texto do PDF de prestação de contas.
    Retorna lista de dicts: {numero, descricao, nivel_hierarquico}.
    """
    if not texto:
        return []

    # Padrão: "3.1.1 Dos Créditos Adicionais Suplementares (Anexo 1)"
    # ou      "3.1 CRÉDITOS ADICIONAIS"
    # ou      "3. ALTERAÇÕES ORÇAMENTÁRIAS"
    patron = re.compile(
        r'^(\d+(?:\.\d+)*\.?)\s{1,4}(.+)',
        re.MULTILINE,
    )

    itens_raw = []
    for m in patron.finditer(texto):
        num = m.group(1).rstrip('.')
        desc = m.group(2).strip()
        # Filtra linhas muito curtas ou que são apenas cabeçalhos de página
        if len(desc) < 5 or desc.lower().startswith('página') or desc.lower().startswith('siga'):
            continue
        # Determina nível hierárquico pela quantidade de pontos
        nivel = num.count('.') + 1
        if nivel > 4:
            continue
        itens_raw.append({'numero': num, 'descricao': desc, 'nivel_hierarquico': nivel})

    # Remove duplicatas preservando ordem
    vistos = set()
    itens = []
    for item in itens_raw:
        chave = item['numero']
        if chave not in vistos:
            vistos.add(chave)
            itens.append(item)

    # Agrupa itens de alto nível para criar uma estrutura limpa
    SECOES_PRINCIPAIS = [
        ('1', 'Responsável pela Unidade'),
        ('2', 'Execução Orçamentária até o Período'),
        ('2.1', 'Demonstrativo da Receita'),
        ('2.2', 'Demonstrativo da Despesa'),
        ('3', 'Alterações Orçamentárias'),
        ('3.1', 'Créditos Adicionais'),
        ('3.1.1', 'Dos Créditos Adicionais Suplementares'),
        ('3.1.2', 'Créditos Adicionais Especiais'),
        ('3.1.3', 'Créditos Adicionais Extraordinários'),
        ('3.2', 'Quadro de Detalhamento de Despesa – QDD'),
        ('3.2.1', 'Das Alterações do Quadro de Detalhamento de Despesa'),
        ('3.3', 'Transposições, Remanejamentos e Transferências'),
        ('3.3.1', 'Das Transposições, Remanejamentos e Transferências de Dotações'),
        ('3.4', 'Descentralização de Créditos Orçamentários'),
        ('3.4.1', 'Das Descentralizações de Créditos Orçamentários'),
        ('4', 'Do Acompanhamento da Execução Financeira'),
        ('4.1', 'Da Execução Financeira'),
        ('4.2', 'Saldo Disponível (DCR)'),
        ('4.3', 'Saldo Disponível em Banco(s)'),
        ('5', 'Dos Duodécimos'),
        ('5.1', 'Valor Repassado a Título de Duodécimo (Prefeitura)'),
        ('5.2', 'Total da Transferência de Duodécimo (Câmara)'),
        ('5.3', 'Valor Total Fixado na LOA para Câmara Municipal'),
        ('5.4', 'Valor Limite – Art. 29-A da CF/88'),
        ('5.5', 'Valor Limite da Cota Mensal'),
        ('6', 'Das Obrigações Constitucionais'),
        ('6.1', 'Da Aplicação em Ações e Serviços Públicos de Saúde (ASPS)'),
        ('6.2', 'Da Aplicação em Manutenção e Desenvolvimento do Ensino (MDE)'),
        ('6.3', 'Da Aplicação do Fundo de Manutenção e Desenvolvimento do Ensino (FUNDEB)'),
        ('6.4', 'Da Despesa com Pessoal no Período'),
        ('6.4.1', 'Despesa com Pessoal por Quadrimestre'),
        ('7', 'Subsídios'),
        ('8', 'Das Transferências Especiais'),
        ('8.1', 'Receitas de Transferências Especiais Recebidas pelo Município'),
        ('8.2', 'Despesas Realizadas com Utilização da Fonte de Recurso Oriunda de Transferências Especiais'),
        ('8.3', 'Das Despesas de Capital'),
    ]

    # Usa a lista padrão como base, depois enriquece com o que extraiu do PDF
    numeros_extraidos = {i['numero'] for i in itens}
    resultado = []
    for num, desc in SECOES_PRINCIPAIS:
        # Verifica se o extractor encontrou algo para este número
        desc_final = desc
        for item_raw in itens:
            if item_raw['numero'] == num:
                desc_final = item_raw['descricao']
                break
        nivel = num.count('.') + 1
        resultado.append({'numero': num, 'descricao': desc_final, 'nivel_hierarquico': nivel})

    return resultado


def _notificar_usuarios_grupo(grupo_perfil: str, titulo: str, mensagem: str, link: str = ''):
    """
    Envia NotificacaoPush para todos os usuários de um perfil específico.
    grupo_perfil: 'JURIDICO', 'ANALISE', 'SIGA', 'ADMIN'
    """
    try:
        if grupo_perfil == 'SIGA':
            usuarios = User.objects.filter(
                perfil__acesso_siga=True,
                is_active=True,
            )
        elif grupo_perfil in ('JURIDICO', 'ANALISE'):
            usuarios = User.objects.filter(
                perfil__perfil_pc=grupo_perfil,
                perfil__acesso_prestacao_contas=True,
                is_active=True,
            )
        elif grupo_perfil == 'ADMIN':
            usuarios = User.objects.filter(is_staff=True, is_active=True)
        else:
            return

        for u in usuarios:
            NotificacaoPush.objects.create(
                usuario_alvo=u,
                titulo=titulo,
                mensagem=mensagem,
                link=link,
            )
    except Exception as e:
        logger.warning('Erro ao criar notificações PC: %s', e)


# ═══════════════════════════════════════════════════════════════════════
# VIEWS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════

from datetime import date, timedelta
# (demais imports já existentes no seu arquivo)


@login_required
def prestacao_contas_monitor(request):
    """
    Tela principal de acompanhamento de prestações de contas.
    Exibe widgets por cliente, separados em Pendentes / Concluídos.

    Parâmetros GET reconhecidos:
      etapa  – filtra por etapa_atual
      q      – busca livre (cliente, unidade, processo)
      vence  – "1" → exibe apenas prestações com prazo vencendo nos próximos 3 dias
               (hoje, amanhã e depois de amanhã)
    """
    if not _pode_acessar_pc(request.user):
        messages.error(request, 'Você não tem permissão para acessar este módulo.')
        return redirect('home')

    perfil = _perfil_pc(request.user)

    # ── Parâmetros de filtro ─────────────────────────────────
    filtro_etapa = request.GET.get('etapa', '')
    filtro_busca = request.GET.get('q', '').strip()
    filtro_vence = request.GET.get('vence', '') == '1'

    hoje            = date.today()
    amanha          = hoje + timedelta(days=1)
    depois_amanha   = hoje + timedelta(days=2)
    janela_vence    = [hoje, amanha, depois_amanha]   # fonte única de verdade

    # ── QuerySet base ────────────────────────────────────────
    qs = PrestacaoContas.objects.select_related(
        'cliente',
        'ultimo_editor'
    ).all()

    if filtro_etapa:
        qs = qs.filter(etapa_atual=filtro_etapa)

    if filtro_busca:
        qs = qs.filter(
            models.Q(cliente__nome__icontains=filtro_busca) |
            models.Q(nome_unidade_pdf__icontains=filtro_busca) |
            models.Q(numero_processo__icontains=filtro_busca)
        )

    if filtro_vence:
        qs = qs.filter(
            prazos__data_limite__in=janela_vence,   # usa a mesma janela
            prazos__concluido=False,
        ).distinct()

    # ── Listas principal e concluídos ────────────────────────
    pendentes_qs = qs.exclude(
        etapa_atual='CONCLUIDO'
    ).order_by('-modificado_em')

    concluidos = qs.filter(
        etapa_atual='CONCLUIDO'
    ).order_by('-modificado_em')

    # Pré-carrega prazos_vence com a mesma janela usada no filtro acima.
    # Quando o filtro está inativo, prazos_vence = [] para evitar queries extras.
    if filtro_vence:
        pendentes = pendentes_qs.prefetch_related(
            Prefetch(
                'prazos',
                queryset=PCPrazo.objects.filter(
                    data_limite__in=janela_vence,   # ← corrigido: igual ao filtro
                    concluido=False,
                ).order_by('data_limite'),
                to_attr='prazos_vence',
            )
        )
    else:
        pendentes = pendentes_qs.prefetch_related(
            Prefetch(
                'prazos',
                queryset=PCPrazo.objects.none(),
                to_attr='prazos_vence',
            )
        )

    # ── Paginação dos concluídos ─────────────────────────────
    paginator = Paginator(concluidos, 12)
    page_num  = request.GET.get('page', 1)
    page_obj  = paginator.get_page(page_num)

    # ── KPIs ─────────────────────────────────────────────────
    # Sempre sobre o universo completo, sem filtro de etapa/vence,
    # mas respeitando o filtro de busca, se houver.
    qs_kpi = PrestacaoContas.objects.all()

    if filtro_busca:
        qs_kpi = qs_kpi.filter(
            models.Q(cliente__nome__icontains=filtro_busca) |
            models.Q(nome_unidade_pdf__icontains=filtro_busca) |
            models.Q(numero_processo__icontains=filtro_busca)
        )

    total           = qs_kpi.count()
    em_analise      = qs_kpi.filter(etapa_atual='ANALISE').count()
    em_siga         = qs_kpi.filter(etapa_atual='SIGA').count()
    em_envio        = qs_kpi.filter(etapa_atual='ENVIO_FINAL').count()
    qtd_concluidos  = qs_kpi.filter(etapa_atual='CONCLUIDO').count()

    qtd_vencendo = qs_kpi.exclude(
        etapa_atual='CONCLUIDO'
    ).filter(
        prazos__data_limite__in=janela_vence,   # ← corrigido: mesma janela
        prazos__concluido=False,
    ).distinct().count()

    context = {
        'pendentes': pendentes,
        'concluidos_page': page_obj,

        # KPIs
        'total': total,
        'em_analise': em_analise,
        'em_siga': em_siga,
        'em_envio': em_envio,
        'qtd_concluidos': qtd_concluidos,
        'qtd_vencendo': qtd_vencendo,

        # Filtros ativos
        'filtro_etapa': filtro_etapa,
        'filtro_busca': filtro_busca,
        'filtro_vence': filtro_vence,

        'perfil_pc': perfil,
        'etapa_choices': EtapaPC.choices,
        'pode_cadastrar': perfil in ('JURIDICO', 'ADMIN'),
    }

    return render(request, 'pc/prestacao_contas_monitor.html', context)

@login_required
def prestacao_contas_nova(request):
    """
    Formulário para o setor Jurídico cadastrar uma nova prestação de contas.
    POST: cria o registro, processa PDF, tenta identificar cliente.
    """
    if not _pode_acessar_pc(request.user):
        return redirect('home')

    perfil = _perfil_pc(request.user)
    if perfil not in ('JURIDICO', 'ADMIN'):
        messages.error(request, 'Somente o setor Jurídico pode cadastrar prestações de contas.')
        return redirect('prestacao_contas_monitor')

    clientes = Cliente.objects.filter(ativo=True).order_by('nome')

    if request.method == 'POST':
        cliente_id    = request.POST.get('cliente_id')
        mes           = request.POST.get('competencia_mes')
        ano           = request.POST.get('competencia_ano')
        processo      = request.POST.get('numero_processo', '').strip()
        inspetoria    = request.POST.get('inspetoria', '').strip()
        obs_cadastro  = request.POST.get('observacao_cadastro', '').strip()
        documento     = request.FILES.get('documento_principal')

        # Validações básicas
        if not mes or not ano:
            messages.error(request, 'Competência (mês e ano) é obrigatória.')
            return render(request, 'pc/prestacao_contas_nova.html',
                          {'clientes': clientes})

        cliente_obj = None
        nome_unidade = ''

        if cliente_id:
            cliente_obj = get_object_or_404(Cliente, pk=cliente_id)

        # Extrai texto do PDF se enviado
        texto_pdf = ''
        cliente_sugerido = None
        confianca = 0.0
        campos_pdf = {}
        if documento:
            texto_pdf = _extrair_texto_pdf(documento)
            campos_pdf = _extrair_campos_pdf(texto_pdf)
            if not cliente_obj and texto_pdf:
                cliente_sugerido, confianca, nome_unidade = _tentar_identificar_cliente(texto_pdf)
                if confianca >= 0.85:
                    cliente_obj = cliente_sugerido
                elif confianca >= 0.70:
                    nome_unidade = nome_unidade
            # Preenche campos do formulário a partir do PDF se não informados
            if not mes:
                mes = campos_pdf.get('competencia_mes')
            if not ano:
                ano = campos_pdf.get('competencia_ano')
            if not processo:
                processo = campos_pdf.get('numero_processo', '').strip()
            if not inspetoria:
                inspetoria = campos_pdf.get('inspetoria', '').strip()
            if not nome_unidade:
                nome_unidade = campos_pdf.get('nome_unidade', '')

        pc = PrestacaoContas.objects.create(
            cliente=cliente_obj,
            nome_unidade_pdf=nome_unidade,
            competencia_mes=int(mes),
            competencia_ano=int(ano),
            numero_processo=processo,
            inspetoria=inspetoria,
            etapa_atual='CADASTRO',
            observacao_cadastro=obs_cadastro,
            cadastrado_por=request.user,
            ultimo_editor=request.user,
            periodo=campos_pdf.get('periodo', ''),
        )

        if documento:
            # Salva o arquivo após criar o objeto (para ter o pk)
            documento.seek(0)
            pc.documento_principal = documento
            pc.save(update_fields=['documento_principal'])

            # Extrai itens do PDF e cria PCItem
            itens = _extrair_itens_pdf(texto_pdf)
            for it in itens:
                PCItem.objects.create(
                    prestacao=pc,
                    numero=it['numero'],
                    descricao=it['descricao'],
                    nivel_hierarquico=it['nivel_hierarquico'],
                )

        # Histórico
        PCHistorico.objects.create(
            prestacao=pc,
            etapa_anterior='',
            etapa_nova='CADASTRO',
            alterado_por=request.user,
            observacao='Cadastro inicial.',
        )

        messages.success(request, 'Prestação de contas cadastrada com sucesso!')
        return redirect('prestacao_contas_detalhe', pk=pc.pk)

    return render(request, 'pc/prestacao_contas_nova.html', {
        'clientes':    clientes,
        'meses':       range(1, 13),
        'anos':        range(timezone.now().year - 2, timezone.now().year + 1),
    })


#view anterior, sem as regras de visualização das anotações
'''
@login_required
def prestacao_contas_detalhe(request, pk):
    """
    Tela de detalhe/trabalho de uma prestação de contas.
    Comportamento adaptativo por perfil:
      - JURIDICO  → vê cadastro/envio final
      - ANALISE   → vê painel de análise com itens/inconsistências
      - SIGA      → vê itens apontados e confirma correção
      - ADMIN     → vê tudo
    """
    if not _pode_acessar_pc(request.user):
        return redirect('home')

    pc     = get_object_or_404(PrestacaoContas, pk=pk)
    perfil = _perfil_pc(request.user)

    itens    = pc.itens.all().order_by('numero')
    anexos   = pc.anexos.select_related('enviado_por').order_by('-criado_em')
    historico = pc.historico.select_related('alterado_por').order_by('-criado_em')
    clientes = Cliente.objects.filter(ativo=True).order_by('nome') if not pc.cliente else []

    context = {
        'pc':        pc,
        'itens':     itens,
        'anexos':    anexos,
        'historico': historico,
        'perfil_pc': perfil,
        'clientes':  clientes,
        'pode_avancar': _pode_avancar_etapa(request.user, pc),
        'proxima_etapa_label': dict(EtapaPC.choices).get(pc.proxima_etapa, ''),
    }
    return render(request, 'pc/prestacao_contas_detalhe.html', context)
'''

@login_required
def prestacao_contas_detalhe(request, pk):
    """
    Tela de detalhe/trabalho de uma prestação de contas.
    Comportamento adaptativo por perfil:
      - JURIDICO  → vê cadastro/envio final
      - ANALISE   → vê painel de análise com itens/inconsistências
      - SIGA      → vê itens apontados e confirma correção
      - ADMIN     → vê tudo

    Regras de exibição das anotações:
      - ADMIN vê todas as anotações.
      - O autor vê todo o histórico das próprias anotações.
      - Para outros usuários, exibe apenas a última anotação de cada autor.
      - SIGA, na etapa SIGA:
          * visualiza confirmações/OK feitas pelo Jurídico;
          * visualiza inconsistências somente quando feitas pela Análise;
          * não visualiza inconsistências feitas pelo Jurídico;
          * não visualiza observações internas do Jurídico.
    """

    if not _pode_acessar_pc(request.user):
        return redirect('home')

    pc = get_object_or_404(PrestacaoContas, pk=pk)
    perfil = _perfil_pc(request.user)

    itens = pc.itens.all().order_by('numero')
    anexos = pc.anexos.select_related('enviado_por').order_by('-criado_em')
    historico = pc.historico.select_related('alterado_por').order_by('-criado_em')
    clientes = Cliente.objects.filter(ativo=True).order_by('nome') if not pc.cliente else []

    def anotacao_deve_aparecer_para_usuario(anot):
        usuario_anotacao = getattr(anot, 'usuario', None)

        perfil_autor = None

        if usuario_anotacao:
            perfil_autor = _perfil_pc(usuario_anotacao)

        anot.perfil_autor_pc = perfil_autor

        tipo = getattr(anot, 'tipo', None)

        # ADMIN visualiza tudo.
        if perfil == 'ADMIN':
            return True

        # O próprio autor visualiza todas as próprias anotações.
        if usuario_anotacao and usuario_anotacao.id == request.user.id:
            return True

        # Regra específica para o SIGA na etapa SIGA.
        if perfil == 'SIGA' and pc.etapa_atual == 'SIGA':

            # Inconsistências: SIGA visualiza apenas as marcadas pela Análise.
            if tipo == 'INCONSISTENCIA':
                return perfil_autor == 'ANALISE'

            # Confirmações/OK do Jurídico podem aparecer para o SIGA.
            if perfil_autor == 'JURIDICO' and tipo == 'OK':
                return True

            # Caso exista algum tipo de confirmação cadastrado por Jurídico.
            if perfil_autor == 'JURIDICO' and tipo == 'CONFIRMACAO':
                return True

            # Observações/devoluções internas do Jurídico não aparecem para o SIGA.
            if perfil_autor == 'JURIDICO':
                return False

            # Anotações da Análise continuam visíveis para o SIGA.
            if perfil_autor == 'ANALISE':
                return True

            # Anotações do próprio SIGA ou Sistema podem aparecer.
            if perfil_autor == 'SIGA' or usuario_anotacao is None:
                return True

            return False

        # Para os demais perfis, mantém visibilidade padrão.
        return True

    def montar_anotacoes_visiveis(item):
        """
        Monta a lista final de anotações visíveis.

        Regra:
          - ADMIN vê todas.
          - O autor vê todo o próprio histórico.
          - Outros usuários veem apenas a última anotação de cada autor.
          - A regra de visibilidade específica do SIGA é aplicada antes.
        """

        anotacoes = list(
            item.anotacoes
            .select_related('usuario')
            .order_by('criado_em', 'pk')
        )

        if perfil == 'ADMIN':
            for anot in anotacoes:
                usuario_anotacao = getattr(anot, 'usuario', None)
                anot.perfil_autor_pc = _perfil_pc(usuario_anotacao) if usuario_anotacao else None

            item.qtd_anotacoes_visiveis = len(anotacoes)
            return anotacoes

        minhas_anotacoes = []
        ultimas_por_usuario = {}

        for anot in anotacoes:
            if not anotacao_deve_aparecer_para_usuario(anot):
                continue

            usuario_anotacao = getattr(anot, 'usuario', None)
            usuario_anotacao_id = getattr(usuario_anotacao, 'id', None)

            # O próprio usuário visualiza todo o histórico dele.
            if usuario_anotacao_id == request.user.id:
                minhas_anotacoes.append(anot)
                continue

            # Para outros usuários, exibe apenas a última anotação por autor.
            chave_usuario = usuario_anotacao_id or 'SISTEMA'
            ultimas_por_usuario[chave_usuario] = anot

        anotacoes_visiveis = minhas_anotacoes + list(ultimas_por_usuario.values())

        anotacoes_visiveis.sort(
            key=lambda anot: (
                anot.criado_em,
                anot.pk
            )
        )

        item.qtd_anotacoes_visiveis = len(anotacoes_visiveis)

        return anotacoes_visiveis

    for item in itens:
        item.anotacoes_visiveis = montar_anotacoes_visiveis(item)

    context = {
        'pc': pc,
        'itens': itens,
        'anexos': anexos,
        'historico': historico,
        'perfil_pc': perfil,
        'clientes': clientes,
        'pode_avancar': _pode_avancar_etapa(request.user, pc),
        'proxima_etapa_label': dict(EtapaPC.choices).get(pc.proxima_etapa, ''),
    }

    return render(request, 'pc/prestacao_contas_detalhe.html', context)


# ── Helper de permissão de avanço ────────────────────────────────────────
def _pode_avancar_etapa(user, pc: PrestacaoContas) -> bool:
    """Verifica se o usuário pode avançar a etapa atual da PC."""
    if pc.etapa_atual == 'CONCLUIDO':
        return False
    if user.is_staff or user.is_superuser:
        return True
    perfil = _perfil_pc(user)
    permissao_necessaria = PERMISSAO_AVANCO.get(pc.etapa_atual, '')
    return perfil == permissao_necessaria


# ═══════════════════════════════════════════════════════════════════════
# ACTIONS (POST-only)
# ═══════════════════════════════════════════════════════════════════════

@login_required
@require_POST
def pc_avancar_etapa(request, pk):
    """Avança a prestação de contas para a próxima etapa do fluxo."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    pc = get_object_or_404(PrestacaoContas, pk=pk)

    if not _pode_avancar_etapa(request.user, pc):
        return JsonResponse(
            {'ok': False, 'error': 'Você não tem permissão para avançar esta etapa.'},
            status=403,
        )

    proxima = pc.proxima_etapa
    if not proxima:
        return JsonResponse({'ok': False, 'error': 'Etapa já é final.'})

    # Validações específicas por etapa
    if pc.etapa_atual == 'CADASTRO':
        if not pc.documento_principal:
            return JsonResponse(
                {'ok': False, 'error': 'É necessário anexar o documento PDF antes de avançar.'}
            )
        if not pc.cliente:
            return JsonResponse(
                {'ok': False, 'error': 'Vincule o cliente antes de avançar para a Análise.'}
            )

    if pc.etapa_atual == 'ENVIO_FINAL':
        if not pc.comprovante_envio:
            return JsonResponse(
                {'ok': False, 'error': 'Anexe o comprovante de envio antes de concluir.'}
            )

    obs = request.POST.get('observacao', '').strip()
    etapa_anterior = pc.etapa_atual

    # Registra histórico
    PCHistorico.objects.create(
        prestacao=pc,
        etapa_anterior=etapa_anterior,
        etapa_nova=proxima,
        alterado_por=request.user,
        observacao=obs,
    )

    # Atualiza observação do setor
    campo_obs = {
        'CADASTRO':    'observacao_cadastro',
        'ANALISE':     'observacao_analise',
        'SIGA':        'observacao_siga',
        'ENVIO_FINAL': 'observacao_envio',
    }.get(etapa_anterior)
    if campo_obs and obs:
        setattr(pc, campo_obs, obs)

    pc.etapa_atual   = proxima
    pc.ultimo_editor = request.user
    pc.save()

    # ── Notificações ──────────────────────────────────────────────────
    nome_cliente = pc.cliente.nome if pc.cliente else pc.nome_unidade_pdf
    link_detalhe = f'/prestacao-contas/{pc.pk}/'

    notif_map = {
        'ANALISE': (
            'ANALISE',
            f'Nova PC para análise — {nome_cliente}',
            f'Prestação {pc.competencia_str} de {nome_cliente} aguarda sua análise.',
        ),
        'SIGA': (
            'SIGA',
            f'PC com inconsistências — {nome_cliente}',
            f'Prestação {pc.competencia_str} de {nome_cliente} tem itens para correção no SIGA.',
        ),
        'ENVIO_FINAL': (
            'JURIDICO',
            f'Correções confirmadas — {nome_cliente}',
            f'SIGA confirmou as correções. Realize o envio final da prestação {pc.competencia_str}.',
        ),
        'CONCLUIDO': (
            'ADMIN',
            f'Prestação concluída — {nome_cliente}',
            f'A prestação {pc.competencia_str} de {nome_cliente} foi concluída.',
        ),
    }
    if proxima in notif_map:
        grupo, titulo, mensagem = notif_map[proxima]
        _notificar_usuarios_grupo(grupo, titulo, mensagem, link_detalhe)

    return JsonResponse({
        'ok':        True,
        'etapa_nova': proxima,
        'etapa_nova_label': dict(EtapaPC.choices).get(proxima, proxima),
    })






@login_required
@require_POST
def pc_item_salvar_obs(request, pk, item_pk):
    """Salva a observação de inconsistência de um item."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc   = get_object_or_404(PrestacaoContas, pk=pk)
    item = get_object_or_404(PCItem, pk=item_pk, prestacao=pc)

    perfil = _perfil_pc(request.user)
    if perfil not in ('ANALISE', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    obs = request.POST.get('observacao', '').strip()
    item.observacao          = obs
    item.tem_inconsistencia  = True
    item.apontado_por        = request.user
    item.apontado_em         = timezone.now()
    item.save()

    return JsonResponse({'ok': True})


@login_required
@require_POST
def pc_upload_anexo(request, pk):
    """Upload de anexo em qualquer etapa."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc      = get_object_or_404(PrestacaoContas, pk=pk)
    arquivo = request.FILES.get('arquivo')
    desc    = request.POST.get('descricao', '').strip()

    if not arquivo:
        return JsonResponse({'ok': False, 'error': 'Nenhum arquivo enviado.'})

    anexo = PCAnexo.objects.create(
        prestacao=pc,
        etapa=pc.etapa_atual,
        arquivo=arquivo,
        descricao=desc,
        enviado_por=request.user,
    )

    return JsonResponse({
        'ok':       True,
        'anexo_id': anexo.pk,
        'nome':     arquivo.name,
        'url':      anexo.arquivo.url,
    })


@login_required
@require_POST
def pc_upload_comprovante(request, pk):
    """Upload do comprovante de envio (etapa ENVIO_FINAL - Jurídico)."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc      = get_object_or_404(PrestacaoContas, pk=pk)
    arquivo = request.FILES.get('comprovante')

    if not arquivo:
        return JsonResponse({'ok': False, 'error': 'Nenhum arquivo enviado.'})

    pc.comprovante_envio = arquivo
    pc.ultimo_editor     = request.user
    pc.save(update_fields=['comprovante_envio', 'ultimo_editor', 'modificado_em'])

    return JsonResponse({'ok': True, 'url': pc.comprovante_envio.url})


@login_required
@require_POST
def pc_vincular_cliente(request, pk):
    """Vincula ou re-vincula o cliente a uma prestação de contas (Jurídico/Admin)."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc          = get_object_or_404(PrestacaoContas, pk=pk)
    cliente_id  = request.POST.get('cliente_id')

    if not cliente_id:
        return JsonResponse({'ok': False, 'error': 'cliente_id obrigatório.'})

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    pc.cliente       = cliente
    pc.ultimo_editor = request.user
    pc.save(update_fields=['cliente', 'ultimo_editor', 'modificado_em'])

    return JsonResponse({'ok': True, 'cliente_nome': cliente.nome})


def _classificar_periodo(mes_inicio: int, mes_fim: int) -> str | None:
    """
    Classifica o período extraído do PDF em quadrimestre.

    TCM/BA emite relatórios quadrimestrais (4 meses cada):
        1Q  →  Janeiro   a  Abril       (01–04)
        2Q  →  Maio      a  Agosto      (05–08)
        3Q  →  Setembro  a  Dezembro    (09–12)
        ANUAL → cobre o ano inteiro     (01–12)

    Exemplos:
        09/2025 a 12/2025  →  '3Q'
        01/2025 a 12/2025  →  'ANUAL'
        01/2025 a 04/2025  →  '1Q'
    """
    if mes_inicio == 1 and mes_fim == 12:
        return 'ANUAL'
    if 1 <= mes_inicio <= 4:
        return '1Q'
    if 5 <= mes_inicio <= 8:
        return '2Q'
    if 9 <= mes_inicio <= 12:
        return '3Q'
    return None


def _extrair_campos_pdf(texto: str) -> dict:
    """
    Extrai campos do relatório TCM/BA a partir do texto do PDF.
    Retorna dict com: nome_unidade, competencia_mes, competencia_ano,
                      inspetoria, numero_processo, periodo (código do choice)
    """
    dados = {}

    # Unidade  ──────────────────────────────────────────────────────────────
    m = re.search(
        r'UNIDADE\s*:\s*(?:Prefeitura\s+Municipal\s+de\s+)?(.+?)(?:\n|INSPETORIA)',
        texto, re.IGNORECASE
    )
    if m:
        dados['nome_unidade'] = m.group(1).strip()

    # Inspetoria  ────────────────────────────────────────────────────────────
    m = re.search(r'INSPETORIA\s*:\s*(.+?)(?:\n|$)', texto, re.IGNORECASE)
    if m:
        dados['inspetoria'] = m.group(1).strip()

    # Processo  ──────────────────────────────────────────────────────────────
    m = re.search(r'Processo\s*:\s*(\S+)', texto, re.IGNORECASE)
    if m:
        dados['numero_processo'] = m.group(1).strip()

    # Período  ───────────────────────────────────────────────────────────────
    # Exemplo:  PERÍODO: 09/2025 a 12/2025
    m = re.search(
        r'PER[IÍ]ODO\s*:\s*(\d{2})/(\d{4})\s*a\s*(\d{2})/(\d{4})',
        texto, re.IGNORECASE
    )
    if m:
        mes_ini  = int(m.group(1))
        ano_ini  = int(m.group(2))
        mes_fim  = int(m.group(3))
        # Competência = último mês/ano do período
        dados['competencia_mes'] = int(m.group(3))
        dados['competencia_ano'] = int(m.group(4))
        # Quadrimestre
        periodo = _classificar_periodo(mes_ini, mes_fim)
        if periodo:
            dados['periodo'] = periodo
    else:
        # Fallback: COMPETÊNCIA mm/aaaa
        m = re.search(r'COMPET[EÊ]NCIA\s*[:\-]?\s*(\d{2})/(\d{4})', texto, re.IGNORECASE)
        if m:
            dados['competencia_mes'] = int(m.group(1))
            dados['competencia_ano'] = int(m.group(2))

    return dados



@login_required
def api_identificar_cliente_pc(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido.'}, status=405)

    texto   = request.POST.get('texto', '')
    arquivo = request.FILES.get('pdf')

    if arquivo and not texto:
        texto = _extrair_texto_pdf(arquivo)

    # Extrai todos os campos
    campos = _extrair_campos_pdf(texto)

    # Identificação do cliente via fuzzy match
    cliente, confianca, _ = _tentar_identificar_cliente(texto)

    return JsonResponse({
        'cliente_id':      cliente.pk if cliente else None,
        'cliente_nome':    cliente.nome if cliente else '',
        'confianca':       round(confianca * 100, 1),
        'nome_extraido':   campos.get('nome_unidade', ''),
        'sugestao_auto':   confianca >= 0.85,
        'competencia_mes': campos.get('competencia_mes', ''),
        'competencia_ano': campos.get('competencia_ano', ''),
        'inspetoria':      campos.get('inspetoria', ''),
        'numero_processo': campos.get('numero_processo', ''),
        'periodo':         campos.get('periodo', ''),
    })
@login_required
def api_pc_data(request):
    """
    Endpoint JSON para o painel de acompanhamento em tempo real.
    Retorna contagens por etapa.
    """
    data = {}
    for etapa, label in EtapaPC.choices:
        data[etapa] = {
            'label': label,
            'count': PrestacaoContas.objects.filter(etapa_atual=etapa).count(),
        }
    return JsonResponse(data)

from .models import PCItemAnotacao, PCPrazo, PCRetorno


# ══════════════════════════════════════════════════════════════════
# RETORNO DE ETAPA (SIGA → ANÁLISE)
# ══════════════════════════════════════════════════════════════════

@login_required
@require_POST
def pc_solicitar_retorno(request, pk):
    """
    SIGA solicita retorno da PC para a etapa de Análise,
    informando o motivo (o que está faltando).
    """
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc     = get_object_or_404(PrestacaoContas, pk=pk)
    perfil = _perfil_pc(request.user)

    if perfil not in ('SIGA', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Apenas o SIGA pode solicitar retorno.'}, status=403)

    if pc.etapa_atual != 'SIGA':
        return JsonResponse({'ok': False, 'error': 'A PC não está na etapa SIGA.'})

    motivo = request.POST.get('motivo', '').strip()
    if not motivo:
        return JsonResponse({'ok': False, 'error': 'Informe o motivo do retorno.'})

    # Registra o retorno
    retorno = PCRetorno.objects.create(
        prestacao=pc,
        solicitado_por=request.user,
        motivo=motivo,
        etapa_origem='SIGA',
        etapa_destino='ANALISE',
        processado=True,
    )

    # Regride a etapa
    etapa_anterior = pc.etapa_atual
    pc.etapa_atual   = 'ANALISE'
    pc.ultimo_editor = request.user
    pc.save(update_fields=['etapa_atual', 'ultimo_editor', 'modificado_em'])

    PCHistorico.objects.create(
        prestacao=pc,
        etapa_anterior=etapa_anterior,
        etapa_nova='ANALISE',
        alterado_por=request.user,
        observacao=f'[RETORNO SIGA] {motivo}',
    )

    # Notifica setor Análise
    nome_cliente = pc.cliente.nome if pc.cliente else pc.nome_unidade_pdf
    _notificar_usuarios_grupo(
        'ANALISE',
        f'Retorno SIGA — {nome_cliente}',
        f'O SIGA devolveu a PC {pc.competencia_str} para revisão: {motivo}',
        f'/prestacao-contas/{pc.pk}/',
    )

    return JsonResponse({'ok': True, 'motivo': motivo})


# ══════════════════════════════════════════════════════════════════
# CONFIRMAÇÃO DE ITEM PELO SIGA
# ══════════════════════════════════════════════════════════════════

@login_required
@require_POST
def pc_item_confirmar_siga(request, pk, item_pk):
    """
    SIGA confirma que a inconsistência de um item foi resolvida.
    Item muda de vermelho (INCONSISTENTE) para verde (CONFIRMADO_SIGA).
    """
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc     = get_object_or_404(PrestacaoContas, pk=pk)
    item   = get_object_or_404(PCItem, pk=item_pk, prestacao=pc)
    perfil = _perfil_pc(request.user)

    if perfil not in ('SIGA', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    obs   = request.POST.get('observacao', '').strip()
    agora = timezone.now()

    item.status_siga    = 'CONFIRMADO_SIGA'
    item.confirmado_por = request.user
    item.confirmado_em  = agora
    item.save(update_fields=['status_siga', 'confirmado_por', 'confirmado_em'])

    anot = PCItemAnotacao.objects.create(
        item=item,
        usuario=request.user,
        tipo='CONFIRMACAO',
        texto=obs or 'Inconsistência confirmada como resolvida pelo SIGA.',
    )

    pendentes = pc.itens.filter(
        tem_inconsistencia=True,
    ).exclude(status_siga='CONFIRMADO_SIGA').count()

    return JsonResponse({
        'ok':          True,
        'status_novo': 'CONFIRMADO_SIGA',
        'pendentes':   pendentes,
        'todos_ok':    pendentes == 0,
        'anotacao': {
            'tipo_label': anot.get_tipo_display(),
            'texto':      anot.texto,
            'usuario':    request.user.get_full_name() or request.user.username,
            'criado_em':  agora.strftime('%d/%m/%Y %H:%M'),
            'cor_bg':     anot.cor_bg,
            'cor_texto':  anot.cor_texto,
        },
    })


@login_required
@require_POST
def pc_item_ok_juridico(request, pk, item_pk):
    """Toggle OK no item — uma vez marca, outra vez remove."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc     = get_object_or_404(PrestacaoContas, pk=pk)
    item   = get_object_or_404(PCItem, pk=item_pk, prestacao=pc)
    perfil = _perfil_pc(request.user)

    if perfil not in ('JURIDICO', 'ANALISE', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    agora   = timezone.now()
    usuario = request.user

    if item.status_siga == 'OK_ANALISE':
        item.status_siga        = 'PENDENTE'
        item.tem_inconsistencia = False
        item.save(update_fields=['status_siga', 'tem_inconsistencia'])
        anot = PCItemAnotacao.objects.create(
            item=item, usuario=usuario,
            tipo='OBSERVACAO', texto='OK removido.',
        )
        acao = 'removido'
    else:
        item.status_siga        = 'OK_ANALISE'
        item.tem_inconsistencia = False
        item.save(update_fields=['status_siga', 'tem_inconsistencia'])
        anot = PCItemAnotacao.objects.create(
            item=item, usuario=usuario,
            tipo='OK', texto='Item verificado e marcado como OK.',
        )
        acao = 'marcado'

    return JsonResponse({
        'ok':        True,
        'status_novo': item.status_siga,
        'acao':      acao,
        'anotacao': {
            'tipo_label': anot.get_tipo_display(),
            'texto':      anot.texto,
            'usuario':    usuario.get_full_name() or usuario.username,
            'criado_em':  agora.strftime('%d/%m/%Y %H:%M'),
            'cor_bg':     anot.cor_bg,
            'cor_texto':  anot.cor_texto,
        },
    })






# ══════════════════════════════════════════════════════════════════
# ANOTAÇÕES POR ITEM
# ══════════════════════════════════════════════════════════════════

@login_required
@require_POST
def pc_item_anotar(request, pk, item_pk):
    """
    Qualquer usuário com acesso pode adicionar uma anotação a um item.
    O tipo é definido pelo perfil + parâmetro enviado.
    """
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc     = get_object_or_404(PrestacaoContas, pk=pk)
    item   = get_object_or_404(PCItem, pk=item_pk, prestacao=pc)
    perfil = _perfil_pc(request.user)

    texto = request.POST.get('texto', '').strip()
    tipo  = request.POST.get('tipo', 'OBSERVACAO')

    if not texto:
        return JsonResponse({'ok': False, 'error': 'Texto da anotação é obrigatório.'})

    # Valida tipo permitido por perfil
    tipos_validos = {
        'JURIDICO': ['INCONSISTENCIA', 'OK', 'OBSERVACAO'],
        'ANALISE':  ['INCONSISTENCIA', 'OK', 'OBSERVACAO'],
        'SIGA':     ['CONFIRMACAO', 'DEVOLUCAO', 'OBSERVACAO'],
        'ADMIN':    ['INCONSISTENCIA', 'OK', 'OBSERVACAO', 'CONFIRMACAO', 'DEVOLUCAO'],
    }
    if tipo not in tipos_validos.get(perfil, ['OBSERVACAO']):
        tipo = 'OBSERVACAO'

    # Se for inconsistência, marca o item também
    if tipo == 'INCONSISTENCIA':
        item.tem_inconsistencia = True
        item.status_siga        = 'INCONSISTENTE'
        item.save(update_fields=['tem_inconsistencia', 'status_siga'])

    anotacao = PCItemAnotacao.objects.create(
        item=item,
        usuario=request.user,
        tipo=tipo,
        texto=texto,
    )

    nome_usuario = (
        request.user.get_full_name() or request.user.username
    )

    return JsonResponse({
        'ok':           True,
        'anotacao_id':  anotacao.pk,
        'tipo':         tipo,
        'tipo_label':   anotacao.get_tipo_display(),
        'texto':        texto,
        'usuario':      nome_usuario,
        'criado_em':    anotacao.criado_em.strftime('%d/%m/%Y %H:%M'),
        'cor_bg':       anotacao.cor_bg,
        'cor_texto':    anotacao.cor_texto,
        'status_item':  item.status_siga,
    })


@login_required
def pc_item_anotacoes(request, pk, item_pk):
    """Retorna o histórico de anotações de um item em JSON."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    item = get_object_or_404(PCItem, pk=item_pk, prestacao__pk=pk)
    data = []
    for a in item.anotacoes.select_related('usuario').order_by('criado_em'):
        data.append({
            'id':        a.pk,
            'tipo':      a.tipo,
            'tipo_label': a.get_tipo_display(),
            'texto':     a.texto,
            'usuario':   a.usuario.get_full_name() or a.usuario.username if a.usuario else 'Sistema',
            'criado_em': a.criado_em.strftime('%d/%m/%Y %H:%M'),
            'cor_bg':    a.cor_bg,
            'cor_texto': a.cor_texto,
        })
    return JsonResponse({'ok': True, 'anotacoes': data})


# ══════════════════════════════════════════════════════════════════
# PRAZOS
# ══════════════════════════════════════════════════════════════════

@login_required
def pc_prazos(request, pk):
    """Lista os prazos de uma PC (JSON para o modal)."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc = get_object_or_404(PrestacaoContas, pk=pk)
    data = []
    for p in pc.prazos.order_by('concluido', 'data_limite'):
        data.append({
            'id':             p.pk,
            'descricao':      p.descricao,
            'data_limite':    p.data_limite.strftime('%d/%m/%Y'),
            'data_iso':       p.data_limite.isoformat(),
            'dias_restantes': p.dias_restantes,
            'concluido':      p.concluido,
            'status_css':     p.status_css,
            'dias_lembrete':  p.dias_lembrete,
        })
    return JsonResponse({'ok': True, 'prazos': data})

@login_required
@require_POST
def pc_item_toggle_inconsistencia(request, pk, item_pk):
    """Marca/desmarca um item como tendo inconsistência."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    pc   = get_object_or_404(PrestacaoContas, pk=pk)
    item = get_object_or_404(PCItem, pk=item_pk, prestacao=pc)

    perfil = _perfil_pc(request.user)
    if perfil not in ('ANALISE', 'JURIDICO', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    item.tem_inconsistencia = not item.tem_inconsistencia
    if item.tem_inconsistencia:
        item.status_siga  = 'INCONSISTENTE'
        item.apontado_por = request.user
        item.apontado_em  = timezone.now()
    else:
        item.status_siga  = 'PENDENTE'
        item.apontado_por = None
        item.apontado_em  = None
    item.save()

    return JsonResponse({
        'ok':                True,
        'tem_inconsistencia': item.tem_inconsistencia,
        'item_pk':           item.pk,
    })


@login_required
@require_POST
def pc_prazo_concluir(request, pk, prazo_pk):
    """Marca um prazo como concluído."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    prazo = get_object_or_404(PCPrazo, pk=prazo_pk, prestacao__pk=pk)
    prazo.concluido = not prazo.concluido
    prazo.save(update_fields=['concluido'])
    return JsonResponse({'ok': True, 'concluido': prazo.concluido})


@login_required
@require_POST
def pc_prazo_excluir(request, pk, prazo_pk):
    """Exclui um prazo."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)
    prazo = get_object_or_404(PCPrazo, pk=prazo_pk, prestacao__pk=pk)
    prazo.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def pc_salvar_periodo(request, pk):
    """Salva o quadrimestre/período da PC (apenas Jurídico/Admin)."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    perfil = _perfil_pc(request.user)
    if perfil not in ('JURIDICO', 'ADMIN') and not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Sem permissão.'}, status=403)

    pc      = get_object_or_404(PrestacaoContas, pk=pk)
    periodo = request.POST.get('periodo', '').strip()

    choices_validos = {c[0] for c in PrestacaoContas.PERIODO_CHOICES} | {''}
    if periodo not in choices_validos:
        return JsonResponse({'ok': False, 'error': 'Período inválido.'})

    pc.periodo = periodo or None
    pc.save(update_fields=['periodo'])

    labels = dict(PrestacaoContas.PERIODO_CHOICES)
    return JsonResponse({
        'ok':           True,
        'periodo_label': labels.get(periodo, '—'),
    })

@login_required
@require_POST
def pc_prazo_salvar(request, pk):
    """Cria ou atualiza um prazo (apenas Jurídico/Admin). Notifica todos ao criar."""
    if not _pode_acessar_pc(request.user):
        return JsonResponse({'ok': False}, status=403)

    perfil = _perfil_pc(request.user)
    if perfil not in ('JURIDICO', 'ADMIN') and not request.user.is_staff:
        return JsonResponse(
            {'ok': False, 'error': 'Apenas o Jurídico pode gerenciar prazos.'},
            status=403,
        )

    pc        = get_object_or_404(PrestacaoContas, pk=pk)
    prazo_id  = request.POST.get('prazo_id')
    descricao = request.POST.get('descricao', '').strip()
    data_str  = request.POST.get('data_limite', '').strip()
    dias_lemb = int(request.POST.get('dias_lembrete', 3))  # sem vírgula

    if not descricao or not data_str:
        return JsonResponse({'ok': False, 'error': 'Descrição e data são obrigatórios.'})

    from datetime import date as dt_date
    try:
        if '/' in data_str:
            dia, mes, ano = data_str.split('/')
            data_limite = dt_date(int(ano), int(mes), int(dia))
        else:
            data_limite = dt_date.fromisoformat(data_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Data inválida.'})

    if prazo_id:
        prazo = get_object_or_404(PCPrazo, pk=prazo_id, prestacao=pc)
        prazo.descricao     = descricao
        prazo.data_limite   = data_limite
        prazo.dias_lembrete = dias_lemb
        prazo.save()
        acao = 'atualizado'
    else:
        prazo = PCPrazo.objects.create(
            prestacao=pc,
            descricao=descricao,
            data_limite=data_limite,
            dias_lembrete=dias_lemb,
            criado_por=request.user,
        )
        acao = 'criado'

    # Notifica todos os usuários com acesso à PC ao criar/atualizar prazo
# Notifica todos os usuários com acesso à PC ao criar/atualizar prazo
    nome_cliente = pc.cliente.nome if pc.cliente else pc.nome_unidade_pdf
    link = f'/prestacao-contas/{pc.pk}/'
    titulo   = f'Prazo {acao}: {descricao[:40]}'
    mensagem = (
        f'Prazo "{descricao}" da PC de {nome_cliente} foi {acao}. '
        f'Vence em: {data_limite.strftime("%d/%m/%Y")}.'
    )

    try:
        # Busca direto pelo model User usando o relacionamento "perfil__"
        usuarios_notificar = User.objects.filter(
            perfil__acesso_prestacao_contas=True,
            is_active=True
        ).exclude(pk=request.user.pk)

        for u in usuarios_notificar:
            NotificacaoPush.objects.create(
                usuario_alvo=u,
                titulo=titulo,
                mensagem=mensagem,
                link=link,
            )
    except Exception as e:
        logger.warning('Erro ao notificar prazo: %s', e)

    return JsonResponse({
        'ok':             True,
        'prazo_id':       prazo.pk,
        'descricao':      prazo.descricao,
        'data_limite':    prazo.data_limite.strftime('%d/%m/%Y'),
        'dias_restantes': prazo.dias_restantes,
        'status_css':     prazo.status_css,
    })

    return JsonResponse({
        'ok':             True,
        'prazo_id':       prazo.pk,
        'descricao':      prazo.descricao,
        'data_limite':    prazo.data_limite.strftime('%d/%m/%Y'),
        'dias_restantes': prazo.dias_restantes,
        'status_css':     prazo.status_css,
    })