# despesas/services/fechamento.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, List
from django.utils import timezone

@dataclass(frozen=True)
class MesRef:
    ano: int
    mes: int  # 1..12

    def as_tuple(self) -> Tuple[int, int]:
        return (self.ano, self.mes)

def _last_day_of_month(dt: datetime) -> datetime:
    # pega o último dia/23:59:59 do mês de dt (em dt.tzinfo)
    next_month = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = next_month - timedelta(seconds=1)
    return last_day.replace(hour=23, minute=59, second=59, microsecond=0)

def agora_local() -> datetime:
    # sempre usar timezone local do Django
    return timezone.localtime(timezone.now())

def mes_corrente() -> MesRef:
    now = agora_local()
    return MesRef(ano=now.year, mes=now.month)

def encerramento_mes_corrente_passou() -> bool:
    """
    Retorna True se já PASSOU o horário de fechamento do mês corrente
    (último dia às 23:59 local). Antes disso, o mês corrente está 'aberto'.
    """
    now = agora_local()
    fechamento = _last_day_of_month(now)
    return now > fechamento

def mes_referencia_por_criado_em(criado_em: datetime) -> MesRef:
    local = timezone.localtime(criado_em)
    return MesRef(ano=local.year, mes=local.month)

def despesa_editavel(criado_em: datetime) -> bool:
    """
    Regra solicitada:
    - Edição só é permitida enquanto o MÊS CORRENTE não tiver fechado.
    - Após o fechamento (31/30 23:59), itens 'anteriormente adicionados' não devem ser editados.
    """
    # Enquanto o mês corrente estiver aberto, permitimos edição APENAS de despesas
    # cujo mês de referência (criado_em) == mês corrente (itens criados neste mês).
    # Após o fechamento do mês corrente, nada anterior é editável.
    now = agora_local()
    mref_item = mes_referencia_por_criado_em(criado_em)
    mref_now = MesRef(ano=now.year, mes=now.month)

    if not encerramento_mes_corrente_passou():
        # mês corrente ainda aberto → só edita se foi criado no mês corrente
        return mref_item == mref_now
    else:
        # mês corrente já fechou → nada anterior é editável
        return False

def inserir_permitido_para_data_fato(_: datetime) -> bool:
    """
    Por sua instrução, não bloquearemos POST por data_fato (podendo ser mês anterior).
    Mantemos essa função para eventual regra futura.
    """
    return True

def meses_para_admin_order(meses_distintos: List[MesRef]) -> List[MesRef]:
    """
    Ordena com o mês CORRENTE primeiro, depois os demais do mais recente para o mais antigo.
    """
    mc = mes_corrente()
    # Cria uma chave de ordenação: mês corrente = (0), outros = (1, ordenação decrescente por (ano,mes))
    def sort_key(m: MesRef):
        is_current = (m.mes == mc.mes and m.ano == mc.ano)
        # invertido para decrescente nos 'outros'
        return (0 if is_current else 1, -m.ano, -m.mes)

    return sorted(meses_distintos, key=sort_key)

def colaborador_pode_editar(user, despesa) -> bool:
    # dono + não aprovada + ainda no mês corrente aberto e criada no mês corrente
    if user != despesa.usuario:
        return False
    if despesa.status == despesa.Status.APROVADA:
        return False
    return despesa_editavel(despesa.criado_em)
