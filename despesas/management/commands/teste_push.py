'''

# despesas/management/commands/teste_push.py
import json
import logging
from django.core.management.base import BaseCommand
from push_notifications.models import WebPushDevice
from despesas.utils.push_utils import (
    extract_subscription_from_device,
    is_subscription_valid,
)

logger = logging.getLogger(__name__)

# Corrigido: payload precisa ser string JSON
PAYLOAD_SAMPLE = json.dumps({
    "title": "Teste CONMAC",
    "body": "Esta é uma notificação de teste enviada via manage.py teste_push",
    "url": "/",
})

class Command(BaseCommand):
    help = "Envia notificação de teste para WebPushDevice ativos; valida subscriptions e marca inválidos."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Não envia, apenas verifica/relata.")
        parser.add_argument('--limit', type=int, default=0, help="Limita número de dispositivos testados (0 = todos)")

    def handle(self, *args, **options):
        dry = options.get('dry_run')
        limit = options.get('limit') or None

        qs = WebPushDevice.objects.filter(active=True).order_by('id')
        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"Encontrados {total} devices ativos. dry_run={dry}"))

        if limit:
            qs = qs[:limit]

        sent = 0
        invalid_count = 0
        for d in qs:
            self.stdout.write(f"\n--- Device id={d.id} user={getattr(d,'user',None)}")
            sub = extract_subscription_from_device(d)
            if not sub:
                self.stdout.write(self.style.WARNING("  -> subscription ausente ou mal formatada. Marcando inactive."))
                d.active = False
                d.save(update_fields=["active"])
                invalid_count += 1
                continue

            if not is_subscription_valid(sub):
                self.stdout.write(self.style.WARNING("  -> subscription inválida (p256dh/auth). Marcando inactive."))
                logger.warning("Invalid subscription for device %s: %s", d.id, sub)
                d.active = False
                d.save(update_fields=["active"])
                invalid_count += 1
                continue

            if dry:
                self.stdout.write(self.style.SUCCESS("  -> OK (dry run): subscription parece válida."))
                continue

            try:
                # payload agora é string JSON
                d.send_message(PAYLOAD_SAMPLE)
                sent += 1
                self.stdout.write(self.style.SUCCESS("  -> Enviado com sucesso."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  -> Erro ao enviar: {e}"))
                logger.exception("Erro ao enviar push para device id=%s", d.id)

        self.stdout.write(self.style.NOTICE(f"\nResumo: enviados={sent}, invalidados={invalid_count}"))

'''
from vapid import Vapid

# Generate a new VAPID key pair
private_key, public_key = Vapid().generate_keys()

print("Private Key:", private_key)
print("Public Key:", public_key)
