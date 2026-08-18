
# despesas/utils.py
import logging
from django.utils import timezone
from firebase_admin import messaging
from .models import FCMToken, NotificacaoPush

logger = logging.getLogger(__name__)

def enviar_notificacao_push(titulo, mensagem, link=None, usuario_alvo=None):
    """
    Cria o registro no banco e dispara a notificação via Firebase.
    Retorna True se enviou com sucesso (pelo menos 1), False se falhou.
    """

    # 1. Gravar o registro no Banco de Dados (Histórico)
    notificacao = NotificacaoPush.objects.create(
        titulo=titulo,
        mensagem=mensagem,
        link=link,
        usuario_alvo=usuario_alvo,
        enviado=False # Começa como falso
    )

    print(f"🔔 Iniciando envio da notificação ID {notificacao.id}: {titulo}")

    # 2. Selecionar os Tokens (Todos ou Específico)
    tokens_queryset = FCMToken.objects.all()

    if usuario_alvo:
        tokens_queryset = tokens_queryset.filter(user=usuario_alvo)

    # Transforma em lista de strings
    lista_tokens = list(tokens_queryset.values_list('token', flat=True))

    # Se não tiver ninguém para receber, para aqui
    if not lista_tokens:
        logger.warning(f"Tentativa de envio '{titulo}' sem tokens destinatários.")
        return False

    # 3. Montar a mensagem do Firebase
    firebase_msg = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=titulo,
            body=mensagem,
        ),
        data={
            "link": link if link else "/",
            "click_action": "FLUTTER_NOTIFICATION_CLICK"
        },
        tokens=lista_tokens,
    )

    # 4. Enviar para o Google
    try:
        response = messaging.send_each_for_multicast(firebase_msg)

        # 5. Atualizar status no Banco
        notificacao.enviado = True
        notificacao.data_envio = timezone.now()
        notificacao.save()

        print(f"✅ Envio concluído! Sucessos: {response.success_count}, Falhas: {response.failure_count}")

        # Limpeza automática de tokens inválidos
        if response.failure_count > 0:
            _limpar_tokens_invalidos(response, lista_tokens)

        return True

    except Exception as e:
        logger.error(f"❌ Erro crítico ao enviar Firebase: {e}")
        return False

def _limpar_tokens_invalidos(response, tokens_originais):
    """Função interna para remover tokens que não existem mais"""
    tokens_para_remover = []
    for idx, resp in enumerate(response.responses):
        if not resp.success:
            err_code = resp.exception.code
            if err_code == 'messaging/registration-token-not-registered':
                tokens_para_remover.append(tokens_originais[idx])

    if tokens_para_remover:
        count = FCMToken.objects.filter(token__in=tokens_para_remover).delete()[0]
        print(f"🧹 Limpeza: {count} tokens inválidos removidos.")