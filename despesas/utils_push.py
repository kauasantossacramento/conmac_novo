# despesas/utils_push.py
from django.utils import timezone
from push_notifications.models import WebPushDevice  # ajuste se o import for outro
import json

def send_push_message_to_all(push_message_obj):
    """
    Envia a mensagem (PushMessage) para todos os WebPushDevice ativos.
    Retorna (sent_count, failed_count).
    """
    payload = {
        "title": push_message_obj.titulo,
        "body": push_message_obj.mensagem,
        "url": push_message_obj.url,
        "tag": "conmac-global"
    }

    devices = WebPushDevice.objects.filter(active=True)
    sent = 0
    failed = 0
    errors = []

    for dev in devices:
        try:
            # dependendo da versão do package, use send_message(JSON) ou send_message(string)
            # tentamos enviar o JSON como dict — a lib geralmente transforma ao enviar
            dev.send_message(payload, ttl=86400)
            sent += 1
        except Exception as e:
            failed += 1
            errors.append(str(e))

    # update objeto
    push_message_obj.enviado = True
    push_message_obj.enviado_em = timezone.now()
    push_message_obj.save(update_fields=['enviado', 'enviado_em'])

    return {"sent": sent, "failed": failed, "errors": errors}
