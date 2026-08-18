import logging
from django.utils import timezone
from firebase_admin import messaging
from despesas.models import FCMToken, NotificacaoPush

logger = logging.getLogger(__name__)

def tentar_enviar_notificacao_existente(notificacao_id):
    """
    Recebe o ID de uma NotificacaoPush já salva no banco.
    Tenta enviar para o Firebase.
    Atualiza o status para enviado=True se der certo.
    """
    try:
        # Recarrega do banco para garantir
        notificacao = NotificacaoPush.objects.get(id=notificacao_id)
        
        # Se já foi enviada, aborta
        if notificacao.enviado:
            return True

        usuario = notificacao.usuario_alvo
        
        # Busca tokens
        tokens = list(FCMToken.objects.filter(user=usuario).values_list('token', flat=True))
        
        if not tokens:
            print(f"⚠️ [FCM] Usuário {usuario} sem tokens. Notificação salva, mas não enviada.")
            return False

        # Monta mensagem
        firebase_msg = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=notificacao.titulo,
                body=notificacao.mensagem,
            ),
            data={
                "link": notificacao.link if notificacao.link else "/",
                "notificacao_id": str(notificacao.id)
            },
            tokens=tokens,
        )

        # Envia
        response = messaging.send_each_for_multicast(firebase_msg)

        if response.success_count > 0:
            notificacao.enviado = True
            notificacao.data_envio = timezone.now()
            notificacao.save(update_fields=['enviado', 'data_envio']) # update_fields evita loop de signals
            print(f"🚀 [FCM] Enviado com sucesso para {usuario}")
            
            # Limpeza de tokens inválidos
            if response.failure_count > 0:
                _limpar_tokens(response, tokens)
            
            return True
        else:
            print(f"❌ [FCM] Falha no envio para {usuario}")
            return False

    except Exception as e:
        logger.error(f"Erro ao processar envio FCM: {e}")
        return False

def _limpar_tokens(response, tokens_originais):
    # (Mantenha sua lógica de limpeza aqui, está correta)
    pass