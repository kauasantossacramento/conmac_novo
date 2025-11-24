# despesas/apps.py
from django.apps import AppConfig

class DespesasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "despesas"

    def ready(self):
        from . import signals  # noqa
