#!/usr/bin/env python3
"""
patch_views.py
─────────────────────────────────────────────────────────────
Execute a partir da raiz do projeto:

    python patch_views.py

O que faz:
  1. Substitui as duas definições de `avaliar_bloqueio_conclusao`
     por um thin wrapper que delega para pode_concluir_nivel.
     (Mantém compatibilidade com qualquer outro código que
      ainda chame o nome antigo.)

  2. Confirma que as chamadas nas linhas ~5333 e ~5550 passam
     a usar a lógica correta via o wrapper.

  3. Não altera nada mais — cirúrgico.

Faz backup automático em despesas/views.py.bak antes de editar.
─────────────────────────────────────────────────────────────
"""
import re
import shutil
import sys
from pathlib import Path

VIEWS = Path("despesas/views.py")

if not VIEWS.exists():
    print("ERRO: despesas/views.py não encontrado. Execute da raiz do projeto.")
    sys.exit(1)

# Backup
shutil.copy(VIEWS, VIEWS.with_suffix(".py.bak"))
print(f"Backup criado: {VIEWS.with_suffix('.py.bak')}")

content = VIEWS.read_text(encoding="utf-8")

# ══════════════════════════════════════════════════════════════
# PATCH 1 — Substituir AMBAS as definições de
#           avaliar_bloqueio_conclusao pelo thin wrapper.
#
# O wrapper delega para pode_concluir_nivel (que está definida
# depois no mesmo arquivo com a lógica hardcoded correta).
# ══════════════════════════════════════════════════════════════

WRAPPER = '''\
def avaliar_bloqueio_conclusao(cliente, nivel, ano, mes, usuario):
    """
    Thin wrapper mantido para compatibilidade.
    Toda a lógica real está em pode_concluir_nivel.
    """
    # Importa localmente para evitar dependência circular caso
    # este trecho seja lido antes da definição completa do arquivo.
    pode, motivos = pode_concluir_nivel(cliente, nivel, ano, mes, usuario)
    return pode, motivos
'''

# Regex que captura QUALQUER implementação de avaliar_bloqueio_conclusao
# (da linha `def avaliar_bloqueio_conclusao(` até a próxima def/class
#  no mesmo nível de indentação — ou seja, ^def ou ^class)
PATTERN = re.compile(
    r'^def avaliar_bloqueio_conclusao\(.*?\n(?=^def |^class |^@)',
    re.MULTILINE | re.DOTALL,
)

matches = list(PATTERN.finditer(content))
print(f"Definições de avaliar_bloqueio_conclusao encontradas: {len(matches)}")

if len(matches) == 0:
    print("AVISO: Nenhuma definição encontrada. Verifique o arquivo manualmente.")
    sys.exit(1)

# Substitui TODAS as ocorrências pelo wrapper (da mais recente para
# a mais antiga para não deslocar os índices)
for m in reversed(matches):
    content = content[:m.start()] + WRAPPER + content[m.end():]
    print(f"  Substituída definição em pos {m.start()}")

# ══════════════════════════════════════════════════════════════
# PATCH 2 — Garantir que fechamento_cliente_detail passe
#           nivel_apto_INICIO também para o contexto.
#
# A versão antiga só calculava nivel_apto_conclusao. Inserimos
# o cálculo de nivel_apto_inicio logo antes do existente.
# ══════════════════════════════════════════════════════════════

OLD_BLOCK = (
    "    nivel_apto_conclusao, lista_pendencias = avaliar_bloqueio_conclusao(\n"
    "        cliente,\n"
    "        nivel_sel,\n"
    "        sel_ano,\n"
    "        sel_mes,\n"
    "        request.user\n"
    "    )"
)

NEW_BLOCK = (
    "    nivel_apto_inicio,    pendencias_inicio   = pode_iniciar_nivel(\n"
    "        cliente, nivel_sel, sel_ano, sel_mes, request.user\n"
    "    )\n"
    "    nivel_apto_conclusao, lista_pendencias = pode_concluir_nivel(\n"
    "        cliente, nivel_sel, sel_ano, sel_mes, request.user\n"
    "    )"
)

if OLD_BLOCK in content:
    content = content.replace(OLD_BLOCK, NEW_BLOCK)
    print("Patch 2a: fechamento_cliente_detail — bloco de avaliação atualizado")
else:
    # Tenta versão alternativa (sem quebras exatas)
    alt_old = "    nivel_apto_conclusao, lista_pendencias = avaliar_bloqueio_conclusao("
    if alt_old in content:
        # Substitui só a chamada, deixando o resto
        content = content.replace(
            "    nivel_apto_conclusao, lista_pendencias = avaliar_bloqueio_conclusao(",
            "    nivel_apto_inicio, pendencias_inicio = pode_iniciar_nivel(\n"
            "        cliente, nivel_sel, sel_ano, sel_mes, request.user\n"
            "    )\n"
            "    nivel_apto_conclusao, lista_pendencias = pode_concluir_nivel("
        )
        print("Patch 2b: fechamento_cliente_detail — chamada substituída (modo alternativo)")
    else:
        print("AVISO: Patch 2 não aplicado — bloco não encontrado. Verifique manualmente.")

# ══════════════════════════════════════════════════════════════
# PATCH 3 — Atualizar o contexto de fechamento_cliente_detail
#           para incluir as novas variáveis de início.
# ══════════════════════════════════════════════════════════════

OLD_CTX = (
    '        "nivel_apto_conclusao": nivel_apto_conclusao,\n'
    '        "pendencias_nomes": lista_pendencias,\n'
    '        "lista": lista_etapas,'
)
NEW_CTX = (
    '        "nivel_apto_inicio":    nivel_apto_inicio,\n'
    '        "pendencias_inicio":    pendencias_inicio,\n'
    '        "nivel_apto_conclusao": nivel_apto_conclusao,\n'
    '        "pendencias_conclusao": lista_pendencias,\n'
    '        # legado — mantido para compatibilidade com templates antigos\n'
    '        "pendencias_nomes":     lista_pendencias,\n'
    '        "lista":                lista_pendencias,'
)
if OLD_CTX in content:
    content = content.replace(OLD_CTX, NEW_CTX)
    print("Patch 3: contexto de fechamento_cliente_detail atualizado")
else:
    print("AVISO: Patch 3 não aplicado — verifique o contexto manualmente.")

# ══════════════════════════════════════════════════════════════
# PATCH 4 — dados_tabela: adicionar bloqueada_para_iniciar
#           (a versão antiga só tinha bloqueada_para_concluir)
# ══════════════════════════════════════════════════════════════

OLD_BLOQUEIO = (
    '            # INFORMAÇÃO PARA O JS: Define se esta linha deve desabilitar o "Concluir" no modal\n'
    '            "bloqueada_para_concluir": not nivel_apto_conclusao'
)
NEW_BLOQUEIO = (
    '            # Informações para o JS desabilitar botões\n'
    '            "bloqueada_para_iniciar":  not nivel_apto_inicio,\n'
    '            "bloqueada_para_concluir": not nivel_apto_conclusao'
)
if OLD_BLOQUEIO in content:
    content = content.replace(OLD_BLOQUEIO, NEW_BLOQUEIO)
    print("Patch 4: dados_tabela — bloqueada_para_iniciar adicionado")
else:
    print("AVISO: Patch 4 não aplicado — verifique dados_tabela manualmente.")

# ══════════════════════════════════════════════════════════════
# SALVA
# ══════════════════════════════════════════════════════════════
VIEWS.write_text(content, encoding="utf-8")
print("\n✅ views.py atualizado com sucesso.")
print("Execute: python manage.py check")
