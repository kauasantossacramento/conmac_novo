from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Retorna dictionary[key] ou None se não existir.
    Uso no template: {{ registros|get_item:etapa_id }}
    """
    try:
        return dictionary.get(key)
    except Exception:
        try:
            # se for objeto que implementa __getitem__
            return dictionary[key]
        except Exception:
            return None