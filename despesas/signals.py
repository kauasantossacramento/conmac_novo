# despesas/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UsuarioPerfil

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile_only_on_create(sender, instance, created, **kwargs):
    # Só cria no primeiro save do usuário.
    if created:
        UsuarioPerfil.objects.get_or_create(user=instance)


# atividades/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import EtapaRegistro, Etapa, FilaAutomatica, NivelChoices

@receiver(post_save, sender=EtapaRegistro)
def etapa_registro_post_save(sender, instance: EtapaRegistro, created, **kwargs):
    """
    Quando um EtapaRegistro é salvo, se o novo status for CONCLUIDO,
    verificar as filas que dependem de etapas deste nível e criar FilaAutomatica
    quando todas as etapas obrigatórias (para uma fila) estiverem concluídas.
    """
    # só reagir quando status final for CONCLUIDO (pode expandir para created + status)
    if instance.status != EtapaRegistroStatus.CONCLUIDO:
        return

    cliente = instance.cliente
    ano = instance.ano
    mes = instance.mes

    # Mapeie aqui os nomes de fila que você quer gerar e qual flag das etapas corresponde.
    # Exemplo: 'fila_siga' depende de Etapa.obrigatoria_para_fila_siga == True
    fila_mappings = [
        ("fila_siga", "obrigatoria_para_fila_siga", NivelChoices.SIGA),
        ("fila_etcm", "obrigatoria_para_fila_etcm", NivelChoices.E_TCM),
        # adicione outras filas/flags aqui se necessário
    ]

    for fila_nome, flag_attr, fila_nivel in fila_mappings:
        # quais etapas consideradas para essa fila (ativas e com a flag=True)
        etapas_req = Etapa.objects.filter(nivel=NivelChoices.FECHAMENTO, ativa=True)
        # selecionar apenas as etapas com a flag específica
        etapas_req = [e for e in etapas_req if getattr(e, flag_attr, False)]

        if not etapas_req:
            continue

        # para este cliente/competência, verificar se todas as etapas_req estão CONCLUIDO
        total = len(etapas_req)
        concluidas = EtapaRegistro.objects.filter(
            cliente=cliente,
            etapa__in=[e.id for e in etapas_req],
            ano=ano,
            mes=mes,
            status=EtapaRegistroStatus.CONCLUIDO
        ).count()

        if concluidas >= total:
            # criar fila automática se ainda não existir (unique_together evita duplicação)
            exists = FilaAutomatica.objects.filter(
                nome=fila_nome,
                cliente=cliente,
                nivel=fila_nivel
            ).exists()
            if not exists:
                FilaAutomatica.objects.create(
                    nome=fila_nome,
                    cliente=cliente,
                    nivel=fila_nivel,
                    data_entrada=timezone.now(),
                    motivo=f"Entrou automaticamente ao concluir etapas obrigatórias ({instance.etapa.nome})"
                )



from django.db.models.signals import post_save
from django.dispatch import receiver
# O erro está na linha abaixo. Você precisa adicionar EtapaRegistroStatus
from .models import EtapaRegistro, EtapaRegistroStatus

@receiver(post_save, sender=EtapaRegistro)
def etapa_registro_post_save(sender, instance, created, **kwargs):
    # O erro acontecia aqui pois ele não encontrava a definição
    if instance.status != EtapaRegistroStatus.CONCLUIDO:
        # ... resto do seu código ...
        pass