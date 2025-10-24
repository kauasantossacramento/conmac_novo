# despesas/services/ui_helpers.py
MESES_PT = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
]

def mes_label_pt(ano: int, mes: int) -> str:
    if 1 <= mes <= 12:
        return f"{MESES_PT[mes]} / {ano}"
    return f"{ano}"
