from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import date
 
from despesas.models import DespesaGeral
from despesas.models import NotificacaoPush
 
 
class Command(BaseCommand):
    help = "Envia lembretes de vencimento de Despesas Gerais via NotificacaoPush"
 
    def handle(self, *args, **options):
        hoje        = date.today()
        staff_users = list(User.objects.filter(is_staff=True, is_active=True))
        despesas    = DespesaGeral.objects.filter(
            status="pendente",
            data_vencimento__isnull=False,
        )
 
        criadas = 0
 
        for desp in despesas:
            lembretes = desp.lembrete_antecedencia or []
            if not lembretes:
                continue
 
            dias = (desp.data_vencimento - hoje).days
 
            # Notifica se o nº de dias bate com algum lembrete configurado
            # ou se está vencida e "0" está na lista (re-alerta diário)
            deve = dias in lembretes or (dias < 0 and 0 in lembretes)
            if not deve:
                continue
 
            # Texto da notificação
            if dias < 0:
                emoji = "🔴"; aviso = f"Vencida há {abs(dias)} dia(s)"
            elif dias == 0:
                emoji = "🔔"; aviso = "Vence HOJE"
            elif dias <= 3:
                emoji = "🟠"; aviso = f"Vence em {dias} dia(s)"
            else:
                emoji = "🟡"; aviso = f"Vence em {dias} dias"
 
            titulo   = f"{emoji} {desp.get_classificacao_display()} — {desp.descricao}"
            mensagem = (
                f"{aviso} · Vencimento: "
                f"{desp.data_vencimento.strftime('%d/%m/%Y')} · R$ {desp.valor}"
            )
            link = f"/financeiro/despesas-gerais/?focus={desp.id}"
 
            for user in staff_users:
                # Evitar duplicata no mesmo dia para o mesmo lançamento
                ja_enviou = NotificacaoPush.objects.filter(
                    usuario_alvo=user,
                    titulo=titulo,
                    criado_em__date=hoje,
                ).exists()
                if ja_enviou:
                    continue
 
                NotificacaoPush.objects.create(
                    usuario_alvo=user,
                    titulo=titulo,
                    mensagem=mensagem,
                    link=link,
                )
                criadas += 1
 
        self.stdout.write(
            self.style.SUCCESS(
                f"[{hoje}] Lembretes criados: {criadas} notificação(ões)."
            )
        )