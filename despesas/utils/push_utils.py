# despesas/utils/push_utils.py
import json
import base64
from typing import Optional, Dict, Any

def safe_b64_pad(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    # remove espaços e newlines acidentais
    s = s.replace("\n", "").replace("\r", "").replace(" ", "")
    # add padding
    return s + "=" * ((4 - len(s) % 4) % 4)

def try_load_json(value: Any) -> Optional[Dict]:
    """
    Tenta transformar value em dict. Aceita dicts já prontos ou strings JSON.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except Exception:
            return None
    if isinstance(value, str):
        s = value.strip()
        # corrigir aspas simples (não ideal mas às vezes salvo assim)
        if s and s[0] == "'" and s[-1] == "'":
            s = s[1:-1]
        try:
            return json.loads(s)
        except Exception:
            # tentar substituições mínimas para tornar JSON válido
            s2 = s.replace("'", '"')
            try:
                return json.loads(s2)
            except Exception:
                return None
    return None

def extract_subscription_from_device(device_obj) -> Optional[Dict]:
    """
    Extrai subscription dict de um modelo WebPushDevice.
    Tenta subscription_info, registration_id (string), etc.
    """
    if not device_obj:
        return None
    # prefer subscription_info (algumas versões do pacote usam esse campo)
    if hasattr(device_obj, "subscription_info") and device_obj.subscription_info:
        if isinstance(device_obj.subscription_info, dict):
            return device_obj.subscription_info
        else:
            maybe = try_load_json(device_obj.subscription_info)
            if maybe:
                return maybe
    # fallback registration_id
    rid = getattr(device_obj, "registration_id", None)
    if rid:
        maybe = try_load_json(rid)
        if maybe:
            return maybe
    # em alguns setups, campo 'device_id' ou 'data' podem conter JSON
    for attr in ("device_id", "data", "info"):
        if hasattr(device_obj, attr):
            v = getattr(device_obj, attr)
            maybe = try_load_json(v)
            if maybe:
                return maybe
    return None

def p256dh_bytes_from_subscription(sub: Dict[str, Any]) -> Optional[bytes]:
    """
    Retorna bytes do chave p256dh (com padding e decode urlsafe).
    """
    if not sub:
        return None
    keys = sub.get("keys") or sub.get("key") or {}
    # algumas subscriptions usam keys.p256dh ou keys['p256dh']
    p = keys.get("p256dh") if isinstance(keys, dict) else None
    if not p and isinstance(sub.get("keys"), dict):
        p = sub["keys"].get("p256dh")
    if not p:
        # às vezes a estrutura é sub["p256dh"]
        p = sub.get("p256dh")
    if not p:
        return None
    try:
        padded = safe_b64_pad(p)
        raw = base64.urlsafe_b64decode(padded)
        return raw
    except Exception:
        # tentar decodificar com b64 standard
        try:
            raw = base64.b64decode(padded)
            return raw
        except Exception:
            return None

def is_subscription_valid(sub: Dict[str, Any]) -> bool:
    """
    Verifica se p256dh decodifica para 65 bytes e começa com 0x04.
    """
    try:
        raw = p256dh_bytes_from_subscription(sub)
        if not raw:
            return False
        # receiver_raw[0] deve ser 0x04 e len == 65
        return len(raw) == 65 and raw[0] == 4
    except Exception:
        return False
