# despesas/utils.py
from dataclasses import dataclass

# Mês em PT-BR, índice 1..12 (posição 0 vazia p/ facilitar indexação)
MESES_PT = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]

def mes_label_pt(ano: int, mes: int) -> str:
    """
    Retorna rótulo 'MÊS / ANO' em PT-BR.
    Se o mês estiver fora de 1..12, retorna apenas 'ANO'.
    """
    if 1 <= int(mes) <= 12:
        return f"{MESES_PT[int(mes)]} / {int(ano)}"
    return str(int(ano))

@dataclass(slots=True)
class MesRef:
    ano: int
    mes: int


