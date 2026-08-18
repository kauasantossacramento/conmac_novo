# utils/notifications.py
import json
from webpush import send_user_notification
from django.contrib.auth.models import User

def notify_user_util(user: User, head: str, body: str, url: str = "/", ttl: int = 1000) -> dict:
    """
    Envia uma notificação webpush para um usuário específico.

    Args:
        user (User): instância do usuário alvo.
        head (str): título da notificação.
        body (str): corpo/mensagem da notificação.
        url (str): URL opcional que será aberta ao clicar.
        ttl (int): tempo de vida da notificação em segundos.

    Returns:
        dict: resultado da operação {"ok": True/False, "error": "..."}
    """
    payload = {
        "head": head,
        "body": body,
        "url": url,
    }
    try:
        send_user_notification(user=user, payload=payload, ttl=ttl)
        return {"ok": True, "status": "Notification sent"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# utils/notifications.py
from django.contrib.auth import get_user_model
from webpush import send_user_notification

User = get_user_model()

def notify_all_users(head: str, body: str, url: str = "/", ttl: int = 1000) -> dict:
    """
    Envia uma notificação webpush para todos os usuários com subscription ativo.
    """
    payload = {
        "head": head,
        "body": body,
        "url": url,
    }
    results = []
    for user in User.objects.all():
        try:
            send_user_notification(user=user, payload=payload, ttl=ttl)
            results.append({"user": user.username, "ok": True})
        except Exception as e:
            results.append({"user": user.username, "ok": False, "error": str(e)})
    return {"sent": sum(1 for r in results if r["ok"]), "errors": results}