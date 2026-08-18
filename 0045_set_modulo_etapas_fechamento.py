# despesas/migrations/0045_set_modulo_etapas_fechamento.py
# ─────────────────────────────────────────────────────────────
# Popula o campo `modulo` nas etapas de FECHAMENTO já existentes
# e garante que as flags de pré-requisito estejam corretas.
#
# Identifica por nome (case-insensitive) pois os IDs podem variar.
# Idempotente: pode rodar múltiplas vezes sem efeito colateral.
# ─────────────────────────────────────────────────────────────
from django.db import migrations


def set_modulo_etapas(apps, schema_editor):
    Etapa = apps.get_model("despesas", "Etapa")

    # ── CONTÁBIL ──────────────────────────────────────────────
    contabil_qs = Etapa.objects.filter(
        nivel="FECHAMENTO",
        nome__icontains="cont",   # "Contábil", "Contabil", "CONTABIL", etc.
    )
    contabil_qs.update(
        modulo="CONTABIL",
        obrigatoria_para_fila_siga=True,
        obrigatoria_para_fila_siope=True,
        obrigatoria_para_fila_siops=True,
        obrigatoria_para_fila_siconf=True,
        obrigatoria_para_fila_etcm=False,
    )
    print(f"  Contábil: {contabil_qs.count()} etapa(s) atualizadas")

    # ── FINANCEIRO ────────────────────────────────────────────
    financeiro_qs = Etapa.objects.filter(
        nivel="FECHAMENTO",
        nome__icontains="financ",  # "Financeiro", "FINANCEIRO", etc.
    )
    financeiro_qs.update(
        modulo="FINANCEIRO",
        obrigatoria_para_fila_etcm=True,
        obrigatoria_para_fila_siga=False,
        obrigatoria_para_fila_siope=False,
        obrigatoria_para_fila_siops=False,
        obrigatoria_para_fila_siconf=False,
    )
    print(f"  Financeiro: {financeiro_qs.count()} etapa(s) atualizadas")


def reverse_set_modulo(apps, schema_editor):
    Etapa = apps.get_model("despesas", "Etapa")
    Etapa.objects.filter(nivel="FECHAMENTO").update(modulo="")


class Migration(migrations.Migration):

    dependencies = [
        ("despesas", "0044_alter_configuracaonivel_options_and_more"),
    ]

    operations = [
        migrations.RunPython(set_modulo_etapas, reverse_set_modulo),
    ]
