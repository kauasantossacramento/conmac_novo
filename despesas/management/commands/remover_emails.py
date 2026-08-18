"""
Management command: remover_emails.py
=============================================

Remove temporariamente e-mails específicos de todos os contratos
e permite restaurá-los depois com os dados originais preservados.

Uso:
    # Remover (salva backup em JSON antes de deletar):
    python manage.py remover_emails.py --acao remover

    # Restaurar a partir do backup gerado:
    python manage.py remover_emails.py --acao restaurar

    # Restaurar a partir de um arquivo de backup específico:
    python manage.py remover_emails.py --acao restaurar --backup caminho/para/backup.json

    # Apenas listar os registros existentes (sem alterar nada):
    python manage.py remover_emails.py --acao listar

Coloque este arquivo em:
    <seu_app>/management/commands/remover_emails.py
"""

import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

# ── E-mails que serão gerenciados ─────────────────────────────────────────
EMAILS_ALVO = [
    "eronssilva@gmail.com",
    "edumacedo77@hotmail.com",
    "andre@conmac.com.br",
    "adriana@conmac.com.br",
]

# Arquivo de backup padrão (criado na raiz do projeto)
BACKUP_DEFAULT = "backup_emails_contrato.json"


class Command(BaseCommand):
    help = (
        "Remove temporariamente e-mails específicos de todos os contratos "
        "e permite restaurá-los posteriormente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--acao",
            choices=["remover", "restaurar", "listar"],
            required=True,
            help="Ação a executar: 'remover', 'restaurar' ou 'listar'.",
        )
        parser.add_argument(
            "--backup",
            default=BACKUP_DEFAULT,
            help=(
                f"Caminho do arquivo JSON de backup "
                f"(padrão: {BACKUP_DEFAULT})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a operação sem gravar nada no banco ou disco.",
        )

    # ──────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        acao    = options["acao"]
        backup  = options["backup"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("⚠  Modo DRY-RUN ativo — nenhuma alteração será gravada.\n")
            )

        if acao == "listar":
            self._listar()
        elif acao == "remover":
            self._remover(backup, dry_run)
        elif acao == "restaurar":
            self._restaurar(backup, dry_run)

    # ── LISTAR ────────────────────────────────────────────────────────────
    def _listar(self):
        from despesas.models import ContratoEmail  # ajuste o app conforme necessário

        registros = (
            ContratoEmail.objects
            .filter(email__in=EMAILS_ALVO)
            .select_related("contrato")
            .order_by("contrato__omie_num_ctr", "email")
        )

        if not registros.exists():
            self.stdout.write(self.style.WARNING("Nenhum registro encontrado para os e-mails alvo."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"{'ID':<6} {'Contrato':<20} {'E-mail':<35} {'Nome contato':<25} {'Principal'}")
        )
        self.stdout.write("-" * 100)
        for r in registros:
            self.stdout.write(
                f"{r.pk:<6} {str(r.contrato.omie_num_ctr):<20} {r.email:<35} "
                f"{r.nome_contato or '':<25} {'Sim' if r.principal else 'Não'}"
            )
        self.stdout.write(f"\nTotal: {registros.count()} registro(s).")

    # ── REMOVER ───────────────────────────────────────────────────────────
    def _remover(self, backup_path: str, dry_run: bool):
        from despesas.models import ContratoEmail  # ajuste o app conforme necessário

        registros = (
            ContratoEmail.objects
            .filter(email__in=EMAILS_ALVO)
            .select_related("contrato")
        )

        if not registros.exists():
            self.stdout.write(self.style.WARNING("Nenhum registro encontrado. Nada a remover."))
            return

        # Serializa para backup
        dados_backup = []
        for r in registros:
            dados_backup.append({
                "contrato_id":  r.contrato_id,
                "email":        r.email,
                "nome_contato": r.nome_contato,
                "principal":    r.principal,
            })

        self.stdout.write(f"Registros encontrados para remoção: {len(dados_backup)}")
        for item in dados_backup:
            self.stdout.write(
                f"  • Contrato {item['contrato_id']} — {item['email']}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Nenhuma alteração realizada."))
            return

        # Grava backup
        payload = {
            "gerado_em": datetime.now().isoformat(),
            "emails_alvo": EMAILS_ALVO,
            "registros": dados_backup,
        }
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"\n✔  Backup salvo em: {os.path.abspath(backup_path)}"))

        # Deleta
        total, _ = registros.delete()
        self.stdout.write(self.style.SUCCESS(f"✔  {total} registro(s) removido(s) com sucesso."))

    # ── RESTAURAR ─────────────────────────────────────────────────────────
    def _restaurar(self, backup_path: str, dry_run: bool):
        from despesas.models import ContratoEmail  # ajuste o app conforme necessário

        if not os.path.exists(backup_path):
            raise CommandError(
                f"Arquivo de backup não encontrado: {backup_path}\n"
                "Execute '--acao remover' primeiro para gerar o backup."
            )

        with open(backup_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        registros = payload.get("registros", [])
        if not registros:
            self.stdout.write(self.style.WARNING("Backup vazio. Nada a restaurar."))
            return

        self.stdout.write(
            f"Backup gerado em: {payload.get('gerado_em', 'desconhecido')}\n"
            f"Registros a restaurar: {len(registros)}"
        )

        criados     = 0
        ignorados   = 0
        erros       = 0

        for item in registros:
            contrato_id  = item["contrato_id"]
            email        = item["email"]
            nome_contato = item.get("nome_contato", "")
            principal    = item.get("principal", False)

            self.stdout.write(f"  • Contrato {contrato_id} — {email}")

            if dry_run:
                continue

            try:
                _, created = ContratoEmail.objects.get_or_create(
                    contrato_id=contrato_id,
                    email=email,
                    defaults={
                        "nome_contato": nome_contato,
                        "principal":    principal,
                    },
                )
                if created:
                    criados += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ↳ Já existe (ignorado): {email} no contrato {contrato_id}"
                        )
                    )
                    ignorados += 1
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"    ↳ Erro ao restaurar {email} no contrato {contrato_id}: {exc}"
                    )
                )
                erros += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Nenhuma alteração realizada."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✔  Restauração concluída — "
                f"criados: {criados}, já existiam: {ignorados}, erros: {erros}."
            )
        )

        if erros == 0 and criados > 0:
            # Pergunta se deve remover o backup após restauração bem-sucedida
            self.stdout.write(
                f"\nDeseja remover o arquivo de backup '{backup_path}'? "
                "(Delete manualmente se quiser manter o histórico)"
            )