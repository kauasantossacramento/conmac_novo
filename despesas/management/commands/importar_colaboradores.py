# ─────────────────────────────────────────────────────────────
#  Salve em:
#    <seuapp>/management/commands/importar_colaboradores.py
#
#  Crie os __init__.py se não existirem:
#    touch <seuapp>/management/__init__.py
#    touch <seuapp>/management/commands/__init__.py
#
#  Uso:
#    python manage.py importar_colaboradores planilha.xlsx
#    python manage.py importar_colaboradores planilha.xlsx --dry-run
# ─────────────────────────────────────────────────────────────

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

try:
    import openpyxl
except ImportError:
    raise ImportError("Instale openpyxl:  pip install openpyxl")

# ← Ajuste 'core' para o nome do seu app Django
from despesas.models import UsuarioPerfil


# ── Helpers ──────────────────────────────────────────────────

def cpf_strip(valor) -> str:
    """Remove máscara do CPF: pontos, traços, espaços."""
    return re.sub(r"[\.\-\s]", "", str(valor or "").strip())


def cpf_mask(cpf_raw) -> str:
    """Formata CPF como 000.000.000-00 se tiver 11 dígitos."""
    c = cpf_strip(cpf_raw)
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    return c


def gerar_username(nome_completo: str, cpf_raw) -> str:
    """Ex: adeilton3580  (primeiro nome + últimos 4 dígitos do CPF)"""
    primeiro = nome_completo.strip().split()[0].lower()
    primeiro = primeiro.translate(str.maketrans(
        "áàãâäéèêëíìîïóòõôöúùûüçñ",
        "aaaaaaeeeeiiiiooooouuuucn"
    ))
    sufixo = cpf_strip(cpf_raw)[-4:]
    return f"{primeiro}{sufixo}"


# ── Command ──────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Importa colaboradores do .xlsx. "
        "Cria usuário+perfil se o CPF não existir; "
        "caso contrário atualiza cargo e salário."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo",
            type=str,
            help="Caminho para o arquivo .xlsx",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simula sem gravar nada no banco.",
        )

    def handle(self, *args, **options):
        arquivo = Path(options["arquivo"])
        dry_run = options["dry_run"]

        if not arquivo.exists():
            raise CommandError(f"Arquivo não encontrado: {arquivo}")

        try:
            ws = openpyxl.load_workbook(arquivo).active
        except Exception as exc:
            raise CommandError(f"Não foi possível abrir o arquivo: {exc}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n⚠  DRY-RUN — nenhuma alteração será gravada.\n")
            )

        criados = atualizados = ignorados = erros = 0

        for i, row in enumerate(ws.iter_rows(values_only=True), start=1):

            # ignora linhas completamente vazias
            if not any(c for c in row if c is not None):
                ignorados += 1
                continue

            if len(row) < 4:
                self.stdout.write(self.style.WARNING(
                    f"  [L{i}] Ignorada — menos de 4 colunas: {row}"
                ))
                ignorados += 1
                continue

            nome_raw, cpf_raw, cargo_raw, sal_raw = row[0], row[1], row[2], row[3]

            nome  = str(nome_raw  or "").strip()
            cargo = str(cargo_raw or "").strip()

            if not nome or not cpf_raw:
                self.stdout.write(self.style.WARNING(
                    f"  [L{i}] Ignorada — nome ou CPF vazio."
                ))
                ignorados += 1
                continue

            try:
                salario = Decimal(str(sal_raw)).quantize(Decimal("0.01"))
            except (InvalidOperation, TypeError):
                self.stdout.write(self.style.WARNING(
                    f"  [L{i}] {nome} — salário inválido '{sal_raw}', usando 0,00"
                ))
                salario = Decimal("0.00")

            cpf_sem = cpf_strip(cpf_raw)
            cpf_fmt = cpf_mask(cpf_raw)

            try:
                foi_criado = self._processar(
                    linha=i, nome=nome,
                    cpf_fmt=cpf_fmt, cpf_sem=cpf_sem,
                    cargo=cargo, salario=salario,
                    dry_run=dry_run,
                )
                if foi_criado:
                    criados += 1
                else:
                    atualizados += 1

            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"  [L{i}] ERRO — {nome}: {exc}"
                ))
                erros += 1

        sep = "─" * 54
        self.stdout.write(f"\n{sep}")
        if dry_run:
            self.stdout.write(self.style.WARNING("  (dry-run — nada foi salvo)"))
        self.stdout.write(f"  ✚  Criados:     {criados}")
        self.stdout.write(f"  ✔  Atualizados: {atualizados}")
        self.stdout.write(f"  ─  Ignorados:   {ignorados}")
        self.stdout.write(f"  ✖  Erros:       {erros}")
        self.stdout.write(f"{sep}\n")

    # ─────────────────────────────────────────────────────────
    def _processar(self, linha, nome, cpf_fmt, cpf_sem, cargo, salario, dry_run) -> bool:
        """
        Retorna True se criou, False se atualizou.
        """
        # Busca com e sem máscara
        perfil = (
            UsuarioPerfil.objects.filter(cpf=cpf_fmt).first()
            or UsuarioPerfil.objects.filter(cpf=cpf_sem).first()
        )

        # ── JÁ EXISTE → atualiza ─────────────────────────────
        if perfil:
            perfil.salario_base = salario
            if cargo:
                perfil.cargo = cargo

            if not dry_run:
                perfil.save(update_fields=["salario_base", "cargo"])

            self.stdout.write(self.style.SUCCESS(
                f"  ✔  [atualizado]  {nome} ({cpf_fmt})"
                f"  →  {cargo or '—'}  |  R$ {salario:,.2f}"
            ))
            return False

        # ── NÃO EXISTE → cria ────────────────────────────────
        partes     = nome.split()
        first_name = partes[0]
        last_name  = " ".join(partes[1:]) if len(partes) > 1 else ""
        username   = gerar_username(nome, cpf_sem)
        senha      = cpf_sem      # senha = CPF sem máscara

        # garante username único
        base, n = username, 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{n}"
            n += 1

        if not dry_run:
            user = User.objects.create_user(
                username=username,
                password=senha,
                first_name=first_name,
                last_name=last_name,
            )
            UsuarioPerfil.objects.create(
                user=user,
                cpf=cpf_fmt,
                salario_base=salario,
                cargo=cargo,
                ativo=True,
            )

        self.stdout.write(self.style.SUCCESS(
            f"  ✚  [criado]      {nome} ({cpf_fmt})"
            f"  →  {cargo or '—'}  |  R$ {salario:,.2f}"
            f"  |  login: {username}"
        ))
        return True