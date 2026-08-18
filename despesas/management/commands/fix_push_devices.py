# despesas/management/commands/fix_push_devices.py
import json
import logging
from django.core.management.base import BaseCommand
from push_notifications.models import WebPushDevice

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Preenche campos p256dh/auth em WebPushDevice a partir do registration_id JSON quando faltantes."

    def handle(self, *args, **options):
        qs = WebPushDevice.objects.all()
        total = qs.count()
        self.stdout.write(f"Scanning {total} devices...")
        updated = 0
        skipped = 0
        for d in qs:
            try:
                if d.p256dh and d.auth:
                    skipped += 1
                    continue
                reg = d.registration_id
                if not reg:
                    self.stdout.write(f"Device id={d.id} sem registration_id, pulando.")
                    continue
                try:
                    sub = json.loads(reg) if isinstance(reg, str) else reg
                except Exception:
                    self.stdout.write(f"Device id={d.id} registration_id não é JSON válido.")
                    continue
                keys = sub.get("keys") or {}
                p = keys.get("p256dh") or sub.get("p256dh") or None
                a = keys.get("auth") or sub.get("auth") or None
                changed = False
                if p and not d.p256dh:
                    d.p256dh = p
                    changed = True
                if a and not d.auth:
                    d.auth = a
                    changed = True
                if changed:
                    d.save(update_fields=["p256dh", "auth"])
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f"Updated device id={d.id}"))
                else:
                    skipped += 1
            except Exception as e:
                logger.exception("Erro em device %s", d.id)
        self.stdout.write(self.style.NOTICE(f"Resumo: updated={updated} skipped={skipped}"))
