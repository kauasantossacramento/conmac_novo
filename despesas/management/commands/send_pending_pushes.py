# despesas/management/commands/send_pending_pushes.py
from django.core.management.base import BaseCommand
from despesas.models import PushMessage
from despesas.utils_push import send_push_message_to_all

class Command(BaseCommand):
    help = "Envia mensagens push criadas e não enviadas."

    def handle(self, *args, **options):
        pendentes = PushMessage.objects.filter(enviado=False).order_by('criado_em')
        for p in pendentes:
            self.stdout.write(f"Enviando {p.id} — {p.titulo}...")
            res = send_push_message_to_all(p)
            self.stdout.write(f" -> enviadas: {res['sent']} falhas: {res['failed']}")
