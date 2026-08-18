"""
Management command: importar_financeiro
=======================================
Lê o CSV `funcionarios_Conmac.csv` (colocado na mesma pasta deste arquivo,
ou seja em: <app>/management/commands/funcionarios_Conmac.csv) e atualiza
o modelo UsuarioPerfil com os dados financeiros de cada funcionário.

Colunas esperadas no CSV (separador ";"):
  0 – Nome completo
  1 – Local  (Analista → 'externo' | Núcleo → 'nucleo')
  2 – Cargo
  3 – Salário contratual  (informativo, não gravado)
  4 – Salário base        → salario_base
  5 – Desconto extra      (informativo, sem campo no model – exibido no log)
  6 – INSS                (propriedade calculada no model – exibido no log)
  7 – IRRF manual         → irrf_manual  (gravado somente quando preenchido)

Uso:
    python manage.py importar_financeiro
    python manage.py importar_financeiro --dry-run       # simula sem salvar
    python manage.py importar_financeiro --criar-novos   # cria usuários não encontrados
    python manage.py importar_financeiro --dry-run --criar-novos  # simula criação

Busca de nomes (4 camadas em ordem crescente de tolerância):
  1. Exato após normalização unicode + lowercase
  2. Sem acentos (remove diacríticos de ambos os lados)
  3. Sem acentos + sem caracteres não-alfanuméricos (pontuação, hífens, apóstrofes)
  4. Parcial: primeiros dois tokens significativos coincidem (primeiro + nome do meio),
     ignorando preposições (de/do/da/dos/das/e). Útil quando o banco tem o nome
     abreviado e o CSV tem o nome completo, ou vice-versa.

Encoding do CSV: latin-1 (ISO-8859-1) — acentos e cedilhas preservados.
Cargos são normalizados via NFC para garantir composição unicode correta.
"""

import csv
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

# Ajuste o import conforme o caminho real do seu app
# from accounts.models import UsuarioPerfil
from despesas.models import UsuarioPerfil  # ← altere para o seu app

User = get_user_model()

CSV_FILENAME = "funcionarios_Conmac.csv"


# ---------------------------------------------------------------------------
# Helpers – parsing
# ---------------------------------------------------------------------------

def _parse_decimal(raw: str) -> Decimal | None:
    """Converte '6.500,00' → Decimal('6500.00'). Retorna None se vazio."""
    value = raw.strip().replace(".", "").replace(",", ".")
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Helpers – normalização de nomes
# ---------------------------------------------------------------------------

def _strip_acentos(texto: str) -> str:
    """
    Remove diacríticos (acentos, cedilhas, til, etc.) via decomposição NFD.
    'Núcleo' → 'Nucleo', 'João' → 'Joao', 'Gonçalves' → 'Goncalves'
    """
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _strip_especiais(texto: str) -> str:
    """Remove tudo que não for letra ou dígito ou espaço."""
    return re.sub(r"[^\w\s]", "", texto, flags=re.UNICODE)


def _normaliza(texto: str) -> str:
    """Normaliza NFC + espaços + lowercase – base para todas as comparações."""
    return " ".join(unicodedata.normalize("NFC", texto).strip().split()).lower()


def _chave_sem_acento(texto: str) -> str:
    """Normaliza e remove acentos."""
    return _normaliza(_strip_acentos(texto))


def _chave_limpa(texto: str) -> str:
    """Normaliza, remove acentos e remove pontuação/hífens."""
    return _normaliza(_strip_acentos(_strip_especiais(texto)))


# ---------------------------------------------------------------------------
# Helpers – tokens significativos (sem preposições)
# ---------------------------------------------------------------------------

_PREPOSICOES = {"de", "do", "da", "dos", "das", "e", "di", "du", "van", "von"}


def _tokens(texto: str, com_acento: bool = True) -> list[str]:
    """
    Tokeniza o nome removendo preposições e termos vazios.
    com_acento=False aplica _strip_acentos antes de tokenizar.
    """
    t = _normaliza(texto)
    if not com_acento:
        t = _strip_acentos(t)
    return [p for p in t.split() if p not in _PREPOSICOES and p]


def _prefixo_coincide(tokens_a: list[str], tokens_b: list[str], min_tokens: int = 2) -> bool:
    """
    Retorna True se os primeiros `min_tokens` tokens significativos
    de ambas as listas forem idênticos e existirem em quantidade suficiente.
    Ex.: ['joao','marcelo','andrade','sena'] e ['joao','marcelo','santos']
         → primeiros 2 coincidem → True
    """
    if len(tokens_a) < min_tokens or len(tokens_b) < min_tokens:
        return False
    return tokens_a[:min_tokens] == tokens_b[:min_tokens]


# ---------------------------------------------------------------------------
# Helpers – busca de usuário (5 camadas)
# ---------------------------------------------------------------------------

def _username_normalizado(user) -> str:
    """
    Retorna o username sem pontuação/underscores/pontos, sem acentos,
    em lowercase — pronto para comparar com tokens do CSV.
    Ex.: 'adriana.santos' → 'adriana santos'
         'luiz_felipe'    → 'luiz felipe'
         'mariana2'       → 'mariana2'
    """
    u = user.username.lower()
    u = re.sub(r"[._\-]", " ", u)   # separadores → espaço
    u = re.sub(r"\d+$", "", u)       # remove sufixo numérico (adriana2 → adriana)
    u = _strip_acentos(u).strip()
    return u


def _username_cobre_nome(username_norm: str, tokens_csv_s: list[str]) -> bool:
    """
    Verifica se todos os tokens do username batem com tokens do início
    do nome do CSV (sem acentos).

    Casos cobertos:
      'adriana'         ←→ ['adriana','santos']          → True  (1 token)
      'adriana santos'  ←→ ['adriana','santos','...']    → True  (2 tokens)
      'luiz felipe'     ←→ ['luiz','felipe','oliveira']  → True  (2 tokens)
      'carlos'          ←→ ['adriana','santos']          → False
    """
    u_tokens = [t for t in username_norm.split() if t]
    if not u_tokens:
        return False
    # Todos os tokens do username devem aparecer (em ordem) nos tokens do CSV
    return tokens_csv_s[:len(u_tokens)] == u_tokens


def _buscar_usuario(nome_csv: str, todos_users):
    """
    Localiza o User correspondente ao nome do CSV em 5 camadas:

      1. full_name exato (NFC + lowercase)
      2. full_name sem acentos
      3. full_name sem acentos + sem pontuação
      4. Primeiros 2 tokens significativos do full_name coincidem
      5. username (sem separadores/sufixo numérico) cobre o início do nome do CSV
         → útil quando first_name/last_name estão vazios no banco

    Retorna (user, perfil, metodo_match) ou (None, None, None).
    """
    nome_exato      = _normaliza(nome_csv)
    nome_sem_acento = _chave_sem_acento(nome_csv)
    nome_limpo      = _chave_limpa(nome_csv)

    tokens_csv_c = _tokens(nome_csv, com_acento=True)
    tokens_csv_s = _tokens(nome_csv, com_acento=False)

    candidato_sem_acento = None
    candidato_limpo      = None
    candidato_parcial    = None
    candidato_username   = None

    for user, perfil in todos_users:
        full = user.get_full_name().strip()

        # ── camadas 1-4: dependem de full_name preenchido ────────────
        if full:
            # camada 1
            if _normaliza(full) == nome_exato:
                return user, perfil, "exato"

            # camada 2
            if candidato_sem_acento is None and _chave_sem_acento(full) == nome_sem_acento:
                candidato_sem_acento = (user, perfil)
                continue

            # camada 3
            if candidato_limpo is None and _chave_limpa(full) == nome_limpo:
                candidato_limpo = (user, perfil)
                continue

            # camada 4
            if candidato_parcial is None:
                tokens_db_c = _tokens(full, com_acento=True)
                tokens_db_s = _tokens(full, com_acento=False)
                if _prefixo_coincide(tokens_csv_c, tokens_db_c) or \
                   _prefixo_coincide(tokens_csv_s, tokens_db_s):
                    candidato_parcial = (user, perfil)

        # ── camada 5: username vs tokens do CSV ──────────────────────
        # (executada sempre — cobre usuários sem first/last name)
        if candidato_username is None:
            u_norm = _username_normalizado(user)
            if _username_cobre_nome(u_norm, tokens_csv_s):
                candidato_username = (user, perfil)

    if candidato_sem_acento:
        return *candidato_sem_acento, "sem_acento"
    if candidato_limpo:
        return *candidato_limpo, "limpo"
    if candidato_parcial:
        return *candidato_parcial, "parcial"
    if candidato_username:
        return *candidato_username, "username"

    return None, None, None


# ---------------------------------------------------------------------------
# Helpers – criação de usuário
# ---------------------------------------------------------------------------

def _gerar_username(nome: str) -> str:
    """
    'João Marcelo de Andrade Sena' → 'joao.marcelo.sena'
    Remove acentos, pontuação e preposições curtas (de/do/da/dos/das/e).
    Garante unicidade adicionando sufixo numérico se necessário.
    """
    PREPOSICOES = {"de", "do", "da", "dos", "das", "e", "di", "du"}
    partes = _strip_acentos(nome).lower().split()
    partes = [re.sub(r"[^a-z0-9]", "", p) for p in partes if p not in PREPOSICOES]
    partes = [p for p in partes if p]  # remove vazios após substituição

    # Usa primeiro nome + último sobrenome
    if len(partes) >= 2:
        base = f"{partes[0]}.{partes[-1]}"
    else:
        base = partes[0] if partes else "usuario"

    username = base
    contador = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{contador}"
        contador += 1

    return username


def _primeiro_ultimo(nome: str):
    """Retorna (first_name, last_name) a partir do nome completo."""
    partes = nome.strip().split()
    if len(partes) == 1:
        return partes[0], ""
    return partes[0], " ".join(partes[1:])


LOCAL_MAP = {
    "analista": "externo",
    "núcleo":   "nucleo",
    "nucleo":   "nucleo",
}


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "Importa dados financeiros do CSV funcionarios_Conmac.csv para UsuarioPerfil. "
        "Reconhece nomes com e sem acentos/caracteres especiais. "
        "Com --criar-novos, cria usuários inexistentes após confirmação."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a importação sem persistir nenhuma alteração no banco.",
        )
        parser.add_argument(
            "--criar-novos",
            action="store_true",
            help=(
                "Ao final, lista os funcionários não encontrados e pergunta "
                "se deseja criá-los. Em --dry-run, apenas exibe o que seria criado."
            ),
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        dry_run     = options["dry_run"]
        criar_novos = options["criar_novos"]

        csv_path = os.path.join(os.path.dirname(__file__), CSV_FILENAME)
        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f"Arquivo não encontrado: {csv_path}"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("*** MODO DRY-RUN – nada será salvo ***\n"))

        # Carrega todos os usuários uma única vez (evita N+1)
        todos_users = [
            (u, getattr(u, "perfil", None))
            for u in User.objects.select_related("perfil").all()
        ]

        atualizados     = 0
        sem_perfil      = []
        nao_encontrados = []   # lista de dicts com todos os dados do CSV

        # ── leitura do CSV ─────────────────────────────────────────────
        with open(csv_path, encoding="latin-1") as f:
            reader = csv.reader(f, delimiter=";")
            for linha_num, row in enumerate(reader, start=1):

                if not row or not row[0].strip():
                    continue

                nome_csv       = row[0].strip()
                local_raw      = row[1].strip().lower() if len(row) > 1 else ""
                cargo          = unicodedata.normalize("NFC", row[2].strip()) if len(row) > 2 else ""
                salario_base   = _parse_decimal(row[4])  if len(row) > 4 else None
                desconto_extra = _parse_decimal(row[5])  if len(row) > 5 else None
                inss_csv       = _parse_decimal(row[6])  if len(row) > 6 else None
                irrf_manual    = _parse_decimal(row[7])  if len(row) > 7 else None
                local_trabalho = LOCAL_MAP.get(local_raw)

                dados_csv = dict(
                    linha=linha_num,
                    nome=nome_csv,
                    cargo=cargo,
                    local_trabalho=local_trabalho,
                    salario_base=salario_base,
                    irrf_manual=irrf_manual,
                    inss_csv=inss_csv,
                    desconto_extra=desconto_extra,
                )

                # ── busca com tolerância a acentos ─────────────────────
                user, perfil, metodo = _buscar_usuario(nome_csv, todos_users)

                if user is None:
                    nao_encontrados.append(dados_csv)
                    self.stdout.write(
                        self.style.WARNING(f"[NÃO ENCONTRADO] Linha {linha_num}: '{nome_csv}'")
                    )
                    continue

                if perfil is None:
                    sem_perfil.append(
                        f"  Linha {linha_num}: '{nome_csv}' "
                        f"(username={user.username}) — sem UsuarioPerfil"
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"[SEM PERFIL] Linha {linha_num}: '{nome_csv}' "
                            f"(username={user.username})"
                        )
                    )
                    continue

                # ── aviso quando o match não foi exato ─────────────────
                match_info = ""
                if metodo == "sem_acento":
                    match_info = self.style.NOTICE(" [match sem acento]")
                elif metodo == "limpo":
                    match_info = self.style.NOTICE(" [match sem acento/pontuação]")
                elif metodo == "parcial":
                    match_info = self.style.NOTICE(
                        f" [match parcial: '{user.get_full_name()}' ← banco]"
                    )
                elif metodo == "username":
                    match_info = self.style.NOTICE(
                        f" [match por username: '{user.username}' — first/last name vazio]"
                    )

                # ── match por username: preenche first/last name se vazio ──
                if metodo == "username" and not user.get_full_name().strip():
                    first_name, last_name = _primeiro_ultimo(nome_csv)
                    if not dry_run:
                        user.first_name = first_name
                        user.last_name  = last_name
                        user.save(update_fields=["first_name", "last_name"])
                    alteracoes.append(
                        f"first_name='{first_name}' last_name='{last_name}' [nome preenchido no User]"
                    )

                # ── atualiza campos do perfil ──────────────────────────
                alteracoes = []

                if salario_base is not None:
                    alteracoes.append(f"salario_base={salario_base}")
                    if not dry_run:
                        perfil.salario_base = salario_base

                if cargo:
                    alteracoes.append(f"cargo='{cargo}'")
                    if not dry_run:
                        perfil.cargo = cargo

                if local_trabalho:
                    alteracoes.append(f"local_trabalho='{local_trabalho}'")
                    if not dry_run:
                        perfil.local_trabalho = local_trabalho

                if irrf_manual is not None:
                    alteracoes.append(f"irrf_manual={irrf_manual}")
                    if not dry_run:
                        perfil.irrf_manual = irrf_manual

                if inss_csv is not None:
                    alteracoes.append(f"[INSS CSV={inss_csv} — log]")

                if desconto_extra is not None:
                    alteracoes.append(f"[desconto_extra={desconto_extra} — log]")

                if not dry_run and alteracoes:
                    perfil.save()

                atualizados += 1
                status = "DRY-RUN" if dry_run else "OK"
                self.stdout.write(
                    f"[{status}]{match_info} {nome_csv}: " + " | ".join(alteracoes)
                )

        # ── resumo parcial ─────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Atualizados : {atualizados}"))

        if sem_perfil:
            self.stdout.write(
                self.style.WARNING(f"\nUsuários sem UsuarioPerfil ({len(sem_perfil)}):")
            )
            for msg in sem_perfil:
                self.stdout.write(self.style.WARNING(msg))

        if not nao_encontrados:
            if dry_run:
                self.stdout.write(self.style.WARNING("\n*** DRY-RUN concluído. ***"))
            return

        # ── funcionários não encontrados ───────────────────────────────
        self.stdout.write(
            self.style.WARNING(f"\nFuncionários NÃO encontrados no banco ({len(nao_encontrados)}):")
        )
        for d in nao_encontrados:
            self.stdout.write(
                self.style.WARNING(
                    f"  Linha {d['linha']:>3}: {d['nome']:<45} "
                    f"cargo='{d['cargo']}' | "
                    f"salario={d['salario_base']} | "
                    f"irrf={d['irrf_manual']}"
                )
            )

        if not criar_novos:
            self.stdout.write(
                "\nDica: rode com --criar-novos para ser perguntado sobre a criação desses usuários."
            )
            if dry_run:
                self.stdout.write(self.style.WARNING("\n*** DRY-RUN concluído. ***"))
            return

        # ── fluxo de criação ──────────────────────────────────────────
        self.stdout.write(
            self.style.HTTP_INFO(
                "\n──────────────────────────────────────────────────────────\n"
                "CRIAÇÃO DE NOVOS USUÁRIOS\n"
                "──────────────────────────────────────────────────────────"
            )
        )

        criados = 0
        ignorados = 0

        for d in nao_encontrados:
            username_sugerido = _gerar_username(d["nome"])
            first_name, last_name = _primeiro_ultimo(d["nome"])

            self.stdout.write(
                f"\n  Nome     : {d['nome']}\n"
                f"  Username : {username_sugerido}\n"
                f"  Cargo    : {d['cargo']}\n"
                f"  Local    : {d['local_trabalho']}\n"
                f"  Salário  : {d['salario_base']}\n"
                f"  IRRF     : {d['irrf_manual']}\n"
            )

            if dry_run:
                self.stdout.write(self.style.NOTICE("  → DRY-RUN: seria criado (sem confirmação)."))
                criados += 1
                continue

            resposta = input("  Criar este usuário? [s/N] ").strip().lower()
            if resposta not in ("s", "sim", "y", "yes"):
                self.stdout.write("  → Ignorado.")
                ignorados += 1
                continue

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username_sugerido,
                        first_name=first_name,
                        last_name=last_name,
                        password=None,
                        is_active=False,
                    )
                    # Usa get_or_create para tolerar post_save signals que
                    # já criam o UsuarioPerfil automaticamente ao criar o User.
                    perfil, criado_agora = UsuarioPerfil.objects.get_or_create(user=user)

                    if d["salario_base"] is not None:
                        perfil.salario_base = d["salario_base"]
                    if d["cargo"]:
                        perfil.cargo = d["cargo"]
                    if d["local_trabalho"]:
                        perfil.local_trabalho = d["local_trabalho"]
                    if d["irrf_manual"] is not None:
                        perfil.irrf_manual = d["irrf_manual"]

                    perfil.save()

                origem = "criado" if criado_agora else "já existia via signal"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  → User criado | Perfil {origem}: username='{username_sugerido}' "
                        f"(is_active=False — ative no admin)"
                    )
                )
                criados += 1

            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  → ERRO ao criar '{d['nome']}': {exc}"))

        # ── resumo final ───────────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: {criados} seriam criados, {len(sem_perfil)} sem perfil."
                )
            )
            self.stdout.write(self.style.WARNING("*** DRY-RUN concluído. Nada foi salvo. ***"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Novos criados : {criados}"))
            if ignorados:
                self.stdout.write(f"Ignorados     : {ignorados}")