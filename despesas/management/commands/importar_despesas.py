"""
Management command: importar_despesas
======================================
Menu principal com quatro ferramentas:

  1. Importar despesas de arquivos CSV
  2. Classificar municípios nas despesas existentes
  3. Alterar status de pagamento em lote
  4. Cancelar recorrência (em lote ou individual)

Uso:
    python manage.py importar_despesas
    python manage.py importar_despesas --pasta /caminho/alternativo
    python manage.py importar_despesas --dry-run
    python manage.py importar_despesas --usuario admin
    python manage.py importar_despesas --ferramenta municipios
    python manage.py importar_despesas --ferramenta status
    python manage.py importar_despesas --ferramenta recorrencia
"""

from __future__ import annotations

import csv
import re
import sys
import calendar
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from despesas.models import DespesaGeral  # ← altere se necessário

User = get_user_model()

# ──────────────────────────────────────────────────────────────────────────────
# Paleta ANSI
# ──────────────────────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"


def c(color: str, text: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{RESET}"
    return text


def hr(char: str = "─", width: int = 60) -> str:
    return c(DIM, char * width)


def fmt_brl(valor: Decimal) -> str:
    s = f"{valor:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def adicionar_meses(data_origem: date | None, meses: int) -> date | None:
    if not data_origem:
        return None
    mes = data_origem.month - 1 + meses
    ano = data_origem.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data_origem.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def normalizar(texto: str) -> str:
    """Remove acentos e converte para UPPER para comparação insensível."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch)).upper()


# ──────────────────────────────────────────────────────────────────────────────
# Leitura interativa
# ──────────────────────────────────────────────────────────────────────────────

def perguntar(prompt: str, opcoes: list[str] | None = None, default: str = "") -> str:
    sufixo = f" [{default}]" if default else ""
    if opcoes:
        sufixo += f" ({'/'.join(opcoes)})"
    while True:
        resposta = input(c(CYAN, f"  → {prompt}{sufixo}: ")).strip()
        if not resposta and default:
            return default
        if opcoes and resposta.lower() not in [o.lower() for o in opcoes]:
            print(c(YELLOW, f"    Opção inválida. Escolha entre: {', '.join(opcoes)}"))
            continue
        if resposta:
            return resposta
        print(c(YELLOW, "    Por favor, informe um valor."))


def perguntar_sim_nao(prompt: str, default: str = "s") -> bool:
    return perguntar(prompt, opcoes=["s", "n"], default=default).lower() == "s"


def perguntar_data(prompt: str, default: date | None = None) -> date | None:
    fmt = "%d/%m/%Y"
    default_str = default.strftime(fmt) if default else ""
    sufixo_none = "" if default else " (Enter = em branco)"
    while True:
        raw = input(
            c(CYAN, f"  → {prompt} (DD/MM/AAAA){sufixo_none}"
              + (f" [{default_str}]" if default_str else "") + ": ")
        ).strip()
        if not raw:
            return default
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            print(c(YELLOW, "    Data inválida. Use DD/MM/AAAA."))


def perguntar_mes(prompt: str, default: date | None = None) -> date:
    default_str = (default or date.today().replace(day=1)).strftime("%m/%Y")
    while True:
        raw = input(c(CYAN, f"  → {prompt} (MM/AAAA) [{default_str}]: ")).strip() or default_str
        try:
            return datetime.strptime(f"01/{raw}", "%d/%m/%Y").date()
        except ValueError:
            print(c(YELLOW, "    Formato inválido. Use MM/AAAA."))


def perguntar_numero(prompt: str, minimo: int = 1, maximo: int | None = None, default: int | None = None) -> int:
    sufixo = f" [{default}]" if default is not None else ""
    while True:
        raw = input(c(CYAN, f"  → {prompt}{sufixo}: ")).strip()
        if not raw and default is not None:
            return default
        if raw.isdigit():
            n = int(raw)
            if minimo <= n and (maximo is None or n <= maximo):
                return n
        intervalo = f"{minimo}-{maximo}" if maximo else f"≥ {minimo}"
        print(c(YELLOW, f"    Número inválido. Use {intervalo}."))


# ──────────────────────────────────────────────────────────────────────────────
# Parsing de CSV
# ──────────────────────────────────────────────────────────────────────────────

def parse_valor(raw: str) -> Decimal:
    limpo = re.sub(r"[^\d,]", "", raw).replace(",", ".")
    partes = limpo.split(".")
    if len(partes) > 2:
        limpo = "".join(partes[:-1]) + "." + partes[-1]
    elif len(partes) == 2 and len(partes[-1]) == 3:
        limpo = "".join(partes)
    try:
        return Decimal(limpo).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"Não foi possível converter o valor: {raw!r}")


def ler_csv(caminho: Path) -> list[dict]:
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            linhas = []
            with caminho.open(encoding=encoding, newline="") as f:
                reader = csv.reader(f, delimiter=";")
                for i, row in enumerate(reader, start=1):
                    if not any(cell.strip() for cell in row):
                        continue
                    if len(row) < 2:
                        print(c(YELLOW, f"    [linha {i}] ignorada — menos de 2 colunas"))
                        continue
                    descricao = row[0].strip().title()
                    try:
                        valor = parse_valor(row[1])
                    except ValueError as e:
                        print(c(YELLOW, f"    [linha {i}] ignorada — {e}"))
                        continue
                    linhas.append({"descricao": descricao, "valor": valor, "linha": i})
            if linhas:
                return linhas
        except UnicodeDecodeError:
            continue
    raise CommandError(f"Não foi possível ler o arquivo: {caminho}")


# ──────────────────────────────────────────────────────────────────────────────
# Menu de categorias
# ──────────────────────────────────────────────────────────────────────────────

CATEGORIAS = DespesaGeral.CLASSIFICACAO_CHOICES


def exibir_menu_categorias() -> tuple[str, str | None]:
    print()
    print(c(BOLD, "  Categorias disponíveis:"))
    for i, (key, label) in enumerate(CATEGORIAS, start=1):
        print(f"    {c(BOLD, str(i))}. {label}")
    while True:
        raw = input(c(CYAN, f"  → Número da categoria [1-{len(CATEGORIAS)}]: ")).strip()
        if not raw.isdigit() or not (1 <= int(raw) <= len(CATEGORIAS)):
            print(c(YELLOW, f"    Número fora do intervalo (1-{len(CATEGORIAS)})."))
            continue
        key, _ = CATEGORIAS[int(raw) - 1]
        custom = perguntar("Nome personalizado para 'Outros'") if key == "outros" else None
        return key, custom


# ──────────────────────────────────────────────────────────────────────────────
# Detecção e gestão de duplicatas (importação CSV)
# ──────────────────────────────────────────────────────────────────────────────

def _varrer_duplicatas(linhas: list[dict]) -> dict[int, list]:
    duplicatas: dict[int, list] = {}
    for idx, item in enumerate(linhas):
        qs = list(
            DespesaGeral.objects.filter(
                descricao__iexact=item["descricao"],
                valor=item["valor"],
            ).order_by("-mes_referencia")
        )
        if qs:
            duplicatas[idx] = qs
    return duplicatas


def _exibir_duplicatas(linhas: list[dict], duplicatas: dict[int, list]) -> None:
    print()
    print(c(BOLD + YELLOW, f"  ⚠️   {len(duplicatas)} registro(s) já existem no banco:\n"))
    for idx, registros in duplicatas.items():
        item = linhas[idx]
        print(f"  {c(BOLD, '•')} {item['descricao']:<42} {fmt_brl(item['valor'])}")
        for reg in registros[:3]:
            venc = reg.data_vencimento.strftime("%d/%m/%Y") if reg.data_vencimento else "—"
            print(
                c(DIM, f"      ↳ [id {reg.pk}] "
                  f"{reg.mes_referencia.strftime('%m/%Y')}  "
                  f"status={reg.status}  "
                  f"venc={venc}  "
                  f"categ={reg.get_classificacao_display()}")
            )
        if len(registros) > 3:
            print(c(DIM, f"      ↳ ... e mais {len(registros) - 3} ocorrência(s)"))


ACOES_DUPLICATA = [
    ("1", "Alterar data de vencimento"),
    ("2", "Alterar status"),
    ("3", "Alterar categoria"),
    ("4", "Excluir registros existentes"),
    ("5", "Ignorar (manter existentes e não reimportar estas linhas)"),
    ("6", "Importar mesmo assim (criar novos registros duplicados)"),
]


def _menu_acao_duplicata() -> str:
    print()
    print(c(BOLD, "  O que deseja fazer com os registros duplicados?"))
    for key, desc in ACOES_DUPLICATA:
        print(f"    {c(BOLD, key)}. {desc}")
    opcoes = [k for k, _ in ACOES_DUPLICATA]
    return perguntar("Escolha uma ação", opcoes=opcoes)


def _aplicar_acao_duplicatas(
    duplicatas: dict[int, list],
    acao: str,
    dry_run: bool,
) -> tuple[set[int], int]:
    todos_registros = [reg for regs in duplicatas.values() for reg in regs]
    indices_com_duplicata = set(duplicatas.keys())

    if acao == "1":
        nova_data = perguntar_data("Nova data de vencimento para os duplicados")
        if not dry_run:
            with transaction.atomic():
                for reg in todos_registros:
                    reg.data_vencimento = nova_data
                    reg.save(update_fields=["data_vencimento", "atualizado_em"])
        _relatorio_acao(
            f"data de vencimento → {nova_data.strftime('%d/%m/%Y') if nova_data else '(em branco)'}",
            len(todos_registros), dry_run,
        )
        return set(), len(todos_registros)

    if acao == "2":
        novo_status = perguntar("Novo status", opcoes=["pendente", "pago"])
        if not dry_run:
            with transaction.atomic():
                for reg in todos_registros:
                    reg.status = novo_status
                    reg.save(update_fields=["status", "atualizado_em"])
        _relatorio_acao(f"status → {novo_status}", len(todos_registros), dry_run)
        return set(), len(todos_registros)

    if acao == "3":
        nova_categ, nova_custom = exibir_menu_categorias()
        if not dry_run:
            with transaction.atomic():
                for reg in todos_registros:
                    reg.classificacao = nova_categ
                    reg.classificacao_custom = nova_custom or ""
                    reg.save(update_fields=["classificacao", "classificacao_custom", "atualizado_em"])
        label = nova_custom or dict(CATEGORIAS).get(nova_categ, nova_categ)
        _relatorio_acao(f"categoria → {label}", len(todos_registros), dry_run)
        return set(), len(todos_registros)

    if acao == "4":
        print()
        print(c(RED, f"  ⚠️   Isso excluirá {len(todos_registros)} registro(s) do banco permanentemente."))
        if not perguntar_sim_nao("Confirma a exclusão?", default="n"):
            print(c(YELLOW, "  Exclusão cancelada. Registros mantidos."))
            return indices_com_duplicata, 0
        if not dry_run:
            ids = [r.pk for r in todos_registros]
            with transaction.atomic():
                DespesaGeral.objects.filter(pk__in=ids).delete()
        _relatorio_acao("excluídos", len(todos_registros), dry_run, cor=RED)
        return set(), len(todos_registros)

    if acao == "5":
        print(c(YELLOW, f"\n  {len(indices_com_duplicata)} linha(s) do CSV serão ignoradas."))
        return indices_com_duplicata, 0

    if acao == "6":
        print(c(YELLOW, "\n  Linhas duplicadas serão importadas normalmente (criará duplicatas)."))
        return set(), 0

    return set(), 0


def _relatorio_acao(descricao: str, qtd: int, dry_run: bool, cor: str = GREEN) -> None:
    prefixo = "[dry-run] " if dry_run else ""
    print(c(cor, f"\n  {prefixo}✔  {qtd} registro(s) — {descricao}"))


# ──────────────────────────────────────────────────────────────────────────────
# ★ NOVA FERRAMENTA 1 — Varredura e classificação de municípios
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# ★ NOVA FERRAMENTA 1 — Varredura e classificação de municípios
# ──────────────────────────────────────────────────────────────────────────────

def _obter_municipios_banco() -> list[dict]:
    """
    Retorna lista de municípios extraída dos Vínculos Centro de Custo x Contrato,
    classificando em Câmara ou Prefeitura.
    """
    try:
        # ATENÇÃO: Substitua 'despesas.models' pelo app real onde está o model!
        from despesas.models import VinculoCentroCustoContrato 
        
        vinculos = (
            VinculoCentroCustoContrato.objects
            .select_related('contrato')
            .exclude(contrato__municipio__isnull=True)
            .exclude(contrato__municipio="")
        )
        
        resultados = {}
        for v in vinculos:
            mun = v.contrato.municipio.strip()
            tipo = v.tipo_entidade  # 'PM', 'CM', 'AUT'
            
            if tipo == 'CM':
                label = f"{mun} (Câmara Municipal)"
                # Gravar com a palavra "Câmara" garante que a View Raio-X 
                # a direcione automaticamente para a seção correta.
                valor_salvar = f"Câmara Municipal de {mun}"
            elif tipo == 'PM':
                label = f"{mun} (Prefeitura)"
                valor_salvar = mun  # Apenas o nome da cidade para prefeituras
            else:
                label = f"{mun} ({v.get_tipo_entidade_display()})"
                valor_salvar = mun
                
            if label not in resultados:
                resultados[label] = {
                    "nome_busca": mun,
                    "label": label,
                    "valor_salvar": valor_salvar
                }
                
        if resultados:
            return sorted(resultados.values(), key=lambda x: x["label"])
            
    except Exception as e:
        print(c(YELLOW, f"  [Aviso] Não foi possível ler os vínculos ({e}). Usando fallback..."))

    # ── Fallback: valores distintos já usados em DespesaGeral ──────────────
    nomes = list(
        DespesaGeral.objects
        .exclude(municipio__isnull=True)
        .exclude(municipio="")
        .values_list("municipio", flat=True)
        .distinct()
    )
    return [{"nome_busca": m, "label": m, "valor_salvar": m} for m in sorted(nomes)]


def _match_municipios(descricao: str, municipios_lista: list[dict]) -> list[dict]:
    """
    Compara a descrição com a raiz do nome do município (nome_busca).
    Inclui inteligência para desambiguar Prefeitura vs Câmara, incluindo a regra "Preposto".
    """
    desc_norm = normalizar(descricao)
    encontrados = []
    
    for item in municipios_lista:
        nome_norm = normalizar(item["nome_busca"])
        padrao = r"\b" + re.escape(nome_norm) + r"\b"
        if re.search(padrao, desc_norm):
            encontrados.append(item)
            
    encontrados.sort(key=lambda x: len(x["nome_busca"]), reverse=True)
    
    if len(encontrados) > 1:
        cidade_alvo = encontrados[0]["nome_busca"]
        candidatos_cidade = [e for e in encontrados if e["nome_busca"] == cidade_alvo]
        
        if len(candidatos_cidade) > 1:
            kw_camara = ["CAMARA", "LEGISLATIV", "VEREADOR", " CM ", " C.M."]
            kw_pref   = ["PREFEITURA", "PREF ", "EXECUTIVO", " PM ", " P.M."]
            
            eh_camara    = any(kw in f" {desc_norm} " for kw in kw_camara)
            eh_pref      = any(kw in f" {desc_norm} " for kw in kw_pref)
            tem_preposto = "PREPOSTO" in desc_norm
            
            if eh_camara:
                # Se tem palavra de câmara, é Câmara sempre.
                encontrados = [e for e in candidatos_cidade if "Câmara" in e["label"]]
            elif eh_pref:
                # Se tem prefeitura explícito, é Prefeitura.
                encontrados = [e for e in candidatos_cidade if "Prefeitura" in e["label"]]
            elif tem_preposto and not eh_camara:
                # REGRA DO PREPOSTO: Tem "Preposto" mas não tem "Câmara"? É Prefeitura.
                encontrados = [e for e in candidatos_cidade if "Prefeitura" in e["label"]]
            else:
                # Mantém ambíguo para o usuário decidir
                encontrados = candidatos_cidade
                
    return encontrados


def _escolher_municipio_da_lista(municipios_lista: list[dict]) -> str | None:
    print()
    print(c(BOLD, "  Municípios/Entidades disponíveis:"))
    for i, item in enumerate(municipios_lista, start=1):
        print(f"    {c(BOLD, str(i))}. {item['label']}")
    print(f"    {c(BOLD, '0')}. Cancelar")
    
    n = perguntar_numero("Escolha o número", minimo=0, maximo=len(municipios_lista))
    if n == 0:
        return None
    return municipios_lista[n - 1]["valor_salvar"]


def _aplicar_classificacao_municipio(
    pares: list[tuple],  # [(DespesaGeral, dict_municipio_ou_str), ...]
    dry_run: bool,
) -> None:
    if dry_run:
        return
        
    ids_por_municipio: dict[str, list[int]] = {}
    
    for desp, mun in pares:
        # Extrai a string correta caso venha o novo formato em dicionário,
        # ou mantém intacto se for o fallback antigo em string.
        valor_str = mun["valor_salvar"] if isinstance(mun, dict) else mun
        
        # Agora 'valor_str' é garantidamente um texto (string)
        ids_por_municipio.setdefault(valor_str, []).append(desp.pk)

    with transaction.atomic():
        for mun_val, ids in ids_por_municipio.items():
            DespesaGeral.objects.filter(pk__in=ids).update(municipio=mun_val)

def _ferramenta_municipios(dry_run: bool) -> None:
    print()
    print(hr("═"))
    print(c(BOLD + MAGENTA, "  🏙️   Classificação de Municípios nas Despesas"))
    if dry_run:
        print(c(YELLOW, "  ⚠️   Modo DRY-RUN — nenhum dado será gravado"))
    print(hr("═"))

    print(c(BOLD, "\n  Carregando municípios dos contratos/vínculos..."))
    municipios_lista = _obter_municipios_banco()

    if not municipios_lista:
        print(c(RED, "  ✖  Nenhum município ou vínculo encontrado no banco."))
        return

    print(c(GREEN, f"  ✔  {len(municipios_lista)} entidade(s) carregada(s):"))
    for item in municipios_lista:
        print(c(DIM, f"     • {item['label']}"))

    print()
    print(c(BOLD, "  Escopo da varredura:"))
    print(f"    {c(BOLD, '1')}. Apenas despesas sem município classificado")
    print(f"    {c(BOLD, '2')}. Todas as despesas (sobrescreve classificações existentes)")
    escopo = perguntar("Escolha", opcoes=["1", "2"], default="1")

    qs = DespesaGeral.objects.all().order_by("mes_referencia", "descricao")
    if escopo == "1":
        qs = qs.filter(Q(municipio__isnull=True) | Q(municipio=""))

    total_base = qs.count()
    if total_base == 0:
        print(c(YELLOW, "\n  Nenhuma despesa encontrada no escopo selecionado."))
        return

    print(c(BOLD, f"\n  🔍  Varrendo {total_base} despesa(s)...\n"))

    matches_auto: list[tuple]  = []   
    matches_multi: list[tuple] = []   
    sem_match: list = []

    for desp in qs.iterator():
        candidatos = _match_municipios(desp.descricao, municipios_lista)
        if len(candidatos) == 1:
            matches_auto.append((desp, candidatos[0]))
        elif len(candidatos) > 1:
            matches_multi.append((desp, candidatos))
        else:
            sem_match.append(desp)

    print(c(BOLD, f"  Resultado da varredura:"))
    print(f"     {c(GREEN,  str(len(matches_auto)))}  correspondência(s) exata(s)")
    print(f"     {c(YELLOW, str(len(matches_multi)))}  correspondência(s) ambígua(s) — requer escolha")
    print(f"     {c(DIM,    str(len(sem_match)))}  sem correspondência")
    print()

    if not matches_auto and not matches_multi:
        print(c(YELLOW, "  Nenhuma correspondência encontrada."))
        return

    alterados = 0

    # PROCESSA MATCHES AUTOMÁTICOS
    if matches_auto:
        print(hr())
        print(c(BOLD, f"  ✅  Correspondências automáticas ({len(matches_auto)}):"))
        print()
        for desp, item_mun in matches_auto:
            mun_atual = f" [já: {desp.municipio}]" if desp.municipio else ""
            print(
                f"    {c(BOLD, '•')} {desp.descricao[:40]:<40} "
                f"{fmt_brl(desp.valor):>14}  "
                f"{c(GREEN, '→')} {c(BOLD, item_mun['label'])}"
                f"{c(DIM, mun_atual)}"
            )

        print()
        modo_auto = perguntar(
            "Aplicar correspondências automáticas",
            opcoes=["todas", "individual", "nenhuma"],
            default="todas",
        )

        if modo_auto == "todas":
            _aplicar_classificacao_municipio(matches_auto, dry_run)
            alterados += len(matches_auto)

        elif modo_auto == "individual":
            for desp, item_mun in matches_auto:
                print()
                print(f"  {desp.descricao}  {fmt_brl(desp.valor)}")
                if perguntar_sim_nao(f"  Classificar como '{item_mun['label']}'?"):
                    _aplicar_classificacao_municipio([(desp, item_mun)], dry_run)
                    alterados += 1
                else:
                    if perguntar_sim_nao("  Escolher outra entidade?", default="n"):
                        mun_escolhido = _escolher_municipio_da_lista(municipios_lista)
                        if mun_escolhido:
                            _aplicar_classificacao_municipio([(desp, mun_escolhido)], dry_run)
                            alterados += 1

    # PROCESSA MATCHES AMBÍGUOS COM MEMÓRIA DE CACHE
    if matches_multi:
        print()
        print(hr())
        print(c(BOLD + YELLOW, f"  ⚠️   Correspondências ambíguas ({len(matches_multi)}) — escolha manual:"))

        # Dicionário para memorizar as escolhas do usuário e evitar perguntas repetidas
        memorias_escolha = {}

        for desp, candidatos in matches_multi:
            desc = desp.descricao
            
            # Verifica se já respondemos para essa descrição exata
            if desc in memorias_escolha:
                mun_escolhido = memorias_escolha[desc]
                if mun_escolhido: # Se não foi "Ignorar"
                    _aplicar_classificacao_municipio([(desp, mun_escolhido)], dry_run)
                    alterados += 1
                continue # Pula para a próxima despesa sem perguntar

            print()
            print(f"  {c(BOLD, desc)}  {fmt_brl(desp.valor)}")
            print(f"  {c(DIM, 'Entidades/Municípios encontrados na descrição:')}")
            for i, item in enumerate(candidatos, start=1):
                print(f"    {c(BOLD, str(i))}. {item['label']}")
            print(f"    {c(BOLD, str(len(candidatos) + 1))}. Ignorar esta despesa (e repetições dela)")

            escolha = perguntar_numero(
                "Escolha o número da entidade correta",
                minimo=1, maximo=len(candidatos) + 1,
            )
            
            if escolha <= len(candidatos):
                mun_escolhido = candidatos[escolha - 1]
                memorias_escolha[desc] = mun_escolhido # Salva a escolha na memória
                _aplicar_classificacao_municipio([(desp, mun_escolhido)], dry_run)
                alterados += 1
            else:
                memorias_escolha[desc] = None # Salva na memória que é para ignorar
                print(c(DIM, "  Ignorado."))

    print()
    print(hr("═"))
    prefixo = "[dry-run] " if dry_run else ""
    print(c(GREEN, f"  {prefixo}✔  {alterados} despesa(s) classificada(s) com município/entidade."))
    if sem_match:
        print(c(DIM, f"  {len(sem_match)} despesa(s) sem correspondência."))
    print(hr("═"))


# ──────────────────────────────────────────────────────────────────────────────
# ★ NOVA FERRAMENTA 2 — Alterar status de pagamento em lote
# ──────────────────────────────────────────────────────────────────────────────

def _ferramenta_status(dry_run: bool) -> None:
    print()
    print(hr("═"))
    print(c(BOLD + BLUE, "  💳  Alteração de Status de Pagamento em Lote"))
    if dry_run:
        print(c(YELLOW, "  ⚠️   Modo DRY-RUN — nenhum dado será gravado"))
    print(hr("═"))

    # 1. Filtros ──────────────────────────────────────────────────────────────
    print()
    print(c(BOLD, "  Defina os filtros (Enter = sem filtro):"))

    # Período
    print()
    filtrar_periodo = perguntar_sim_nao("Filtrar por período (mês referência)?", default="s")
    mes_ini = mes_fim = None
    if filtrar_periodo:
        mes_ini = perguntar_mes("Mês inicial", default=date.today().replace(day=1))
        mes_fim = perguntar_mes("Mês final  ", default=date.today().replace(day=1))
        if mes_fim < mes_ini:
            mes_fim = mes_ini

    # Status atual
    print()
    status_filtro = perguntar(
        "Filtrar por status atual",
        opcoes=["pendente", "pago", "ambos"],
        default="pendente",
    )

    # Município
    print()
    filtrar_municipio = perguntar_sim_nao("Filtrar por município?", default="n")
    municipio_filtro = None
    if filtrar_municipio:
        municipios_banco = _obter_municipios_banco()
        if municipios_banco:
            municipio_filtro = _escolher_municipio_da_lista(municipios_banco)
        else:
            municipio_filtro = input(c(CYAN, "  → Nome do município: ")).strip() or None

    # Categoria
    print()
    filtrar_categ = perguntar_sim_nao("Filtrar por categoria?", default="n")
    categ_filtro = None
    if filtrar_categ:
        categ_filtro, _ = exibir_menu_categorias()

    # Busca por nome
    print()
    busca = input(c(CYAN, "  → Buscar por trecho do nome (Enter = todos): ")).strip()

    # 2. Monta QuerySet ───────────────────────────────────────────────────────
    qs = DespesaGeral.objects.all()
    if mes_ini:
        qs = qs.filter(mes_referencia__gte=mes_ini)
    if mes_fim:
        qs = qs.filter(mes_referencia__lte=mes_fim)
    if status_filtro != "ambos":
        qs = qs.filter(status=status_filtro)
    if municipio_filtro:
        qs = qs.filter(municipio__iexact=municipio_filtro)
    if categ_filtro:
        qs = qs.filter(classificacao=categ_filtro)
    if busca:
        qs = qs.filter(descricao__icontains=busca)

    qs = qs.order_by("mes_referencia", "classificacao", "descricao")
    total = qs.count()

    if total == 0:
        print(c(YELLOW, "\n  Nenhuma despesa encontrada com os filtros aplicados."))
        return

    # 3. Preview ──────────────────────────────────────────────────────────────
    print()
    print(hr())
    print(c(BOLD, f"  {total} despesa(s) encontrada(s):"))
    print()

    PREVIEW_MAX = 30
    lista = list(qs[:PREVIEW_MAX + 1])
    tem_mais = len(lista) > PREVIEW_MAX
    for desp in lista[:PREVIEW_MAX]:
        venc = desp.data_vencimento.strftime("%d/%m/%Y") if desp.data_vencimento else "—"
        status_cor = GREEN if desp.status == "pago" else YELLOW
        mun = f"  [{desp.municipio}]" if desp.municipio else ""
        a = c(DIM, f"{str(desp.pk)[:6]:>6}")
        b = f"{desp.descricao[:40]:<40}"
        c = desp.mes_referencia.strftime('%m/%Y')
        d = f"{fmt_brl(desp.valor):>14}"
        e = c(status_cor, f"{desp.status:<10}")  # Espaçamento aplicado ANTES da cor
        f = c(DIM, mun)
        print(
            f"{a}"
            f"{b}"
            f"{c}"
            f"{d}"
            f"{e}"
            f"{f}"
        )
    if tem_mais:
        print(c(DIM, f"  ... e mais {total - PREVIEW_MAX} registro(s) não exibidos"))

    # 4. Modo: lote ou individual ─────────────────────────────────────────────
    print()
    modo = perguntar(
        "Modo de alteração",
        opcoes=["lote", "individual"],
        default="lote",
    )

    novo_status = perguntar("Novo status", opcoes=["pendente", "pago"])

    if modo == "lote":
        print()
        total_val = sum(d.valor for d in qs.iterator())
        print(c(BOLD, f"  Resumo do lote:"))
        print(f"     Registros   : {total}")
        print(f"     Valor total : {fmt_brl(total_val)}")
        print(f"     Novo status : {c(GREEN if novo_status == 'pago' else YELLOW, novo_status)}")
        print()
        if not perguntar_sim_nao("Confirma alteração em lote?"):
            print(c(YELLOW, "  Cancelado."))
            return
        if not dry_run:
            with transaction.atomic():
                qs.update(status=novo_status)
        _relatorio_acao(f"status → {novo_status}", total, dry_run)

    else:  # individual
        alterados = 0
        for desp in qs.iterator():
            print()
            venc = desp.data_vencimento.strftime("%d/%m/%Y") if desp.data_vencimento else "—"
            print(
                f"  {c(BOLD, desp.descricao)}  {fmt_brl(desp.valor)}  "
                f"{desp.mes_referencia.strftime('%m/%Y')}  venc={venc}  "
                f"status={c(GREEN if desp.status == 'pago' else YELLOW, desp.status)}"
            )
            if perguntar_sim_nao(f"  Alterar para '{novo_status}'?"):
                if not dry_run:
                    desp.status = novo_status
                    desp.save(update_fields=["status", "atualizado_em"])
                alterados += 1
        _relatorio_acao(f"status → {novo_status}", alterados, dry_run)

    print(hr("═"))


# ──────────────────────────────────────────────────────────────────────────────
# ★ NOVA FERRAMENTA 3 — Cancelar recorrência
# ──────────────────────────────────────────────────────────────────────────────

def _ferramenta_recorrencia(dry_run: bool) -> None:
    print()
    print(hr("═"))
    print(c(BOLD + RED, "  🔁  Cancelamento de Recorrência"))
    if dry_run:
        print(c(YELLOW, "  ⚠️   Modo DRY-RUN — nenhum dado será gravado"))
    print(hr("═"))
    print()

    # 1. Carrega despesas recorrentes com meses futuros ──────────────────────
    hoje = date.today().replace(day=1)

    qs_rec = (
        DespesaGeral.objects
        .filter(recorrente=True, mes_referencia__gte=hoje)
        .order_by("descricao", "mes_referencia")
    )

    total_rec = qs_rec.count()
    if total_rec == 0:
        print(c(YELLOW, "  Nenhuma despesa recorrente com meses futuros encontrada."))
        return

    # 2. Agrupa por descrição ─────────────────────────────────────────────────
    grupos: dict[str, list] = {}
    for desp in qs_rec.iterator():
        grupos.setdefault(desp.descricao, []).append(desp)

    print(c(BOLD, f"  {len(grupos)} grupo(s) de despesas recorrentes encontrado(s):"))
    print()

    for i, (desc, registros) in enumerate(grupos.items(), start=1):
        meses = sorted(set(r.mes_referencia.strftime("%m/%Y") for r in registros))
        total_val = sum(r.valor for r in registros)
        print(
            f"  {c(BOLD, str(i)):>4}.  {desc[:44]:<44}  "
            f"{fmt_brl(registros[0].valor):>14}  "
            f"{c(DIM, str(len(registros)) + ' meses')}  "
            f"total={fmt_brl(total_val)}"
        )
        print(c(DIM, f"         Meses: {', '.join(meses[:6])}" + (" ..." if len(meses) > 6 else "")))

    # 3. Modo: lote ou individual ─────────────────────────────────────────────
    print()
    modo = perguntar(
        "Modo de cancelamento",
        opcoes=["todos", "selecionar", "individual"],
        default="selecionar",
    )

    grupos_list = list(grupos.items())
    grupos_escolhidos: list[tuple[str, list]] = []

    if modo == "todos":
        grupos_escolhidos = grupos_list

    elif modo == "selecionar":
        raw = input(c(CYAN, "  → Números dos grupos (separados por vírgula): ")).strip()
        for parte in raw.split(","):
            parte = parte.strip()
            if parte.isdigit():
                idx = int(parte) - 1
                if 0 <= idx < len(grupos_list):
                    grupos_escolhidos.append(grupos_list[idx])
                else:
                    print(c(YELLOW, f"    '{parte}' fora do intervalo — ignorado."))
        if not grupos_escolhidos:
            print(c(YELLOW, "  Nenhum grupo válido selecionado."))
            return

    elif modo == "individual":
        grupos_escolhidos = grupos_list  # tratado registro a registro abaixo

    # 4. Define ação de cancelamento ──────────────────────────────────────────
    print()
    print(c(BOLD, "  Ação para os meses futuros selecionados:"))
    print(f"    {c(BOLD, '1')}. Marcar recorrente=False (mantém registros, para de repetir)")
    print(f"    {c(BOLD, '2')}. Excluir os registros futuros")
    print(f"    {c(BOLD, '3')}. Marcar recorrente=False E alterar status para 'pendente'")
    acao_rec = perguntar("Escolha", opcoes=["1", "2", "3"])

    # 5. A partir de qual mês? ────────────────────────────────────────────────
    print()
    mes_corte = perguntar_mes("Cancelar a partir de qual mês?", default=hoje)

    # 6. Aplica ───────────────────────────────────────────────────────────────
    total_afetados = 0

    for desc, registros in grupos_escolhidos:
        futuros = [r for r in registros if r.mes_referencia >= mes_corte]
        if not futuros:
            continue

        if modo == "individual":
            print()
            print(hr("·"))
            print(c(BOLD, f"  Grupo: {desc}"))
            meses_str = ", ".join(r.mes_referencia.strftime("%m/%Y") for r in futuros[:6])
            print(c(DIM, f"  Meses futuros: {meses_str}"))
            if not perguntar_sim_nao(f"  Cancelar {len(futuros)} registro(s)?"):
                continue

        ids = [r.pk for r in futuros]

        if not dry_run:
            with transaction.atomic():
                if acao_rec == "1":
                    DespesaGeral.objects.filter(pk__in=ids).update(recorrente=False)
                elif acao_rec == "2":
                    DespesaGeral.objects.filter(pk__in=ids).delete()
                elif acao_rec == "3":
                    DespesaGeral.objects.filter(pk__in=ids).update(
                        recorrente=False, status="pendente"
                    )

        total_afetados += len(ids)

    # 7. Relatório ────────────────────────────────────────────────────────────
    print()
    print(hr("═"))
    prefixo = "[dry-run] " if dry_run else ""
    acoes_desc = {
        "1": "recorrente=False",
        "2": "excluídos",
        "3": "recorrente=False + status=pendente",
    }
    print(c(GREEN if total_afetados else YELLOW,
            f"  {prefixo}✔  {total_afetados} registro(s) — {acoes_desc.get(acao_rec, '')}"))
    print(hr("═"))


# ──────────────────────────────────────────────────────────────────────────────
# Command principal
# ──────────────────────────────────────────────────────────────────────────────

MENU_PRINCIPAL = [
    ("1", "📥  Importar despesas de CSV"),
    ("2", "🏙️   Classificar municípios nas despesas existentes"),
    ("3", "💳  Alterar status de pagamento em lote"),
    ("4", "🔁  Cancelar recorrência (em lote ou individual)"),
    ("5", "⏪  Aplicar classificação retroativa (mês anterior)"),
    ("6", "📋  Copiar/Clonar despesas de um mês para outro"), # <--- NOVA
    ("7", "🚪  Sair"),
]

FERRAMENTAS_FLAG = {
    "importar":    "1",
    "municipios":  "2",
    "status":      "3",
    "recorrencia": "4",
    "retroativo":  "5",
    "clonar":      "6", # <--- NOVA
}

def _ferramenta_copiar(dry_run: bool) -> None:
    print()
    print(hr("═"))
    print(c(BOLD + MAGENTA, "  📋  Clonagem de Despesas (Copiar mês para outro)"))
    print(hr("═"))

    # 1. Escolha dos meses
    mes_origem = perguntar_mes("Mês de ORIGEM (de onde copiar)")
    mes_destino = perguntar_mes("Mês de DESTINO (para onde copiar)")

    if mes_origem == mes_destino:
        print(c(RED, "  ✖  O mês de origem não pode ser igual ao de destino."))
        return

    # 2. Busca despesas do mês de origem
    despesas_origem = DespesaGeral.objects.filter(mes_referencia=mes_origem)
    
    if not despesas_origem.exists():
        print(c(YELLOW, f"  Nenhuma despesa encontrada no mês {mes_origem.strftime('%m/%Y')}."))
        return

    # 3. Verifica se já existem despesas no mês destino
    if DespesaGeral.objects.filter(mes_referencia=mes_destino).exists():
        print(c(YELLOW, f"  ⚠️  Atenção: Já existem despesas no mês {mes_destino.strftime('%m/%Y')}. Clonar criará duplicatas."))
        if not perguntar_sim_nao("Prosseguir mesmo assim?"):
            return

    # 4. Clonagem
    print(f"\n  Clonando {despesas_origem.count()} despesas...")
    
    if not dry_run:
        novas_despesas = []
        with transaction.atomic():
            for d in despesas_origem:
                # Cria uma cópia limpando campos que devem mudar
                d.pk = None 
                d.mes_referencia = mes_destino
                d.status = 'pendente'  # Sempre clona como pendente
                d.criado_em = None
                d.atualizado_em = None
                novas_despesas.append(d)
            
            DespesaGeral.objects.bulk_create(novas_despesas)
    
    prefixo = "[dry-run] " if dry_run else ""
    print(c(GREEN, f"\n  {prefixo}✔  {despesas_origem.count()} despesa(s) clonadas para {mes_destino.strftime('%m/%Y')} com sucesso!"))
    print(hr("═"))
    
def _ferramenta_retroativa(dry_run: bool) -> None:
    print()
    print(hr("═"))
    print(c(BOLD + MAGENTA, "  ⏪  Aplicação Retroativa de Municípios"))
    print(hr("═"))

    # 1. Escolha dos meses
    mes_origem = perguntar_mes("Mês de ORIGEM (onde já existem classificações)")
    mes_destino = perguntar_mes("Mês de DESTINO (onde aplicar as classificações)")

    # 2. Busca despesas do mês de origem que possuem município
    base_classificacao = DespesaGeral.objects.filter(
        mes_referencia=mes_origem
    ).exclude(municipio__isnull=True).exclude(municipio="")

    # Dicionário: (descricao, valor) -> municipio
    mapa_classificacao = {
        (d.descricao, d.valor): d.municipio 
        for d in base_classificacao
    }

    print(f"  {c(BOLD, str(len(mapa_classificacao)))} mapeamentos encontrados no mês {mes_origem.strftime('%m/%Y')}.")

    # 3. Busca despesas do mês de destino sem classificação
    qs_destino = DespesaGeral.objects.filter(
        mes_referencia=mes_destino
    ).filter(Q(municipio__isnull=True) | Q(municipio=""))

    total_alvos = qs_destino.count()
    if total_alvos == 0:
        print(c(YELLOW, "  Nenhuma despesa sem município encontrada no mês destino."))
        return

    print(f"  {total_alvos} despesa(s) sem classificação no mês {mes_destino.strftime('%m/%Y')}.")

    # 4. Aplicação
    alterados = 0
    if not dry_run:
        with transaction.atomic():
            for desp in qs_destino.iterator():
                chave = (desp.descricao, desp.valor)
                if chave in mapa_classificacao:
                    desp.municipio = mapa_classificacao[chave]
                    desp.save(update_fields=['municipio', 'atualizado_em'])
                    alterados += 1
    else:
        # Apenas simulação
        for desp in qs_destino.iterator():
            if (desp.descricao, desp.valor) in mapa_classificacao:
                alterados += 1

    prefixo = "[dry-run] " if dry_run else ""
    print(c(GREEN, f"\n  {prefixo}✔  {alterados} despesas atualizadas retroativamente."))
    print(hr("═"))

class Command(BaseCommand):
    help = (
        "Ferramentas para gestão de Despesas Gerais: importação CSV, "
        "classificação de municípios, alteração de status e cancelamento de recorrência."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pasta", type=str, default=None,
            help="Caminho alternativo para buscar os CSVs (padrão: pasta deste arquivo).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Simula sem gravar nada no banco de dados.",
        )
        parser.add_argument(
            "--usuario", type=str, default=None,
            help="Username do criador das despesas (importação CSV).",
        )
        parser.add_argument(
            "--ferramenta", type=str, default=None,
            choices=list(FERRAMENTAS_FLAG.keys()),
            help="Acessa diretamente uma ferramenta sem exibir o menu principal.",
        )

    # ── entry point ────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        print()
        print(hr("═"))
        print(c(BOLD, "  💼  Gestão de Despesas Gerais — CONMAC"))
        if dry_run:
            print(c(YELLOW, "  ⚠️   Modo DRY-RUN — nenhum dado será gravado"))
        print(hr("═"))

        # Acesso direto por flag ────────────────────────────────────────────
        if options["ferramenta"]:
            escolha = FERRAMENTAS_FLAG[options["ferramenta"]]
        else:
            escolha = self._menu_principal()

        if escolha == "1":
            self._fluxo_importacao(options)
        elif escolha == "2":
            _ferramenta_municipios(dry_run)
        elif escolha == "3":
            _ferramenta_status(dry_run)
        elif escolha == "4":
            _ferramenta_recorrencia(dry_run)
        elif escolha == "5": # <--- NOVA
            _ferramenta_retroativa(dry_run)
        elif escolha == "6": # <--- NOVA
            _ferramenta_copiar(dry_run)
        else:
            print(c(DIM, "\n  Saindo.\n"))

    # ── menu principal ─────────────────────────────────────────────────────────

    def _menu_principal(self) -> str:
        print()
        print(c(BOLD, "  O que deseja fazer?"))
        print()
        for key, desc in MENU_PRINCIPAL:
            print(f"    {c(BOLD, key)}. {desc}")
        print()
        opcoes = [k for k, _ in MENU_PRINCIPAL]
        return perguntar("Escolha uma opção", opcoes=opcoes)

    # ── fluxo de importação (mantido intacto) ──────────────────────────────────

    def _fluxo_importacao(self, options: dict) -> None:
        pasta   = Path(options["pasta"]) if options["pasta"] else Path(__file__).parent
        dry_run = options["dry_run"]

        print()
        print(hr("═"))
        print(c(BOLD, "  📂  Importador de Despesas Gerais (CSV)"))
        print(hr("═"))

        criado_por = self._resolver_usuario(options["usuario"])

        csvs = sorted(pasta.glob("*.csv"))
        if not csvs:
            raise CommandError(f"Nenhum arquivo .csv encontrado em: {pasta}")

        print(c(BOLD, f"\n  Encontrado(s) {len(csvs)} arquivo(s) CSV em:\n  {pasta}\n"))
        for i, p in enumerate(csvs, start=1):
            print(f"    {c(BOLD, str(i))}. {p.name}  {c(DIM, f'({p.stat().st_size} bytes)')}")

        arquivos_escolhidos = self._escolher_arquivos(csvs)

        total_importados = total_alterados = total_erros = 0

        for caminho in arquivos_escolhidos:
            imp, alt, err = self._processar_arquivo(caminho, criado_por, dry_run)
            total_importados += imp
            total_alterados  += alt
            total_erros      += err

        print()
        print(hr("═"))
        print(c(BOLD, "  ✅  Importação concluída"))
        print(f"     Novos registros gravados  : {c(GREEN,  str(total_importados))}")
        print(f"     Registros existentes alt. : {c(BLUE,   str(total_alterados))}")
        if total_erros:
            print(f"     Erros / ignorados         : {c(RED, str(total_erros))}")
        if dry_run:
            print(c(YELLOW, "     (nenhuma alteração real — dry-run ativo)"))
        print(hr("═"))
        print()

    # ── seleção de arquivos ────────────────────────────────────────────────────

    def _resolver_usuario(self, username: str | None):
        if not username:
            return None
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(c(YELLOW, f"  Usuário '{username}' não encontrado — criado_por em branco."))
            return None

    def _escolher_arquivos(self, csvs: list[Path]) -> list[Path]:
        if len(csvs) == 1:
            if perguntar_sim_nao(f"Importar '{csvs[0].name}'?"):
                return csvs
            raise CommandError("Nenhum arquivo selecionado.")

        print()
        raw = perguntar("Quais arquivos? (números separados por vírgula, ou 'todos')", default="todos")
        if raw.lower() == "todos":
            return csvs

        selecionados = []
        for parte in raw.split(","):
            parte = parte.strip()
            if parte.isdigit() and 1 <= int(parte) <= len(csvs):
                selecionados.append(csvs[int(parte) - 1])
            else:
                print(c(YELLOW, f"    '{parte}' ignorado."))

        if not selecionados:
            raise CommandError("Nenhum arquivo válido selecionado.")
        return selecionados

    # ── processamento de um arquivo CSV ───────────────────────────────────────

    def _processar_arquivo(
        self, caminho: Path, criado_por, dry_run: bool
    ) -> tuple[int, int, int]:

        print()
        print(hr())
        print(c(BOLD, f"  📄  {caminho.name}"))
        print(hr())

        try:
            linhas = ler_csv(caminho)
        except Exception as e:
            self.stderr.write(c(RED, f"  Erro ao ler {caminho.name}: {e}"))
            return 0, 0, 1

        if not linhas:
            print(c(YELLOW, "  Nenhuma linha válida encontrada."))
            return 0, 0, 0

        print(c(BOLD, f"\n  {len(linhas)} registro(s) no CSV:\n"))
        for item in linhas:
            print(f"    • {item['descricao']:<46} {fmt_brl(item['valor'])}")

        print()
        if not perguntar_sim_nao("Prosseguir com este arquivo?"):
            print(c(YELLOW, "  Arquivo ignorado."))
            return 0, 0, 0

        print()
        print(c(BOLD, "  🔍  Varrendo duplicatas no banco de dados..."))
        duplicatas = _varrer_duplicatas(linhas)

        indices_a_pular: set[int] = set()
        alterados = 0

        if not duplicatas:
            print(c(GREEN, "  ✔  Nenhuma duplicata encontrada. Tudo limpo!\n"))
        else:
            _exibir_duplicatas(linhas, duplicatas)
            print()
            modo_granular = perguntar_sim_nao(
                f"Tratar as {len(duplicatas)} duplicata(s) individualmente?",
                default="n",
            )
            if modo_granular:
                for idx, regs in duplicatas.items():
                    item = linhas[idx]
                    print()
                    print(hr("·"))
                    print(c(BOLD, f"  Duplicata: {item['descricao']}  {fmt_brl(item['valor'])}"))
                    for reg in regs[:3]:
                        venc = reg.data_vencimento.strftime("%d/%m/%Y") if reg.data_vencimento else "—"
                        print(c(DIM, f"    ↳ [id {reg.pk}] {reg.mes_referencia.strftime('%m/%Y')} "
                                     f"status={reg.status} venc={venc}"))
                    acao = _menu_acao_duplicata()
                    pular, alt = _aplicar_acao_duplicatas({idx: regs}, acao, dry_run)
                    indices_a_pular |= pular
                    alterados += alt
            else:
                acao = _menu_acao_duplicata()
                indices_a_pular, alterados = _aplicar_acao_duplicatas(duplicatas, acao, dry_run)

        linhas_import = [
            item for i, item in enumerate(linhas)
            if i not in indices_a_pular
        ]

        if not linhas_import:
            print(c(YELLOW, "\n  Nenhuma linha restante para importar."))
            return 0, alterados, 0

        print()
        print(hr())
        print(c(BOLD, f"  ⚙️   Configurações para {len(linhas_import)} registro(s) a importar"))
        print(hr())

        classificacao, classificacao_custom = exibir_menu_categorias()

        print()
        mes_referencia = perguntar_mes("Mês de referência inicial", default=date.today().replace(day=1))

        print()
        recorrente = perguntar_sim_nao("As despesas são recorrentes?", default="n")
        meses_recorrencia = 1
        if recorrente:
            meses_raw = input(c(CYAN, "  → Por quantos meses essa despesa se repete? [12]: ")).strip()
            meses_recorrencia = int(meses_raw) if meses_raw.isdigit() and int(meses_raw) > 0 else 12

        print()
        data_vencimento = perguntar_data("Data de vencimento do 1º mês")

        print()
        status_resp = perguntar("Status inicial do 1º mês", opcoes=["pendente", "pago"], default="pendente")

        # Classificação de município ao importar ─────────────────────────────
        print()
        associar_mun = perguntar_sim_nao("Associar um município a estas despesas?", default="n")
        municipio_import: str | None = None
        if associar_mun:
            municipios_banco = _obter_municipios_banco()
            if municipios_banco:
                municipio_import = _escolher_municipio_da_lista(municipios_banco)
            else:
                municipio_import = input(c(CYAN, "  → Nome do município: ")).strip() or None

        print()
        obs_raw = input(c(CYAN, "  → Observação (Enter para pular): ")).strip()

        print()
        print(hr())
        print(c(BOLD, "  📋  Resumo:"))
        cat_label = classificacao_custom or dict(CATEGORIAS).get(classificacao, classificacao)
        total_linhas_importadas = len(linhas_import)
        total_registros_banco = total_linhas_importadas * meses_recorrencia
        total_val_base = sum(i["valor"] for i in linhas_import)
        total_val_projetado = total_val_base * meses_recorrencia

        print(f"     Categoria        : {cat_label}")
        print(f"     Mês referência   : {mes_referencia.strftime('%m/%Y')}")
        print(f"     Recorrente       : {'Sim (' + str(meses_recorrencia) + ' meses)' if recorrente else 'Não'}")
        print(f"     Vencimento (1º)  : {data_vencimento.strftime('%d/%m/%Y') if data_vencimento else '—'}")
        print(f"     Status inicial   : {status_resp}")
        print(f"     Município        : {municipio_import or '—'}")
        print(f"     Registros no CSV : {total_linhas_importadas}")
        print(f"     Gravações Projet.: {total_registros_banco}")
        print(f"     Total Base       : {fmt_brl(total_val_base)}")
        print(f"     Total Projetado  : {fmt_brl(total_val_projetado)}")
        if indices_a_pular:
            print(f"     Pulados (dup.)   : {len(indices_a_pular)}")
        print(hr())

        print()
        if not perguntar_sim_nao("Confirma e grava?"):
            print(c(YELLOW, "  Importação cancelada."))
            return 0, alterados, 0

        if dry_run:
            print(c(YELLOW, f"\n  [dry-run] {total_registros_banco} registro(s) seriam gravados."))
            return total_registros_banco, alterados, 0

        importados = erros = 0
        try:
            with transaction.atomic():
                for item in linhas_import:
                    for i in range(meses_recorrencia):
                        try:
                            mes_atual       = adicionar_meses(mes_referencia, i)
                            vencimento_atual = adicionar_meses(data_vencimento, i)
                            status_atual    = status_resp if i == 0 else "pendente"

                            DespesaGeral.objects.create(
                                classificacao=classificacao,
                                classificacao_custom=classificacao_custom or "",
                                descricao=item["descricao"],
                                valor=item["valor"],
                                mes_referencia=mes_atual,
                                recorrente=recorrente,
                                data_vencimento=vencimento_atual,
                                status=status_atual,
                                observacao=obs_raw,
                                municipio=municipio_import or "",
                                criado_por=criado_por,
                            )
                            importados += 1
                        except Exception as e:
                            self.stderr.write(
                                c(RED, f"  Erro ao gravar '{item['descricao']}' "
                                  f"(Mês {mes_atual.strftime('%m/%Y')}): {e}")
                            )
                            erros += 1
        except Exception as e:
            self.stderr.write(c(RED, f"  Erro na transação — rollback: {e}"))
            return 0, alterados, total_linhas_importadas

        print(c(GREEN, f"\n  ✔  {importados} despesa(s) gerada(s) com sucesso!"))
        if erros:
            print(c(RED, f"  ✖  {erros} erro(s)."))

        return importados, alterados, erros
        





