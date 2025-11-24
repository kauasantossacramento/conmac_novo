from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils.timezone import now
from .forms import DespesaForm, LoteReembolsoForm
from datetime import date
from .services.fechamento import mes_corrente, meses_para_admin_order
from django.db.models.functions import TruncMonth
from .services.fechamento import MesRef, mes_corrente, meses_para_admin_order
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa, LoteReembolso, ChecklistItem
from .forms import DespesaForm, LoteReembolsoForm, ChecklistForm
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.contrib.auth import logout  # já deve ter: login_required, messages, etc.
from calendar import month_name
from django.utils.timezone import now
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from .services.fechamento import MesRef, mes_corrente
from django.http import JsonResponse, HttpResponseForbidden
# despesas/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseBadRequest, HttpResponse
from django.utils.timezone import now
from urllib.parse import urlencode
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa
from .forms import CentroForm, AssociaAnalistaForm, AdminReembolsoForm


from urllib.parse import urlencode


from .services.ui_helpers import mes_label_pt
from .services.fechamento import MesRef, colaborador_pode_editar
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils.timezone import now
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required


from decimal import Decimal
from django.contrib.auth import get_user_model
User = get_user_model()


# despesas/views.py
from django.db.models import Sum, Q
from .utils import mes_label_pt, MesRef

from decimal import Decimal
from django.contrib.auth.decorators import login_required

from django.shortcuts import render, get_object_or_404, redirect
from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto, LoteReembolso
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils.timezone import now
from django.shortcuts import render
from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .services.ui_helpers import mes_label_pt
from .services.fechamento import MesRef
from decimal import Decimal
from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce


def _rotulo_filtro(ano: int, mes: int) -> str:
    if ano == 0 and mes == 0:
        return "TODOS"
    if ano == 0:
        return f"{mes_label_pt(2000, mes).split(' / ')[0]} / TODOS OS ANOS"  # só nome do mês
    if mes == 0:
        return f"TODOS / {ano}"
    return mes_label_pt(ano, mes)

'''
@login_required
def viagens_lista(request):
    user = request.user

    # ---------- filtro (default = mês atual na 1ª abertura) ----------
    hoje = now()
    raw_ano = request.GET.get("ano")
    raw_mes = request.GET.get("mes")

    if raw_ano is None and raw_mes is None:
        # Primeira abertura: mês/ano correntes
        sel_ano, sel_mes = hoje.year, hoje.month
    else:
        # Usuário enviou algo (aceita 0 = TODOS)
        try:
            sel_ano = int(raw_ano) if raw_ano not in (None, "") else 0
        except ValueError:
            sel_ano = 0
        try:
            sel_mes = int(raw_mes) if raw_mes not in (None, "") else 0
        except ValueError:
            sel_mes = 0

    # base do usuário
    base_user = Despesa.objects.filter(usuario=user)

    # meses/anos disponíveis (p/ combos)
    meses_qs = (
        base_user.annotate(m=TruncMonth("data_fato"))
        .values_list("m", flat=True).distinct().order_by("-m")
    )
    anos_disponiveis = sorted({d.year for d in meses_qs}, reverse=True)
    meses_numeros = [(i, f"{i:02d}") for i in range(1, 13)]
    # inclui o "TODOS" (0)
    meses_numeros.insert(0, (0, "TODOS"))

    if anos_disponiveis and sel_ano not in (*anos_disponiveis, 0):
        # se o ano selecionado não existe, cai no ano atual (se existir) ou 0
        sel_ano = hoje.year if hoje.year in anos_disponiveis else 0
    if not (0 <= sel_mes <= 12):
        sel_mes = 0

    # ---------- escopo filtrado ----------
    escopo = base_user
    if sel_ano:
        escopo = escopo.filter(data_fato__year=sel_ano)
    if sel_mes:
        escopo = escopo.filter(data_fato__month=sel_mes)

    # rótulo do cabeçalho
    mes_label_txt = _rotulo_filtro(sel_ano, sel_mes)

    # centros atribuídos
    assoc_ids = (AssociacaoCentroCusto.objects
                 .filter(usuario=user, ativo=True)
                 .values_list("centro_id", flat=True))
    centros = CentroDeCusto.objects.filter(id__in=assoc_ids, ativo=True).order_by("nome")

    # KPIs no escopo
    total_mes = escopo.aggregate(total_val=Sum("valor")).get("total_val") or Decimal("0")
    total_reembolsadas = escopo.filter(status=Despesa.Status.APROVADA)\
                               .aggregate(total_aprov=Sum("valor")).get("total_aprov") or Decimal("0")
    total_pendentes = total_mes - total_reembolsadas

    # Itens por centro (escopo atual)
    centros_data = []
    for c in centros:
        itens = list(
            escopo.filter(centro=c)
            .order_by("-data_fato", "-criado_em", "-id")[:200]
        )
        centros_data.append({"centro": c, "itens": itens})

    # “Anteriores”: só faz sentido quando é UM mês específico
    meses_anteriores = []
    if sel_ano and sel_mes:
        meses_ant_qs = (
            base_user.exclude(data_fato__year=sel_ano, data_fato__month=sel_mes)
            .annotate(m=TruncMonth("data_fato"))
            .values_list("m", flat=True)
            .distinct()
            .order_by("-m")
        )
        for d in meses_ant_qs:
            mref = MesRef(ano=d.year, mes=d.month)
            label = mes_label_pt(mref.ano, mref.mes)
            centros_mes_ids = (
                base_user.filter(data_fato__year=mref.ano, data_fato__month=mref.mes)
                .values_list("centro_id", flat=True)
                .distinct()
            )
            centros_list = list(CentroDeCusto.objects.filter(id__in=centros_mes_ids).order_by("nome"))
            meses_anteriores.append({"mref": mref, "label": label, "centros": centros_list})

    return render(request, "viagens/lista.html", {
        "centros_data": centros_data,
        "mes_corrente_label": mes_label_txt,
        "total_mes": total_mes,
        "total_reembolsadas": total_reembolsadas,
        "total_pendentes": total_pendentes,
        "meses_anteriores": meses_anteriores,
        # combos
        "meses_numeros": meses_numeros,
        "anos_disponiveis": [0, *anos_disponiveis],  # inclui TODOS
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,
        "tem_aprovadas": base_user.filter(status=Despesa.Status.APROVADA).exists(),
    })
'''

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models.functions import TruncMonth
from decimal import Decimal
from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .utils import mes_label_pt, MesRef  # ajuste conforme seu projeto

from decimal import Decimal
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils.timezone import now, timedelta
from django.contrib.auth.decorators import login_required

# suponho que as seguintes entidades/auxiliares já estejam importadas no módulo:
# from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
# from .helpers import MesRef, mes_label_pt

@login_required
def viagens_lista(request):
    user = request.user
    assoc_ids = AssociacaoCentroCusto.objects.filter(usuario=user, ativo=True).values_list("centro_id", flat=True)

    raw_centro = request.GET.get("centro")
    centro_sel = None
    if raw_centro not in (None, "", "0"):
        try:
            cid = int(raw_centro)
        except (TypeError, ValueError):
            cid = None
        if cid:
            centro_sel = CentroDeCusto.objects.filter(id__in=assoc_ids, id=cid, ativo=True).first()

    hoje = now()
    raw_ano = request.GET.get("ano")
    raw_mes = request.GET.get("mes")

    if raw_ano is None and raw_mes is None:
        sel_ano, sel_mes = hoje.year, hoje.month
    else:
        try:
            sel_ano = int(raw_ano) if raw_ano not in (None, "") else 0
        except ValueError:
            sel_ano = 0
        try:
            sel_mes = int(raw_mes) if raw_mes not in (None, "") else 0
        except ValueError:
            sel_mes = 0

    base_user = Despesa.objects.filter(usuario=user)

    meses_qs = base_user.annotate(m=TruncMonth("data_fato")).values_list("m", flat=True).distinct().order_by("-m")
    anos_disponiveis = sorted({d.year for d in meses_qs}, reverse=True)
    meses_numeros = [(0, "TODOS")] + [(i, f"{i:02d}") for i in range(1, 13)]

    if anos_disponiveis and sel_ano not in (*anos_disponiveis, 0):
        sel_ano = hoje.year if hoje.year in anos_disponiveis else 0
    if not (0 <= sel_mes <= 12):
        sel_mes = 0

    escopo = base_user
    if centro_sel:
        escopo = escopo.filter(centro=centro_sel)
    if sel_ano:
        escopo = escopo.filter(data_fato__year=sel_ano)
    if sel_mes:
        escopo = escopo.filter(data_fato__month=sel_mes)

    mes_corrente_label = mes_label_pt(sel_ano, sel_mes) if sel_ano and sel_mes else "Período selecionado"

    centros_vinculados = CentroDeCusto.objects.filter(id__in=assoc_ids, ativo=True).order_by("nome")
    centros = CentroDeCusto.objects.filter(id=centro_sel.id, ativo=True) if centro_sel else centros_vinculados

    total_reembolsadas = escopo.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_reprovado = escopo.filter(status=Despesa.Status.REPROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_mes1 = escopo.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_mes = total_mes1 - total_reprovado
    total_pendentes = total_mes - total_reembolsadas

    centros_data = []
    for c in centros:
        all_itens = escopo.filter(centro=c).order_by("-data_fato", "-criado_em", "-id")
        paginator = Paginator(all_itens, 6)
        page_number = request.GET.get(f"page_{c.id}", 1)
        page_obj = paginator.get_page(page_number)
        centros_data.append({
            "centro": c,
            "itens": page_obj.object_list,
            "page_obj": page_obj,
        })

    meses_anteriores = []
    if sel_ano and sel_mes:
        base_outros = base_user.filter(centro=centro_sel) if centro_sel else base_user
        meses_ant_qs = base_outros.exclude(data_fato__year=sel_ano, data_fato__month=sel_mes)\
                                  .annotate(m=TruncMonth("data_fato"))\
                                  .values_list("m", flat=True).distinct().order_by("-m")
        for d in meses_ant_qs:
            mref = MesRef(ano=d.year, mes=d.month)
            label = mes_label_pt(mref.ano, mref.mes)
            centros_mes_ids = base_outros.filter(data_fato__year=mref.ano, data_fato__month=mref.mes)\
                                         .values_list("centro_id", flat=True).distinct()
            centros_list = list(CentroDeCusto.objects.filter(id__in=centros_mes_ids).order_by("nome"))
            meses_anteriores.append({"mref": mref, "label": label, "centros": centros_list})

    # --------- ALERTA: despesas REPROVADAS recentes (últimos 7 dias) ---------
    limite = hoje - timedelta(days=7)
    reprovadas_recentes_qs = base_user.filter(
        status=Despesa.Status.REPROVADA,
        criado_em__gte=limite
    )
    tem_reprovadas_recentes = reprovadas_recentes_qs.exists()

    reprovadas_info = None
    if tem_reprovadas_recentes:
        reprovadas_info = {
            "quantidade": reprovadas_recentes_qs.count(),
            "valor_total": reprovadas_recentes_qs.aggregate(v=Sum("valor"))["v"] or Decimal("0"),
            "ultima_data": reprovadas_recentes_qs.order_by("-criado_em").first().criado_em,
        }

    # --------- ALERTA: despesas APROVADAS/PAGAS recentes (últimos 7 dias) ---------
    # incluir APROVADA e tentar detectar eventuais status de "pago" no enum (nomes comuns)
    paid_status_candidates = []
    for name in ("PAGO", "PAGA", "LIQUIDADA", "QUITADA", "PAGO_PAGTO", "REEMBOLSADA"):
        st = getattr(Despesa.Status, name, None)
        if st is not None:
            paid_status_candidates.append(st)

    # garantir incluir APROVADA (evita duplicar)
    aprov_statuses = [Despesa.Status.APROVADA] + [s for s in paid_status_candidates if s != Despesa.Status.APROVADA]

    aprovadas_recentes_qs = base_user.filter(
        status__in=aprov_statuses,
        criado_em__gte=limite
    )
    tem_aprovadas_recentes = aprovadas_recentes_qs.exists()

    aprovadas_info = None
    if tem_aprovadas_recentes:
        aprovadas_info = {
            "quantidade": aprovadas_recentes_qs.count(),
            "valor_total": aprovadas_recentes_qs.aggregate(v=Sum("valor"))["v"] or Decimal("0"),
            "ultima_data": aprovadas_recentes_qs.order_by("-criado_em").first().criado_em,
            "ids": list(aprovadas_recentes_qs.order_by("-criado_em").values_list("id", flat=True)[:25]),
        }

    return render(request, "viagens/lista.html", {
        "centros_data": centros_data,
        "centro_sel": centro_sel,
        "centros_vinculados": centros_vinculados,
        "mes_corrente_label": mes_corrente_label,
        "total_mes": total_mes,
        "total_reembolsadas": total_reembolsadas,
        "total_pendentes": total_pendentes,
        "meses_anteriores": meses_anteriores,
        "meses_numeros": meses_numeros,
        "anos_disponiveis": [0, *anos_disponiveis],
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,
        "tem_aprovadas": base_user.filter(status=Despesa.Status.APROVADA).exists(),

        # novos campos sobre reprovações recentes
        "tem_reprovadas_recentes": tem_reprovadas_recentes,
        "reprovadas_info": reprovadas_info,

        # novos campos sobre aprovações/pagamentos recentes
        "tem_aprovadas_recentes": tem_aprovadas_recentes,
        "aprovadas_info": aprovadas_info,
    })


# despesas/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.timezone import now

from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .utils import MesRef, mes_label_pt  # (ajuste o import se seu helper estiver noutro módulo)


@login_required
def despesa_modal(request, pk):
    obj = get_object_or_404(Despesa, pk=pk, usuario=request.user)

    lote_pag = (LoteReembolso.objects
                .filter(despesas=obj, comprovante_reembolso__isnull=False)
                .order_by("-criado_em")
                .first())

    # Regra pré-existente + limite de edições
    pode_editar_rule = colaborador_pode_editar(request.user, obj)
    pode_editar = pode_editar_rule and obj.edit_count < 2

    return render(request, "viagens/despesa_modal.html", {
        "obj": obj,
        "lote_pag": lote_pag,
        "pode_editar": pode_editar,
        "max_edicoes": 2,
    })




# despesas/views.py
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import Despesa, AssociacaoCentroCusto, CentroDeCusto
from .forms import AdminReembolsoForm


from .forms import AdminReembolsoForm, AdminLoteReembolsoForm


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.contrib import messages

from .models import Despesa
from .forms import AdminReembolsoForm, AdminLoteReembolsoForm

from urllib.parse import urlencode
from django.urls import reverse
from urllib.parse import urlencode

from urllib.parse import urlparse, parse_qs
from django.http import QueryDict
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, render
from django.contrib.admin.views.decorators import staff_member_required

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from urllib.parse import urlparse, parse_qs

from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .forms import AdminReembolsoForm, AdminLoteReembolsoForm
from django.contrib.auth.models import User



from urllib.parse import urlparse, parse_qs
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Despesa
from .forms import AdminReembolsoForm, AdminLoteReembolsoForm


'''
def _to_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _first(qs_dict, key, default=None):
    vals = qs_dict.get(key, [])
    return vals[0] if vals else default

STATUS_MAP = {
    "PENDENTE": Despesa.Status.PENDENTE,
    "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
    "APROVADA": Despesa.Status.APROVADA,
    "REPROVADA": Despesa.Status.REPROVADA,
}

@staff_member_required
def despesa_modal_admin(request, pk):
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )

    # --- Filtros preservados ---
    centro_id = _to_int(request.GET.get("centro") or request.POST.get("centro"))
    user_id = _to_int(request.GET.get("user") or request.POST.get("user"))
    ano = _to_int(request.GET.get("ano") or request.POST.get("ano"))
    mes = _to_int(request.GET.get("mes") or request.POST.get("mes"))
    st_param = (request.GET.get("st") or request.POST.get("st") or "").upper().strip()

    if any(v is None for v in (centro_id, user_id, ano, mes)) or not st_param:
        ref = request.META.get("HTTP_REFERER") or ""
        try:
            ref_qs = parse_qs(urlparse(ref).query)
        except Exception:
            ref_qs = {}
        if centro_id is None: centro_id = _to_int(_first(ref_qs, "centro"))
        if user_id is None: user_id = _to_int(_first(ref_qs, "user"))
        if ano is None: ano = _to_int(_first(ref_qs, "ano"))
        if mes is None: mes = _to_int(_first(ref_qs, "mes"))
        if not st_param: st_param = (_first(ref_qs, "st", "") or "").upper().strip()

    st_val = STATUS_MAP.get(st_param) if st_param else None
    modo_lote = (request.POST.get("modo") == "lote") or \
                (request.GET.get("lote") == "1") or (request.POST.get("lote") == "1")

    # --- Queryset base com filtros ---
    qs_base = Despesa.objects.select_related("centro", "usuario")
    if centro_id: qs_base = qs_base.filter(centro_id=centro_id)
    if user_id: qs_base = qs_base.filter(usuario_id=user_id)
    if ano: qs_base = qs_base.filter(data_fato__year=ano)
    if mes: qs_base = qs_base.filter(data_fato__month=mes)
    if st_val: qs_base = qs_base.filter(status=st_val)
    qs_base = qs_base.order_by("-data_fato", "-criado_em", "-id")

    # --- Navegação pré-save ---
    id_list = list(qs_base.values_list("id", flat=True))
    def _prev_next_ids(current_id):
        if current_id in id_list:
            idx = id_list.index(current_id)
            return (id_list[idx - 1] if idx > 0 else None,
                    id_list[idx + 1] if idx < len(id_list) - 1 else None)
        return None, None

    prev_id_before, next_id_before = _prev_next_ids(d.id)

    # --- Preservar filtros em hidden fields ---
    preserved = {}
    if centro_id: preserved["centro"] = str(centro_id)
    if user_id: preserved["user"] = str(user_id)
    if ano: preserved["ano"] = str(ano)
    if mes: preserved["mes"] = str(mes)
    if st_param: preserved["st"] = st_param
    if modo_lote: preserved["lote"] = "1"

    def _url_for(target_id):
        preserved_qs = QueryDict(mutable=True)
        preserved_qs.update(preserved)
        qs_str = preserved_qs.urlencode()
        return f"{reverse('despesa_modal_admin', args=[target_id])}?{qs_str}" if target_id else None

    form_action = reverse('despesa_modal_admin', args=[d.pk])
    user_obj = User.objects.filter(pk=user_id).first() if user_id else None

    if modo_lote:
        form_lote = AdminLoteReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            centro=d.centro, ano=d.data_fato.year, mes=d.data_fato.month,
            user=user_obj,
        )
        form_individual = AdminReembolsoForm(instance=d)
        if request.method == "POST":
            if form_lote.is_valid():
                count = form_lote.aplicar()
                d.refresh_from_db()
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                form_lote = AdminLoteReembolsoForm(
                    centro=d.centro, ano=d.data_fato.year, mes=d.data_fato.month, user=user_obj
                )
            else:
                messages.error(request, "Corrija os erros e tente novamente.")
    else:
        form_individual = AdminReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            instance=d,
        )
        form_lote = AdminLoteReembolsoForm(
            centro=d.centro, ano=d.data_fato.year, mes=d.data_fato.month, user=user_obj
        )

        if request.method == "POST":
            go = request.POST.get("__go")  # 'next' | 'prev' | None
            old_status = d.status
            should_save = (
                d.status == Despesa.Status.PENDENTE
                and form_individual.is_valid()
                and form_individual.cleaned_data.get('marcar_analisada', False)
            )

            if form_individual.is_valid() or not should_save:
                if go in ("next", "prev"):
                    saved_message = ""
                    if should_save:
                        d = form_individual.save()
                        d.refresh_from_db()
                        saved_message = "Despesa atualizada. "
                        if st_val and old_status == st_val and d.status != st_val:
                            saved_message += "Fora do filtro. "
                    if saved_message:
                        messages.success(request, saved_message + "Navegando…")
                    else:
                        messages.success(request, "Navegando…")

                    target_id = next_id_before if go == "next" else prev_id_before
                    if target_id:
                        target = get_object_or_404(
                            Despesa.objects.select_related("centro", "usuario"),
                            pk=target_id
                        )
                        t_prev_id, t_next_id = _prev_next_ids(target.id)
                        return render(request, "centros/_modal_despesa_admin.html", {
                            "d": target,
                            "form": AdminReembolsoForm(instance=target),
                            "form_lote": form_lote,
                            "modo_lote": False,
                            "prev_url": _url_for(t_prev_id),
                            "next_url": _url_for(t_next_id),
                            "fora_do_filtro": False,
                            "form_action": reverse('despesa_modal_admin', args=[target.id]),
                            "preserved": preserved,
                        })
                    messages.info(request, "Não há mais itens na direção escolhida.")
                else:
                    if should_save:
                        d = form_individual.save()
                        d.refresh_from_db()
                        saiu_do_filtro = st_val and old_status == st_val and d.status != st_val
                        if saiu_do_filtro:
                            target_id = next_id_before or prev_id_before
                            if target_id:
                                target = get_object_or_404(
                                    Despesa.objects.select_related("centro", "usuario"),
                                    pk=target_id
                                )
                                t_prev_id, t_next_id = _prev_next_ids(target.id)
                                messages.success(request, "Despesa atualizada e fora do filtro. Avançando…")
                                return render(request, "centros/_modal_despesa_admin.html", {
                                    "d": target,
                                    "form": AdminReembolsoForm(instance=target),
                                    "form_lote": form_lote,
                                    "modo_lote": False,
                                    "prev_url": _url_for(t_prev_id),
                                    "next_url": _url_for(t_next_id),
                                    "fora_do_filtro": False,
                                    "form_action": reverse('despesa_modal_admin', args=[target.id]),
                                    "preserved": preserved,
                                })
                            messages.info(request, "Despesa atualizada. Não há mais itens no filtro atual.")
                        else:
                            messages.success(request, "Despesa atualizada com sucesso.")
                    else:
                        messages.info(request, "Nenhuma alteração necessária.")
            else:
                messages.error(request, "Corrija os erros e tente novamente.")

    return render(request, "centros/_modal_despesa_admin.html", {
        "d": d,
        "form": form_individual,
        "form_lote": form_lote,
        "modo_lote": modo_lote,
        "prev_url": _url_for(prev_id_before),
        "next_url": _url_for(next_id_before),
        "fora_do_filtro": (d.id not in id_list),
        "form_action": form_action,
        "preserved": preserved,
    })
'''

'''
@staff_member_required
def despesa_modal_admin(request, pk):
    """
    Modal do admin para editar 1 despesa ou aplicar alterações em lote
    (no mesmo centro/mês da despesa aberta). Sempre retorna o partial do modal.
    """
    # carrega já com os FKs usados no template
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )
    centro = d.centro
    ano = d.data_fato.year
    mes = d.data_fato.month

    # alterna modo
    modo_lote = (request.POST.get("modo") == "lote") or (request.GET.get("lote") == "1")

    if modo_lote:
        # ---------- LOTE ----------
        form_lote = AdminLoteReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            centro=centro,
            ano=ano,
            mes=mes,
        )
        # mostra o individual apenas para consulta quando em lote
        form_individual = AdminReembolsoForm(instance=d)

        if request.method == "POST":
            if form_lote.is_valid():
                count = form_lote.aplicar()          # aplica status / comprovante / pago_em nas selecionadas
                d.refresh_from_db()                   # atualiza a atual caso ela esteja entre as alteradas
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                # recria o form de lote “limpo” mas mantendo o modo_lote ativo
                form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano, mes=mes)
            else:
                messages.error(request, "Corrija os erros e tente novamente.")
    else:
        # ---------- INDIVIDUAL ----------
        form_individual = AdminReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            instance=d,
        )
        form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano, mes=mes)

        if request.method == "POST":
            if form_individual.is_valid():
                d = form_individual.save()           # salva status, comprovante_pagamento e pago_em
                d.refresh_from_db()
                messages.success(request, "Despesa atualizada com sucesso.")
            else:
                messages.error(request, "Corrija os erros e tente novamente.")

    # Render SEMPRE o partial do modal (sem redirect)
    return render(request, "centros/_modal_despesa_admin.html", {
        "d": d,                         # inclui d.pago_em (pode ser None)
        "form": form_individual,
        "form_lote": form_lote,
        "modo_lote": modo_lote,
        "has_prev": bool(prev_url),
        "has_next": bool(next_url),
    })
'''



# views.py
from urllib.parse import urlparse, parse_qs
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.http import QueryDict
from django.utils import timezone

from .models import Despesa, AssociacaoCentroCusto, CentroDeCusto
from .forms import AdminReembolsoForm, AdminLoteReembolsoForm
from django.contrib.auth.models import User

from django.views.decorators.http import require_http_methods
from django.http import QueryDict, HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.utils import timezone

def _to_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _first(qs_dict, key, default=None):
    vals = qs_dict.get(key, [])
    return vals[0] if vals else default

STATUS_MAP = {
    "PENDENTE": Despesa.Status.PENDENTE,
    "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
    "APROVADA": Despesa.Status.APROVADA,
    "REPROVADA": Despesa.Status.REPROVADA,
}

# views.py

from urllib.parse import urlparse, parse_qs
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

@staff_member_required
@require_POST
def despesa_modal_nav(request, pk):
    """
    Navega PRÓX/ANT dentro do mesmo filtro do modal de despesa.
    NUNCA retorna página inteira: sempre o partial do modal.
    """
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )

    # --- filtros (da URL e/ou dos hiddens do form) ---
    def _to_int(val, default=None):
        try:
            return int(val) if val not in (None, "") else default
        except (TypeError, ValueError):
            return default

    centro_id = _to_int(request.GET.get("centro") or request.POST.get("centro"))
    user_id   = _to_int(request.GET.get("user")   or request.POST.get("user"))
    ano       = _to_int(request.GET.get("ano")    or request.POST.get("ano"))
    mes       = _to_int(request.GET.get("mes")    or request.POST.get("mes"))
    st_param  = ((request.GET.get("st") or request.POST.get("st") or "").upper().strip())

    st_val = STATUS_MAP.get(st_param) if st_param else None

    # --- queryset filtrado (mesma ordem da lista) ---
    qs = Despesa.objects.select_related("centro", "usuario")
    if centro_id: qs = qs.filter(centro_id=centro_id)
    if user_id:   qs = qs.filter(usuario_id=user_id)
    if ano:       qs = qs.filter(data_fato__year=ano)
    if mes:       qs = qs.filter(data_fato__month=mes)
    if st_val:    qs = qs.filter(status=st_val)
    qs = qs.order_by("-data_fato", "-criado_em", "-id")

    ids = list(qs.values_list("id", flat=True))

    def _prev_next_ids(curr):
        if curr in ids:
            i = ids.index(curr)
            prev_id = ids[i-1] if i > 0 else None
            next_id = ids[i+1] if i < len(ids)-1 else None
            return prev_id, next_id
        return None, None

    prev_id, next_id = _prev_next_ids(d.id)

    # --- decide alvo conforme botão ---
    nav = (request.POST.get("nav") or "").lower()
    target_id = d.id
    if nav == "next" and next_id:
        target_id = next_id
    elif nav == "prev" and prev_id:
        target_id = prev_id

    target = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=target_id
    )
    t_prev, t_next = _prev_next_ids(target.id)

    # --- reconstruir qs (sempre inclui partial=1) ---
    preserved = QueryDict(mutable=True)
    if centro_id: preserved["centro"] = str(centro_id)
    if user_id:   preserved["user"]   = str(user_id)
    if ano:       preserved["ano"]    = str(ano)
    if mes:       preserved["mes"]    = str(mes)
    if st_param:  preserved["st"]     = st_param
    preserved["partial"] = "1"
    qs_str = preserved.urlencode()

    nav_action  = f"{reverse('despesa_modal_nav',  args=[target.id])}?{qs_str}"
    form_action = f"{reverse('despesa_modal_admin', args=[target.id])}?{qs_str}"

    resp = render(request, "centros/_modal_despesa_admin.html", {
        "d": target,
        "form": AdminReembolsoForm(instance=target),
        "form_lote": AdminLoteReembolsoForm(centro=target.centro, ano=target.data_fato.year, mes=target.data_fato.month),
        "modo_lote": False,
        "has_prev": bool(t_prev),
        "has_next": bool(t_next),
        "nav_action": nav_action,
        "form_action": form_action,
        "preserved": dict(preserved.lists()),
        "fora_do_filtro": (target.id not in ids),
    })
    resp["X-Modal-Partial"] = "despesa"
    return resp


'''
# views.py
from urllib.parse import urlparse, parse_qs
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import QueryDict, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone

# Helpers (use os seus se já existirem)
def _to_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _first(qs_dict, key, default=None):
    vals = qs_dict.get(key, [])
    return vals[0] if vals else default

STATUS_MAP = {
    "PENDENTE": Despesa.Status.PENDENTE,
    "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
    "APROVADA": Despesa.Status.APROVADA,
    "REPROVADA": Despesa.Status.REPROVADA,
}

@staff_member_required
def despesa_modal_admin(request, pk):
    """
    Modal do admin para editar 1 despesa ou aplicar alterações em lote.

    - Calcula prev/next com base nos filtros correntes (?centro=&user=&ano=&mes=&st=)
      para habilitar/ocultar os botões no cabeçalho do modal.
    - Define nav_action (POST) que aponta para despesa_modal_nav (a view de navegação).
    - Define form_action para que os form(s) do modal postem de volta a este modal
      preservando a querystring do filtro (evita “cair” na página index).
    - Se a requisição NÃO for AJAX e vier por GET/POST direto, redireciona para a
      própria URL do modal com a QS correta; se for AJAX, sempre renderiza o partial.
    """
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )
    centro = d.centro
    ano_d  = d.data_fato.year
    mes_d  = d.data_fato.month

    # ---------------- Filtros correntes (URL e, se faltar, do referer) ----------------
    centro_id = _to_int(request.GET.get("centro"))
    user_id   = _to_int(request.GET.get("user"))
    ano       = _to_int(request.GET.get("ano"))
    mes       = _to_int(request.GET.get("mes"))
    st_param  = (request.GET.get("st") or "").upper().strip()

    if any(v is None for v in (centro_id, user_id, ano, mes)) or not st_param:
        ref = request.META.get("HTTP_REFERER") or ""
        try:
            ref_qs = parse_qs(urlparse(ref).query)
        except Exception:
            ref_qs = {}
        if centro_id is None: centro_id = _to_int(_first(ref_qs, "centro"))
        if user_id   is None: user_id   = _to_int(_first(ref_qs, "user"))
        if ano       is None: ano       = _to_int(_first(ref_qs, "ano"))
        if mes       is None: mes       = _to_int(_first(ref_qs, "mes"))
        if not st_param:      st_param  = (_first(ref_qs, "st", "") or "").upper().strip()

    st_val = STATUS_MAP.get(st_param) if st_param else None

    # ---------------- Alterna modo (lote/individual) ----------------
    modo_lote = (request.POST.get("modo") == "lote") or (request.GET.get("lote") == "1")

    # ---------------- Queryset para prev/next (mesma regra e ordenação do index) ----------------
    qs_base = Despesa.objects.select_related("centro", "usuario")
    if centro_id: qs_base = qs_base.filter(centro_id=centro_id)
    if user_id:   qs_base = qs_base.filter(usuario_id=user_id)
    if ano:       qs_base = qs_base.filter(data_fato__year=ano)
    if mes:       qs_base = qs_base.filter(data_fato__month=mes)
    if st_val:    qs_base = qs_base.filter(status=st_val)
    qs_base = qs_base.order_by("-data_fato", "-criado_em", "-id")

    id_list = list(qs_base.values_list("id", flat=True))

    def _prev_next_ids(current_id):
        if current_id in id_list:
            i = id_list.index(current_id)
            prev_id = id_list[i-1] if i > 0 else None
            next_id = id_list[i+1] if i < len(id_list)-1 else None
            return prev_id, next_id
        return None, None

    prev_id, next_id = _prev_next_ids(d.id)
    has_prev = bool(prev_id)
    has_next = bool(next_id)

    # ---------------- Preservar filtros: nav_action + form_action ----------------
    preserved = QueryDict(mutable=True)
    if centro_id: preserved["centro"] = str(centro_id)
    if user_id:   preserved["user"]   = str(user_id)
    if ano:       preserved["ano"]    = str(ano)
    if mes:       preserved["mes"]    = str(mes)
    if st_param:  preserved["st"]     = st_param
    if modo_lote: preserved["lote"]   = "1"
    qs_str = preserved.urlencode()

    nav_action  = f"{reverse('despesa_modal_nav',  args=[d.pk])}?{qs_str}"
    form_action = f"{reverse('despesa_modal_admin', args=[d.pk])}?{qs_str}"

    # ---------------- Forms (sua lógica original — inalterada) ----------------
    if modo_lote:
        form_lote = AdminLoteReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            centro=centro, ano=ano_d, mes=mes_d,
        )
        form_individual = AdminReembolsoForm(instance=d)

        if request.method == "POST":
            if form_lote.is_valid():
                count = form_lote.aplicar()
                d.refresh_from_db()
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)
            else:
                messages.error(request, "Corrija os erros e tente novamente.")
    else:
        form_individual = AdminReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            instance=d,
        )
        form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)

        if request.method == "POST":
            if form_individual.is_valid():
                d = form_individual.save()
                d.refresh_from_db()
                messages.success(request, "Despesa atualizada com sucesso.")
            else:
                messages.error(request, "Corrija os erros e tente novamente.")

    # ---------------- Somente partial no XHR; se não for XHR, redireciona para o próprio modal ----------------
    is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not is_xhr and request.method in ("POST", "GET"):
        # garante que, se alguém acessou direto, não “abre” a index no modal por engano
        return redirect(f"{reverse('despesa_modal_admin', args=[d.pk])}?{qs_str}")

    return render(request, "centros/_modal_despesa_admin.html", {
        "d": d,
        "form": form_individual,
        "form_lote": form_lote,
        "modo_lote": modo_lote,

        # navegação no cabeçalho do modal
        "has_prev": has_prev,
        "has_next": has_next,
        "nav_action": nav_action,

        # ação correta dos formulários do modal (use isto no template)
        "form_action": form_action,
    })
'''


'''

ESSE AQUI ERA O ANTERIOR

from urllib.parse import urlparse, parse_qs
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

def _to_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _first(qs_dict, key, default=None):
    vals = qs_dict.get(key, [])
    return vals[0] if vals else default

STATUS_MAP = {
    "PENDENTE": Despesa.Status.PENDENTE,
    "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
    "APROVADA": Despesa.Status.APROVADA,
    "REPROVADA": Despesa.Status.REPROVADA,
}

@staff_member_required
def despesa_modal_admin(request, pk):
    """
    Modal do admin para editar 1 despesa ou aplicar alterações em lote.

    - Calcula prev/next com base nos filtros correntes (?centro=&user=&ano=&mes=&st=)
    - O campo 'marcar_analisada' só tem efeito ao salvar no formulário principal (não na navegação)
    - Se o usuário clicar nos botões do rodapé (salvar e ir para anterior/próxima),
      a view salva e navega dentro do MESMO queryset do filtro original.
    - Garante partial em XHR/partial=1 e redireciona p/ si mesmo com QS quando não for XHR
    """
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )
    centro = d.centro
    ano_d  = d.data_fato.year
    mes_d  = d.data_fato.month

    # ---------------- Filtros atuais (URL; se faltar, herdamos do Referer) ----------------
    centro_id = _to_int(request.GET.get("centro"))
    user_id   = _to_int(request.GET.get("user"))
    ano       = _to_int(request.GET.get("ano"))
    mes       = _to_int(request.GET.get("mes"))
    st_param  = (request.GET.get("st") or "").upper().strip()

    if any(v is None for v in (centro_id, user_id, ano, mes)) or not st_param:
        ref = request.META.get("HTTP_REFERER") or ""
        try:
            ref_qs = parse_qs(urlparse(ref).query)
        except Exception:
            ref_qs = {}
        if centro_id is None: centro_id = _to_int(_first(ref_qs, "centro"))
        if user_id   is None: user_id   = _to_int(_first(ref_qs, "user"))
        if ano       is None: ano       = _to_int(_first(ref_qs, "ano"))
        if mes       is None: mes       = _to_int(_first(ref_qs, "mes"))
        if not st_param:      st_param  = (_first(ref_qs, "st", "") or "").upper().strip()

    st_val = STATUS_MAP.get(st_param) if st_param else None

    # ---------------- Alterna modo (lote/individual) ----------------
    modo_lote = (request.POST.get("modo") == "lote") or (request.GET.get("lote") == "1")

    # ---------------- Queryset da navegação (mesma ordenação da lista) ----------------
    qs_base = Despesa.objects.select_related("centro", "usuario")
    if centro_id: qs_base = qs_base.filter(centro_id=centro_id)
    if user_id:   qs_base = qs_base.filter(usuario_id=user_id)
    if ano:       qs_base = qs_base.filter(data_fato__year=ano)
    if mes:       qs_base = qs_base.filter(data_fato__month=mes)
    if st_val:    qs_base = qs_base.filter(status=st_val)
    qs_base = qs_base.order_by("-data_fato", "-criado_em", "-id")

    id_list = list(qs_base.values_list("id", flat=True))

    def _prev_next_ids(current_id):
        if current_id in id_list:
            i = id_list.index(current_id)
            prev_id = id_list[i-1] if i > 0 else None
            next_id = id_list[i+1] if i < len(id_list)-1 else None
            return prev_id, next_id
        return None, None

    # prev/next para a DESPESA ATUAL (antes de salvar — isso é importante)
    prev_id, next_id = _prev_next_ids(d.id)

    # ---------------- Preservar filtros (QS para actions) ----------------
    preserved = QueryDict(mutable=True)
    if centro_id: preserved["centro"] = str(centro_id)
    if user_id:   preserved["user"]   = str(user_id)
    if ano:       preserved["ano"]    = str(ano)
    if mes:       preserved["mes"]    = str(mes)
    if st_param:  preserved["st"]     = st_param
    if modo_lote: preserved["lote"]   = "1"
    preserved["partial"] = "1"  # ajuda a blindar respostas de página inteira

    qs_str = preserved.urlencode()
    nav_action  = f"{reverse('despesa_modal_nav',  args=[d.pk])}?{qs_str}"  # segue existindo p/ quem quiser só navegar
    form_action = f"{reverse('despesa_modal_admin', args=[d.pk])}?{qs_str}"

    # Flags para o template (cabeçalho e rodapé)
    has_prev = bool(prev_id)
    has_next = bool(next_id)

    # ---------------- Forms ----------------
    if modo_lote:
        form_lote = AdminLoteReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            centro=centro, ano=ano_d, mes=mes_d,
        )
        form_individual = AdminReembolsoForm(instance=d)

        if request.method == "POST":
            if form_lote.is_valid():
                count = form_lote.aplicar()
                d.refresh_from_db()
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)
            else:
                messages.error(request, "Corrija os erros e tente novamente.")
    else:
        form_individual = AdminReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            instance=d,
        )
        form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)

        if request.method == "POST":
            # capturamos intenção de navegação do rodapé do form PRINCIPAL
            go = (request.POST.get("__go") or "").lower()  # 'prev' | 'next' | ''
            if form_individual.is_valid():
                # salva (inclui lógica do marcar_analisada dentro do form)
                d = form_individual.save()
                d.refresh_from_db()

                # Se o usuário pediu para ir para anterior/próxima, usamos prev_id/next_id
                # calculados ANTES de salvar (ou seja, dentro do filtro original).
                target_id = None
                if go == "prev" and has_prev:
                    target_id = prev_id
                elif go == "next" and has_next:
                    target_id = next_id

                if target_id:
                    # Troca o objeto atual para o alvo e recalcula vizinhos (com a mesma id_list)
                    d = get_object_or_404(
                        Despesa.objects.select_related("centro", "usuario"),
                        pk=target_id
                    )
                    t_prev_id, t_next_id = _prev_next_ids(d.id)
                    has_prev, has_next = bool(t_prev_id), bool(t_next_id)

                    # Atualiza actions para o novo alvo (mantendo a mesma QS)
                    nav_action  = f"{reverse('despesa_modal_nav',  args=[d.pk])}?{qs_str}"
                    form_action = f"{reverse('despesa_modal_admin', args=[d.pk])}?{qs_str}"

                    # Recria os forms “limpos” apontando para o alvo
                    form_individual = AdminReembolsoForm(instance=d)
                    form_lote       = AdminLoteReembolsoForm(centro=d.centro, ano=d.data_fato.year, mes=d.data_fato.month)

                    messages.success(request, "Despesa salva. Avançando no filtro.")
                else:
                    messages.success(request, "Despesa atualizada com sucesso.")
            else:
                messages.error(request, "Corrija os erros e tente novamente.")

    # ---------------- Somente partial em XHR/partial=1; senão, redireciona p/ si com QS ----------------
    is_partial = (
        request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        or request.GET.get("partial") == "1"
        or request.POST.get("partial") == "1"
    )
    if not is_partial and request.method in ("GET", "POST"):
        # Evita cair numa página inteira dentro do modal
        return redirect(f"{reverse('despesa_modal_admin', args=[d.pk])}?{qs_str}")

    resp = render(request, "centros/_modal_despesa_admin.html", {
        "d": d,
        "form": form_individual,
        "form_lote": form_lote,
        "modo_lote": modo_lote,

        # navegação no cabeçalho e rodapé
        "has_prev": has_prev,
        "has_next": has_next,
        "nav_action": nav_action,

        # ação correta do formulário principal
        "form_action": form_action,

        # para o template injetar <input type=hidden> dos filtros
        "preserved": dict(preserved),
    })
    resp["X-Modal-Partial"] = "despesa"
    return resp
'''

from urllib.parse import urlparse, parse_qs
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import QueryDict
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse

def _to_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (TypeError, ValueError):
        return default

def _first(qs_dict, key, default=None):
    vals = qs_dict.get(key, [])
    return vals[0] if vals else default

STATUS_MAP = {
    "PENDENTE": Despesa.Status.PENDENTE,
    "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
    "APROVADA": Despesa.Status.APROVADA,
    "REPROVADA": Despesa.Status.REPROVADA,
}

@staff_member_required
def despesa_modal_admin(request, pk):
    """
    Modal do admin (individual e lote).
    - Calcula prev/next com base nos filtros (?centro=&user=&ano=&mes=&st=).
    - Após salvar no modo individual:
        * Se a despesa continuar no filtro: re-renderiza ela mesma.
        * Se sair do filtro: abre automaticamente a PRÓXIMA (ou anterior) do mesmo filtro.
    - Sempre retorna fragmento (quando XHR/partial=1) com X-Modal-Partial=despesa.
    """
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )
    centro = d.centro
    ano_d  = d.data_fato.year
    mes_d  = d.data_fato.month

    # --- Filtros vindos da URL; se faltarem, herdar do referer ---
    centro_id = _to_int(request.GET.get("centro"))
    user_id   = _to_int(request.GET.get("user"))
    ano       = _to_int(request.GET.get("ano"))
    mes       = _to_int(request.GET.get("mes"))
    st_param  = (request.GET.get("st") or "").upper().strip()

    if any(v is None for v in (centro_id, user_id, ano, mes)) or not st_param:
        ref = request.META.get("HTTP_REFERER") or ""
        try:
            ref_qs = parse_qs(urlparse(ref).query)
        except Exception:
            ref_qs = {}
        if centro_id is None: centro_id = _to_int(_first(ref_qs, "centro"))
        if user_id   is None: user_id   = _to_int(_first(ref_qs, "user"))
        if ano       is None: ano       = _to_int(_first(ref_qs, "ano"))
        if mes       is None: mes       = _to_int(_first(ref_qs, "mes"))
        if not st_param:      st_param  = (_first(ref_qs, "st", "") or "").upper().strip()

    st_val = STATUS_MAP.get(st_param) if st_param else None

    # --- Alterna modo ---
    modo_lote = (request.POST.get("modo") == "lote") or (request.GET.get("lote") == "1")

    # --- Queryset do filtro (ordenação idêntica à lista) ---
    qs_base = Despesa.objects.select_related("centro", "usuario")
    if centro_id: qs_base = qs_base.filter(centro_id=centro_id)
    if user_id:   qs_base = qs_base.filter(usuario_id=user_id)
    if ano:       qs_base = qs_base.filter(data_fato__year=ano)
    if mes:       qs_base = qs_base.filter(data_fato__month=mes)
    if st_val:    qs_base = qs_base.filter(status=st_val)
    qs_base = qs_base.order_by("-data_fato", "-criado_em", "-id")

    # Captura a lista de IDs ANTES de salvar (para saber posição do item atual)
    id_list = list(qs_base.values_list("id", flat=True))

    def _prev_next_ids(current_id):
        if current_id in id_list:
            i = id_list.index(current_id)
            prev_id = id_list[i-1] if i > 0 else None
            next_id = id_list[i+1] if i < len(id_list)-1 else None
            return prev_id, next_id
        return None, None

    # --- Preservar filtros para actions/hidden e deixar "partial=1" sempre presente ---
    preserved = QueryDict(mutable=True)
    if centro_id: preserved["centro"] = str(centro_id)
    if user_id:   preserved["user"]   = str(user_id)
    if ano:       preserved["ano"]    = str(ano)
    if mes:       preserved["mes"]    = str(mes)
    if st_param:  preserved["st"]     = st_param
    if modo_lote: preserved["lote"]   = "1"
    preserved["partial"] = "1"  # força fragmento
    qs_str = preserved.urlencode()

    def _urls_for(obj_id):
        return (
            f"{reverse('despesa_modal_nav',  args=[obj_id])}?{qs_str}",
            f"{reverse('despesa_modal_admin', args=[obj_id])}?{qs_str}",
        )

    # ---------------- MODO LOTE ----------------
    if modo_lote:
        form_lote = AdminLoteReembolsoForm(
            data=request.POST or None,
            files=request.FILES or None,
            centro=centro, ano=ano_d, mes=mes_d,
        )
        form_individual = AdminReembolsoForm(instance=d)

        if request.method == "POST":
            if form_lote.is_valid():
                count = form_lote.aplicar()
                d.refresh_from_db()
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)
            else:
                messages.error(request, "Corrija os erros e tente novamente.")

        # prev/next para o item atual
        prev_id, next_id = _prev_next_ids(d.id)
        has_prev = bool(prev_id); has_next = bool(next_id)
        nav_action, form_action = _urls_for(d.id)

        resp = render(request, "centros/_modal_despesa_admin.html", {
            "d": d,
            "form": form_individual,
            "form_lote": form_lote,
            "modo_lote": True,
            "has_prev": has_prev,
            "has_next": has_next,
            "nav_action": nav_action,
            "form_action": form_action,
            "preserved": dict(preserved.lists()),  # para hidden fields no template
        })
        resp["X-Modal-Partial"] = "despesa"
        return resp

    # ---------------- MODO INDIVIDUAL ----------------
    form_individual = AdminReembolsoForm(
        data=request.POST or None,
        files=request.FILES or None,
        instance=d,
    )
    form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano_d, mes=mes_d)

    # alvo a ser exibido ao final (padrão: a própria despesa)
    target = d
    switch_to_neighbor = False

    if request.method == "POST":
        if form_individual.is_valid():
            # status ANTES de salvar (para detectar saída do filtro)
            old_status = d.status
            d = form_individual.save()
            d.refresh_from_db()

            # Se há um filtro de status ativo e a despesa mudou de status (saiu do filtro),
            # pulamos automaticamente para a PRÓXIMA (ou anterior) do filtro original.
            if st_val and d.status != st_val:
                prev_id, next_id = _prev_next_ids(d.id)
                jump_id = next_id or prev_id  # tenta próxima; senão, anterior
                if jump_id:
                    target = get_object_or_404(
                        Despesa.objects.select_related("centro", "usuario"),
                        pk=jump_id
                    )
                    switch_to_neighbor = True
                    messages.success(request, "Alterações salvas. Avançando para a próxima no filtro.")
                else:
                    messages.success(request, "Alterações salvas. Não há mais itens no filtro atual.")
            else:
                messages.success(request, "Despesa atualizada com sucesso.")
        else:
            messages.error(request, "Corrija os erros e tente novamente.")

    # Recalcula prev/next **sempre com base no id_list capturado antes do save**,
    # mas agora usando o `target` (que pode ser a próxima despesa).
    prev_id, next_id = _prev_next_ids(target.id)
    has_prev = bool(prev_id); has_next = bool(next_id)
    nav_action, form_action = _urls_for(target.id)

    # Se não for XHR/partial, redireciona para a própria URL com QS (evita abrir a index)
    is_partial = (
        request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        or request.GET.get("partial") == "1"
        or request.POST.get("partial") == "1"
    )
    if not is_partial and request.method in ("GET", "POST"):
        return redirect(form_action)

    resp = render(request, "centros/_modal_despesa_admin.html", {
        "d": target,
        "form": AdminReembolsoForm(instance=target) if switch_to_neighbor else form_individual,
        "form_lote": form_lote,
        "modo_lote": False,
        "has_prev": has_prev,
        "has_next": has_next,
        "nav_action": nav_action,
        "form_action": form_action,
        "preserved": dict(preserved.lists()),  # hidden fields no template
        "fora_do_filtro": (target.id not in id_list),
    })
    resp["X-Modal-Partial"] = "despesa"
    return resp


from django.contrib import messages
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
# ... seus imports
from .forms import DespesaForm
from .models import Despesa, LoteReembolso
from .services.fechamento import colaborador_pode_editar  # se já existir

# views.py
from django.db.models import F

MAX_EDICOES = 2  # regra: até 2 edições após a primeira análise do admin

@login_required
def despesa_update(request, pk):
    obj = get_object_or_404(Despesa, pk=pk, usuario=request.user)

        # Captura a página anterior (fallback para lista)
    from urllib.parse import urlparse

    referer_raw = request.META.get("HTTP_REFERER")
    referer = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("viagens_lista")  # fallback seguro

    if referer_raw:
        parsed = urlparse(referer_raw)
        if parsed.path != request.path:  # evita redirecionar para si mesmo
            referer = referer_raw

    # Regra de fechamento geral
    if not colaborador_pode_editar(request.user, obj):
        messages.error(request, "Esta despesa não pode mais ser editada.")
        return redirect(referer)

    # Bloqueio se já houve análise e atingiu o limite
    if obj.foi_avaliada and obj.edit_count >= MAX_EDICOES:
        messages.error(
            request,
            f"Você não pode editar mais esta despesa. Você já editou {obj.edit_count} vez(es) após a primeira avaliação."
        )
        return redirect(referer)

    if request.method == "POST":
        form = DespesaForm(request.user, request.POST, request.FILES, instance=obj)
        if form.is_valid():
            inst = form.save(commit=False)

            # Toda edição volta para PENDENTE
            inst.status = Despesa.Status.PENDENTE
            inst.save()

            # Contabiliza edição se já houve avaliação
            if obj.foi_avaliada:
                Despesa.objects.filter(pk=inst.pk).update(edit_count=F("edit_count") + 1)

            messages.success(
                request,
                "Despesa atualizada. O status foi alterado para PENDENTE para nova revisão."
            )
            return redirect(referer)
    else:
        form = DespesaForm(request.user, instance=obj)

    return render(request, "viagens/despesa_form_inline.html", {
        "form": form,
        "obj": obj,
        "limite_edicao_atingido": obj.foi_avaliada and obj.edit_count >= MAX_EDICOES,
        "max_edicoes": MAX_EDICOES,
    })


# despesas/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .forms import DespesaForm
from .models import Despesa

@login_required
def despesa_edit(request, pk):
    """
    Edição de despesa pelo COLABORADOR, com formulário seguro.
    """
    obj = get_object_or_404(Despesa, pk=pk, usuario=request.user)

    if request.method == "POST":
        form = DespesaForm(request.user, request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Despesa atualizada.")
            return redirect("viagens_lista")  # ou outra rota (ex.: detail/lista)
    else:
        form = DespesaForm(request.user, instance=obj)

    return render(request, "despesas/form_update.html", {"form": form, "obj": obj})

@login_required
def home(request):
    # cards precisam saber se há aprovadas
    despesas_user = Despesa.objects.filter(usuario=request.user)
    tem_aprovadas = despesas_user.filter(status=Despesa.Status.APROVADA).exists()

    # checklist (somente pendentes na lista principal)
    form = ChecklistForm()
    pendentes = ChecklistItem.objects.filter(usuario=request.user, concluido=False).order_by("-criado_em")[:20]

    return render(request, "home.html", {
        "tem_aprovadas": tem_aprovadas,
        "checklist_form": form,
        "checklist_pendentes": pendentes,
    })

@login_required
def checklist_add(request):
    if request.method != "POST":
        return HttpResponseForbidden()
    form = ChecklistForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.usuario = request.user
        item.save()
        messages.success(request, "Tarefa adicionada ao checklist.")
    return redirect("home")

@login_required
def checklist_done(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden()
    item = get_object_or_404(ChecklistItem, pk=pk, usuario=request.user)
    item.concluido = True
    item.concluido_em = timezone.now()
    item.save(update_fields=["concluido", "concluido_em"])
    # some da lista (porque a home só lista pendentes)
    return redirect("home")

# despesas/views.py
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.urls import reverse
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required

# supondo que você tenha esse form (já usamos antes)
# class DespesaForm(forms.ModelForm):
#     def __init__(self, user, *args, **kwargs): ...


'''
@login_required
def despesa_create(request):
    # centro pré-selecionado (opcional)
    cid = request.GET.get("centro")
    initial = {}
    if cid:
        initial["centro"] = cid

    if request.method == "POST":
        form = DespesaForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.save()
            # resposta para requisição AJAX (modal)
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": True, "redirect": reverse("viagens_lista")}, status=201)
            # fallback página completa
            messages.success(request, "Despesa cadastrada.")
            return redirect("viagens_lista")
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                # re-renderiza o form do modal COM erros (200 para substituir HTML)
                return render(request, "despesas/_form_modal.html", {"form": form}, status=200)
    else:
        form = DespesaForm(request.user, initial=initial)

    # AJAX ⇒ render parcial de modal
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "despesas/_form_modal.html", {"form": form})

    # Página completa (fallback)
    return render(request, "despesas/form.html", {"form": form})
'''

# views.py
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

@login_required
def despesa_create(request):
    # centro pré-selecionado (opcional)
    cid = request.GET.get("centro")
    initial = {}
    if cid:
        initial["centro"] = cid

    # calcula a URL de retorno (mantém filtros da página atual)
    def _next_url_default():
        ref = request.META.get("HTTP_REFERER")
        if ref and url_has_allowed_host_and_scheme(ref, allowed_hosts={request.get_host()}):
            return ref
        return reverse("viagens_lista")

    next_url = request.GET.get("next") or _next_url_default()

    if request.method == "POST":
        form = DespesaForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.usuario = request.user
            obj.save()

            # AJAX (modal): devolve JSON com a URL para recarregar a MESMA página
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                # tenta usar 'next' do POST; senão, Referer; senão, fallback
                posted_next = request.POST.get("next")
                redirect_url = (
                    posted_next if (posted_next and url_has_allowed_host_and_scheme(
                        posted_next, allowed_hosts={request.get_host()}))
                    else _next_url_default()
                )
                return JsonResponse({"ok": True, "redirect": redirect_url}, status=201)

            # Página completa (fallback)
            messages.success(request, "Despesa cadastrada.")
            return redirect(next_url)
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                # re-renderiza o form do modal COM erros (200 substitui o HTML no modal)
                return render(request, "despesas/_form_modal.html", {"form": form}, status=200)
    else:
        form = DespesaForm(request.user, initial=initial)

    # AJAX ⇒ render parcial (inclui hidden next para POST)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "despesas/_form_modal.html", {"form": form, "next_url": next_url})

    # Página completa (fallback)
    return render(request, "despesas/form.html", {"form": form, "next_url": next_url})


@login_required
def despesa_edit(request, pk):
    obj = get_object_or_404(Despesa, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = DespesaForm(request.user, request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Despesa atualizada.")
            return redirect("viagens_lista")  # ou para onde você preferir
    else:
        form = DespesaForm(request.user, instance=obj)
    return render(request, "despesas/form_edit.html", {"form": form, "obj": obj})


@login_required
def despesa_detail(request, pk):
    obj = get_object_or_404(Despesa, pk=pk)
    # visibilidade: autor ou admin
    if request.user != obj.usuario and not request.user.groups.filter(name="AdminModulo").exists():
        messages.error(request, "Sem permissão para visualizar esta despesa.")
        return redirect("home")
    return render(request, "despesas/detail.html", {"obj": obj})


@login_required
@permission_required("despesas.view_centrodecusto", raise_exception=True)
def admin_centros(request):
    # Visão global (antes de filtrar) — totais do mês do cadastro corrente
    qs = Despesa.objects.filter(criado_em__month=now().month, criado_em__year=now().year)
    total_mes = qs.aggregate(total=Sum("valor"))["total"] or 0
    total_reembolsadas = qs.filter(status=Despesa.Status.APROVADA).aggregate(total=Sum("valor"))["total"] or 0

    centros = CentroDeCusto.objects.filter(ativo=True)
    return render(request, "admin/centros.html", {
        "centros": centros,
        "total_mes": total_mes,
        "total_reembolsadas": total_reembolsadas,
    })

@login_required
@permission_required("despesas.change_despesa", raise_exception=True)
def aprovar_despesa(request, pk):
    obj = get_object_or_404(Despesa, pk=pk)
    obj.status = Despesa.Status.APROVADA
    obj.save(update_fields=["status"])
    messages.success(request, "Despesa aprovada.")
    return redirect("admin_centro_detail", centro_id=obj.centro_id)

@login_required
@permission_required("despesas.change_despesa", raise_exception=True)
def reprovar_despesa(request, pk):
    obj = get_object_or_404(Despesa, pk=pk)
    obj.status = Despesa.Status.REPROVADA
    obj.save(update_fields=["status"])
    messages.success(request, "Despesa reprovada.")
    return redirect("admin_centro_detail", centro_id=obj.centro_id)

@login_required
@permission_required("despesas.add_lotereembolso", raise_exception=True)
def lote_create(request):
    if request.method == "POST":
        form = LoteReembolsoForm(request.POST, request.FILES)
        if form.is_valid():
            lote = form.save(commit=False)
            lote.criado_por = request.user
            lote.save()
            form.save_m2m()
            messages.success(request, "Lote de reembolso criado.")
            return redirect("lote_detail", pk=lote.pk)
    else:
        form = LoteReembolsoForm()
    return render(request, "admin/lote_form.html", {"form": form})

@login_required
@permission_required("despesas.view_lotereembolso", raise_exception=True)
def lote_detail(request, pk):
    lote = get_object_or_404(LoteReembolso, pk=pk)
    return render(request, "admin/lote_detail.html", {"lote": lote})

from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render, get_object_or_404
from django.utils.timezone import now

from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .services.ui_helpers import mes_label_pt
from .services.fechamento import MesRef

def _rotulo_filtro(ano: int, mes: int) -> str:
    if ano == 0 and mes == 0:
        return "TODOS"
    if ano == 0:
        # pega só o nome PT-BR do mês
        return f"{mes_label_pt(2000, mes).split(' / ')[0]} / TODOS OS ANOS"
    if mes == 0:
        return f"TODOS / {ano}"
    return mes_label_pt(ano, mes)


from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now

@login_required
def relatorio(request):
    user = request.user
    hoje = now()

    # --- filtros (default: mês atual) ---
    raw_ano = request.GET.get("ano")
    raw_mes = request.GET.get("mes")
    raw_centro = request.GET.get("centro")

    if raw_ano is None and raw_mes is None and raw_centro is None:
        sel_ano, sel_mes = hoje.year, hoje.month
    else:
        try:
            sel_ano = int(raw_ano) if raw_ano not in (None, "") else 0
        except ValueError:
            sel_ano = 0
        try:
            sel_mes = int(raw_mes) if raw_mes not in (None, "") else 0
        except ValueError:
            sel_mes = 0

    # base do usuário
    base = Despesa.objects.filter(usuario=user)

    # valida centro (se vier)
    centro_obj = None
    if raw_centro:
        try:
            cid = int(raw_centro)
            centro_obj = get_object_or_404(
                CentroDeCusto,
                id=cid,
                ativo=True,
                id__in=AssociacaoCentroCusto.objects.filter(
                    usuario=user, ativo=True
                ).values_list("centro_id", flat=True),
            )
            base = base.filter(centro=centro_obj)
        except (ValueError, CentroDeCusto.DoesNotExist):
            centro_obj = None

    # aplica escopo do período
    if sel_ano:
        base = base.filter(data_fato__year=sel_ano)
    if sel_mes:
        base = base.filter(data_fato__month=sel_mes)

    # rótulo do período
    periodo_label = _rotulo_filtro(sel_ano, sel_mes)

    # ============== IGNORAR REPROVADAS (via queryset) ==============
    base_sem_reprov = base.exclude(status=Despesa.Status.REPROVADA)

    # KPIs a partir do queryset já “limpo”
    total_periodo = base_sem_reprov.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_reemb   = base_sem_reprov.filter(status=Despesa.Status.APROVADA)\
                                   .aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_pend    = base_sem_reprov.filter(status=Despesa.Status.PENDENTE)\
                                   .aggregate(v=Sum("valor"))["v"] or Decimal("0")

    # blocos por centro (subtotais também sem reprovadas)
    if centro_obj:
        centros_list = [centro_obj]
    else:
        centros_list = list(
            CentroDeCusto.objects
            .filter(id__in=base.values_list("centro_id", flat=True).distinct())
            .order_by("nome")
        )

    centros_blocos = []
    for c in centros_list:
        qs_centro = base.filter(centro=c).order_by("data_fato", "criado_em", "id")
        subtotal = (qs_centro.exclude(status=Despesa.Status.REPROVADA)
                              .aggregate(v=Sum("valor"))["v"] or Decimal("0"))
        itens = list(qs_centro)  # mantém a listagem como está (se quiser, pode também excluir aqui)
        centros_blocos.append({
            "centro": c,
            "subtotal": subtotal,  # ← já sem reprovadas
            "itens": itens,
        })

    contexto = {
        "periodo_label": periodo_label,
        "analista": (user.get_full_name() or user.username).upper(),
        "total_periodo": total_periodo,   # ← usar este no template
        "total_reemb": total_reemb,       # ← e este
        "total_pend": total_pend,         # ← e este
        "centros_blocos": centros_blocos,
        "somente_um_centro": bool(centro_obj),
    }
    return render(request, "relatorios/relatorio.html", contexto)



@login_required
def notificacoes_placeholder(request): #para substituição futura, funcionará para exibir as notificações na tela inicial
    messages.success(request, f"Em breve a funcionalidade de notificações estará disponível!")
    return redirect("home")

@login_required
def links_placeholder(request): #não é uma função essencial
    return render(request, "placeholders/links.html")


@login_required
@permission_required("despesas.view_centrodecusto", raise_exception=True)
def admin_centros(request):
    # mês corrente sempre em destaque
    mc = mes_corrente()

    # Lista de meses existentes (por criado_em) para filtros
    meses_qs = (Despesa.objects
                .annotate(m=TruncMonth("criado_em"))
                .values_list("m", flat=True)
                .distinct()
                .order_by("-m"))

    meses_distintos = [
        MesRef(ano=d.year, mes=d.month) for d in meses_qs if d is not None
    ]
    meses_ordenados = meses_para_admin_order(meses_distintos)

    # Totais do mês corrente (por criado_em)

    qs_corrente = Despesa.objects.filter(criado_em__year=mc.ano, criado_em__month=mc.mes)
    total_reprov = qs_corrente.filter(status=Despesa.Status.REPROVADA).aggregate(total=Sum("valor"))["total"] or 0
    total_mes1 = qs_corrente.aggregate(total=Sum("valor"))["total"] or 0
    total_mes = total_mes1 - total_reprov
    total_reembolsadas = qs_corrente.filter(status=Despesa.Status.APROVADA).aggregate(total=Sum("valor"))["total"] or 0

    centros = CentroDeCusto.objects.filter(ativo=True)
    return render(request, "admin/centros.html", {
        "centros": centros,
        "total_mes": total_mes,
        "total_reembolsadas": total_reembolsadas,
        "mes_corrente": mc,
        "meses": meses_ordenados,  # corrente primeiro
    })


from django.core.paginator import Paginator

@login_required
@permission_required("despesas.view_centrodecusto", raise_exception=True)
def admin_centro_detail(request, centro_id):
    centro = get_object_or_404(CentroDeCusto, pk=centro_id)

    despesas_qs = Despesa.objects.filter(centro=centro).order_by("-criado_em")
    associados_qs = (AssociacaoCentroCusto.objects
                     .filter(centro=centro, ativo=True)
                     .select_related("usuario")
                     .order_by("usuario__first_name","usuario__username"))

    # paginação independente
    pd = request.GET.get("pd") or 1  # page despesas
    pa = request.GET.get("pa") or 1  # page associados

    desp_paginator = Paginator(despesas_qs, 5)
    assoc_paginator = Paginator(associados_qs, 5)

    despesas_page = desp_paginator.get_page(pd)
    associados_page = assoc_paginator.get_page(pa)

    return render(request, "admin/centro_detail.html", {
        "centro": centro,
        "despesas_page": despesas_page,
        "associados_page": associados_page,
    })

def logout_view(request):
    logout(request)
    messages.success(request, "Você saiu com segurança.")
    return redirect("login")




def _is_admin(u):  # admin/gente que libera reembolsos
    return u.is_active and (u.is_staff or u.is_superuser)

def _label_mes_pt(ano, mes):
    MESES = ["JANEIRO","FEVEREIRO","MARÇO","ABRIL","MAIO","JUNHO","JULHO",
             "AGOSTO","SETEMBRO","OUTUBRO","NOVEMBRO","DEZEMBRO"]
    if 1 <= mes <= 12:
        return f"{MESES[mes-1]} / {ano}"
    return "TODOS / TODOS"

def _meses_anos_disponiveis(qs):
    mlist = (qs.annotate(m=TruncMonth("data_fato"))
               .values_list("m", flat=True).distinct().order_by("-m"))
    anos = sorted({d.year for d in mlist}, reverse=True)
    return anos, mlist


from django.contrib.auth import get_user_model
# se já existir, mantenha seu helper:
# from .utils import _label_mes_pt, _meses_anos_disponiveis, _is_admin

from django.contrib.auth import get_user_model

from django.contrib.auth import get_user_model

User = get_user_model()


from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.db.models.functions import TruncMonth

# ... seus imports e helpers (_is_admin, _label_mes_pt, _meses_anos_disponiveis, models etc.)
'''
@login_required
@user_passes_test(_is_admin)
def centros_index(request):
    # --------- parâmetros de filtro (centro, usuário) ---------
    raw_centro = request.GET.get("centro", "")
    raw_user   = request.GET.get("user", "")

    try:
        sel_centro = int(raw_centro) if raw_centro else 0
    except ValueError:
        sel_centro = 0

    try:
        sel_user = int(raw_user) if raw_user else 0
    except ValueError:
        sel_user = 0

    # --------- período (mês/ano) ---------
    try:
        sel_mes = int(request.GET.get("mes") or 0)
        sel_ano = int(request.GET.get("ano") or 0)
    except ValueError:
        sel_mes = sel_ano = 0

    hoje = now()
    if not (1 <= sel_mes <= 12):
        sel_mes = hoje.month
    if not sel_ano:
        sel_ano = hoje.year

    # --------- filtro por status (aceita ?st= ou ?status=) ---------
    raw_status = request.GET.get("st", request.GET.get("status", "TODOS"))
    raw_status = (raw_status or "TODOS").strip().upper()

    STATUS_MAP = {
        "TODOS": None,
        "PENDENTE": Despesa.Status.PENDENTE,                 # Pendente (não analisada)
        "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,     # Pendente de pagamento (ADMIN)
        "APROVADA": Despesa.Status.APROVADA,
        "REPROVADA": Despesa.Status.REPROVADA,
    }
    sel_status = raw_status if raw_status in STATUS_MAP else "TODOS"

    status_opts = [
        ("TODOS", "Todos os status"),
        ("PENDENTE", "Pendente (não analisada)"),
        ("PENDENTE_PAGTO", "Pendente de pagamento"),
        ("APROVADA", "Aprovadas"),
        ("REPROVADA", "Reprovadas"),
    ]

    # --------- centros e analistas (para os selects) ---------
    centros = CentroDeCusto.objects.filter(ativo=True).order_by("nome")
    centro_obj = get_object_or_404(centros, pk=sel_centro) if sel_centro else None

    analistas_all = User.objects.filter(
        is_active=True,
        id__in=AssociacaoCentroCusto.objects.filter(ativo=True).values("usuario_id")
    ).order_by("first_name", "last_name", "username")

    if centro_obj:
        analistas_opts = analistas_all.filter(
            id__in=AssociacaoCentroCusto.objects.filter(
                centro=centro_obj, ativo=True
            ).values("usuario_id")
        )
    else:
        analistas_opts = analistas_all

    user_sel = get_object_or_404(analistas_all, pk=sel_user) if sel_user else None

    # --------- base e período ---------
    base = Despesa.objects.all()
    periodo_base = base.filter(data_fato__year=sel_ano, data_fato__month=sel_mes)

    if centro_obj:
        periodo_base = periodo_base.filter(centro=centro_obj)
    if user_sel:
        periodo_base = periodo_base.filter(usuario=user_sel)

    # aplica status (se não for TODOS)
    if STATUS_MAP[sel_status] is not None:
        periodo = periodo_base.filter(status=STATUS_MAP[sel_status])
    else:
        periodo = periodo_base

    # --------- KPIs (acompanhando o status selecionado) ---------
    total_bruto = periodo.aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_aprov = periodo.filter(status=Despesa.Status.APROVADA)\
                         .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_reprov = periodo.filter(status=Despesa.Status.REPROVADA)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_analise = periodo.filter(status=Despesa.Status.PENDENTE)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_pagto   = periodo.filter(status=Despesa.Status.PENDENTE_PAGTO)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")

    total_mes = total_bruto - total_reprov
    total_pendentes = (pend_analise or Decimal("0")) + (pend_pagto or Decimal("0"))

    # --------- lista (paginada) ---------
    pagina = request.GET.get("p", 1)
    despesas_mes = []
    if centro_obj or user_sel:
        qs_lista = periodo.order_by("-data_fato", "-criado_em", "-id")
        despesas_mes = Paginator(qs_lista, 5).get_page(pagina)

    # --------- meses anteriores (quando filtra por centro) ---------
    meses_anteriores = []
    if centro_obj:
        outros_meses = (base.filter(centro=centro_obj)
                          .exclude(data_fato__year=sel_ano, data_fato__month=sel_mes)
                          .annotate(m=TruncMonth("data_fato"))
                          .values_list("m", flat=True).distinct().order_by("-m"))
        for d in outros_meses:
            meses_anteriores.append({
                "label": _label_mes_pt(d.year, d.month),
                "ano": d.year,
                "mes": d.month
            })

    # --------- associados (mostrar só quando NÃO filtrando por analista) ---------
    associados = []
    if centro_obj and not user_sel:
        associados = (AssociacaoCentroCusto.objects
                      .filter(centro=centro_obj, ativo=True)
                      .select_related("usuario")
                      .order_by("usuario__first_name","usuario__last_name"))

    # --------- ALERTA: pendências de QUALQUER mês anterior ao selecionado ---------
    inicio_mes_selecionado = date(sel_ano, sel_mes, 1)
    pend_prev_qs = Despesa.objects.filter(
        data_fato__lt=inicio_mes_selecionado,
        status__in=[Despesa.Status.PENDENTE, Despesa.Status.PENDENTE_PAGTO],
    )
    if centro_obj:
        pend_prev_qs = pend_prev_qs.filter(centro=centro_obj)
    if user_sel:
        pend_prev_qs = pend_prev_qs.filter(usuario=user_sel)

    pend_count = pend_prev_qs.count()
    pend_total = pend_prev_qs.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    alerta_pendencias = None
    if pend_count > 0:
        pend_analise_prev = pend_prev_qs.filter(status=Despesa.Status.PENDENTE).count()
        pend_pagto_prev   = pend_prev_qs.filter(status=Despesa.Status.PENDENTE_PAGTO).count()
        # rótulo informando o corte ("anteriores a mm/aaaa selecionado")
        alerta_pendencias = {
            "label_mes": f"anteriores a {_label_mes_pt(sel_ano, sel_mes)}",
            "quantidade": pend_count,
            "valor_total": pend_total,
            "qtd_analise": pend_analise_prev,
            "qtd_pagto": pend_pagto_prev,
        }

    # --------- combos período ---------
    anos_disponiveis, _ = _meses_anos_disponiveis(base)
    meses_numeros = [(i, f"{i:02d}") for i in range(1, 13)]

    # monta QS base para reuso em links
    qs_base = (
        f"centro={(centro_obj.id if centro_obj else '')}"
        f"&user={(user_sel.id if user_sel else '')}"
        f"&ano={sel_ano}&mes={sel_mes}&st={sel_status}"
    )

    ctx = {
        # selects
        "centros": centros,
        "analistas_opts": analistas_opts,
        "status_opts": status_opts,
        "sel_status": sel_status,

        # seleções atuais
        "centro_sel": centro_obj,
        "user_sel": user_sel,
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,

        # KPIs
        "mes_label": _label_mes_pt(sel_ano, sel_mes),
        "total_mes": total_mes,
        "total_reembolsadas": total_aprov,
        "total_pendentes": total_pendentes,

        # lista & auxiliares
        "despesas_mes": despesas_mes,
        "meses_anteriores": meses_anteriores,
        "associados": associados,

        # combos período
        "anos_disponiveis": anos_disponiveis,
        "meses_numeros": meses_numeros,

        # alerta atualizado (todas as pendências anteriores)
        "alerta_pendencias": alerta_pendencias,

        # qs base p/ links
        "qs_base": qs_base,
    }
    return render(request, "centros/index.html", ctx)
'''


@login_required
@user_passes_test(_is_admin)
def centros_index(request):
    # --------- parâmetros de filtro (centro, usuário) ---------
    raw_centro = request.GET.get("centro", "")
    raw_user   = request.GET.get("user", "")

    try:
        sel_centro = int(raw_centro) if raw_centro else 0
    except ValueError:
        sel_centro = 0

    try:
        sel_user = int(raw_user) if raw_user else 0
    except ValueError:
        sel_user = 0

    # --------- período (mês/ano) ---------
    try:
        sel_mes = int(request.GET.get("mes") or 0)
        sel_ano = int(request.GET.get("ano") or 0)
    except ValueError:
        sel_mes = sel_ano = 0

    hoje = now()
    if not (1 <= sel_mes <= 12):
        sel_mes = hoje.month
    if not sel_ano:
        sel_ano = hoje.year

    # --------- filtro por status (aceita ?st= ou ?status=) ---------
    raw_status = request.GET.get("st", request.GET.get("status", "TODOS"))
    raw_status = (raw_status or "TODOS").strip().upper()

    STATUS_MAP = {
        "TODOS": None,
        "PENDENTE": Despesa.Status.PENDENTE,                 # Pendente (não analisada)
        "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,     # Pendente de pagamento (ADMIN)
        "APROVADA": Despesa.Status.APROVADA,
        "REPROVADA": Despesa.Status.REPROVADA,
    }
    sel_status = raw_status if raw_status in STATUS_MAP else "TODOS"

    status_opts = [
        ("TODOS", "Todos os status"),
        ("PENDENTE", "Pendente (não analisada)"),
        ("PENDENTE_PAGTO", "Pendente de pagamento"),
        ("APROVADA", "Aprovadas"),
        ("REPROVADA", "Reprovadas"),
    ]

    # --------- centros e analistas (para os selects) ---------
    centros = CentroDeCusto.objects.filter(ativo=True).order_by("nome")
    centro_obj = get_object_or_404(centros, pk=sel_centro) if sel_centro else None

    analistas_all = User.objects.filter(
        is_active=True,
        id__in=AssociacaoCentroCusto.objects.filter(ativo=True).values("usuario_id")
    ).order_by("first_name", "last_name", "username")

    if centro_obj:
        analistas_opts = analistas_all.filter(
            id__in=AssociacaoCentroCusto.objects.filter(
                centro=centro_obj, ativo=True
            ).values("usuario_id")
        )
    else:
        analistas_opts = analistas_all

    user_sel = get_object_or_404(analistas_all, pk=sel_user) if sel_user else None

    # --------- base e período ---------
    base = Despesa.objects.all()
    periodo_base = base.filter(data_fato__year=sel_ano, data_fato__month=sel_mes)

    if centro_obj:
        periodo_base = periodo_base.filter(centro=centro_obj)
    if user_sel:
        periodo_base = periodo_base.filter(usuario=user_sel)

    # aplica status (se não for TODOS)
    if STATUS_MAP[sel_status] is not None:
        periodo = periodo_base.filter(status=STATUS_MAP[sel_status])
    else:
        periodo = periodo_base

    # --------- KPIs (acompanhando o status selecionado) ---------
    total_bruto = periodo.aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_aprov = periodo.filter(status=Despesa.Status.APROVADA)\
                         .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_reprov = periodo.filter(status=Despesa.Status.REPROVADA)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_analise = periodo.filter(status=Despesa.Status.PENDENTE)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_pagto   = periodo.filter(status=Despesa.Status.PENDENTE_PAGTO)\
                          .aggregate(s=Sum("valor"))["s"] or Decimal("0")

    total_mes = total_bruto - total_reprov
    total_pendentes = (pend_analise or Decimal("0")) + (pend_pagto or Decimal("0"))

    # --------- lista (paginada) ---------
    pagina = request.GET.get("p", 1)
    despesas_mes = []
    if centro_obj or user_sel:
        qs_lista = periodo.order_by("-data_fato", "-criado_em", "-id")
        despesas_mes = Paginator(qs_lista, 5).get_page(pagina)

    # --------- meses anteriores (quando filtra por centro) ---------
    meses_anteriores = []
    if centro_obj:
        outros_meses = (base.filter(centro=centro_obj)
                          .exclude(data_fato__year=sel_ano, data_fato__month=sel_mes)
                          .annotate(m=TruncMonth("data_fato"))
                          .values_list("m", flat=True).distinct().order_by("-m"))
        for d in outros_meses:
            meses_anteriores.append({
                "label": _label_mes_pt(d.year, d.month),
                "ano": d.year,
                "mes": d.month
            })

    # --------- associados (mostrar só quando NÃO filtrando por analista) ---------
    associados = []
    if centro_obj and not user_sel:
        associados = (AssociacaoCentroCusto.objects
                      .filter(centro=centro_obj, ativo=True)
                      .select_related("usuario")
                      .order_by("usuario__first_name","usuario__last_name"))

    # --------- ALERTA: pendências de QUALQUER mês anterior ao selecionado ---------
    inicio_mes_selecionado = date(sel_ano, sel_mes, 1)
    pend_prev_qs = Despesa.objects.filter(
        data_fato__lt=inicio_mes_selecionado,
        status__in=[Despesa.Status.PENDENTE, Despesa.Status.PENDENTE_PAGTO],
    )
    if centro_obj:
        pend_prev_qs = pend_prev_qs.filter(centro=centro_obj)
    if user_sel:
        pend_prev_qs = pend_prev_qs.filter(usuario=user_sel)

    pend_count = pend_prev_qs.count()
    pend_total = pend_prev_qs.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    alerta_pendencias = None
    if pend_count > 0:
        pend_analise_prev = pend_prev_qs.filter(status=Despesa.Status.PENDENTE).count()
        pend_pagto_prev   = pend_prev_qs.filter(status=Despesa.Status.PENDENTE_PAGTO).count()
        # rótulo informando o corte ("anteriores a mm/aaaa selecionado")
        alerta_pendencias = {
            "label_mes": f"anteriores a {_label_mes_pt(sel_ano, sel_mes)}",
            "quantidade": pend_count,
            "valor_total": pend_total,
            "qtd_analise": pend_analise_prev,
            "qtd_pagto": pend_pagto_prev,
        }

    # --------- combos período ---------
    anos_disponiveis, _ = _meses_anos_disponiveis(base)
    meses_numeros = [(i, f"{i:02d}") for i in range(1, 13)]

    # monta QS base para reuso em links
    qs_base = (
        f"centro={(centro_obj.id if centro_obj else '')}"
        f"&user={(user_sel.id if user_sel else '')}"
        f"&ano={sel_ano}&mes={sel_mes}&st={sel_status}"
    )

    ctx = {
        # selects
        "centros": centros,
        "analistas_opts": analistas_opts,
        "status_opts": status_opts,
        "sel_status": sel_status,

        # seleções atuais
        "centro_sel": centro_obj,
        "user_sel": user_sel,
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,

        # KPIs
        "mes_label": _label_mes_pt(sel_ano, sel_mes),
        "total_mes": total_mes,
        "total_reembolsadas": total_aprov,
        "total_pendentes": total_pendentes,

        # lista & auxiliares
        "despesas_mes": despesas_mes,
        "meses_anteriores": meses_anteriores,
        "associados": associados,

        # combos período
        "anos_disponiveis": anos_disponiveis,
        "meses_numeros": meses_numeros,

        # alerta atualizado (todas as pendências anteriores)
        "alerta_pendencias": alerta_pendencias,

        # qs base p/ links
        "qs_base": qs_base,
    }
    return render(request, "centros/index.html", ctx)



@user_passes_test(_is_admin)
@login_required
def centro_novo_modal(request):
    # modal para criar centro
    if request.method == "POST":
        form = CentroForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponse("<script>window.location.reload()</script>")
    else:
        form = CentroForm()
    return render(request, "centros/_modal_centro_form.html", {"form": form})


from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import CentroDeCusto, AssociacaoCentroCusto
from .forms import AssociaAnalistaForm

@user_passes_test(_is_admin)
@login_required
def associar_analista_modal(request, centro_id):
    centro = get_object_or_404(CentroDeCusto, pk=centro_id, ativo=True)

    if request.method == "POST":
        form = AssociaAnalistaForm(request.POST, centro=centro)
        if form.is_valid():
            AssociacaoCentroCusto.objects.get_or_create(
                centro=centro,
                usuario=form.cleaned_data["usuario"],
                defaults={"ativo": True}
            )
            return HttpResponse(status=200)  # ✅ apenas status 200
    else:
        form = AssociaAnalistaForm(centro=centro)

    return render(request, "centros/_modal_associa_form.html", {
        "form": form,
        "centro": centro
    })

from .forms import AdminReembolsoForm, AdminLoteReembolsoForm




@login_required
def centros_relatorio(request):
    """
    Relatório administrativo.
    Querystring:
      - centro (int, opcional)
      - ano/mes (opcionais; se ausentes, atual)
    Agrega TODAS as despesas (não filtra por usuario do request).
    """
    sel_centro = request.GET.get("centro")
    sel_ano = int(request.GET.get("ano") or 0)
    sel_mes = int(request.GET.get("mes") or 0)

    qs = Despesa.objects.all()  # <— sem filtro por usuario!

    if sel_centro:
        qs = qs.filter(centro_id=sel_centro)

    hoje = now()
    if not (1 <= sel_mes <= 12): sel_mes = hoje.month
    if not sel_ano: sel_ano = hoje.year

    qs_periodo = qs.filter(data_fato__year=sel_ano, data_fato__month=sel_mes)

    total = qs_periodo.aggregate(v=Sum("valor"))["v"] or 0
    reemb = qs_periodo.filter(status=Despesa.Status.APROVADA)\
                      .aggregate(v=Sum("valor"))["v"] or 0
    pend = total - reemb

    centros = (CentroDeCusto.objects.filter(id__in=qs_periodo.values_list("centro_id", flat=True).distinct())
               .order_by("nome"))

    ctx = {
        "periodo_label": mes_label_pt(sel_ano, sel_mes),
        "kpi_total": total, "kpi_reemb": reemb, "kpi_pend": pend,
        "centros": centros,  # renderize blocos por centro no template
        "sel_ano": sel_ano, "sel_mes": sel_mes, "sel_centro": sel_centro,
    }
    return render(request, "centros/relatorio.html", ctx)


# despesas/views.py
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
@require_http_methods(["POST"])
def centro_associacao_remover(request, assoc_id):
    assoc = get_object_or_404(AssociacaoCentroCusto, pk=assoc_id)
    nome = assoc.usuario.get_full_name() or assoc.usuario.username
    assoc.delete()
    messages.success(request, f"Usuário “{nome}” removido do centro com sucesso.")
    nxt = request.POST.get("next") or reverse("centros")
    return redirect(nxt)



# despesas/views.py
from django.contrib.auth.forms import UserCreationForm

@staff_member_required
@require_http_methods(["GET", "POST"])
def usuario_create_modal(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Usuário criado com sucesso.")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": True, "user_id": user.id, "username": user.username})
            return redirect(reverse("centros"))
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return render(request, "centros/_modal_usuario_create.html", {"form": form})
    else:
        form = UserCreationForm()
    return render(request, "centros/_modal_usuario_create.html", {"form": form})


@login_required
def centros_relatorio(request):
    sel_centro = request.GET.get("centro")
    sel_ano = int(request.GET.get("ano") or 0)
    sel_mes = int(request.GET.get("mes") or 0)

    qs = Despesa.objects.all()  # não filtra por request.user

    if sel_centro:
        qs = qs.filter(centro_id=sel_centro)

    hoje = now()
    if not (1 <= sel_mes <= 12):
        sel_mes = hoje.month
    if not sel_ano:
        sel_ano = hoje.year

    qs_periodo = qs.filter(data_fato__year=sel_ano, data_fato__month=sel_mes)

    kpi_total = qs_periodo.aggregate(v=Sum("valor"))["v"] or 0
    kpi_reemb = qs_periodo.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or 0
    kpi_pend = kpi_total - kpi_reemb

    centros = (
        CentroDeCusto.objects.filter(
            id__in=qs_periodo.values_list("centro_id", flat=True).distinct()
        )
        .order_by("nome")
    )

    ctx = {
        "periodo_label": mes_label_pt(sel_ano, sel_mes),
        "kpi_total": kpi_total,
        "kpi_reemb": kpi_reemb,
        "kpi_pend": kpi_pend,
        "centros": centros,
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,
        "sel_centro": sel_centro,
    }
    return render(request, "centros/relatorio.html", ctx)



@login_required
def centros_relatorio_redirect(request):
    """
    Lê ?centro=, ?ano= e ?mes= da tela de Centros de Custo
    e redireciona para a view 'relatorio' reaproveitando os parâmetros.
    Aceita GET ou POST.
    """
    data = request.POST if request.method == "POST" else request.GET

    centro = data.get("centro")
    ano = data.get("ano")
    mes = data.get("mes")

    params = {}
    if centro:
        params["centro"] = centro
    if ano:
        params["ano"] = ano
    if mes:
        params["mes"] = mes

    url = reverse("relatorio")
    if params:
        url = f"{url}?{urlencode(params)}"
    return redirect(url)


@login_required
def relatorio_usuario(request):
    """
    Relatório do COLABORADOR/ANALISTA:
    - escopo SEMPRE restrito a request.user
    - aceita ?centro= (opcional, mas só entre os centros que o user está associado)
    - aceita ?ano=YYYY&mes=MM (default = mês atual)
    """
    user = request.user
    qs = Despesa.objects.filter(usuario=user)

    centro_param = request.GET.get("centro")
    ano = int(request.GET.get("ano") or 0)
    mes = int(request.GET.get("mes") or 0)

    hoje = now()
    if not (1 <= mes <= 12): mes = hoje.month
    if not ano: ano = hoje.year

    # restringe centros aos associados ao user
    centros_ids = (AssociacaoCentroCusto.objects
                   .filter(usuario=user, ativo=True)
                   .values_list("centro_id", flat=True))
    centros_user = CentroDeCusto.objects.filter(id__in=centros_ids, ativo=True).order_by("nome")

    centro = None
    if centro_param:
        try:
            cid = int(centro_param)
        except (TypeError, ValueError):
            cid = None
        if cid and cid in set(centros_ids):
            centro = Centrosel = get_object_or_404(centros_user, pk=cid)
            qs = qs.filter(centro=centro)

    qs = qs.filter(data_fato__year=ano, data_fato__month=mes).order_by("-data_fato","-criado_em","-id")

    kpi_total = qs.aggregate(v=Sum("valor"))["v"] or 0
    kpi_reemb = qs.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or 0
    kpi_pend = kpi_total - kpi_reemb

    ctx = {
        "escopo": "usuario",
        "periodo_label": mes_label_pt(ano, mes),
        "kpi_total": kpi_total, "kpi_reemb": kpi_reemb, "kpi_pend": kpi_pend,
        "itens": qs,
        "centros": centros_user,
        "centro_sel": centro,
        "sel_ano": ano, "sel_mes": mes,
    }
    return render(request, "relatorios/usuario.html", ctx)


'''
@staff_member_required
def relatorio_centro(request):
    """
    Relatório do ADMIN por Centro de Custo
    - ?centro=ID (obrigatório)
    - ?ano=YYYY & ?mes=MM (MM=01..12) ou mes=0 para TODOS os meses do ano
    - Extras: ?tipo=TODOS|REEMBOLSADAS|PENDENTES  e ?q=termo (busca)
    """
    # --- Centro ---
    centro_id = request.GET.get("centro")
    if not centro_id:
        return redirect(reverse("centros_index"))
    try:
        centro_id = int(centro_id)
    except (TypeError, ValueError):
        return redirect(reverse("centros_index"))

    centro = get_object_or_404(CentroDeCusto, pk=centro_id, ativo=True)

    # --- Período (defaults = mês/ano atual) ---
    hoje = now()
    try:
        ano = int(request.GET.get("ano") or hoje.year)
    except (TypeError, ValueError):
        ano = hoje.year

    raw_mes = request.GET.get("mes")
    if raw_mes is None:
        mes = hoje.month
    else:
        try:
            mes = int(raw_mes)
        except ValueError:
            mes = hoje.month

    # mes=0 => todos os meses do ano; se inválido (diferente de 0) cai no mês atual
    if mes != 0 and not (1 <= mes <= 12):
        mes = hoje.month

    # --- Base do período (para totais do período completo) ---
    qs_periodo = (
        Despesa.objects
        .filter(centro=centro, data_fato__year=ano)
        .select_related("usuario")
    )
    if mes != 0:
        qs_periodo = qs_periodo.filter(data_fato__month=mes)

    # --- KPIs do período (sem filtros tipo/q) com agregação única ---
    agg = qs_periodo.aggregate(
        total=Sum("valor"),
        aprovadas=Sum("valor", filter=Q(status=Despesa.Status.APROVADA)),
        pendentes=Sum("valor", filter=Q(status=Despesa.Status.PENDENTE)),
        reprovadas=Sum("valor", filter=Q(status=Despesa.Status.REPROVADA)),
    )
    total_mes           = agg["total"] or Decimal("0")
    total_reembolsadas  = agg["aprovadas"] or Decimal("0")
    total_pendentes     = agg["pendentes"] or Decimal("0")          # apenas PENDENTE
    total_nao_aprovadas = total_mes - total_reembolsadas            # pendente + reprovada (opcional)

    periodo_label = mes_label_pt(ano, mes) if mes != 0 else f"{ano} (TODOS os meses)"

    # --- Lista exibida (aplica filtros tipo/q) ---
    qs = qs_periodo.order_by("-data_fato", "-criado_em", "-id")

    tipo = (request.GET.get("tipo") or "TODOS").upper()
    if tipo == "REEMBOLSADAS":
        qs = qs.filter(status=Despesa.Status.APROVADA)
    elif tipo == "PENDENTES":
        qs = qs.filter(status=Despesa.Status.PENDENTE)  # mais preciso que "exclude aprovadas"

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q) |
            Q(descricao__icontains=q) |
            Q(usuario__first_name__icontains=q) |
            Q(usuario__last_name__icontains=q) |
            Q(usuario__username__icontains=q)
        )

    # --- Agregação por usuário com base na lista filtrada ---
    por_usuario = (
        qs.values("usuario__id", "usuario__first_name", "usuario__last_name", "usuario__username")
          .annotate(total=Sum("valor"))
          .order_by("-total")
    )

    # Para o select de meses (formato que o template espera)
    MESES_NUMEROS = [f"{i:02d}" for i in range(1, 13)]

    ctx = {
        "escopo": "centro",
        "centro": centro,
        "periodo_label": periodo_label,

        # KPIs (cards da UI)
        "kpi_total": total_mes,
        "kpi_reemb": total_reembolsadas,
        "kpi_pend": total_pendentes,

        # Também com os nomes "total_*" (compatibilidade)
        "total_mes": total_mes,
        "total_reembolsadas": total_reembolsadas,
        "total_pendentes": total_pendentes,
        "total_nao_aprovadas": total_nao_aprovadas,  # caso deseje usar no template

        # Lista e agrupamentos exibidos
        "despesas": qs,
        "itens": qs,  # compatibilidade
        "por_usuario": por_usuario,

        # Filtros/controles
        "sel_ano": ano,
        "sel_mes": mes,                 # pode ser 0
        "meses_numeros": MESES_NUMEROS, # ["01",...,"12"]
        "tipo": tipo,
        "q": q,
    }

    # Versão de impressão (A4)
    if request.GET.get("modo") == "print":
        return render(request, "relatorios/admin_centro_print.html", ctx)

    return render(request, "relatorios/admin_centro.html", ctx)
'''

from django.contrib.auth import get_user_model
User = get_user_model()

# views.py
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseBadRequest, HttpResponse
from django.contrib import messages
from django import forms
from django.utils import timezone

@staff_member_required
@require_http_methods(["GET", "POST"])
def despesas_lote_modal(request):
    # Detecta se é chamada via modal (AJAX) ou se pediram explicitamente o parcial
    is_partial = (
        request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
        or request.GET.get("partial") == "1"
        or request.POST.get("partial") == "1"
    )

    # --- coleta parâmetros (QS ou POST) ---
    raw_centro = request.GET.get("centro") or request.POST.get("centro")
    raw_user   = request.GET.get("user")   or request.POST.get("user")
    raw_ano    = request.GET.get("ano")    or request.POST.get("ano")
    raw_mes    = request.GET.get("mes")    or request.POST.get("mes")

    # valida período
    try:
        ano = int(raw_ano); mes = int(raw_mes)
    except (TypeError, ValueError):
        resp = render(request, "centros/_modal_lote_admin.html",
                      {"form_lote": None, "erro_parametros": True, "modal_kind": "lote"},
                      status=400)
        resp["X-Modal-Partial"] = "lote"
        return resp

    centro = None
    user_obj = None
    try:
        if raw_centro:
            centro = get_object_or_404(CentroDeCusto, pk=int(raw_centro), ativo=True)
    except (TypeError, ValueError):
        centro = None
    try:
        if raw_user:
            user_obj = get_object_or_404(User, pk=int(raw_user), is_active=True)
    except (TypeError, ValueError):
        user_obj = None

    if not centro and not user_obj:
        resp = render(request, "centros/_modal_lote_admin.html",
                      {"form_lote": None, "erro_parametros": True, "modal_kind": "lote"},
                      status=400)
        resp["X-Modal-Partial"] = "lote"
        return resp

    if request.method == "POST":
        form_lote = AdminLoteReembolsoForm(
            data=request.POST, files=request.FILES,
            centro=centro, ano=ano, mes=mes, user=user_obj
        )
        if form_lote.is_valid():
            try:
                count = form_lote.aplicar()
                messages.success(request, f"{count} despesa(s) atualizada(s) em lote.")
                # recria limpo para permanecer no modal
                form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano, mes=mes, user=user_obj)
                status_code = 200
            except forms.ValidationError as e:
                messages.error(request, e.messages[0] if e.messages else "Erro ao aplicar em lote.")
                status_code = 400
        else:
            messages.error(request, "Corrija os erros e tente novamente.")
            status_code = 400
    else:
        form_lote = AdminLoteReembolsoForm(centro=centro, ano=ano, mes=mes, user=user_obj)
        status_code = 200

    resp = render(request, "centros/_modal_lote_admin.html", {
        "form_lote": form_lote,
        "centro": centro, "user_obj": user_obj, "ano": ano, "mes": mes,
        "modal_kind": "lote",
    }, status=status_code)
    # Sinalização útil para seu JS (opcional)
    resp["X-Modal-Partial"] = "lote"
    return resp

from datetime import datetime

@staff_member_required
def relatorio_centro(request):
    # --- Centro ---
    centro_id = request.GET.get("centro")
    if not centro_id:
        return redirect(reverse("centros_index"))
    try:
        centro_id = int(centro_id)
    except (TypeError, ValueError):
        return redirect(reverse("centros_index"))

    centro = get_object_or_404(CentroDeCusto, pk=centro_id, ativo=True)

    # --- Colaborador (opcional) ---
    user_id = request.GET.get("user")
    colaborador = None
    if user_id:
        try:
            user_id = int(user_id)
            colaborador = get_object_or_404(User, pk=user_id, is_active=True)
        except (TypeError, ValueError):
            colaborador = None

    # --- Período (defaults = mês/ano atual) ---
    hoje = now()
    try:
        ano = int(request.GET.get("ano") or hoje.year)
    except (TypeError, ValueError):
        ano = hoje.year

    raw_mes = request.GET.get("mes")
    if raw_mes is None:
        mes = hoje.month
    else:
        try:
            mes = int(raw_mes)
        except ValueError:
            mes = hoje.month

    if mes != 0 and not (1 <= mes <= 12):
        mes = hoje.month

    # --- Base do período ---
    qs_periodo = (
        Despesa.objects
        .filter(centro=centro, data_fato__year=ano)
        .select_related("usuario")
    )
    if mes != 0:
        qs_periodo = qs_periodo.filter(data_fato__month=mes)

    if colaborador:
        qs_periodo = qs_periodo.filter(usuario=colaborador)

    # --- KPIs ---
    agg = qs_periodo.aggregate(
        bruto=Sum("valor"),
        aprovadas=Sum("valor", filter=Q(status=Despesa.Status.APROVADA)),
        pendentes=Sum("valor", filter=Q(status=Despesa.Status.PENDENTE)),
        reprovadas=Sum("valor", filter=Q(status=Despesa.Status.REPROVADA)),
    )
    total_bruto        = agg["bruto"] or Decimal("0")
    total_reprovadas   = agg["reprovadas"] or Decimal("0")
    total_mes          = total_bruto - total_reprovadas
    total_reembolsadas = agg["aprovadas"] or Decimal("0")
    total_pendentes    = agg["pendentes"] or Decimal("0")

    periodo_label = mes_label_pt(ano, mes) if mes != 0 else f"{ano} (TODOS os meses)"

    # --- Lista (com filtros opcionais) ---
    qs = qs_periodo.order_by("-data_fato", "-criado_em", "-id")

    tipo = (request.GET.get("tipo") or "TODOS").upper()
    if tipo == "REEMBOLSADAS":
        qs = qs.filter(status=Despesa.Status.APROVADA)
    elif tipo == "PENDENTES":
        qs = qs.filter(status=Despesa.Status.PENDENTE)

    # --- Busca por texto (insensível a maiúsculas/minúsculas) ---
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q) |
            Q(descricao__icontains=q) |
            Q(usuario__first_name__icontains=q) |
            Q(usuario__last_name__icontains=q) |
            Q(usuario__username__icontains=q)
        )

    # --- Filtro por período livre ---
    de_raw = request.GET.get("de", "").strip()
    ate_raw = request.GET.get("ate", "").strip()

    def parse_data(data_str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(data_str, fmt).date()
            except ValueError:
                continue
        return None

    de = parse_data(de_raw)
    ate = parse_data(ate_raw)

    if de:
        qs = qs.filter(data_fato__gte=de)
    if ate:
        qs = qs.filter(data_fato__lte=ate)

    # --- Agregação por usuário ---
    if colaborador:
        por_usuario = (
            qs.values("usuario__id", "usuario__first_name", "usuario__last_name", "usuario__username")
              .annotate(
                  total=Coalesce(
                      Sum("valor", filter=Q(status=Despesa.Status.APROVADA)),
                      Value(Decimal("0")),
                      output_field=Despesa._meta.get_field("valor"),
                  )
              )
              .order_by("-total")
        )
    else:
        por_usuario = (
            qs.values("usuario__id", "usuario__first_name", "usuario__last_name", "usuario__username")
              .annotate(
                  total=Coalesce(
                      Sum("valor", filter=~Q(status=Despesa.Status.REPROVADA)),
                      Value(Decimal("0")),
                      output_field=Despesa._meta.get_field("valor"),
                  )
              )
              .order_by("-total")
        )

    MESES_NUMEROS = [f"{i:02d}" for i in range(1, 13)]

    ctx = {
        "escopo": "centro",
        "centro": centro,
        "colaborador": colaborador,
        "periodo_label": periodo_label,

        # KPIs
        "kpi_total": total_mes,
        "kpi_reemb": total_reembolsadas,
        "kpi_pend":  total_pendentes,

        # Lista
        "despesas": qs,
        "itens": qs,
        "por_usuario": por_usuario,

        # Filtros
        "sel_ano": ano,
        "sel_mes": mes,
        "meses_numeros": MESES_NUMEROS,
        "tipo": tipo,
        "q": q,
        "de": de_raw,
        "ate": ate_raw,
        "user_sel": colaborador.pk if colaborador else None,
    }

    # --- PRINT (PDF) ---
    if request.GET.get("modo") == "print":
        if colaborador:
            qs_print = qs.exclude(status=Despesa.Status.REPROVADA)
            ctx_print = dict(ctx)
            ctx_print["despesas"] = qs_print
            ctx_print["itens"] = qs_print
            ctx_print["ocultou_reprovadas_no_print"] = True
            return render(request, "relatorios/admin_centro_print.html", ctx_print)

        return render(request, "relatorios/admin_centro_print.html", ctx)

    return render(request, "relatorios/admin_centro.html", ctx)

from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils.timezone import now
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def relatorio_colaborador(request):
    """
    Relatório do ADMIN por Colaborador dentro de um Centro de Custo.
    Parâmetros:
      - ?centro=ID (obrigatório)
      - ?user=ID   (obrigatório; id do usuário/colaborador)
      - ?ano=YYYY  (default: ano atual)
      - ?mes=MM    (1..12; ou 0 = TODOS os meses do ano)
      - Extras: ?tipo=TODOS|REEMBOLSADAS|PENDENTES  e ?q=termo (busca)
    Reaproveita o layout A4 existente (print) e a página padrão.
    """

    # --- Centro ---
    centro_id = request.GET.get("centro")
    user_id   = request.GET.get("user")
    if not centro_id or not user_id:
        return redirect(reverse("centros_index"))

    try:
        centro_id = int(centro_id)
        user_id   = int(user_id)
    except (TypeError, ValueError):
        return redirect(reverse("centros_index"))

    centro = get_object_or_404(CentroDeCusto, pk=centro_id, ativo=True)
    colaborador = get_object_or_404(User, pk=user_id, is_active=True)

    # --- Período (defaults = mês/ano atual) ---
    hoje = now()
    try:
        ano = int(request.GET.get("ano") or hoje.year)
    except (TypeError, ValueError):
        ano = hoje.year

    raw_mes = request.GET.get("mes")
    if raw_mes is None:
        mes = hoje.month
    else:
        try:
            mes = int(raw_mes)
        except ValueError:
            mes = hoje.month

    if mes != 0 and not (1 <= mes <= 12):
        mes = hoje.month

    # --- Base do período (para KPIs do período completo) ---
    qs_periodo = (
        Despesa.objects
        .filter(centro=centro, usuario=colaborador, data_fato__year=ano)
        .select_related("usuario")
    )
    if mes != 0:
        qs_periodo = qs_periodo.filter(data_fato__month=mes)
    # --- KPIs (uma agregação só) ---
    agg = qs_periodo.aggregate(
        total=Sum("valor"),
        aprovadas=Sum("valor", filter=Q(status=Despesa.Status.APROVADA)),
        pendentes=Sum("valor", filter=Q(status=Despesa.Status.PENDENTE)),
        reprovadas=Sum("valor", filter=Q(status=Despesa.Status.REPROVADA)),
    )
    total = agg["total"] or Decimal("0")
    reprovadas = agg["reprovadas"] or Decimal("0")
    kpi_total = total - reprovadas
    kpi_reemb = agg["aprovadas"] or Decimal("0")
    kpi_pend  = agg["pendentes"] or Decimal("0")

    periodo_label = mes_label_pt(ano, mes) if mes != 0 else f"{ano} (TODOS os meses)"

    # --- Lista exibida (aplica filtros tipo/q) ---
    qs = qs_periodo.order_by("-data_fato", "-criado_em", "-id")

    tipo = (request.GET.get("tipo") or "TODOS").upper()
    if tipo == "REEMBOLSADAS":
        qs = qs.filter(status=Despesa.Status.APROVADA)
    elif tipo == "PENDENTES":
        qs = qs.filter(status=Despesa.Status.PENDENTE)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q) |
            Q(descricao__icontains=q)
        )

    # “por_usuario” aqui terá um único colaborador — mantém compatibilidade do template
    por_usuario = (
        qs.values(
            "usuario__id",
            "usuario__first_name",
            "usuario__last_name",
            "usuario__username",
        )
        .annotate(
            total=Coalesce(
                Sum("valor", filter=~Q(status=Despesa.Status.REPROVADA)),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-total")
    )


    MESES_NUMEROS = [f"{i:02d}" for i in range(1, 13)]

    ctx = {
        "escopo": "colaborador",
        "centro": centro,
        "colaborador": colaborador,        # <<< usar no template A4
        "periodo_label": periodo_label,

        "kpi_total": kpi_total,
        "kpi_reemb": kpi_reemb,
        "kpi_pend":  kpi_pend,

        "despesas": qs,
        "itens": qs,                       # compat
        "por_usuario": por_usuario,

        "sel_ano": ano,
        "sel_mes": mes,
        "meses_numeros": MESES_NUMEROS,
        "tipo": tipo,
        "q": q,
    }

    if request.GET.get("modo") == "print":
        # reaproveita o A4 existente
        return render(request, "relatorios/admin_centro_print.html", ctx)

    # pode reaproveitar a mesma tela padrão
    return render(request, "relatorios/admin_centro.html", ctx)



@login_required
def centros_relatorio_redirect(request):
    params = request.GET.copy()  # centro, ano, mes, tipo...
    base = reverse("relatorio_centro")  # <-- agora vai para o relatório admin
    return redirect(f"{base}?{params.urlencode()}") if params else redirect(base)



# despesas/views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now

from .models import Despesa, CentroDeCusto, AssociacaoCentroCusto
from .utils import mes_label_pt, MesRef  # ajuste os imports utilitarios conforme o seu projeto


'''
@login_required
def meus_centros(request):
    user = request.user

    # ---------- filtro (mês/ano) ----------
    hoje = now()
    raw_ano = request.GET.get("ano")
    raw_mes = request.GET.get("mes")

    if raw_ano is None and raw_mes is None:
        sel_ano, sel_mes = hoje.year, hoje.month
    else:
        try:
            sel_ano = int(raw_ano) if raw_ano not in (None, "") else 0
        except ValueError:
            sel_ano = 0
        try:
            sel_mes = int(raw_mes) if raw_mes not in (None, "") else 0
        except ValueError:
            sel_mes = 0

    base_user = Despesa.objects.filter(usuario=user)

    # combos
    meses_qs = (
        base_user.annotate(m=TruncMonth("data_fato"))
        .values_list("m", flat=True).distinct().order_by("-m")
    )
    anos_disponiveis = sorted({d.year for d in meses_qs}, reverse=True)
    meses_numeros = [(i, f"{i:02d}")] * 0  # só para registrar a linha
    meses_numeros = [(i, f"{i:02d}") for i in range(1, 13)]
    meses_numeros.insert(0, (0, "TODOS"))

    if anos_disponiveis and sel_ano not in (*anos_disponiveis, 0):
        sel_ano = hoje.year if hoje.year in anos_disponiveis else 0
    if not (0 <= sel_mes <= 12):
        sel_mes = 0

    # ---------- escopo ----------
    escopo = base_user
    if sel_ano:
        escopo = escopo.filter(data_fato__year=sel_ano)
    if sel_mes:
        escopo = escopo.filter(data_fato__month=sel_mes)

    # KPIs do período (globais — todos os centros do usuário)
    total_mes = escopo.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_reemb = escopo.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_pend = total_mes - total_reemb

    # Centros associados ao usuário
    assoc_ids = (AssociacaoCentroCusto.objects
                 .filter(usuario=user, ativo=True)
                 .values_list("centro_id", flat=True))
    centros = CentroDeCusto.objects.filter(id__in=assoc_ids, ativo=True).order_by("nome")

    # rótulo do cabeçalho
    periodo_label = mes_label_pt(sel_ano, sel_mes) if sel_mes else (f"{sel_ano}" if sel_ano else "Todos os períodos")

    # “OUTROS MESES”
    meses_anteriores = []
    if sel_ano and sel_mes:
        meses_ant_qs = (
            base_user.exclude(data_fato__year=sel_ano, data_fato__month=sel_mes)
            .annotate(m=TruncMonth("data_fato"))
            .values_list("m", flat=True).distinct().order_by("-m")
        )
        for d in meses_ant_qs:
            mref = MesRef(ano=d.year, mes=d.month)
            label = mes_label_pt(mref.ano, mref.mes)
            meses_anteriores.append({"mref": mref, "label": label})

    return render(request, "viagens/meus_centros.html", {
        "centros": centros,
        "periodo_label": periodo_label,
        "total_mes": total_mes,
        "total_reembolsadas": total_reemb,
        "total_pendentes": total_pend,
        "meses_numeros": meses_numeros,
        "anos_disponiveis": [0, *anos_disponiveis],
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,
        "meses_anteriores": meses_anteriores,
    })
'''



@login_required
def viagens_centros(request):
    user = request.user
    hoje = now()

    # --- filtros mês/ano (0 = TODOS) ---
    raw_ano = request.GET.get("ano")
    raw_mes = request.GET.get("mes")

    if raw_ano is None and raw_mes is None:
        sel_ano, sel_mes = hoje.year, hoje.month
    else:
        try:
            sel_ano = int(raw_ano) if raw_ano not in (None, "") else 0
        except ValueError:
            sel_ano = 0
        try:
            sel_mes = int(raw_mes) if raw_mes not in (None, "") else 0
        except ValueError:
            sel_mes = 0

    base_user = Despesa.objects.filter(usuario=user)

    meses_qs = (
        base_user.annotate(m=TruncMonth("data_fato"))
        .values_list("m", flat=True).distinct().order_by("-m")
    )
    anos_disponiveis = sorted({d.year for d in meses_qs}, reverse=True)
    meses_numeros = [(0, "TODOS")] + [(i, f"{i:02d}") for i in range(1, 13)]

    if anos_disponiveis and sel_ano not in (*anos_disponiveis, 0):
        sel_ano = hoje.year if hoje.year in anos_disponiveis else 0
    if not (0 <= sel_mes <= 12):
        sel_mes = 0

    # --- escopo do período ---
    escopo = base_user
    if sel_ano:
        escopo = escopo.filter(data_fato__year=sel_ano)
    if sel_mes:
        escopo = escopo.filter(data_fato__month=sel_mes)

    # --- centros associados ao user ---
    assoc_ids = (AssociacaoCentroCusto.objects
                 .filter(usuario=user, ativo=True)
                 .values_list("centro_id", flat=True))
    centros = CentroDeCusto.objects.filter(id__in=assoc_ids, ativo=True).order_by("nome")

    # KPIs do período (globais)
#    total_mes = escopo.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_reemb = escopo.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_reprovado = escopo.filter(status=Despesa.Status.REPROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_mes1 = escopo.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    total_mes = total_mes1 - total_reprovado
    total_pend = total_mes - total_reemb

    # totais por centro
    centros_cards = []
    for c in centros:
        qs_c = escopo.filter(centro=c)
        k_total1 = qs_c.aggregate(v=Sum("valor"))["v"] or Decimal("0")
        k_reprovada = qs_c.filter(status=Despesa.Status.REPROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
        k_total = k_total1 - k_reprovada
        k_reemb = qs_c.filter(status=Despesa.Status.APROVADA).aggregate(v=Sum("valor"))["v"] or Decimal("0")
        k_pend  = k_total - k_reemb
        centros_cards.append({
            "centro": c,
            "k_total": k_total, "k_reemb": k_reemb, "k_pend": k_pend,
        })

    ctx = {
        "mes_corrente_label": mes_label_pt(sel_ano, sel_mes) if sel_ano and sel_mes else "Período selecionado",
        "total_mes": total_mes,
        "total_reembolsadas": total_reemb,
        "total_pendentes": total_pend,
        "centros_cards": centros_cards,
        "meses_numeros": meses_numeros,
        "anos_disponiveis": [0, *anos_disponiveis],
        "sel_ano": sel_ano,
        "sel_mes": sel_mes,
    }
    return render(request, "viagens/centros_usuario.html", ctx)

from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum

def _mes_anterior(dt):
    """Retorna (ano, mes) do mês anterior à data dt."""
    primeiro = dt.replace(day=1)
    ultimo_mes_anterior = primeiro - timedelta(days=1)
    return ultimo_mes_anterior.year, ultimo_mes_anterior.month



# views.py
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

@login_required
@require_POST
def despesa_delete(request, pk):
    """
    Colaborador exclui sua própria despesa *PENDENTE*.
    Preserva filtros retornando para a URL passada em return_to.
    """
    return_to = request.POST.get("return_to") or reverse("viagens_lista")

    d = get_object_or_404(Despesa, pk=pk, usuario=request.user)

    if d.status != Despesa.Status.PENDENTE:
        messages.error(request, "Só é possível excluir despesas em status PENDENTE.")
        return redirect(return_to)

    # (opcional) bloqueio por fechamento do mês:
    # if not despesa_editavel(d.criado_em):
    #     messages.error(request, "Este lançamento não pode mais ser excluído (mês fechado).")
    #     return redirect(return_to)

    d.delete()
    messages.success(request, "Despesa excluída com sucesso.")
    return redirect(return_to)



# views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils.text import slugify
from decimal import Decimal, InvalidOperation

@login_required
def api_pendentes_ultimas5_duplicadas(request):
    """
    Retorna JSON com grupos de duplicidade entre as *5 últimas* despesas PENDENTES
    do usuário logado. Duplicidade = (titulo_normalizado, valor, data_fato) iguais.
    """
    qs = (Despesa.objects
          .filter(usuario=request.user, status=Despesa.Status.PENDENTE)
          .order_by('-criado_em')[:5])

    def norm_titulo(s: str) -> str:
        s = (s or "").strip().lower()
        # remove espaços repetidos e normaliza
        s = " ".join(s.split())
        return slugify(s, allow_unicode=True)

    bucket = {}
    items = []
    for d in qs:
        # normaliza valor (2 casas) e data (YYYY-MM-DD)
        try:
            v = (Decimal(d.valor).quantize(Decimal("0.01")) if d.valor is not None else None)
        except (InvalidOperation, TypeError):
            v = None
        k = (norm_titulo(d.titulo), str(v) if v is not None else "", d.data_fato.isoformat() if d.data_fato else "")
        item = {
            "id": d.id,
            "titulo": d.titulo or "",
            "valor": str(v) if v is not None else "",
            "data_fato": d.data_fato.isoformat() if d.data_fato else "",
            "modal_url": reverse("despesa_modal", args=[d.id]),
        }
        items.append(item)
        bucket.setdefault(k, []).append(item)

    duplicates = []
    for k, group in bucket.items():
        if len(group) >= 2:
            titulo_norm, valor_norm, data_norm = k
            duplicates.append({
                "key": {
                    "titulo_norm": titulo_norm,
                    "valor": valor_norm,
                    "data_fato": data_norm,
                },
                "items": group,
                "ids": [it["id"] for it in group],
            })

    return JsonResponse({
        "count": len(duplicates),
        "duplicates": duplicates,
    })



from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Max, Count, Q
from decimal import Decimal

from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Max, Count, Q
from decimal import Decimal

@login_required
@user_passes_test(_is_admin)
@require_http_methods(["GET", "POST"])
def centros_pendentes_summary(request):
    """
    Partial: resumo de pendentes por colaborador, agora respeitando mes/ano (e opcionalmente centro).
    Aceita parâmetros (POST ou GET):
      - top: int (limite)
      - escopo_associados: bool
      - mes: int (1-12) opcional
      - ano: int opcional
      - centro: int opcional (id do CentroDeCusto) — se fornecido, filtra pelo centro
    """
    # parâmetros básicos
    top_n = request.POST.get("top") or request.GET.get("top") or None
    try:
        top_n = int(top_n) if top_n else None
    except ValueError:
        top_n = None

    escopo_associados = (request.POST.get("escopo_associados", request.GET.get("escopo_associados", "")).lower() in ("1","true","t","y","yes"))

    # novo: mês/ano/centro opcionais para filtro temporal/por centro
    raw_mes = request.POST.get("mes", request.GET.get("mes", ""))
    raw_ano = request.POST.get("ano", request.GET.get("ano", ""))
    raw_centro = request.POST.get("centro", request.GET.get("centro", ""))

    try:
        sel_mes = int(raw_mes) if raw_mes else None
        if sel_mes and not (1 <= sel_mes <= 12):
            sel_mes = None
    except ValueError:
        sel_mes = None

    try:
        sel_ano = int(raw_ano) if raw_ano else None
    except ValueError:
        sel_ano = None

    try:
        sel_centro = int(raw_centro) if raw_centro else None
    except ValueError:
        sel_centro = None

    # base: pendentes (dois status)
    pend_qs = Despesa.objects.filter(status__in=[Despesa.Status.PENDENTE, Despesa.Status.PENDENTE_PAGTO])

    # aplicar filtro por mês/ano quando fornecido
    if sel_ano:
        pend_qs = pend_qs.filter(data_fato__year=sel_ano)
    if sel_mes:
        pend_qs = pend_qs.filter(data_fato__month=sel_mes)

    # aplicar filtro por centro se fornecido
    if sel_centro:
        pend_qs = pend_qs.filter(centro_id=sel_centro)

    # escopo de associados (opcional)
    if escopo_associados:
        user_ids_scope = AssociacaoCentroCusto.objects.filter(ativo=True).values_list("usuario_id", flat=True)
        pend_qs = pend_qs.filter(usuario_id__in=user_ids_scope)

    # agregação por usuário (mantém mesma estrutura)
    agreg = (
        pend_qs.values("usuario")
        .annotate(
            valor_pend_analise=Sum("valor", filter=Q(status=Despesa.Status.PENDENTE)),
            valor_pend_pagto=Sum("valor", filter=Q(status=Despesa.Status.PENDENTE_PAGTO)),
            ultima_criacao=Max("criado_em"),
            qtd_total=Count("id"),
        )
        .order_by("-ultima_criacao")
    )

    if top_n:
        agreg = agreg[:top_n]

    user_ids = [a["usuario"] for a in agreg]
    users = {u.id: u for u in User.objects.filter(id__in=user_ids)}

    pendentes_analise = []
    pendentes_pagamento = []
    total_analise = Decimal("0")
    total_pagamento = Decimal("0")

    for a in agreg:
        u = users.get(a["usuario"])
        if not u:
            continue
        v_analise = a.get("valor_pend_analise") or Decimal("0")
        v_pagto = a.get("valor_pend_pagto") or Decimal("0")
        item = {
            "usuario": u,
            "valor_pend_analise": v_analise,
            "valor_pend_pagto": v_pagto,
            "valor_total": v_analise + v_pagto,
            "ultima_criacao": a.get("ultima_criacao"),
            "qtd_total": a.get("qtd_total") or 0,
        }
        if v_analise and v_analise > 0:
            pendentes_analise.append(item)
            total_analise += v_analise
        if v_pagto and v_pagto > 0:
            pendentes_pagamento.append(item)
            total_pagamento += v_pagto

    ctx = {
        "pendentes_analise": pendentes_analise,
        "pendentes_pagamento": pendentes_pagamento,
        "pendentes_analise_total": total_analise,
        "pendentes_pagamento_total": total_pagamento,
        "qs_base": request.POST.get("qs_base", request.GET.get("qs_base", "")),
        # opcional: ecoar sel_mes/sel_ano para o template se quiser mostrar label
        "sel_mes": sel_mes,
        "sel_ano": sel_ano,
        "sel_centro": sel_centro,
    }
    return render(request, "centros/_pendentes_summary.html", ctx)
