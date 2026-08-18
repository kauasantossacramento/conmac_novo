# despesas/utils/notification_service.py
import json
from datetime import datetime
from django.utils import timezone
from push_notifications.models import WebPushDevice
from .push_utils import normalize_subscription_from_model, is_subscription_valid

def _build_payload(title, body, url='/', extra=None):
    return {
        "title": title,
        "body": body,
        "url": url,
        "extra": extra or {}
    }

def notification(title: str, body: str, url: str = '/', users=None, mark_sent_on_db=True):
    """
    Envia notificação para:
        - se users for None -> todos WebPushDevice ativos
        - se users for queryset/list de Users -> devices desses users
    Retorna dicionário resumo com counts e falhas.
    """
    qs = WebPushDevice.objects.filter(active=True)
    if users is not None:
        # aceita queryset/user list
        user_ids = [u.id for u in users] if hasattr(users, "__iter__") else [users.id]
        qs = qs.filter(user_id__in=user_ids)

    payload = _build_payload(title, body, url)
    sent = 0
    failed = []
    for d in qs:
        sub = normalize_subscription_from_model(d)
        if not sub or not is_subscription_valid(sub):
            # marca inativo para evitar futuras tentativas
            d.active = False
            d.save(update_fields=['active'])
            failed.append((d.id, "invalid subscription"))
            continue
        try:
            d.send_message(payload)
            sent += 1
        except Exception as e:
            # falha de envio: log e marcar para investigação
            failed.append((d.id, str(e)))
            # opcional: d.active = False; d.save(update_fields=['active'])
    return {"sent": sent, "failed": failed, "requested": qs.count()}
