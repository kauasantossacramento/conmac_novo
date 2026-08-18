import os
import logging
from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)

class DespesasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "despesas"
    verbose_name = "Atividades / Fechamento"

    def ready(self):
        # 1. Signals
        try:
            from . import signals
        except ImportError:
            pass

        # 2. Firebase
        self.inicializar_firebase()

    def inicializar_firebase(self):
        try:
            import firebase_admin
            from firebase_admin import credentials, initialize_app
        except ImportError:
            logger.warning("Firebase Admin SDK não instalado.")
            return

        if firebase_admin._apps:
            return

        # Busca o caminho no settings.py
        cred_json_path = getattr(settings, "FIREBASE_CREDENTIALS_FILE", None)
        project_id = getattr(settings, "FIREBASE_PROJECT_ID", "conmac-app")

        # Opções com o ID do Projeto
        firebase_options = {'projectId': project_id}

        try:
            if cred_json_path and os.path.exists(cred_json_path):
                cred = credentials.Certificate(cred_json_path)
                initialize_app(credential=cred, options=firebase_options)
                print(f"✅ Firebase Conectado! (Arquivo: {cred_json_path})") # Print para debug no log
            else:
                # Se cair aqui, é porque o caminho está errado ou a variável está None
                print(f"❌ ERRO CRÍTICO FIREBASE: Arquivo não encontrado no caminho: {cred_json_path}")
                logger.error(f"Arquivo de credenciais Firebase não encontrado: {cred_json_path}")
                
                # Tenta fallback (mas provavelmente falhará no PA)
                try:
                    cred = credentials.ApplicationDefault()
                    initialize_app(credential=cred, options=firebase_options)
                except Exception:
                    pass

        except Exception as e:
            logger.exception("Erro fatal inicializando Firebase: %s", e)