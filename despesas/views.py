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
from .models import Contrato
from django.contrib.auth import logout  # já deve ter: login_class required, messages, etc.
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
from .models import CentroDeCusto, AssociacaoCentroCusto, Despesa, VinculoFuncionarioCentro
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
from .utils.mes_label_pt import mes_label_pt, MesRef

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

@login_required
def home(request):
    return render(request, "home.html")

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
from push_notifications.models import WebPushDevice
from django.contrib.auth.models import User
from .models import NotificacaoConfig

def notify(message, users=None, icon=None, url=None):
    """
    Envia push notification para um ou mais usuários.
    users=None envia para TODOS com dispositivo registrado.
    """
    # 1. Verificar se notificações de status estão habilitadas
    config = NotificacaoConfig.objects.filter(chave="alteracao_status_etapa").first()
    if config and not config.habilitado:
        return False  # notificações desligadas pelo admin

    payload = {
        "title": "Notificação do Sistema",
        "body": message,
        "icon": icon or "/static/img/notificacao_icon.png",
        "data": {"url": url or "/"},
    }

    # 2. Determinar usuários
    if users is None:
        dispositivos = WebPushDevice.objects.all()
    else:
        if not isinstance(users, (list, tuple)):
            users = [users]
        dispositivos = WebPushDevice.objects.filter(user__in=users)

    # 3. Enviar
    for dev in dispositivos:
        dev.send_message(message, extra=payload)

    return True



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
  # (ajuste o import se seu helper estiver noutro módulo)


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
    """
    d = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=pk
    )

    # --- filtros (da URL e/ou dos hiddens do form) ---
    def _to_int(val, default=None):
        try:
            # Garante limpeza caso venha string suja de lista (ex: "['1']")
            if isinstance(val, str):
                val = val.replace('[', '').replace(']', '').replace("'", "").replace('"', "")
            return int(val) if val not in (None, "") else default
        except (TypeError, ValueError):
            return default

    centro_id = _to_int(request.GET.get("centro") or request.POST.get("centro"))
    user_id   = _to_int(request.GET.get("user")   or request.POST.get("user"))
    ano       = _to_int(request.GET.get("ano")    or request.POST.get("ano"))
    mes       = _to_int(request.GET.get("mes")    or request.POST.get("mes"))
    st_param  = ((request.GET.get("st") or request.POST.get("st") or "").upper().strip())

    st_val = STATUS_MAP.get(st_param) if st_param else None

    # --- queryset filtrado ---
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

    # Se a despesa atual não está no filtro (ex: status mudou), mas usuário clicou nav,
    # tentamos encontrar o vizinho mais lógico ou manter o atual.
    if d.id not in ids:
        # Fallback: se não achou no filtro, mas tem nav, tenta ir para o primeiro/último ou stay
        # Mas para evitar saltos lógicos perigosos, mantemos o target_id e o aviso de 'fora do filtro'
        pass
    else:
        if nav == "next" and next_id:
            target_id = next_id
        elif nav == "prev" and prev_id:
            target_id = prev_id

    target = get_object_or_404(
        Despesa.objects.select_related("centro", "usuario"),
        pk=target_id
    )
    t_prev, t_next = _prev_next_ids(target.id)

    # --- reconstruir qs ---
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
        # CORREÇÃO AQUI: Passar o objeto QueryDict, não dict de listas
        "preserved": preserved,
        "fora_do_filtro": (target.id not in ids),
    })
    resp["X-Modal-Partial"] = "despesa"
    return resp

import os
import io
import re
import json
import tempfile
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

import os
import io
import re
import json
import tempfile
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

import os
import io
import re
import json
import tempfile
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

os.environ['TESSDATA_PREFIX'] = '/home/conmac/tessdata'

# Diretório temporário para jobs em andamento
JOBS_DIR = '/tmp/ocr_jobs'
os.makedirs(JOBS_DIR, exist_ok=True)

CHUNK_SIZE = 4

# ─── PODER DE PROCESSAMENTO ───────────────────────────────────────────────────
# Ajuste empírico: 1 (mais lento/seguro) → 4 (mais rápido/agressivo).
# Com 5 workers no PythonAnywhere, recomenda-se começar em 2 e subir gradualmente.
# Afeta: threads do Poppler e nível de compressão PNG.
COMPRESSION_POWER = 2 # ← altere aqui para testar

_POPPLER_THREADS = max(1, COMPRESSION_POWER)          # threads no convert_from_path
_PNG_COMPRESS    = max(1, 9 - COMPRESSION_POWER * 2)  # 1=rápido … 7=menor arquivo
# power=1 → compress=7  |  power=2 → compress=5  |  power=3 → compress=3  |  power=4 → compress=1

# pytesseract abre subprocessos internamente — paralelismo de páginas pode causar
# falhas silenciosas no PythonAnywhere. Mantenha em 1 até confirmar estabilidade.
# Suba para 2 apenas para testes controlados com poucos usuários simultâneos.
_PAGE_WORKERS = 2 # ← altere com cautela

# ─── PRESETS ─────────────────────────────────────────────────────────────────

PRESETS = {
    "ultra": {
        "dpi": 72,
        "threshold": 200,
        "label": "Ultra",
        "est_per_page_kb": 11,
        "description": "Menor tamanho possível. Adequado para arquivos com texto grande.",
    },
    "leve": {
        "dpi": 85,
        "threshold": 200,
        "label": "Leve",
        "est_per_page_kb": 15,
        "description": "Bom balanço para documentos de texto (ofícios, decretos, leis).",
    },
    "equilibrado": {
        "dpi": 100,
        "threshold": 195,
        "label": "Equilibrado",
        "est_per_page_kb": 19,
        "description": "Recomendado. Textos nítidos, tamanho controlado.",
    },
    "qualidade": {
        "dpi": 120,
        "threshold": 190,
        "label": "Qualidade",
        "est_per_page_kb": 25,
        "description": "Mais nítido. Bom para PDFs com tabelas ou texto pequeno.",
    },
}

# ─── UTILITÁRIOS ─────────────────────────────────────────────────────────────

def _bytes_to_mb(b):
    return round(b / (1024 * 1024), 3)


def _get_effective_lang(desired="por+eng"):
    import subprocess
    try:
        env = os.environ.copy()
        env['TESSDATA_PREFIX'] = '/home/conmac/tessdata'
        result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        available = result.stderr + result.stdout
        requested = [l for l in desired.split('+') if l in available]
        return '+'.join(requested) if requested else 'eng'
    except Exception:
        return 'eng'


def _job_dir(job_id):
    return os.path.join(JOBS_DIR, job_id)


def _job_meta(job_id):
    path = os.path.join(_job_dir(job_id), 'meta.json')
    with open(path) as f:
        return json.load(f)


def _save_meta(job_id, meta):
    path = os.path.join(_job_dir(job_id), 'meta.json')
    with open(path, 'w') as f:
        json.dump(meta, f)


# ─── NÚCLEO ──────────────────────────────────────────────────────────────────

def _make_ocr_page(pil_img, dpi, threshold, lang):
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
    import pytesseract

    gray = pil_img.convert('L')
    bw = gray.point(lambda x: 255 if x > threshold else 0)

    w_px, h_px = bw.size
    w_pt = w_px * 72.0 / dpi
    h_pt = h_px * 72.0 / dpi

    img_buf = io.BytesIO()
    # _PNG_COMPRESS deriva de COMPRESSION_POWER: mais poder = menos compressão PNG = mais rápido
    bw.save(img_buf, format='PNG', compress_level=_PNG_COMPRESS, optimize=True)
    img_buf.seek(0)

    pdf_buf = io.BytesIO()
    c = rl_canvas.Canvas(pdf_buf, pagesize=(w_pt, h_pt))
    c.drawImage(ImageReader(img_buf), 0, 0, width=w_pt, height=h_pt)

    try:
        hocr = pytesseract.image_to_pdf_or_hocr(
            gray,
            extension='hocr',
            lang=lang,
            config='--oem 1 --psm 3',  # oem 1 = LSTM only (sem engine legado); psm 3 = sem OSD
            timeout=25,
        )
    except Exception:
        hocr = b""

    word_pattern = re.compile(
        rb"title='bbox (\d+) (\d+) (\d+) (\d+)[^']*'[^>]*>([^<]+)<",
        re.IGNORECASE,
    )
    for m in word_pattern.finditer(hocr):
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        word = m.group(5).decode('utf-8', errors='replace').strip()
        if not word:
            continue
        x_pt = x1 * 72.0 / dpi
        y_pt = h_pt - y2 * 72.0 / dpi
        fs = max(4.0, min((y2 - y1) * 72.0 / dpi * 0.85, 22.0))
        c.setFont("Helvetica", fs)
        c.setFillColorRGB(0, 0, 0, 0)
        try:
            c.drawString(x_pt, y_pt, word)
        except Exception:
            pass

    c.showPage()
    c.save()
    return pdf_buf.getvalue()


# ─── VIEWS ───────────────────────────────────────────────────────────────────

def ocr_compress_page(request):
    lang = _get_effective_lang("por+eng")
    return render(request, "compress_pdf.html", {
        "presets": PRESETS,
        "ocr_lang": lang,
        "ocr_por_ok": "por" in lang,
    })


@require_http_methods(["POST"])
def ocr_iniciar(request):
    """
    Passo 1: recebe o PDF, salva no disco, retorna job_id e total de páginas.
    """
    from pypdf import PdfReader

    pdf_file = request.FILES.get("pdf_file")
    preset_key = request.POST.get("preset", "equilibrado")

    if not pdf_file:
        return JsonResponse({"erro": "Nenhum arquivo enviado."}, status=400)
    if not pdf_file.name.lower().endswith(".pdf"):
        return JsonResponse({"erro": "Apenas arquivos PDF são suportados."}, status=400)
    if preset_key not in PRESETS:
        preset_key = "equilibrado"

    job_id = str(uuid.uuid4())
    jdir = _job_dir(job_id)
    os.makedirs(jdir, exist_ok=True)

    # Salva PDF original
    input_bytes = pdf_file.read()
    input_path = os.path.join(jdir, 'input.pdf')
    with open(input_path, 'wb') as f:
        f.write(input_bytes)

    # Conta páginas
    reader = PdfReader(io.BytesIO(input_bytes))
    total_pages = len(reader.pages)
    total_chunks = (total_pages + CHUNK_SIZE - 1) // CHUNK_SIZE

    # Salva metadados do job
    _save_meta(job_id, {
        "preset_key": preset_key,
        "original_name": pdf_file.name,
        "original_bytes": len(input_bytes),
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "chunks_done": 0,
        "lang": _get_effective_lang("por+eng"),
    })

    return JsonResponse({
        "job_id": job_id,
        "total_pages": total_pages,
        "total_chunks": total_chunks,
        "chunk_size": CHUNK_SIZE,
    })


@require_http_methods(["POST"])
def ocr_processar_chunk(request):
    """
    Passo 2: processa um chunk de páginas. Chamado repetidamente pelo frontend.
    """
    from pdf2image import convert_from_path
    from pypdf import PdfWriter, PdfReader

    try:
        body = json.loads(request.body)
        job_id = body.get("job_id")
        chunk_index = int(body.get("chunk_index", 0))
    except Exception:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    jdir = _job_dir(job_id)
    if not os.path.exists(jdir):
        return JsonResponse({"erro": "Job não encontrado."}, status=404)

    meta = _job_meta(job_id)
    preset = PRESETS[meta["preset_key"]]
    dpi = preset["dpi"]
    threshold = preset["threshold"]
    lang = meta["lang"]
    total_pages = meta["total_pages"]

    first_page = chunk_index * CHUNK_SIZE + 1
    last_page = min(first_page + CHUNK_SIZE - 1, total_pages)

    input_path = os.path.join(jdir, 'input.pdf')

    import time
    t0 = time.time()

    # _POPPLER_THREADS acelera a rasterização do Poppler
    images = convert_from_path(
        input_path,
        dpi=dpi,
        fmt='jpeg',
        first_page=first_page,
        last_page=last_page,
        thread_count=_POPPLER_THREADS,
    )
    t_poppler = round(time.time() - t0, 2)

    # Processa páginas do chunk em paralelo, mantendo a ordem original
    def _process_page(img):
        return _make_ocr_page(img, dpi, threshold, lang)

    page_bytes_ordered = [None] * len(images)

    with ThreadPoolExecutor(max_workers=_PAGE_WORKERS) as executor:
        futures = {executor.submit(_process_page, img): idx for idx, img in enumerate(images)}
        for future in as_completed(futures):
            idx = futures[future]
            page_bytes_ordered[idx] = future.result()

    t_ocr = round(time.time() - t0 - t_poppler, 2)

    writer = PdfWriter()
    for page_bytes in page_bytes_ordered:
        reader = PdfReader(io.BytesIO(page_bytes))
        writer.add_page(reader.pages[0])

    chunk_path = os.path.join(jdir, f'chunk_{chunk_index:04d}.pdf')
    with open(chunk_path, 'wb') as f:
        writer.write(f)

    t_total = round(time.time() - t0, 2)

    # Atualiza progresso
    meta["chunks_done"] = chunk_index + 1
    _save_meta(job_id, meta)

    return JsonResponse({
        "ok": True,
        "chunk_index": chunk_index,
        "pages_processed": last_page,
        "total_pages": total_pages,
        "chunks_done": meta["chunks_done"],
        "total_chunks": meta["total_chunks"],
        # diagnóstico de tempo — remova quando não precisar mais
        "debug_t_poppler_s": t_poppler,
        "debug_t_ocr_s": t_ocr,
        "debug_t_total_s": t_total,
    })


@require_http_methods(["POST"])
def ocr_finalizar(request):
    """
    Passo 3: mescla todos os chunks e devolve o PDF final para download.
    """
    from pypdf import PdfWriter, PdfReader

    try:
        body = json.loads(request.body)
        job_id = body.get("job_id")
    except Exception:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    jdir = _job_dir(job_id)
    if not os.path.exists(jdir):
        return JsonResponse({"erro": "Job não encontrado."}, status=404)

    meta = _job_meta(job_id)

    # Ordena e mescla todos os chunks
    writer = PdfWriter()
    for i in range(meta["total_chunks"]):
        chunk_path = os.path.join(jdir, f'chunk_{i:04d}.pdf')
        if not os.path.exists(chunk_path):
            return JsonResponse(
                {"erro": f"Chunk {i} não encontrado. Processe todos os chunks primeiro."},
                status=400,
            )
        reader = PdfReader(chunk_path)
        for page in reader.pages:
            writer.add_page(page)

    output_buf = io.BytesIO()
    writer.write(output_buf)
    output_bytes = output_buf.getvalue()

    # Limpa arquivos temporários do job
    shutil.rmtree(jdir, ignore_errors=True)

    original_bytes = meta["original_bytes"]
    final_mb = _bytes_to_mb(len(output_bytes))
    reduction = round((1 - len(output_bytes) / original_bytes) * 100, 1) if original_bytes > 0 else 0

    base_name = os.path.splitext(meta["original_name"])[0]
    output_name = f"{base_name}_OCR_{final_mb}MB.pdf"

    response = HttpResponse(output_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{output_name}"'
    response["X-Original-MB"]   = str(_bytes_to_mb(original_bytes))
    response["X-Final-MB"]      = str(final_mb)
    response["X-Pages"]         = str(meta["total_pages"])
    response["X-DPI"]           = str(PRESETS[meta["preset_key"]]["dpi"])
    response["X-Preset"]        = PRESETS[meta["preset_key"]]["label"]
    response["X-Lang"]          = meta["lang"]
    response["X-Reduction-Pct"] = str(reduction)
    return response

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

from django.conf import settings


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


from datetime import date
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.timezone import now
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator

@login_required
@user_passes_test(_is_admin)
def centros_index(request):
    # ==========================================================
    # --- PROCESSAMENTO DO CARTÃO (POST) ---
    # ==========================================================
    if request.method == "POST":
        raw_user_post = request.POST.get("user_id")
        if raw_user_post:
            user_post = get_object_or_404(User, pk=int(raw_user_post))
            cartao = getattr(user_post, 'cartao_corporativo', None)

            if cartao and cartao.habilitado:
                action = request.POST.get("action")

                # AÇÃO: RECARREGAR
                if action == "recarregar":
                    tipo = request.POST.get("tipo_recarga")

                    if tipo == "aprovadas":
                        val_str = request.POST.get("valor_aprovadas", "0").replace(',', '.')
                    else:
                        val_str = request.POST.get("valor_especifico", "0").replace(',', '.')

                    try:
                        valor_recarga = Decimal(val_str)
                    except (ValueError, TypeError):
                        valor_recarga = Decimal('0.00')

                    if valor_recarga > 0:
                        if cartao.excedente > 0:
                            if valor_recarga >= cartao.excedente:
                                valor_recarga -= cartao.excedente
                                cartao.excedente = Decimal('0.00')
                            else:
                                cartao.excedente -= valor_recarga
                                valor_recarga = Decimal('0.00')

                        cartao.saldo_atual += valor_recarga
                        cartao.save()

                # AÇÃO: ALTERAR LIMITE
                elif action == "alterar_limite":
                    val_str = request.POST.get("novo_limite", "0").replace(',', '.')
                    try:
                        novo_limite = Decimal(val_str)
                    except (ValueError, TypeError):
                        novo_limite = Decimal('0.00')

                    if novo_limite > 0:
                        cartao.limite = novo_limite
                        cartao.save()

        get_params = request.GET.urlencode()
        return redirect(f"{request.path}?{get_params}")
    # ==========================================================

    # --------- Parâmetros de Filtro Multi-Select ---------
    raw_centros = request.GET.getlist("centro")
    raw_users   = request.GET.getlist("user")
    raw_meses   = request.GET.getlist("mes")

    centros_int = [int(c) for c in raw_centros if c.isdigit()]
    users_int   = [int(u) for u in raw_users if u.isdigit()]
    meses_int   = [int(m) for m in raw_meses if m.isdigit() and 1 <= int(m) <= 12]

    try:
        sel_ano = int(request.GET.get("ano") or 0)
    except ValueError:
        sel_ano = 0

    hoje = now()
    if not meses_int:
        meses_int = [hoje.month]
    if not sel_ano:
        sel_ano = hoje.year

    # --------- Filtro por Status ---------
    raw_status = request.GET.get("st", request.GET.get("status", "TODOS"))
    raw_status = (raw_status or "TODOS").strip().upper()

    STATUS_MAP = {
        "TODOS": None,
        "PENDENTE": Despesa.Status.PENDENTE,
        "PENDENTE_PAGTO": Despesa.Status.PENDENTE_PAGTO,
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

    # --------- Querysets de Referência (Dropdowns) ---------
    centros = CentroDeCusto.objects.filter(ativo=True).order_by("nome")

    analistas_all = User.objects.filter(
        is_active=True,
        id__in=AssociacaoCentroCusto.objects.filter(ativo=True).values("usuario_id")
    ).order_by("first_name", "last_name", "username")

    if centros_int:
        analistas_opts = analistas_all.filter(
            id__in=AssociacaoCentroCusto.objects.filter(
                centro_id__in=centros_int, ativo=True
            ).values("usuario_id")
        )
    else:
        analistas_opts = analistas_all

    centro_unico = get_object_or_404(centros, pk=centros_int[0]) if len(centros_int) == 1 else None
    user_unico   = get_object_or_404(analistas_all, pk=users_int[0]) if len(users_int) == 1 else None

    # --------- Base e Período ---------
    base = Despesa.objects.all()
    periodo_base = base.filter(data_fato__year=sel_ano, data_fato__month__in=meses_int)

    if centros_int:
        periodo_base = periodo_base.filter(centro_id__in=centros_int)
    if users_int:
        periodo_base = periodo_base.filter(usuario_id__in=users_int)

    if STATUS_MAP[sel_status] is not None:
        periodo = periodo_base.filter(status=STATUS_MAP[sel_status])
    else:
        periodo = periodo_base

    # --------- KPIs ---------
    total_bruto  = periodo.aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_aprov  = periodo.filter(status=Despesa.Status.APROVADA).aggregate(s=Sum("valor"))["s"] or Decimal("0")
    total_reprov = periodo.filter(status=Despesa.Status.REPROVADA).aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_analise = periodo.filter(status=Despesa.Status.PENDENTE).aggregate(s=Sum("valor"))["s"] or Decimal("0")
    pend_pagto   = periodo.filter(status=Despesa.Status.PENDENTE_PAGTO).aggregate(s=Sum("valor"))["s"] or Decimal("0")

    total_mes      = total_bruto - total_reprov
    total_pendentes = pend_analise + pend_pagto

    # --------- Lista Paginada ---------
    pagina = request.GET.get("p", 1)
    despesas_mes = []
    if centros_int or users_int:
        qs_lista = periodo.order_by("-data_fato", "-criado_em", "-id")
        despesas_mes = Paginator(qs_lista, 5).get_page(pagina)

    # --------- Meses Anteriores (Histórico) ---------
    meses_anteriores = []
    if centros_int:
        outros_meses = (base.filter(centro_id__in=centros_int)
                          .exclude(data_fato__year=sel_ano, data_fato__month__in=meses_int)
                          .annotate(m=TruncMonth("data_fato"))
                          .values_list("m", flat=True).distinct().order_by("-m"))
        for d in outros_meses:
            meses_anteriores.append({
                "label": _label_mes_pt(d.year, d.month),
                "ano": d.year,
                "mes": d.month
            })

    # --------- Associados ---------
    associados = []
    if centros_int and not users_int:
        associados = (AssociacaoCentroCusto.objects
                      .filter(centro_id__in=centros_int, ativo=True)
                      .select_related("usuario")
                      .order_by("usuario__first_name", "usuario__last_name"))

    # --------- ALERTA: Pendências ---------
    min_mes = min(meses_int)
    inicio_mes_selecionado = date(sel_ano, min_mes, 1)

    pend_prev_qs = Despesa.objects.filter(
        data_fato__lt=inicio_mes_selecionado,
        status__in=[Despesa.Status.PENDENTE, Despesa.Status.PENDENTE_PAGTO],
    )
    if centros_int:
        pend_prev_qs = pend_prev_qs.filter(centro_id__in=centros_int)
    if users_int:
        pend_prev_qs = pend_prev_qs.filter(usuario_id__in=users_int)

    pend_count = pend_prev_qs.count()
    pend_total = pend_prev_qs.aggregate(v=Sum("valor"))["v"] or Decimal("0")
    alerta_pendencias = None

    if pend_count > 0:
        alerta_pendencias = {
            "label_mes": f"anteriores a {_label_mes_pt(sel_ano, min_mes)}",
            "quantidade": pend_count,
            "valor_total": pend_total,
            "qtd_analise": pend_prev_qs.filter(status=Despesa.Status.PENDENTE).count(),
            "qtd_pagto": pend_prev_qs.filter(status=Despesa.Status.PENDENTE_PAGTO).count(),
        }

    # --------- Labels Inteligentes ---------
    if not centros_int:
        centro_label = "Todos os Centros"
    elif len(centros_int) == 1:
        centro_label = centro_unico.nome
    else:
        centro_label = f"{len(centros_int)} centros"

    if not users_int:
        user_label = "Todos os Analistas"
    elif len(users_int) == 1:
        user_label = user_unico.get_full_name() or user_unico.username
    else:
        user_label = f"{len(users_int)} analistas"

    MESES_NOME = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                  'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
    if len(meses_int) == 12:
        meses_label = "Todos os meses"
    elif len(meses_int) == 1:
        meses_label = MESES_NOME[meses_int[0] - 1]
    else:
        meses_label = ", ".join(MESES_NOME[m - 1][:3] for m in sorted(meses_int))

    anos_disponiveis, _ = _meses_anos_disponiveis(base)
    meses_numeros = [(i, f"{i:02d}") for i in range(1, 13)]

    # --------- Reconstrução da QueryString ---------
    qs_dict = request.GET.copy()
    if 'p' in qs_dict:
        del qs_dict['p']

    # CORREÇÃO: 'ano' e 'mes' podem não estar em request.GET quando foram
    # aplicados como valores padrão. Forçamos os valores computados para
    # garantir que qs_base seja sempre completo (ex: URLs dos modais de lote).
    qs_dict['ano'] = str(sel_ano)
    qs_dict.setlist('mes', [str(m) for m in meses_int])

    qs_base = qs_dict.urlencode()

    # --------- Cartão Corporativo ---------
    cartao_admin = getattr(user_unico, 'cartao_corporativo', None) if user_unico else None

    ctx = {
        "centros": centros,
        "analistas_opts": analistas_opts,
        "status_opts": status_opts,

        "centros_sel": centros_int,
        "users_sel": users_int,
        "meses_sel": meses_int,
        "sel_ano": sel_ano,
        "sel_status": sel_status,

        "centro_unico": centro_unico,
        "user_unico": user_unico,

        "centro_label": centro_label,
        "user_label": user_label,
        "meses_label": meses_label,

        "mes_label": _label_mes_pt(sel_ano, min_mes) if len(meses_int) == 1 else meses_label,
        "total_mes": total_mes,
        "total_reembolsadas": total_aprov,
        "total_pendentes": total_pendentes,

        "despesas_mes": despesas_mes,
        "meses_anteriores": meses_anteriores,
        "associados": associados,

        "anos_disponiveis": anos_disponiveis,
        "meses_numeros": meses_numeros,

        "alerta_pendencias": alerta_pendencias,
        "qs_base": qs_base,

        "cartao_admin": cartao_admin,
        "total_aprov_mes": total_aprov,
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
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from decimal import Decimal
from django.contrib.auth import get_user_model
from .models import CentroDeCusto, Despesa # Confirme se o caminho está certo
from .forms import AdminLoteReembolsoForm  # Confirme se o caminho está certo

User = get_user_model() # Isso corrige o erro de referência ao User

# Substitua a view despesas_lote_modal existente por esta versão corrigida

# Em views.py

from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.db import transaction  # <--- IMPORTANTE: Importação necessária
from decimal import Decimal
# Certifique-se de importar seus Models e Forms aqui (ex: CentroDeCusto, User, AdminLoteReembolsoForm)

def despesas_lote_modal(request):
    """
    Modal para alteração de status em lote.
    """

    # ── UTILITÁRIOS ──────────────────────────────────────────────────────
    def safe_int(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    def clean_param(val):
        """
        Normaliza o valor antes de converter para int.
        Protege contra casos como "[4]" ou "4,5" que podem vir
        de uma QueryString mal montada (ex: lista serializada como string).
        """
        if not val:
            return val
        return val.strip().strip("[]").split(",")[0].strip()

    # 1. Recupera parâmetros (prioriza GET para garantir a URL correta, depois POST)
    raw_centro = clean_param(request.GET.get("centro") or request.POST.get("centro"))
    raw_user   = clean_param(request.GET.get("user")   or request.POST.get("user"))
    raw_ano    = clean_param(request.GET.get("ano")    or request.POST.get("ano"))
    raw_mes    = clean_param(request.GET.get("mes")    or request.POST.get("mes"))

    # 2. Conversão segura de inteiros
    centro_id = safe_int(raw_centro)
    user_id   = safe_int(raw_user)
    ano       = safe_int(raw_ano)
    mes       = safe_int(raw_mes)

    # 3. Validação Básica
    if (not centro_id and not user_id) or not ano or not mes:
        resp = render(request, "centros/_modal_reembolso_lote.html",
                      {"erro_parametros": True, "msg": "Parâmetros de filtro perdidos."},
                      status=400)
        resp["X-Modal-Partial"] = "lote"
        return resp

    # 4. Busca Objetos
    centro = None
    if centro_id:
        centro = get_object_or_404(CentroDeCusto, pk=centro_id)

    user_obj = None
    colaborador_nome = None
    if user_id:
        user_obj = get_object_or_404(User, pk=user_id)
        colaborador_nome = user_obj.get_full_name() or user_obj.username

    # 5. Processamento POST
    if request.method == "POST":
        form_lote = AdminLoteReembolsoForm(
            data=request.POST,
            files=request.FILES,
            centro=centro,
            ano=ano,
            mes=mes,
            user=user_obj
        )

        if form_lote.is_valid():
            try:
                with transaction.atomic():
                    count = form_lote.aplicar()

                messages.success(request, f"✅ {count} despesa(s) atualizada(s) com sucesso!")

                form_lote = AdminLoteReembolsoForm(
                    centro=centro, ano=ano, mes=mes, user=user_obj
                )
                status_code = 200

            except Exception as e:
                if "locked" in str(e):
                    messages.error(request, "O sistema está processando outra requisição...")
                else:
                    messages.error(request, f"Erro ao aplicar: {e}")
                status_code = 400
        else:
            messages.error(request, "Erro no formulário. Verifique os campos.")
            status_code = 400
    else:
        # GET: Formulário vazio inicial
        form_lote = AdminLoteReembolsoForm(
            centro=centro, ano=ano, mes=mes, user=user_obj
        )
        status_code = 200

    # 6. Preparação do Contexto
    despesas_qs = form_lote.fields["despesas"].queryset
    total_disponivel = despesas_qs.aggregate(total=Sum("valor"))["total"] or Decimal("0")
    qtd_disponivel = despesas_qs.count()

    context = {
        "form_lote": form_lote,
        "centro": centro,
        "user_obj": user_obj,
        "colaborador_nome": colaborador_nome,
        "ano": ano,
        "mes": mes,
        "centro_id": centro_id or "",
        "user_id": user_id or "",
        "total_disponivel": total_disponivel,
        "qtd_disponivel": qtd_disponivel,
        "erro_parametros": False
    }

    resp = render(request, "centros/_modal_reembolso_lote.html", context, status=status_code)
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
  # ajuste os imports utilitarios conforme o seu projeto


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

'''

#cartão coorporativo + tela de viagens

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from decimal import Decimal
# Certifique-se de importar now e mes_label_pt conforme já existem no seu arquivo

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

    # ==========================================================
    # --- NOVA FUNCIONALIDADE: Controle do Cartão Empresarial ---
    # ==========================================================
    cartao = getattr(user, 'cartao_corporativo', None)
    exibir_cartao = bool(cartao and cartao.habilitado)

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
        # --- Variáveis Injetadas para o Frontend ---
        "cartao": cartao,
        "exibir_cartao": exibir_cartao,
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



# ==============================================================================
# IMPORTAÇÕES NECESSÁRIAS (Garanta que estas linhas estejam no TOPO do arquivo)
# ==============================================================================
from django.shortcuts import render
from django.db.models import Sum, Q, Max, Count
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from .models import Despesa, AssociacaoCentroCusto
# ==============================================================================


from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Q, Max, Count
from django.contrib.auth.models import User

# Certifique-se de importar seus modelos Despesa e AssociacaoCentroCusto adequadamente no topo do arquivo.

@login_required
@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["GET", "POST"])
def centros_pendentes_summary(request):
    """
    Retorna HTML para o relatório.
    - Se users_int: Retorna lista detalhada de despesas desses usuários (Item a Item).
    - Se não: Retorna lista agregada por colaborador (incluindo Reprovadas).
    """

    # --- 1. Captura de Parâmetros Múltiplos ---
    def get_int_list(key):
        """Captura múltiplos parâmetros do POST ou GET e converte para inteiros."""
        vals = request.POST.getlist(key) or request.GET.getlist(key)
        return [int(v) for v in vals if v.isdigit()]

    # Singular
    raw_top = request.POST.get("top") or request.GET.get("top")
    top_n = int(raw_top) if raw_top and raw_top.isdigit() else None

    raw_ano = request.POST.get("ano") or request.GET.get("ano")
    sel_ano = int(raw_ano) if raw_ano and raw_ano.isdigit() else None

    # Múltiplos
    meses_int = get_int_list("mes")
    meses_int = [m for m in meses_int if 1 <= m <= 12] # Valida meses 1 a 12

    centros_int = get_int_list("centro")
    users_int   = get_int_list("user")

    escopo = str(request.POST.get("escopo_associados", "")).lower()
    escopo_associados = escopo in ("1", "true", "t", "yes", "on")

    # --- 2. QuerySet Base ---
    status_list = ['PENDENTE', 'PENDENTE_PAGTO', 'APROVADA', 'REPROVADA']
    pend_qs = Despesa.objects.filter(status__in=status_list)

    # Aplica os filtros recebidos da tela
    if sel_ano:
        pend_qs = pend_qs.filter(data_fato__year=sel_ano)
    if meses_int:
        pend_qs = pend_qs.filter(data_fato__month__in=meses_int)
    if centros_int:
        pend_qs = pend_qs.filter(centro_id__in=centros_int)

    # --- 3. Lógica Bifurcada (Detalhe vs Geral) ---

    # A) MODO DETALHE: Se tem usuário(s) selecionado(s), mostra item a item
    if users_int:
        pend_qs = pend_qs.filter(usuario_id__in=users_int).select_related('centro', 'usuario')

        # Ordena por data
        despesas_lista = pend_qs.order_by('-data_fato', '-id')

        if top_n:
            despesas_lista = despesas_lista[:top_n]

        ctx = {
            "modo_detalhe": True, # Ativa visualização item a item no template
            "despesas_lista": despesas_lista,
            "users_sel": users_int,
        }
        return render(request, "centros/_pendentes_summary.html", ctx)

    # B) MODO GERAL: Agregado por colaborador
    if escopo_associados:
        try:
            # Se não há filtro estrito de usuário, pega apenas associados ativos
            u_ids = AssociacaoCentroCusto.objects.filter(ativo=True).values_list("usuario_id", flat=True)
            pend_qs = pend_qs.filter(usuario_id__in=u_ids)
        except Exception:
            pass

    # Agregação agrupando por usuário
    agreg = (
        pend_qs.values("usuario")
        .annotate(
            v_analise=Sum("valor", filter=Q(status='PENDENTE')),
            v_pagto=Sum("valor", filter=Q(status='PENDENTE_PAGTO')),
            v_pago=Sum("valor", filter=Q(status='APROVADA')),
            v_reprovada=Sum("valor", filter=Q(status='REPROVADA')),
            ultima=Max("criado_em"),
            qtd=Count("id"),
        )
        .order_by("-ultima")
    )

    if top_n: agreg = agreg[:top_n]

    user_ids = [row["usuario"] for row in agreg]
    users = {u.id: u for u in User.objects.filter(id__in=user_ids)}

    p_analise, p_pagto, p_pago, p_reprovada = [], [], [], []
    t_analise = t_pagto = t_pago = t_reprovada = Decimal("0")

    for row in agreg:
        u = users.get(row["usuario"])
        if not u: continue

        val_analise = row["v_analise"] or Decimal("0")
        val_pagto = row["v_pagto"] or Decimal("0")
        val_pago = row["v_pago"] or Decimal("0")
        val_reprovada = row["v_reprovada"] or Decimal("0")

        item = {
            "usuario": u,
            "valor_pend_analise": val_analise,
            "valor_pend_pagto": val_pagto,
            "valor_pago": val_pago,
            "valor_reprovada": val_reprovada,
        }

        # Adiciona nas listas se tiver valor > 0
        if val_analise > 0:
            p_analise.append(item); t_analise += val_analise
        if val_pagto > 0:
            p_pagto.append(item); t_pagto += val_pagto
        if val_pago > 0:
            p_pago.append(item); t_pago += val_pago
        if val_reprovada > 0:
            p_reprovada.append(item); t_reprovada += val_reprovada

    ctx = {
        "modo_detalhe": False,
        "pendentes_analise": p_analise, "pendentes_analise_total": t_analise,
        "pendentes_pagamento": p_pagto, "pendentes_pagamento_total": t_pagto,
        "pendentes_pago": p_pago,       "pendentes_pago_total": t_pago,
        "pendentes_reprovada": p_reprovada, "pendentes_reprovada_total": t_reprovada,

        # Opcional repassar os filtros para o template, caso utilize lá dentro:
        "meses_sel": meses_int,
        "sel_ano": sel_ano,
        "centros_sel": centros_int,
    }

    return render(request, "centros/_pendentes_summary.html", ctx)

#COMEÇA AQUI O GESTOR DE ATIVIDADES


# views.py (adicione no módulo de views existente)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.db.models import Q

from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro, NivelChoices,
    EtapaRegistroStatus
)

# views.py (adicionar os imports acima se ainda não tiver)
from django.shortcuts import render
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from .models import NivelChoices



# despesas/views.py
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest, HttpResponse
from django.urls import reverse
from django.db.models import Count, Q, Sum
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST
from django.forms.models import model_to_dict

from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro, EtapaHistorico,
    NivelChoices, EtapaRegistroStatus, FilaAutomatica
)

# Ajuste de permissão simples (faça sua lógica real se houver grupos/perfis)
def user_is_admin(user):
    return user.is_superuser or user.is_staff

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.utils.timezone import now
from django.db.models import Q
from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro, EtapaHistorico,
    NivelChoices, EtapaRegistroStatus, FilaAutomatica
)

# opção: habilitar criação automática de registros NAO_INICIADO ao abrir a tela
AUTO_CREATE_REGISTROS = True

from django.db import models # Importante para o Prefetch
# ... mantenha seus outros imports (shortcuts, decorators, timezone, etc)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.db import models
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse, HttpResponseBadRequest

from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro,
    EtapaHistorico, NivelChoices, EtapaRegistroStatus, FilaAutomatica
)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from .models import (
    Cliente, AssociacaoUsuarioCliente, Etapa, EtapaRegistro,
    NivelChoices, EtapaRegistroStatus
)

from .models import Etapa, EtapaRegistro
from .forms import EtapaForm

from django.db.models import Max # <--- IMPORTANTE: Adicione este import no topo
from django.urls import reverse # Certifique-se de importar isso

import logging

logger = logging.getLogger(__name__)

import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.timezone import now
from django.contrib.auth import get_user_model

# Importação dos Models
from .models import (
    Cliente,
    Etapa,
    EtapaRegistro,
    AssociacaoUsuarioCliente,
    EtapaHistorico,
    EtapaRegistroStatus,
    NivelChoices
)

# --- AQUI ESTÁ A MUDANÇA SOLICITADA ---
# Importamos o pacote 'utils' inteiro para usar 'utils.enviar_notificacao_push'
from . import utils

User = get_user_model()

# --- Funções Auxiliares (mantendo as que você já usa) ---
# Se elas estiverem em outro arquivo, importe-as.
# Se estiverem neste mesmo arquivo views.py, certifique-se de que estão definidas acima.

# Exemplo de stub caso precise importar de algum lugar:


import traceback
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.contrib.auth import get_user_model

# SEUS IMPORTS (Confirme se os caminhos estão certos)
from .models import (
    Cliente, Etapa, EtapaRegistro, EtapaHistorico,
    AssociacaoUsuarioCliente, NivelChoices, EtapaRegistroStatus
)
# IMPORTANTE: O arquivo utils.py deve estar na mesma pasta ou ajustado aqui
from . import utils

User = get_user_model()


import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.contrib.auth import get_user_model

# SEUS IMPORTS DE MODELOS
from .models import (
    Cliente, Etapa, EtapaRegistro, EtapaHistorico,
    AssociacaoUsuarioCliente, NivelChoices, EtapaRegistroStatus
)

# IMPORTANTE: Importe o arquivo utils onde está a função 'notificar_usuario_individual'
from . import utils

# Se a função fechamento_esta_fechado estiver neste mesmo arquivo, ok.
# Se estiver em outro, faça o import. Ex: from .helpers import fechamento_esta_fechado


import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.contrib.auth import get_user_model

# SEUS IMPORTS DE MODELOS
from .models import (
    Cliente, Etapa, EtapaRegistro, EtapaHistorico,
    AssociacaoUsuarioCliente, NivelChoices, EtapaRegistroStatus
)

# IMPORTANTE: Importe o arquivo utils onde está a função 'notificar_usuario_individual'
from . import utils

# Se a função fechamento_esta_fechado estiver neste mesmo arquivo, ok.
# Se estiver em outro, faça o import. Ex: from .helpers import fechamento_esta_fechado

# Helpers de verificação (se estiver em outro arquivo, ajuste o import)
# from .helpers import fechamento_esta_fechado

User = get_user_model()
logger = logging.getLogger(__name__)

import json
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt

# Imports dos seus Models
from .models import (
    Cliente, Etapa, EtapaRegistro, EtapaHistorico,
    AssociacaoUsuarioCliente, NivelChoices, EtapaRegistroStatus,
    NotificacaoPush
)

# Import do Utils (que contém a função tentar_enviar_notificacao_existente)
from . import utils

User = get_user_model()
logger = logging.getLogger(__name__)

# --- VIEW 1: GATILHO (API para o Javascript chamar) ---
@login_required
@require_POST
def api_disparar_notificacoes(request):
    """
    Recebe IDs de notificações via JSON e processa o envio.
    Chamado pelo Frontend logo após salvar o registro.
    """
    try:
        data = json.loads(request.body)
        ids = data.get("ids", [])
    except:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    if not ids:
        return JsonResponse({"ok": True, "enviados": 0})

    sucessos = 0
    # Processa cada ID usando a função do utils que busca no banco e envia
    for notif_id in ids:
        try:
            if utils.tentar_enviar_notificacao_existente(notif_id):
                sucessos += 1
        except Exception as e:
            logger.error(f"Erro ao disparar ID {notif_id}: {e}")

    return JsonResponse({"ok": True, "enviados": sucessos})


# views.py
import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from push_notifications.models import WebPushDevice

from django.conf import settings
import os

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, "static", "sw.js")
    if not os.path.exists(sw_path):
        raise Http404("Service worker not found")
    with open(sw_path, "r", encoding="utf-8") as f:
        return HttpResponse(f.read(), content_type="application/javascript")


# core/views_vapid.py
import json
import os
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

@require_GET
@cache_control(public=True, max_age=3600)  # em produção ok; para debug troque ou remova
def vapid_js(request):
    """
    Serve um pequeno JS que define `window.__VAPID_PUBLIC_KEY`.
    Procura a chave nas seguintes ordens:
      1) settings.VAPID_PUBLIC_KEY
      2) settings.PUSH_NOTIFICATIONS_SETTINGS["APP_SERVER_KEY"]
      3) env VAPID_PUBLIC_KEY
      4) env PUSH_APP_SERVER_KEY
    Retorna um JS com a string (json.dumps garante escape seguro).
    """
    # 1) prioridade: settings.VAPID_PUBLIC_KEY
    vapid_key = getattr(settings, "VAPID_PUBLIC_KEY", None)

    # 2) fallback: settings.PUSH_NOTIFICATIONS_SETTINGS.get("APP_SERVER_KEY")
    if not vapid_key:
        pns = getattr(settings, "PUSH_NOTIFICATIONS_SETTINGS", None)
        if isinstance(pns, dict):
            vapid_key = pns.get("APP_SERVER_KEY") or pns.get("APP_SERVER_KEY".upper())

    # 3) fallback: environment variables
    if not vapid_key:
        vapid_key = os.environ.get("VAPID_PUBLIC_KEY") or os.environ.get("PUSH_APP_SERVER_KEY") or ""

    # garantir string limpa (não exponha a chave privada aqui)
    if vapid_key is None:
        vapid_key = ""

    # Monta JS de forma segura (json.dumps escapa a string)
    js = (
        f"/* VAPID injector - do not expose private key */\n"
        f"window.__VAPID_PUBLIC_KEY = {json.dumps(vapid_key)};\n"
        f"window.__CONMAC_VAPID_INJECTED = true;\n"
    )

    # Para debug: se quiser desativar cache durante testes, comente cache_control decorator acima
    return HttpResponse(js, content_type="application/javascript")



# despesas/views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from .utils_push import send_push_message_to_all

@staff_member_required
def push_send_view(request, pk):
    msg = get_object_or_404(PushMessage, pk=pk)
    result = send_push_message_to_all(msg)
    # você pode mostrar resultado na UI usando messages framework
    from django.contrib import messages
    messages.success(request, f"Enviadas: {result['sent']}, Falhas: {result['failed']}")
    return redirect(reverse('admin:despesas_pushmessage_change', args=[msg.id]))


import json
from django.http import JsonResponse



# despesas/views.py (ou onde você mantém suas views)
import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.text import slugify
from push_notifications.models import WebPushDevice

def _extract_keys(sub):
    """Extrai p256dh e auth de um subscription dict."""
    try:
        keys = sub.get("keys", {})
        return keys.get("p256dh"), keys.get("auth")
    except Exception:
        return None, None

def push_register_device(request):
    """
    Recebe JSON { subscription: { ... } } e salva/atualiza WebPushDevice.
    Salva registration_id (JSON string), e também preenche p256dh/auth.
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("JSON inválido")

    sub = body.get("subscription") or body.get("subscription_info") or body.get("subscriptionInfo")
    if not sub:
        return JsonResponse({"ok": False, "error": "subscription ausente"}, status=400)

    # se veio como string, tenta parse
    if isinstance(sub, str):
        try:
            sub = json.loads(sub)
        except Exception:
            return JsonResponse({"ok": False, "error": "subscription mal formatada"}, status=400)

    endpoint = sub.get("endpoint")
    if not endpoint:
        return JsonResponse({"ok": False, "error": "endpoint ausente"}, status=400)

    # extrai chaves
    p256dh, auth = _extract_keys(sub)
    if not p256dh or not auth:
        return JsonResponse({"ok": False, "error": "subscription sem chaves válidas (p256dh/auth)"}, status=400)

    # guarda JSON completo
    reg_json = json.dumps(sub, ensure_ascii=False)

    user = request.user if request.user.is_authenticated else None

    # busca por endpoint existente
    existing = WebPushDevice.objects.filter(registration_id__icontains=endpoint)
    if user:
        existing = existing.filter(user=user)

    device = existing.first()
    if device:
        device.registration_id = reg_json
        device.p256dh = p256dh
        device.auth = auth
        device.active = True
        device.save(update_fields=["registration_id", "p256dh", "auth", "active"])
    else:
        name = f"web-{slugify(user.username if user else 'anon')}"
        WebPushDevice.objects.create(
            user=user,
            name=name,
            registration_id=reg_json,
            p256dh=p256dh,
            auth=auth,
            active=True,
        )

    return JsonResponse({"ok": True})



#conmacfest2025

from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import RsvpForm
# eventos/views.py

def rsvp_create(request):
    if request.method == "POST":
        form = RsvpForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, "eventos/rsvp_form.html", {"success": True})
    else:
        form = RsvpForm()

    return render(request, "eventos/rsvp_form.html", {"form": form})

#------------------

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import FCMToken

@csrf_exempt # Adicione se estiver tendo problemas de CSRF via API/Fetch, mas @login_required geralmente cuida da sessão
@login_required
def salvar_fcm_token(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            token = data.get("token")

            if token:
                # --- CORREÇÃO AQUI ---
                # Procuramos pelo TOKEN (que é único por dispositivo), não pelo usuário.
                # Se o token já existe, atualizamos o 'user' (caso o dispositivo tenha mudado de dono).
                # Se não existe, cria um novo registro.
                obj, created = FCMToken.objects.update_or_create(
                    token=token,
                    defaults={'user': request.user}
                )

                action = "Criado" if created else "Atualizado"
                print(f"DEBUG DJANGO: Token {action} para {request.user} - ID: {obj.id}")

                return JsonResponse({"status": "success", "message": "Token salvo"})
            else:
                print("DEBUG DJANGO: Token veio vazio")
                return JsonResponse({"status": "error", "message": "Token vazio"}, status=400)

        except Exception as e:
            print(f"DEBUG DJANGO: Erro ao processar: {e}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método não permitido"}, status=405)


from django.shortcuts import render, get_object_or_404
from .models import Prefeitura

def acesso_formulario(request, slug_prefeitura):
    # Tenta buscar a prefeitura, se não achar retorna erro 404
    prefeitura = get_object_or_404(Prefeitura, slug=slug_prefeitura)

    # Contexto base para o template
    context = {
        'prefeitura': prefeitura,
        'status': 'liberado'
    }

    # VERIFICAÇÃO 1: A prefeitura foi desativada manualmente no admin?
    if not prefeitura.ativo:
        context['status'] = 'bloqueado_admin'
        return render(request, 'siops/status_bloqueado.html', context)

    # VERIFICAÇÃO 2: Já existe um questionário respondido para esta prefeitura?
    # O uso de hasattr verifica a relação OneToOne reverse (related_name='questionario')
    if hasattr(prefeitura, 'questionario'):
        context['status'] = 'ja_respondido'
        # Opcional: passar a data de envio para exibir na tela
        context['data_envio'] = prefeitura.questionario.data_envio
        return render(request, 'siops/status_bloqueado.html', context)

    # SE PASSOU: Renderiza o formulário (que faremos na próxima etapa)
    # Por enquanto, renderizamos um template provisório de "Início"
    return render(request, 'siops/inicio_formulario.html', context)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Prefeitura
from .forms import QuestionarioForm

def preencher_questionario(request, slug_prefeitura):
    prefeitura = get_object_or_404(Prefeitura, slug=slug_prefeitura)

    # 1. Verificações de Segurança (reaproveitando a lógica da etapa 1)
    if not prefeitura.ativo:
        return render(request, 'siops/status_bloqueado.html', {'prefeitura': prefeitura, 'status': 'bloqueado_admin'})

    if hasattr(prefeitura, 'questionario'):
        return render(request, 'siops/status_bloqueado.html', {
            'prefeitura': prefeitura,
            'status': 'ja_respondido',
            'data_envio': prefeitura.questionario.data_envio
        })

    # 2. Processamento do Formulário
    if request.method == 'POST':
        form = QuestionarioForm(request.POST)
        if form.is_valid():
            questionario = form.save(commit=False)
            questionario.prefeitura = prefeitura # Vincula à prefeitura da URL
            questionario.save()

            # Feedback e Redirecionamento
            messages.success(request, f"Obrigado! Os dados de {prefeitura.nome} foram enviados com sucesso.")
            # Redireciona para a mesma página, que agora cairá no bloco 'ja_respondido'
            return redirect('questionario_siops', slug_prefeitura=slug_prefeitura)
        else:
            messages.error(request, "Por favor, corrija os erros indicados no formulário.")
    else:
        form = QuestionarioForm()

    return render(request, 'siops/form_wizard.html', {
        'form': form,
        'prefeitura': prefeitura
    })

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.conf import settings
import os
# Import do WeasyPrint
from weasyprint import HTML, CSS

from .models import QuestionarioSIOPS

def gerar_pdf_questionario(request, questionario_id):
    # Busca o questionário
    questionario = QuestionarioSIOPS.objects.get(id=questionario_id)

    # Prepara o contexto
    context = {
        'q': questionario,
        'p': questionario.prefeitura,
    }

    # Renderiza o HTML
    html_string = render_to_string('siops/pdf_template.html', context)

    # Configuração para encontrar imagens estáticas (CSS e Imagens)
    # Isso garante que o WeasyPrint ache o 'logo_conmac.png'
    if settings.DEBUG:
        base_url = request.build_absolute_uri('/')
    else:
        base_url = os.path.join(settings.STATIC_ROOT, '')

    # Gera o PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="siops_{questionario.prefeitura.slug}.pdf"'

    HTML(string=html_string, base_url=base_url).write_pdf(
        response,
        stylesheets=[CSS(string='@page { size: A4; margin: 1.5cm; }')]
    )

    return response



#painel de acompanhamento




from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from .models import Cliente, Etapa, EtapaRegistro, NivelChoices


from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import Cliente, Etapa, EtapaRegistro, NivelChoices


from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import Etapa, EtapaRegistro, Cliente


from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from .models import Etapa, EtapaRegistro, Cliente

from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import Etapa, EtapaRegistro, Cliente

from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from .models import Etapa, EtapaRegistro, Cliente


#_________________________________________

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.db.models import Max
from datetime import datetime, timedelta

# --- 1. IMPORTS DE MODELOS E FORMS ---
from .models import (
    Despesa, ChecklistItem, NivelChoices,
    ConfiguracaoNivel, AssociacaoUsuarioCliente, Cliente,
    Etapa, EtapaRegistro, EtapaRegistroStatus, UsuarioPerfil,
    SolicitacaoReabertura
)

# Tratamento para evitar erro de importação se o arquivo forms.py variar
try:
    from .forms import ChecklistForm, EtapaForm
except ImportError:
    ChecklistForm = None
    EtapaForm = None

# --- 2. HELPERS (FUNÇÕES AUXILIARES) ---

'''
def verificar_nivel_desbloqueado(cliente, ano, mes, nivel_alvo):
    """Verifica tecnicamente se o nível anterior foi concluído."""
    nivel_anterior = get_nivel_anterior(nivel_alvo)

    # Se não tem pré-requisito (ex: FECHAMENTO), está liberado
    if not nivel_anterior:
        return True

    # Busca etapas ativas do nível anterior
    etapas_req = Etapa.objects.filter(nivel=nivel_anterior, ativa=True)
    if not etapas_req.exists():
        return True

    # Conta quantas foram concluídas
    concluidas = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_req,
        status=EtapaRegistroStatus.CONCLUIDO
    ).count()

    # Só desbloqueia se TUDO do anterior estiver pronto
    return concluidas >= etapas_req.count()
'''

# --- 3. VIEW PRINCIPAL ---
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.db.models import Max
from datetime import datetime

# --- 1. IMPORTS COMPLETOS E SEGUROS ---
from .models import (
    Despesa, ChecklistItem, NivelChoices,
    ConfiguracaoNivel, AssociacaoUsuarioCliente, Cliente,
    Etapa, EtapaRegistro, EtapaRegistroStatus, UsuarioPerfil,
    SolicitacaoReabertura
)

# Tratamento para evitar erro se forms.py tiver nomes diferentes
try:
    from .forms import ChecklistForm, EtapaForm
except ImportError:
    ChecklistForm = None
    EtapaForm = None

# --- 2. HELPERS (FUNÇÕES AUXILIARES) ---

def tem_permissao_nivel(user, nivel_key):
    """Verifica se o usuário tem permissão no perfil para acessar o nível."""
    if user.is_superuser: return True
    try:
        perfil = user.perfil
        mapa = {
            "FECHAMENTO": perfil.acesso_fechamento, "SIGA": perfil.acesso_siga,
            "E-TCM": perfil.acesso_etcm, "SIOPE": perfil.acesso_siope,
            "SIOPS": perfil.acesso_siops, "SICONF": perfil.acesso_siconf,
        }
        return mapa.get(nivel_key, False)
    except:
        return False

def get_status_requisitos(cliente, ano, mes, nivel_alvo):
    """
    Verifica a 'Soma de Requisitos'.
    Retorna uma tupla: (esta_desbloqueado: bool, data_ultima_conclusao: datetime)
    """
    # 1. Mapeia o nível alvo para o campo booleano da Etapa
    mapa_campos = {
        "SIGA": "obrigatoria_para_fila_siga",
        "E-TCM": "obrigatoria_para_fila_etcm",
        "SIOPE": "obrigatoria_para_fila_siope",
        "SIOPS": "obrigatoria_para_fila_siops",
        "SICONF": "obrigatoria_para_fila_siconf",
    }

    campo_filtro = mapa_campos.get(nivel_alvo)

    # Se o nível não tem requisitos específicos (ex: FECHAMENTO), está livre
    if not campo_filtro:
        return True, datetime.min

    # 2. Busca TODAS as etapas do sistema que travam este nível
    # Isso garante a "Soma de Requisitos" independente de onde a etapa esteja
    etapas_requisito = Etapa.objects.filter(ativa=True, **{campo_filtro: True})

    total_requisitos = etapas_requisito.count()

    if total_requisitos == 0:
        return True, datetime.min

    # 3. Verifica quais dessas foram concluídas para este cliente/competência
    registros_concluidos = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_requisito,
        status=EtapaRegistroStatus.CONCLUIDO
    )

    qtd_concluidas = registros_concluidos.count()

    # 4. A Regra de Ouro: Tem que ter concluído TODAS as obrigatórias
    esta_liberado = (qtd_concluidas >= total_requisitos)

    data_liberacao = datetime.min
    if esta_liberado:
        # Pega a data da ÚLTIMA conclusão. É essa data que define a posição na fila.
        agregado = registros_concluidos.aggregate(Max('modificado_em'))
        if agregado['modificado_em__max']:
            data_liberacao = agregado['modificado_em__max']

    return esta_liberado, data_liberacao

# --- 3. VIEW PRINCIPAL ---

def check_global_requirements(cliente, ano, mes, nivel_alvo):
    """
    Verifica a soma de todos os requisitos globais para um nível.
    Retorna: (bool: apto_para_concluir, list: pendencias, datetime: data_liberacao)
    """
    from .models import Etapa, EtapaRegistro, EtapaRegistroStatus
    from django.db.models import Max
    from datetime import datetime

    nivel_str = str(nivel_alvo).strip()

    # Mapeamento de campos de trava no Model Etapa
    mapa_campos = {
        "SIGA": "obrigatoria_para_fila_siga",
        "E-TCM": "obrigatoria_para_fila_etcm",
        "SIOPE": "obrigatoria_para_fila_siope",
        "SIOPS": "obrigatoria_para_fila_siops",
        "SICONF": "obrigatoria_para_fila_siconf",
    }

    campo_trava = mapa_campos.get(nivel_str)

    # Níveis sem requisitos (ex: FECHAMENTO) ou não mapeados
    if not campo_trava:
        return True, [], datetime.min

    # 1. Busca TODAS as etapas do sistema (qualquer nível) que travam o nível_alvo
    etapas_obrigatorias = Etapa.objects.filter(ativa=True, **{campo_trava: True})

    if not etapas_obrigatorias.exists():
        return True, [], datetime.min

    # 2. Verifica quais dessas etapas foram concluídas
    registros_concluidos = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_obrigatorias,
        status=EtapaRegistroStatus.CONCLUIDO
    )

    ids_obrigatorios = set(etapas_obrigatorias.values_list('id', flat=True))
    ids_concluidos = set(registros_concluidos.values_list('etapa_id', flat=True))

    ids_pendentes = ids_obrigatorios - ids_concluidos

    if not ids_pendentes:
        # Se liberado, retorna a data da última conclusão para a lógica de Fila FIFO
        data_liberacao = registros_concluidos.aggregate(Max('modificado_em'))['modificado_em__max'] or datetime.min
        return True, [], data_liberacao

    # 3. Retorna nomes das pendências para o template
    nomes_pendentes = list(Etapa.objects.filter(id__in=ids_pendentes).values_list('nome', flat=True))
    return False, nomes_pendentes, datetime.max



def check_requirements_logic(cliente, ano, mes, nivel_alvo):
    """
    Retorna (True, []) se estiver tudo ok.
    Retorna (False, ['Etapa A', 'Etapa B']) se houver pendências.
    """
    from .models import Etapa, EtapaRegistro, EtapaRegistroStatus

    nivel_str = str(nivel_alvo).upper().strip()

    # Mapeamento dos campos booleanos no model Etapa
    mapa_campos = {
        "SIGA": "obrigatoria_para_fila_siga",
        "E-TCM": "obrigatoria_para_fila_etcm",
        "SIOPE": "obrigatoria_para_fila_siope",
        "SIOPS": "obrigatoria_para_fila_siops",
        "SICONF": "obrigatoria_para_fila_siconf",
    }

    campo_filtro = mapa_campos.get(nivel_str)
    if not campo_filtro:
        return True, []

    # 1. Busca TODAS as etapas que possuem a flag de trava para este nível alvo
    etapas_obrigatorias = Etapa.objects.filter(ativa=True, **{campo_filtro: True})

    if not etapas_obrigatorias.exists():
        return True, []

    # 2. Verifica quais dessas foram concluídas pelo cliente nesta competência
    ids_exigidos = set(etapas_obrigatorias.values_list('id', flat=True))

    concluidas = set(EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa_id__in=ids_exigidos,
        status=EtapaRegistroStatus.CONCLUIDO
    ).values_list('etapa_id', flat=True))

    ids_pendentes = ids_exigidos - concluidas

    if not ids_pendentes:
        return True, []

    # 3. Busca os nomes das etapas pendentes
    nomes_pendentes = list(Etapa.objects.filter(id__in=ids_pendentes).values_list('nome', flat=True))
    return False, nomes_pendentes

#INTEGRAÇÃO OMIE

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.contrib import messages
from .models import Contrato, ServicoExtra
from .omie_service import OmieService

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.contrib import messages
from datetime import date, timedelta
from .models import Contrato, ServicoExtra
from .omie_service import OmieService

def is_staff(user):
    return user.is_staff

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.contrib import messages
from datetime import date, timedelta
from .models import Contrato, ServicoExtra
from .omie_service import OmieService



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Q
from datetime import date, timedelta



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Q
from datetime import date, timedelta
from time import sleep # Importante para evitar bloqueio da API (425)

# Importações Locais
from .models import Contrato, ServicoExtra
from .omie_service import OmieService
from .forms import EdicaoLoteContratoForm, ServicoExtraForm

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Q
from datetime import date, timedelta
import json

# Importe seus models
from .models import Contrato, ServicoExtra


# views_receitas_dashboard.py — versão 2
# Adicione / substitua no seu views.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Q
from datetime import date, timedelta
import json

from .models import Contrato, ServicoExtra
# ─────────────────────────────────────────────────────────────
#  DASHBOARD DE RECEITAS / CONTRATOS
# ─────────────────────────────────────────────────────────────
@login_required #verificar coerencia
def receitas_dashboard(request):
    from .models import NotaFiscal, ConfiguracaoSistema

    hoje            = date.today()
    limite_aviso    = hoje + timedelta(days=30)
    STATUS_INATIVOS = ['99', 'Cancelado', 'Inativo', 'Suspenso']

    # Feature flag (Django admin → Configurações do Sistema). Desligada por
    # padrão — o indicador "oficial" de faturado/não faturado fica dentro do
    # fluxo de faturar em lote (ver painel de confirmação do modal), não
    # aqui no dashboard. Isso aqui é um extra opcional pra quem quiser.
    mostrar_status_fat = ConfiguracaoSistema.obter().dashboard_mostra_status_faturamento

    # ── Filtros GET ──────────────────────────────────────────
    q              = request.GET.get('q', '').strip()
    municipio_f    = request.GET.get('municipio', '').strip()
    entidade_f     = request.GET.get('entidade', '').strip()   # 'municipio' | 'camara' | ''

    # Competência de referência p/ status "faturado/não faturado" — padrão
    # é o mês mais recente (mês atual). O usuário pode escolher outro mês
    # pra checar contratos que ficaram sem nota emitida naquele período.
    try:
        mes_f = int(request.GET.get('mes_fat') or hoje.month)
        assert 1 <= mes_f <= 12
    except (TypeError, ValueError, AssertionError):
        mes_f = hoje.month
    try:
        ano_f = int(request.GET.get('ano_fat') or hoje.year)
    except (TypeError, ValueError):
        ano_f = hoje.year
    apenas_nao_faturados = mostrar_status_fat and request.GET.get('nao_faturados') == '1'

    contratos_qs = Contrato.objects.all().order_by('municipio', 'tipo_entidade', 'status_omie', '-valor_mensal')

    if q:
        contratos_qs = contratos_qs.filter(
            Q(cliente_nome__icontains=q) | Q(omie_num_ctr__icontains=q)
        )

    municipios_f = request.GET.getlist('municipio')          # lista (pode ser vazia)
    municipios_f = [m for m in municipios_f if m.strip()]   # remove vazios
    if municipios_f:
        contratos_qs = contratos_qs.filter(municipio__in=municipios_f)

    if entidade_f:
        contratos_qs = contratos_qs.filter(tipo_entidade=entidade_f)

    # ── KPIs ─────────────────────────────────────────────────
    ativos_qs        = contratos_qs.exclude(status_omie__in=STATUS_INATIVOS)
    total_recorrente = ativos_qs.aggregate(s=Sum('valor_mensal'))['s'] or 0
    total_extra      = ServicoExtra.objects.aggregate(s=Sum('valor'))['s'] or 0
    total_geral      = total_recorrente + total_extra
    qtd_vencendo     = ativos_qs.filter(data_vigencia_final__range=[hoje, limite_aviso]).count()

    # ── Contratos faturados na competência de referência (só se a flag
    #    estiver ligada — ver ConfiguracaoSistema) ──────────────────────
    if mostrar_status_fat:
        contratos_faturados_ids = set(
            NotaFiscal.objects
            .filter(competencia_mes=mes_f, competencia_ano=ano_f, status='emitida', contrato_id__isnull=False)
            .values_list('contrato_id', flat=True)
            .distinct()
        )
    else:
        contratos_faturados_ids = set()

    # ── Lista para template ──────────────────────────────────
    contratos_list = []
    qtd_faturados_periodo     = 0
    qtd_nao_faturados_periodo = 0
    for c in contratos_qs:
        is_inativo  = str(c.status_omie) in STATUS_INATIVOS
        is_vencendo = (
            not is_inativo
            and c.data_vigencia_final
            and hoje <= c.data_vigencia_final <= limite_aviso
        )
        faturado_periodo = c.id in contratos_faturados_ids
        if mostrar_status_fat and not is_inativo:
            if faturado_periodo:
                qtd_faturados_periodo += 1
            else:
                qtd_nao_faturados_periodo += 1

        if apenas_nao_faturados and (faturado_periodo or is_inativo):
            continue

        contratos_list.append({
            'obj':               c,
            'is_inativo':        is_inativo,
            'is_vencendo':       is_vencendo,
            'faturado_periodo':  faturado_periodo,
        })

    # ── Dados para os filtros ─────────────────────────────────
    municipios_existentes = (
        Contrato.objects
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )
    municipios_filtro = list(municipios_existentes)

    MESES_NOMES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
    }
    anos_filtro_fat = list(range(hoje.year - 2, hoje.year + 2))

    context = {
        'contratos_list':       contratos_list,
        'total_recorrente':     total_recorrente,
        'total_extra':          total_extra,
        'total_geral':          total_geral,
        'qtd_vencendo':         qtd_vencendo,
        'q':                    q,
        'municipios_f':          municipios_f,
        'entidade_f':           entidade_f,
        'municipios_filtro':    municipios_filtro,
        'municipios_existentes': municipios_existentes,
        'alerta_docs': get_alerta_documentos(),
        # Status de faturamento por competência — ligado via Django admin
        # (ConfiguracaoSistema.dashboard_mostra_status_faturamento)
        'mostrar_status_fat':         mostrar_status_fat,
        'mes_fat':                    mes_f,
        'mes_fat_nome':               MESES_NOMES[mes_f],
        'ano_fat':                    ano_f,
        'meses_nomes':                MESES_NOMES,
        'anos_filtro_fat':            anos_filtro_fat,
        'apenas_nao_faturados':       apenas_nao_faturados,
        'qtd_faturados_periodo':      qtd_faturados_periodo,
        'qtd_nao_faturados_periodo':  qtd_nao_faturados_periodo,
    }
    return render(request, 'receitas_dashboard.html', context)

# views.py

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import EmailMunicipioForm
from .models import EmailMunicipio

@login_required
def adicionar_email_municipio(request):
    if request.method == 'POST':
        # Campos fixos
        municipio     = request.POST.get('municipio', '').strip()
        tipo_entidade = request.POST.get('tipo_entidade', '').strip() or None

        # Listas de e-mails
        emails        = request.POST.getlist('email[]')
        nomes         = request.POST.getlist('nome_contato[]')
        principais    = request.POST.getlist('principal[]')  # só vêm os marcados

        if not municipio or not any(e.strip() for e in emails):
            messages.error(request, "Informe o município e ao menos um e-mail.")
            form = EmailMunicipioForm(request.POST)
            return render(request, 'adicionar_email_municipio.html', {'form': form})

        total_criados   = 0
        total_ignorados = 0

        for i, email in enumerate(emails):
            email = email.strip()
            if not email:
                continue
            nome      = nomes[i].strip() if i < len(nomes) else ''
            principal = str(i) in [str(j) for j, _ in enumerate(emails)
                        if f'principal[{j}]' in request.POST] or (i == 0 and '1' in principais)

            # Forma mais simples: verifica pelo índice da lista de checkboxes
            # Como checkboxes sem valor não são enviados, usamos presença na lista
            principal = len(principais) > 0 and str(i) in request.POST.getlist('principal_idx[]')

            # ── modo mais confiável: usar campo auxiliar de índice ──
            # (ver dica abaixo)
            registro, _ = EmailMunicipio.objects.get_or_create(
                municipio=municipio,
                tipo_entidade=tipo_entidade,
                email=email,
                defaults={'nome_contato': nome, 'principal': False},
            )
            resultado = registro.propagar()
            total_criados   += resultado['criados']
            total_ignorados += resultado['ignorados']

        messages.success(
            request,
            f"✔ {total_criados} vínculo(s) criado(s). "
            f"{total_ignorados} já existiam e foram mantidos."
        )
        return redirect('receitas_dashboard')

    else:
        initial = {
            'municipio':     request.GET.get('municipio', ''),
            'tipo_entidade': request.GET.get('entidade', ''),
        }
        form = EmailMunicipioForm(initial=initial)

    return render(request, 'adicionar_email_municipio.html', {'form': form})
# ─────────────────────────────────────────────────────────────
#  EDITAR MUNICÍPIO DO CONTRATO (AJAX)
# ─────────────────────────────────────────────────────────────
@login_required
def editar_municipio_contrato(request, contrato_id):
    """
    POST /receitas/contratos/<id>/municipio/
    Body JSON: { "municipio": "...", "tipo_entidade": "municipio"|"camara"|"" }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido'}, status=405)

    contrato = get_object_or_404(Contrato, id=contrato_id)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    municipio     = body.get('municipio',     '').strip()
    tipo_entidade = body.get('tipo_entidade', '').strip()

    contrato.municipio     = municipio     or None
    contrato.tipo_entidade = tipo_entidade or None
    contrato.save(update_fields=['municipio', 'tipo_entidade'])

    LABELS = {'municipio': 'Município', 'camara': 'Câmara Municipal'}

    return JsonResponse({
        'ok':                   True,
        'municipio':            contrato.municipio or '',
        'tipo_entidade':        contrato.tipo_entidade or '',
        'tipo_entidade_display': LABELS.get(contrato.tipo_entidade or '', ''),
    })


'''
@login_required
def editar_lote_modal(request):
    """
    Processa a edição em lote via AJAX (Modal).
    Inclui tratamento de 'Rate Limit' para evitar erro 425.
    """
    if request.method == 'POST':
        form = EdicaoLoteContratoForm(request.POST)
        if form.is_valid():
            ids_str = form.cleaned_data['ids_selecionados']

            # Captura dados do formulário
            novo_valor = form.cleaned_data['valor_mensal']
            novo_nbs = form.cleaned_data['codigo_nbs']
            novo_mes = form.cleaned_data['nova_competencia_mes']
            novo_ano = form.cleaned_data['nova_competencia_ano']

            # Monta dicionário de competência se preenchido
            competencia = None
            if novo_mes and novo_ano:
                competencia = {'mes': novo_mes, 'ano': novo_ano}

            # Validação simples (Verifica se não é None, para permitir valor 0)
            if novo_valor is None and not novo_nbs and not competencia:
                 return HttpResponse('<div class="alert alert-warning">⚠️ Preencha ao menos um campo para salvar.</div>')

            if not ids_str:
                return HttpResponse('<div class="alert alert-warning">Nenhum contrato selecionado.</div>')

            ids = ids_str.split(',')
            contratos = Contrato.objects.filter(id__in=ids)
            service = OmieService()

            sucessos = 0
            erros = 0
            msgs_erro = [] # Acumula mensagens detalhadas
            total_items = len(contratos)

            for index, contrato in enumerate(contratos):
                # Chama o serviço passando todos os parâmetros
                ok, msg = service.alterar_contrato_lote(
                    contrato.omie_cod_ctr,
                    novo_valor=novo_valor,
                    novo_nbs=novo_nbs,
                    nova_competencia=competencia
                )

                if ok:
                    # Atualiza banco local se sucesso
                    if novo_valor is not None:
                        contrato.valor_mensal = novo_valor
                    contrato.save()
                    sucessos += 1
                else:
                    erros += 1
                    # Guarda a mensagem real do Omie para exibir ao usuário
                    # Filtra mensagens duplicadas
                    msg_limpa = f"<b>Ctr {contrato.omie_num_ctr}:</b> {msg}"
                    if msg_limpa not in msgs_erro:
                        msgs_erro.append(msg_limpa)

                # --- FREIO (Throttling) ---
                # Pausa para evitar bloqueio da API (Erro 425) se houver muitos itens
                if index < total_items - 1:
                    sleep(2.0)

            # Retorno Visual para o Modal
            if erros > 0:
                html_erro = "<br>".join(msgs_erro[:5]) # Mostra até 5 erros
                if len(msgs_erro) > 5: html_erro += "<br>...e outros."

                # Se teve algum sucesso, muda a cor do alerta para amarelo (Warning) em vez de vermelho (Danger)
                alert_class = "alert-warning" if sucessos > 0 else "alert-danger"
                titulo = "⚠️ Processo Concluído com Ressalvas" if sucessos > 0 else "❌ Falha na Operação"

                return HttpResponse(f"""
                    <div class="alert {alert_class}" style="font-size: 0.9rem;">
                        <strong>{titulo}:</strong><br>
                        ✅ Salvos: {sucessos} | ❌ Falhas: {erros}
                        <hr style="margin: 5px 0;">
                        {html_erro}
                    </div>
                    <div style="text-align: right;">
                        <button class="btn-outline" data-close-modal>Fechar</button>
                    </div>
                """)

            return HttpResponse(f"""
                <div class="alert alert-success">
                    ✅ Sucesso! {sucessos} contratos atualizados.
                </div>
                <script>
                    setTimeout(function(){{ window.location.reload(); }}, 1000);
                </script>
            """)

    else:
        # GET: Abre o modal e carrega dados iniciais
        ids_str = request.GET.get('ids', '')
        ids = ids_str.split(',') if ids_str else []
        qtd = len(ids)

        detalhes_atuais = None
        aviso_lote = False

        # Se for apenas 1 contrato, buscamos os dados no Omie para exibir "Dados Atuais"
        if qtd == 1:
            try:
                contrato_db = Contrato.objects.get(id=ids[0])
                service = OmieService()

                # Busca segura
                dados_api = service.consultar_contrato_completo(contrato_db.omie_cod_ctr)

                if dados_api and 'contratoCadastro' in dados_api:
                    ctr = dados_api['contratoCadastro']
                    cabecalho = ctr.get('cabecalho', {})
                    itens = ctr.get('itensContrato', [])
                    item_principal = itens[0] if itens else {} # Pega item 0

                    # Extração segura de campos aninhados
                    nbs_atual = item_principal.get('itemCabecalho', {}).get('codNBS', '-')
                    descr_atual = item_principal.get('itemDescrServ', {}).get('descrCompleta', 'Sem descrição')

                    detalhes_atuais = {
                        'valor': cabecalho.get('nValTotMes'),
                        'nbs': nbs_atual,
                        'descricao': descr_atual
                    }
            except Exception as e:
                print(f"Erro ao carregar detalhes no modal: {e}")

        else:
            aviso_lote = True

        form = EdicaoLoteContratoForm(initial={'ids_selecionados': ids_str})

        context = {
            'form': form,
            'qtd': qtd,
            'detalhes': detalhes_atuais,
            'aviso_lote': aviso_lote
        }
        # Ajuste: Adicionado 'despesas/' para garantir localização correta
        return render(request, 'modal_editar_lote.html', context)


import json
from time import sleep
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

import json
from time import sleep
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# ─────────────────────────────────────────────────────────────────────────────
# MAPA de número de mês → nome em MAIÚSCULAS (para alterar_contrato_lote)
# ─────────────────────────────────────────────────────────────────────────────
MESES_UPPER = {
    1: 'JANEIRO', 2: 'FEVEREIRO', 3: 'MARÇO',    4: 'ABRIL',
    5: 'MAIO',    6: 'JUNHO',     7: 'JULHO',     8: 'AGOSTO',
    9: 'SETEMBRO',10: 'OUTUBRO', 11: 'NOVEMBRO', 12: 'DEZEMBRO',
}


@login_required
@require_POST
def faturar_lote_view(request):
    """
    POST /receitas/contratos/faturar-lote/

    Fatura contratos em lote, com ou sem alteração de competência prévia.

    Body JSON esperado:
    {
        "ids": [1, 2, 3],                 # IDs internos (pk) dos contratos
        "competencia": {                  # opcional — omitir para faturar direto
            "mes_num": 3,                 # int 1-12
            "ano":     "2026"             # string ou int
        }
    }

    Resposta:
    {
        "ok":       true,
        "total":    3,
        "sucessos": 2,
        "erros":    1,
        "msgs_erro": ["Ctr 0042: <motivo>"]
    }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    ids         = data.get('ids', [])
    competencia = data.get('competencia')   # pode ser None

    if not ids:
        return JsonResponse({'ok': False, 'erro': 'Nenhum contrato informado'}, status=400)

    from .models import Contrato
    from .omie_service import OmieService

    contratos = list(Contrato.objects.filter(id__in=ids))
    service   = OmieService()

    sucessos   = 0
    erros      = 0
    msgs_erro  = []
    total      = len(contratos)

    print(f"--- Faturar Lote | total={total} | alterar_comp={bool(competencia)} ---")

    for idx, contrato in enumerate(contratos):
        num_ctr = contrato.omie_num_ctr or contrato.omie_cod_ctr

        # ── 1. Alterar competência (se solicitado) ────────────────────────────
        if competencia:
            mes_num = int(competencia['mes_num'])
            ano     = str(competencia['ano'])
            mes_str = MESES_UPPER.get(mes_num, str(mes_num))

            ok_alt, msg_alt = service.alterar_contrato_lote(
                contrato.omie_cod_ctr,
                nova_competencia={'mes': mes_str, 'ano': ano},
            )

            if not ok_alt:
                erros += 1
                msgs_erro.append(f"<b>Ctr {num_ctr}:</b> Falha ao alterar competência — {msg_alt}")
                _throttle(idx, total)
                continue   # não fatura se alteração falhou

            # Pausa obrigatória entre a alteração e o faturamento do mesmo contrato
            sleep(2.0)

        # ── 2. Faturar contrato ───────────────────────────────────────────────
        ok_fat, res_fat = service.faturar_contrato(contrato.omie_cod_ctr)

        if ok_fat:
            sucessos += 1
        else:
            erros += 1
            msgs_erro.append(f"<b>Ctr {num_ctr}:</b> {res_fat}")

        _throttle(idx, total)

    print(f"--- Faturar Lote End | sucessos={sucessos} erros={erros} ---")

    return JsonResponse({
        'ok':        True,
        'total':     total,
        'sucessos':  sucessos,
        'erros':     erros,
        'msgs_erro': msgs_erro[:8],   # limita a 8 mensagens de erro exibidas
    })


def _throttle(idx, total):
    """Pausa entre requisições para evitar erro 425 / REDUNDANT do Omie."""
    if idx < total - 1:
        sleep(2.0)
'''

import json
from time import sleep

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import EdicaoLoteContratoForm
from .models import Contrato
from .omie_service import OmieService


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

MESES_UPPER = {
    1: 'JANEIRO',  2: 'FEVEREIRO', 3: 'MARÇO',    4: 'ABRIL',
    5: 'MAIO',     6: 'JUNHO',     7: 'JULHO',     8: 'AGOSTO',
    9: 'SETEMBRO', 10: 'OUTUBRO',  11: 'NOVEMBRO', 12: 'DEZEMBRO',
}


def _throttle(idx: int, total: int, delay: float = 2.0) -> None:
    """Pausa entre chamadas à API do Omie para evitar erro 425."""
    if idx < total - 1:
        sleep(delay)


# ─────────────────────────────────────────────────────────────────────────────
# View principal: abre o modal (GET) e salva alterações (POST)
# ─────────────────────────────────────────────────────────────────────────────
"""
SUBSTITUIR a view editar_lote_modal inteiramente por esta versão.

ÚNICA mudança: o POST agora retorna JsonResponse em vez de HttpResponse
com HTML. O GET (abertura do modal) permanece idêntico ao original.

O script da página (submeterEdicao) chama r.json() e espera:
  { ok, sucessos, erros, msgs_erro }   — resultado da operação
  { ok: False, msg }                   — erro de validação/formulário
"""

from time import sleep
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from time import sleep

def _atualizar_cache_local_pos_omie(contrato, dados_response, novo_valor):
    """
    Atualiza os campos de cache local do Contrato a partir do retorno de
    alterar_contrato_lote (já reflete a versão final, pós-alteração — não
    precisa de uma segunda consulta na Omie).
    """
    from decimal import Decimal
    try:
        itens = dados_response['contratoCadastro'].get('itensContrato', [])
        item0 = itens[0] if itens else {}
        descr = item0.get('itemDescrServ', {}).get('descrCompleta')
        nbs   = item0.get('itemCabecalho', {}).get('codNBS')
        aliq  = item0.get('itemImpostos', {}).get('aliqISS')
        if descr:
            contrato.descricao_servico = descr
        if nbs:
            contrato.codigo_nbs = str(nbs).strip()
        if aliq is not None:
            contrato.aliquota_iss = Decimal(str(aliq))
    except Exception:
        pass
    if novo_valor is not None:
        contrato.valor_mensal = novo_valor
    contrato.dados_locais_atualizados_em = timezone.now()


@login_required
def editar_lote_modal(request):
    if request.method == 'POST':
        from .forms import EdicaoLoteContratoForm
        from .models import Contrato
        from .omie_service import OmieService, atualizar_competencia_em_descricao

        form = EdicaoLoteContratoForm(request.POST)
        if not form.is_valid():
            erros_form = '; '.join(
                '{}: {}'.format(f, ', '.join(e))
                for f, e in form.errors.items()
            )
            return JsonResponse({'ok': False, 'msg': erros_form or 'Formulário inválido.'})

        ids_str          = form.cleaned_data['ids_selecionados']
        novo_valor        = form.cleaned_data['valor_mensal']
        novo_nbs          = form.cleaned_data['codigo_nbs']
        novo_mes          = form.cleaned_data['nova_competencia_mes']
        novo_ano          = form.cleaned_data['nova_competencia_ano']
        sincronizar_omie  = form.cleaned_data['sincronizar_omie']

        if novo_valor is None and not novo_nbs and not (novo_mes and novo_ano):
            return JsonResponse({'ok': False, 'msg': 'Preencha ao menos um campo para salvar.'})

        if not ids_str:
            return JsonResponse({'ok': False, 'msg': 'Nenhum contrato selecionado.'})

        competencia = {'mes': novo_mes, 'ano': novo_ano} if (novo_mes and novo_ano) else None

        # ✅ Suporta chunk parcial: o JS envia apenas os IDs deste lote
        ids       = [i.strip() for i in ids_str.split(',') if i.strip()]
        contratos = Contrato.objects.filter(id__in=ids)
        service   = OmieService()

        sucessos  = 0
        erros     = 0
        msgs_erro = []

        for index, contrato in enumerate(contratos):
            if sincronizar_omie:
                # ── Caminho de sempre: grava na Omie e cacheia local ──────
                ok, msg, *extra = service.alterar_contrato_lote(
                    contrato.omie_cod_ctr,
                    novo_valor=novo_valor,
                    novo_nbs=novo_nbs,
                    nova_competencia=competencia,
                )
                if ok:
                    dados_response = extra[0] if extra else None
                    if dados_response:
                        _atualizar_cache_local_pos_omie(contrato, dados_response, novo_valor)
                    elif novo_valor is not None:
                        contrato.valor_mensal = novo_valor

                    # Primeira vez que este contrato é sincronizado: também
                    # busca e cacheia os dados fiscais do tomador (CNPJ,
                    # endereço...) — precisa pra emitir via SAATRI Direto
                    # sem depender da Omie. Só refaz se ainda não tiver.
                    if not contrato.dados_tomador:
                        tomador = service.consultar_cliente_completo(contrato.cliente_id_omie)
                        if tomador:
                            contrato.dados_tomador = tomador

                    contrato.save()
                    sucessos += 1
                else:
                    erros += 1
                    msg_limpa = '<b>Ctr {}:</b> {}'.format(contrato.omie_num_ctr, msg)
                    if msg_limpa not in msgs_erro:
                        msgs_erro.append(msg_limpa)

                # Mantém o sleep apenas entre itens (não após o último)
                if index < len(contratos) - 1:
                    sleep(1.5)

            else:
                # ── Sincronizar com Omie DESLIGADO: só atualiza o cache
                # local, sem nenhuma chamada à Omie. Precisa já ter uma
                # descrição em cache pra poder editar a competência nela.
                if competencia and not contrato.descricao_servico:
                    erros += 1
                    msgs_erro.append(
                        f"<b>Ctr {contrato.omie_num_ctr}:</b> ainda não tem descrição em cache local — "
                        f"sincronize com a Omie pelo menos uma vez antes de editar sem sincronizar."
                    )
                    continue

                if novo_valor is not None:
                    contrato.valor_mensal = novo_valor
                if novo_nbs:
                    contrato.codigo_nbs = novo_nbs
                if competencia:
                    contrato.descricao_servico = atualizar_competencia_em_descricao(
                        contrato.descricao_servico, competencia['mes'].upper(), competencia['ano']
                    )
                contrato.dados_locais_atualizados_em = timezone.now()
                contrato.save()
                sucessos += 1

        return JsonResponse({
            'ok':        True,
            'sucessos':  sucessos,
            'erros':     erros,
            'msgs_erro': msgs_erro,
        })

    # GET — sem alterações ...

    # ── GET — abre o modal (idêntico ao original) ──────────────────────
    from .forms import EdicaoLoteContratoForm
    from .models import Contrato
    from .omie_service import OmieService

    ids_str = request.GET.get('ids', '')
    ids     = ids_str.split(',') if ids_str else []
    qtd     = len(ids)

    detalhes_atuais = None
    aviso_lote      = False

    if qtd == 1:
        try:
            contrato_db = Contrato.objects.get(id=ids[0])
            service     = OmieService()
            dados_api   = service.consultar_contrato_completo(contrato_db.omie_cod_ctr)

            if dados_api and 'contratoCadastro' in dados_api:
                ctr             = dados_api['contratoCadastro']
                cabecalho       = ctr.get('cabecalho', {})
                itens           = ctr.get('itensContrato', [])
                item_principal  = itens[0] if itens else {}

                detalhes_atuais = {
                    'valor':     cabecalho.get('nValTotMes'),
                    'nbs':       item_principal.get('itemCabecalho', {}).get('codNBS', '-'),
                    'descricao': item_principal.get('itemDescrServ', {}).get('descrCompleta', 'Sem descrição'),
                }
        except Exception as e:
            print('Erro ao carregar detalhes no modal:', e)
    else:
        aviso_lote = True

    form = EdicaoLoteContratoForm(initial={'ids_selecionados': ids_str})

    return render(request, 'modal_editar_lote.html', {
        'form':      form,
        'qtd':       qtd,
        'detalhes':  detalhes_atuais,
        'aviso_lote': aviso_lote,
    })

# ─────────────────────────────────────────────────────────────────────────────
# View de faturamento em lote
# ─────────────────────────────────────────────────────────────────────────────


import json
from time import sleep
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST


MESES_UPPER = {
    1:  'JANEIRO',   2: 'FEVEREIRO', 3:  'MARÇO',
    4:  'ABRIL',     5: 'MAIO',      6:  'JUNHO',
    7:  'JULHO',     8: 'AGOSTO',    9:  'SETEMBRO',
    10: 'OUTUBRO',  11: 'NOVEMBRO', 12: 'DEZEMBRO',
}


@login_required
@require_POST
def faturar_lote_view(request):
    """
    POST /receitas/contratos/faturar-lote/

    Fatura contratos em lote. No fluxo "Salvar e Faturar" o save
    já foi feito por editar_lote_modal e competencia chega como null.
    No fluxo "Faturar sem editar" competencia pode ser enviada para
    alterar antes de faturar.

    Body JSON:
    {
        "ids": [1, 2, 3],
        "competencia": {"mes_num": 3, "ano": "2026"}  ← opcional
    }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    ids         = data.get('ids', [])
    competencia = data.get('competencia')

    if not ids:
        return JsonResponse({'ok': False, 'erro': 'Nenhum contrato informado'}, status=400)

    from .models import Contrato
    from .omie_service import OmieService

    contratos = list(Contrato.objects.filter(id__in=ids))
    service   = OmieService()

    sucessos  = 0
    erros     = 0
    msgs_erro = []
    total     = len(contratos)

    print(f"--- Faturar Lote | total={total} | com_competencia={bool(competencia)} ---")

    for idx, contrato in enumerate(contratos):
        num_ctr = contrato.omie_num_ctr or str(contrato.omie_cod_ctr)

        # ── 1. Alterar competência (só quando enviada explicitamente) ──
        if competencia:
            mes_num = int(competencia.get('mes_num', 0))
            ano     = str(competencia.get('ano', ''))
            mes_str = MESES_UPPER.get(mes_num, '')

            if not mes_str or not ano:
                erros += 1
                msgs_erro.append(
                    f"<b>Ctr {num_ctr}:</b> Competência inválida "
                    f"(mes_num={mes_num} ano={ano})"
                )
                _throttle(idx, total)
                continue

            ok_alt, msg_alt = service.alterar_contrato_lote(
                contrato.omie_cod_ctr,
                nova_competencia={'mes': mes_str, 'ano': ano},
            )

            if not ok_alt:
                erros += 1
                msgs_erro.append(
                    f"<b>Ctr {num_ctr}:</b> Falha ao alterar competência — {msg_alt}"
                )
                _throttle(idx, total)
                continue

            sleep(2.0)   # pausa obrigatória entre alterar e faturar

        # ── 2. Faturar ──────────────────────────────────────────────────
        ok_fat, res_fat = service.faturar_contrato(contrato.omie_cod_ctr)

        if ok_fat:
            sucessos += 1
        else:
            erros += 1
            msgs_erro.append(f"<b>Ctr {num_ctr}:</b> {res_fat}")

        _throttle(idx, total)

    print(f"--- Faturar Lote End | sucessos={sucessos} erros={erros} ---")

    return JsonResponse({
        'ok':        True,
        'total':     total,
        'sucessos':  sucessos,
        'erros':     erros,
        'msgs_erro': msgs_erro[:8],
    })


def _throttle(idx, total):
    if idx < total - 1:
        sleep(2.0)


@login_required
def status_faturamento_contratos(request):
    """
    GET JSON — pra usar no painel de confirmação do "Faturar em lote"
    (ver painel-confirmacao em modal_editar_lote.html): dado um conjunto de
    contratos selecionados e uma competência, diz quais já têm NFS-e
    emitida naquele período e quais não têm — pra revisar antes de
    confirmar (evita faturar de novo quem já foi faturado, e mostra quem
    ainda falta).

    Params: ?ids=1,2,3&mes=8&ano=2026 (mes/ano opcionais, default mês atual)
    """
    from .models import NotaFiscal

    ids_raw = request.GET.get('ids', '')
    try:
        ids = [int(i) for i in ids_raw.split(',') if i.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'IDs inválidos'}, status=400)

    if not ids:
        return JsonResponse({'ok': False, 'erro': 'Nenhum contrato informado'}, status=400)

    hoje = date.today()
    try:
        mes = int(request.GET.get('mes') or hoje.month)
        assert 1 <= mes <= 12
    except (TypeError, ValueError, AssertionError):
        mes = hoje.month
    try:
        ano = int(request.GET.get('ano') or hoje.year)
    except (TypeError, ValueError):
        ano = hoje.year

    contratos = Contrato.objects.filter(id__in=ids).order_by('cliente_nome')
    faturados_ids = set(
        NotaFiscal.objects
        .filter(contrato_id__in=ids, competencia_mes=mes, competencia_ano=ano, status='emitida')
        .values_list('contrato_id', flat=True)
        .distinct()
    )

    faturados     = []
    nao_faturados = []
    for c in contratos:
        item = {'id': c.id, 'nome': c.cliente_nome or c.omie_num_ctr or f'Contrato {c.id}'}
        if c.id in faturados_ids:
            faturados.append(item)
        else:
            nao_faturados.append(item)

    return JsonResponse({
        'ok': True, 'mes': mes, 'ano': ano,
        'faturados': faturados, 'nao_faturados': nao_faturados,
    })


def _digits(s):
    return re.sub(r'\D', '', s or '')


def _achar_contrato_por_cnpj(cnpj_digits):
    """
    Tenta achar o Contrato cujo tomador (cache local `dados_tomador.cpf_cnpj`)
    bate com o CNPJ/CPF informado. Compara em Python (dígitos only) em vez de
    fazer lookup de chave JSON no banco, pra não depender de suporte a JSON1
    no SQLite de produção.
    """
    if not cnpj_digits:
        return None
    for c in Contrato.objects.exclude(dados_tomador={}).only('id', 'cliente_nome', 'omie_num_ctr', 'dados_tomador'):
        if _digits((c.dados_tomador or {}).get('cpf_cnpj', '')) == cnpj_digits:
            return c
    return None


@login_required
def buscar_contrato_por_cnpj(request):
    """
    GET JSON — dado o CNPJ/CPF do tomador, tenta achar o Contrato
    correspondente. Params: ?cnpj=00.000.000/0000-00 (com ou sem máscara)
    """
    cnpj = _digits(request.GET.get('cnpj', ''))
    if not cnpj:
        return JsonResponse({'ok': False, 'erro': 'Informe um CNPJ/CPF.'})

    contrato = _achar_contrato_por_cnpj(cnpj)
    if contrato:
        return JsonResponse({
            'ok': True,
            'contrato': {'id': contrato.id, 'nome': contrato.cliente_nome or contrato.omie_num_ctr or f'Contrato {contrato.id}'},
        })
    return JsonResponse({'ok': True, 'contrato': None})


@login_required
def listar_contratos_selecao(request):
    """
    GET JSON — lista simples (id + nome) de todos os contratos, pra povoar o
    <select> de associação manual no "Importar Nota Fiscal" (usado quando o
    CNPJ do tomador não bate automaticamente com nenhum contrato cacheado, ou
    pra corrigir a sugestão automática).
    """
    contratos = Contrato.objects.order_by('cliente_nome').values('id', 'cliente_nome', 'omie_num_ctr')
    itens = [
        {'id': c['id'], 'nome': c['cliente_nome'] or c['omie_num_ctr'] or f"Contrato {c['id']}"}
        for c in contratos
    ]
    return JsonResponse({'ok': True, 'contratos': itens})


@login_required
def consultar_nota_saatri_para_importar(request):
    """
    GET JSON — 1º passo do "Importar Nota Fiscal": dado só o número da
    NFS-e, consulta o SAATRI (ConsultarNfsePorFaixa — mesma rota do "Baixar
    SAATRI") e devolve os dados completos da nota (tomador, valores,
    competência, descrição) já prontos pra conferência/importação, mais o
    Contrato sugerido por CNPJ (se achar).

    Params: ?numero=2995
    """
    numero = (request.GET.get('numero') or '').strip()
    if not numero:
        return JsonResponse({'ok': False, 'erro': 'Informe o número da NFS-e.'})

    from .saatri import client as saatri_client

    resultado = saatri_client.consultar_nfse_por_faixa(numero)
    notas = resultado.get('notas') or []
    if not notas:
        erros = resultado.get('erros') or []
        msg = ('; '.join(f"[{e['codigo']}] {e['mensagem']}" for e in erros)
               if erros else 'SAATRI não encontrou nenhuma NFS-e com esse número.')
        return JsonResponse({'ok': False, 'erro': msg})

    n = notas[0]
    cnpj_tomador = _digits(n.get('cnpj_tomador', ''))
    contrato = _achar_contrato_por_cnpj(cnpj_tomador)

    data_emissao_raw = n.get('data_emissao') or ''
    competencia_raw  = n.get('competencia') or data_emissao_raw
    comp_mes = comp_ano = None
    try:
        comp_ano = int(competencia_raw[0:4])
        comp_mes = int(competencia_raw[5:7])
    except (ValueError, IndexError):
        pass

    return JsonResponse({
        'ok': True,
        'nota': {
            'numero_nfse':        n.get('numero'),
            'codigo_verificacao': n.get('codigo_verificacao'),
            'cnpj_tomador':       cnpj_tomador,
            'cliente_nome':       n.get('cliente_nome'),
            'descricao':          n.get('descricao'),
            'valor_bruto':        str(n.get('valor_bruto') or 0),
            'valor_iss':          str(n.get('valor_iss') or 0),
            'valor_liquido':      str(n.get('valor_liquido') or 0),
            'data_emissao':       data_emissao_raw[:10] if data_emissao_raw else '',
            'competencia_mes':    comp_mes,
            'competencia_ano':    comp_ano,
        },
        'contrato_sugerido': (
            {'id': contrato.id, 'nome': contrato.cliente_nome or contrato.omie_num_ctr or f'Contrato {contrato.id}'}
            if contrato else None
        ),
    })


@login_required
def importar_nota_fiscal(request):
    """
    POST JSON — cria uma NotaFiscal com origem='manual': cadastro de uma nota
    que já existe (emitida fora do sistema, ou de um período anterior ao
    início do controle local) e que precisa aparecer nos relatórios junto
    com as demais. `contrato_id` é opcional — quando o tomador não bate com
    nenhum Contrato cadastrado, a nota é salva "avulsa" (sem contrato),
    identificada pelo `cnpj_tomador` salvo diretamente na nota.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    from .models import NotaFiscal
    import json as json_lib

    try:
        dados = json_lib.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'erro': 'Corpo da requisição inválido.'})

    contrato_id      = dados.get('contrato_id') or None
    numero_nfse      = (dados.get('numero_nfse') or '').strip()
    cnpj_tomador     = _digits(dados.get('cnpj_tomador', ''))
    cliente_nome     = (dados.get('cliente_nome') or '').strip()
    competencia_mes  = dados.get('competencia_mes')
    competencia_ano  = dados.get('competencia_ano')
    data_emissao     = (dados.get('data_emissao') or '').strip()
    valor_bruto      = dados.get('valor_bruto')

    if not numero_nfse:
        return JsonResponse({'ok': False, 'erro': 'Informe o número da NFS-e.'})
    if not competencia_mes or not competencia_ano:
        return JsonResponse({'ok': False, 'erro': 'Informe a competência (mês/ano).'})
    if not data_emissao:
        return JsonResponse({'ok': False, 'erro': 'Informe a data de emissão.'})
    if valor_bruto in (None, ''):
        return JsonResponse({'ok': False, 'erro': 'Informe o valor bruto da nota.'})

    contrato = None
    if contrato_id:
        contrato = Contrato.objects.filter(pk=contrato_id).first()
        if not contrato:
            return JsonResponse({'ok': False, 'erro': 'Contrato não encontrado.'})
        cliente_nome = cliente_nome or contrato.cliente_nome
    elif not cliente_nome:
        return JsonResponse({'ok': False, 'erro': 'Sem contrato associado — informe ao menos o nome do tomador (nota avulsa).'})

    if NotaFiscal.objects.filter(numero_nfse=numero_nfse).exists():
        return JsonResponse({'ok': False, 'erro': f'Já existe uma nota nº {numero_nfse} importada no sistema.'})

    try:
        valor_bruto   = Decimal(str(valor_bruto))
        valor_iss     = Decimal(str(dados.get('valor_iss') or 0))
        valor_liquido = Decimal(str(dados.get('valor_liquido') or valor_bruto))
    except Exception:
        return JsonResponse({'ok': False, 'erro': 'Valores inválidos.'})

    nota = NotaFiscal.objects.create(
        contrato=contrato,
        origem='manual',
        numero_nfse=numero_nfse,
        codigo_verificacao=(dados.get('codigo_verificacao') or '').strip() or None,
        cnpj_tomador=cnpj_tomador or None,
        cliente_nome=cliente_nome,
        descricao=(dados.get('descricao') or '').strip(),
        valor_bruto=valor_bruto,
        valor_iss=valor_iss,
        valor_liquido=valor_liquido,
        competencia_mes=int(competencia_mes),
        competencia_ano=int(competencia_ano),
        data_emissao=data_emissao,
        status='emitida',
    )

    return JsonResponse({'ok': True, 'nota_id': nota.id, 'avulsa': contrato is None})


@login_required
def consultar_notas_fiscais(request):
    """
    GET JSON — busca em NotaFiscal por nome do tomador, CNPJ, competência
    (de/até) e faixa de valor. Novo item "Consultar Notas" do modal
    Sincronizar NFS-e — cobre tanto notas normais (com Contrato) quanto
    avulsas (importadas manualmente sem Contrato).

    Params (todos opcionais): ?nome=&cnpj=&comp_ini=2026-01&comp_fim=2026-12
                               &valor_min=&valor_max=
    """
    from .models import NotaFiscal

    qs = NotaFiscal.objects.select_related('contrato').filter(status='emitida')

    nome = (request.GET.get('nome') or '').strip()
    if nome:
        qs = qs.filter(cliente_nome__icontains=nome)

    cnpj = _digits(request.GET.get('cnpj', ''))
    if cnpj:
        cond = Q(cnpj_tomador=cnpj)
        contrato_match = _achar_contrato_por_cnpj(cnpj)
        if contrato_match:
            cond |= Q(contrato_id=contrato_match.id)
        qs = qs.filter(cond)

    comp_ini = (request.GET.get('comp_ini') or '').strip()
    if comp_ini:
        try:
            ano_i, mes_i = (int(p) for p in comp_ini.split('-'))
            qs = qs.filter(Q(competencia_ano__gt=ano_i) | Q(competencia_ano=ano_i, competencia_mes__gte=mes_i))
        except ValueError:
            pass

    comp_fim = (request.GET.get('comp_fim') or '').strip()
    if comp_fim:
        try:
            ano_f, mes_f = (int(p) for p in comp_fim.split('-'))
            qs = qs.filter(Q(competencia_ano__lt=ano_f) | Q(competencia_ano=ano_f, competencia_mes__lte=mes_f))
        except ValueError:
            pass

    valor_min = request.GET.get('valor_min')
    if valor_min:
        try:
            qs = qs.filter(valor_liquido__gte=Decimal(valor_min))
        except Exception:
            pass

    valor_max = request.GET.get('valor_max')
    if valor_max:
        try:
            qs = qs.filter(valor_liquido__lte=Decimal(valor_max))
        except Exception:
            pass

    qs = qs.order_by('-competencia_ano', '-competencia_mes', '-data_emissao')[:200]

    itens = [{
        'id':             n.id,
        'numero_nfse':    n.numero_nfse,
        'cliente_nome':   n.cliente_nome,
        'origem':         n.origem,
        'competencia':    f'{n.competencia_mes:02d}/{n.competencia_ano}',
        'valor_liquido':  str(n.valor_liquido),
        'data_emissao':   n.data_emissao.isoformat() if n.data_emissao else None,
        'avulsa':         n.contrato_id is None,
    } for n in qs]

    return JsonResponse({'ok': True, 'total': len(itens), 'notas': itens})


@login_required
def sincronizar_receitas_view(request):
    """
    Aciona a sincronização manual.
    """
    service = OmieService()
    try:
        service.sincronizar_dados()
        return HttpResponse("""
            <script>
                alert('Sincronização concluída com sucesso!');
                window.location.href = document.referrer;
            </script>
        """)
    except Exception as e:
        return HttpResponse(f"Erro na sincronização: {e}")


# views_receitas_notas.py
# Adicione estas views ao seu views.py existente (junto com receitas_dashboard e editar_lote_modal)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.contrib import messages
from datetime import date
import json

# Importe seus models e service
from .models import Contrato, NotaFiscal, RecebimentoNota
from .omie_service import OmieService


# ─────────────────────────────────────────────────────────────
#  DASHBOARD DE NOTAS POR COMPETÊNCIA
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import date
import json

from .models import Contrato, NotaFiscal, RecebimentoNota
from .omie_service import OmieService


# views_receitas_notas.py  — versão 2
# Adicione / substitua no seu views.py existente.

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from datetime import date
import json

from .models import Contrato, NotaFiscal, RecebimentoNota
from .omie_service import OmieService


# ─────────────────────────────────────────────────────────────
#  DASHBOARD DE NOTAS POR COMPETÊNCIA
# ─────────────────────────────────────────────────────────────
from collections import defaultdict
from django.http import JsonResponse

# ─────────────────────────────────────────────────────────────────
# Dependências adicionais necessárias no topo do arquivo de views
# ─────────────────────────────────────────────────────────────────
from collections import defaultdict
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Case, When, DecimalField, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render

# from .models import NotaFiscal, Contrato  ← já existem no seu arquivo


# ─────────────────────────────────────────────────────────────────
# VIEW PRINCIPAL — suporte a múltiplos meses e múltiplos municípios
# ─────────────────────────────────────────────────────────────────
'''
@login_required
def notas_competencia(request):
    hoje = date.today()

    # ── Coleta multi-selects ──────────────────────────────────────────────────
    meses_sel     = request.GET.getlist('mes')
    anos_sel      = request.GET.getlist('ano')
    municipios_sel = request.GET.getlist('municipio')
    entidades_sel = request.GET.getlist('entidade')
    contratos_sel = request.GET.getlist('contrato')
    status_sel    = request.GET.getlist('status')

    # ── Normaliza para inteiros com defaults ──────────────────────────────────
    meses_int = [int(m) for m in meses_sel if m.isdigit() and 1 <= int(m) <= 12]
    if not meses_int:
        meses_int = [hoje.month]

    anos_range_list = list(range(hoje.year - 2, hoje.year + 2))
    anos_int = [int(a) for a in anos_sel if a.isdigit() and int(a) in anos_range_list]
    if not anos_int:
        anos_int = [hoje.year]

    # ── Helper: aplica filtros comuns de município / entidade / contrato ──────
    def apply_common_filters(qs):
        if municipios_sel:
            qs = qs.filter(contrato__municipio__in=municipios_sel)
        if entidades_sel:
            qs = qs.filter(contrato__tipo_entidade__in=entidades_sel)
        if contratos_sel:
            qs = qs.filter(contrato_id__in=contratos_sel)
        return qs

    ORDER = (
        'contrato__municipio', 'contrato__tipo_entidade',
        'contrato__cliente_nome', 'data_emissao',
    )

    # ── Bases por status ──────────────────────────────────────────────────────
    emitidas_qs = apply_common_filters(
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='emitida')
        .select_related('contrato', 'confirmacao')
        .order_by(*ORDER)
    )
    inativas_qs = apply_common_filters(
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='inativa')
        .select_related('contrato', 'confirmacao', 'inativada_por')
        .order_by(*ORDER)
    )

    # ── Filtra por status selecionados ────────────────────────────────────────
    show_paga     = 'paga'     in status_sel
    show_pendente = 'pendente' in status_sel
    show_inativa  = 'inativa'  in status_sel

    parts = []
    if not status_sel:
        # padrão: todas as emitidas
        parts.append(emitidas_qs)
    else:
        if show_paga and show_pendente:
            parts.append(emitidas_qs)                                   # todas emitidas
        elif show_paga:
            parts.append(emitidas_qs.filter(confirmacao__confirmado=True))
        elif show_pendente:
            parts.append(emitidas_qs.exclude(confirmacao__confirmado=True))
        if show_inativa:
            parts.append(inativas_qs)

    if not parts:
        parts.append(emitidas_qs)

    notas_qs = []
    for part in parts:
        notas_qs.extend(list(part))

    # ── KPIs (base: todas emitidas do período, sem outros filtros) ────────────
    base_kpi = (
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='emitida')
        .select_related('confirmacao')
    )
    total_emitido  = float(base_kpi.aggregate(s=Sum('valor_liquido'))['s'] or 0)
    total_recebido = sum(
        float(n.confirmacao.valor_recebido or n.valor_liquido)
        for n in base_kpi
        if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
    )
    qtd_emitidas  = base_kpi.count()
    qtd_pagas     = sum(
        1 for n in base_kpi
        if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
    )
    qtd_pendentes = qtd_emitidas - qtd_pagas
    qtd_inativas  = NotaFiscal.objects.filter(
        competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='inativa'
    ).count()
    pct_recebido = round((total_recebido / total_emitido * 100) if total_emitido else 0, 1)
    a_receber    = total_emitido - total_recebido

    # ── Municípios disponíveis ────────────────────────────────────────────────
    municipios = (
        Contrato.objects
        .filter(
            notas_fiscais__competencia_mes__in=meses_int,
            notas_fiscais__competencia_ano__in=anos_int,
            notas_fiscais__status='emitida',
        )
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )

    # ── Contratos disponíveis ─────────────────────────────────────────────────
    contratos_filtro = (
        Contrato.objects
        .filter(
            notas_fiscais__competencia_mes__in=meses_int,
            notas_fiscais__competencia_ano__in=anos_int,
        )
        .distinct()
        .order_by('municipio', 'cliente_nome')
    )

    # ── Lista final ───────────────────────────────────────────────────────────
    notas_list = []
    for nota in notas_qs:
        rec = getattr(nota, 'confirmacao', None)
        notas_list.append({
            'nota':                  nota,
            'municipio':             nota.municipio,
            'tipo_entidade':         nota.tipo_entidade,
            'tipo_entidade_display': nota.tipo_entidade_display,
            'paga':                  bool(rec and rec.confirmado),
            'valor_recebido':        (rec.valor_recebido or nota.valor_liquido) if (rec and rec.confirmado) else None,
            'data_recebimento':      rec.data_recebimento if rec else None,
            'observacao':            rec.observacao if rec else '',
        })

    # ── Constantes de exibição ────────────────────────────────────────────────
    MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    ENTIDADES = [
        ('municipio', 'Prefeitura Municipal'),
        ('camara',    'Câmara Municipal'),
    ]

    STATUS_OPTS = [
        ('paga',     '✅ Pagas'),
        ('pendente', '⏳ Pendentes'),
        ('inativa',  '🚫 Inativas'),
    ]

    # ── Labels dos botões ─────────────────────────────────────────────────────
    if len(meses_int) == 12:
        meses_label = 'Todos os meses'
    elif len(meses_int) == 1:
        meses_label = MESES[meses_int[0] - 1]
    else:
        meses_label = ', '.join(MESES[m - 1][:3] for m in sorted(meses_int))

    if len(anos_int) == len(anos_range_list):
        anos_label = 'Todos os anos'
    elif len(anos_int) == 1:
        anos_label = str(anos_int[0])
    else:
        anos_label = ', '.join(str(a) for a in sorted(anos_int))

    entidades_map = dict(ENTIDADES)
    if not entidades_sel:
        entidades_label = 'Todas entidades'
    elif len(entidades_sel) == 1:
        entidades_label = entidades_map.get(entidades_sel[0], entidades_sel[0])
    else:
        entidades_label = f'{len(entidades_sel)} entidades'

    status_map = dict(STATUS_OPTS)
    if not status_sel:
        status_label = 'Todas as notas'
    elif len(status_sel) == 1:
        status_label = status_map.get(status_sel[0], status_sel[0])
    else:
        status_label = f'{len(status_sel)} status'

    if not contratos_sel:
        contratos_label = 'Todos os contratos'
    elif len(contratos_sel) == 1:
        try:
            c = Contrato.objects.get(id=int(contratos_sel[0]))
            contratos_label = c.cliente_nome or str(c.omie_num_ctr)
        except (Contrato.DoesNotExist, ValueError):
            contratos_label = '1 contrato'
    else:
        contratos_label = f'{len(contratos_sel)} contratos'

    # ── Context ───────────────────────────────────────────────────────────────
    context = {
        # seleções (listas de ints / strings para comparação no template)
        'meses_sel':      meses_int,
        'anos_sel':       anos_int,
        'municipios_sel': municipios_sel,
        'entidades_sel':  entidades_sel,
        'contratos_sel':  contratos_sel,   # lista de strings (vindas do GET)
        'status_sel':     status_sel,
        # labels dos botões
        'meses_label':    meses_label,
        'anos_label':     anos_label,
        'entidades_label': entidades_label,
        'contratos_label': contratos_label,
        'status_label':   status_label,
        # dados
        'notas_list':        notas_list,
        'municipios':        list(municipios),
        'contratos_filtro':  contratos_filtro,
        # KPIs
        'total_emitido':  total_emitido,
        'total_recebido': total_recebido,
        'a_receber':      a_receber,
        'qtd_emitidas':   qtd_emitidas,
        'qtd_pagas':      qtd_pagas,
        'qtd_pendentes':  qtd_pendentes,
        'qtd_inativas':   qtd_inativas,
        'pct_recebido':   pct_recebido,
        # ranges / constantes para o template
        'anos_range':   anos_range_list,
        'meses_range':  range(1, 13),
        'MESES':        MESES,
        'ENTIDADES':    ENTIDADES,
        'STATUS_OPTS':  STATUS_OPTS,
    }
    return render(request, 'notas_competencia.html', context)
'''


import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import (
    NotaFiscal,
    Contrato,
    PrevisaoPagamento,
    PrevisaoPagamentoLog,
    RecebimentoNota,
)


# ─────────────────────────────────────────────────────────────────
# Helper de serialização — previsão + histórico, pronto pro JS
# ─────────────────────────────────────────────────────────────────
def _serializar_previsao(p):
    return {
        'id':                     p.id,
        'municipio':              p.municipio,
        'tipo_entidade':          p.tipo_entidade,
        'competencia_mes':        p.competencia_mes,
        'competencia_ano':        p.competencia_ano,
        'data_prevista':          p.data_prevista.isoformat() if p.data_prevista else None,
        'valor_previsto':         str(p.valor_previsto),
        'status':                 p.status,
        'status_display':         p.get_status_display(),
        'data_verificacao':       p.data_verificacao.isoformat() if p.data_verificacao else None,
        'observacao':             p.observacao or '',
        'atualizado_em':          p.atualizado_em.isoformat() if p.atualizado_em else None,
        'historico': [
            {
                'tipo_evento':             ev.tipo_evento,
                'tipo_evento_display':     ev.get_tipo_evento_display(),
                'data_prevista_snapshot':  ev.data_prevista_snapshot.isoformat() if ev.data_prevista_snapshot else None,
                'valor_previsto_snapshot': str(ev.valor_previsto_snapshot) if ev.valor_previsto_snapshot is not None else None,
                'observacao':              ev.observacao or '',
                'usuario':                 ev.usuario.get_username() if ev.usuario_id else None,
                'criado_em':               ev.criado_em.isoformat() if ev.criado_em else None,
            }
            for ev in p.historico.all()
        ],
    }


# ─────────────────────────────────────────────────────────────────
# VIEW PRINCIPAL — suporte a múltiplos meses, múltiplos municípios
# e agora também a previsão de pagamento por município-entidade
# ─────────────────────────────────────────────────────────────────
@login_required
def notas_competencia(request):
    hoje = date.today()

    # ── Coleta multi-selects ──────────────────────────────────────────────────
    meses_sel      = request.GET.getlist('mes')
    anos_sel       = request.GET.getlist('ano')
    municipios_sel = request.GET.getlist('municipio')
    entidades_sel  = request.GET.getlist('entidade')
    contratos_sel  = request.GET.getlist('contrato')
    status_sel     = request.GET.getlist('status')

    # ── Normaliza para inteiros com defaults ──────────────────────────────────
    meses_int = [int(m) for m in meses_sel if m.isdigit() and 1 <= int(m) <= 12]
    if not meses_int:
        meses_int = [hoje.month]

    anos_range_list = list(range(hoje.year - 2, hoje.year + 2))
    anos_int = [int(a) for a in anos_sel if a.isdigit() and int(a) in anos_range_list]
    if not anos_int:
        anos_int = [hoje.year]

    # ── Helper: aplica filtros comuns de município / entidade / contrato ──────
    def apply_common_filters(qs):
        if municipios_sel:
            qs = qs.filter(contrato__municipio__in=municipios_sel)
        if entidades_sel:
            qs = qs.filter(contrato__tipo_entidade__in=entidades_sel)
        if contratos_sel:
            qs = qs.filter(contrato_id__in=contratos_sel)
        return qs

    ORDER = (
        'contrato__municipio', 'contrato__tipo_entidade',
        'contrato__cliente_nome', 'data_emissao',
    )

    # ── Bases por status ──────────────────────────────────────────────────────
    emitidas_qs = apply_common_filters(
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='emitida')
        .select_related('contrato', 'confirmacao')
        .order_by(*ORDER)
    )
    inativas_qs = apply_common_filters(
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='inativa')
        .select_related('contrato', 'confirmacao', 'inativada_por')
        .order_by(*ORDER)
    )

    # ── Filtra por status selecionados ────────────────────────────────────────
    show_paga     = 'paga'     in status_sel
    show_pendente = 'pendente' in status_sel
    show_inativa  = 'inativa'  in status_sel

    parts = []
    if not status_sel:
        # padrão: todas as emitidas
        parts.append(emitidas_qs)
    else:
        if show_paga and show_pendente:
            parts.append(emitidas_qs)                                   # todas emitidas
        elif show_paga:
            parts.append(emitidas_qs.filter(confirmacao__confirmado=True))
        elif show_pendente:
            parts.append(emitidas_qs.exclude(confirmacao__confirmado=True))
        if show_inativa:
            parts.append(inativas_qs)

    if not parts:
        parts.append(emitidas_qs)

    notas_qs = []
    for part in parts:
        notas_qs.extend(list(part))

    # ── KPIs (base: todas emitidas do período, sem outros filtros) ────────────
    base_kpi = (
        NotaFiscal.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='emitida')
        .select_related('confirmacao')
    )
    total_emitido  = float(base_kpi.aggregate(s=Sum('valor_liquido'))['s'] or 0)
    total_recebido = sum(
        float(n.confirmacao.valor_recebido or n.valor_liquido)
        for n in base_kpi
        if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
    )
    qtd_emitidas  = base_kpi.count()
    qtd_pagas     = sum(
        1 for n in base_kpi
        if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
    )
    qtd_pendentes = qtd_emitidas - qtd_pagas
    qtd_inativas  = NotaFiscal.objects.filter(
        competencia_mes__in=meses_int, competencia_ano__in=anos_int, status='inativa'
    ).count()
    pct_recebido = round((total_recebido / total_emitido * 100) if total_emitido else 0, 1)
    a_receber    = total_emitido - total_recebido

    # ── Municípios disponíveis ────────────────────────────────────────────────
    municipios = (
        Contrato.objects
        .filter(
            notas_fiscais__competencia_mes__in=meses_int,
            notas_fiscais__competencia_ano__in=anos_int,
            notas_fiscais__status='emitida',
        )
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )

    # ── Contratos disponíveis ─────────────────────────────────────────────────
    contratos_filtro = (
        Contrato.objects
        .filter(
            notas_fiscais__competencia_mes__in=meses_int,
            notas_fiscais__competencia_ano__in=anos_int,
        )
        .distinct()
        .order_by('municipio', 'cliente_nome')
    )

    # ── Lista final ───────────────────────────────────────────────────────────
    notas_list = []
    for nota in notas_qs:
        rec = getattr(nota, 'confirmacao', None)
        notas_list.append({
            'nota':                  nota,
            'municipio':             nota.municipio,
            'tipo_entidade':         nota.tipo_entidade,
            'tipo_entidade_display': nota.tipo_entidade_display,
            'paga':                  bool(rec and rec.confirmado),
            'valor_recebido':        (rec.valor_recebido or nota.valor_liquido) if (rec and rec.confirmado) else None,
            'data_recebimento':      rec.data_recebimento if rec else None,
            'observacao':            rec.observacao if rec else '',
        })

    # ── PREVISÃO DE PAGAMENTO — agregada por MUNICÍPIO-ENTIDADE ───────────────
    # Busca todas as previsões da(s) competência(s) selecionada(s), já
    # respeitando os filtros de município / entidade em vigor. O histórico
    # (PrevisaoPagamentoLog) vem junto via prefetch, então o painel não
    # precisa de um endpoint GET separado para montar a timeline.
    previsoes_qs = (
        PrevisaoPagamento.objects
        .filter(competencia_mes__in=meses_int, competencia_ano__in=anos_int)
        .prefetch_related('historico')
        .order_by('municipio', 'tipo_entidade', '-competencia_ano', '-competencia_mes')
    )
    if municipios_sel:
        previsoes_qs = previsoes_qs.filter(municipio__in=municipios_sel)
    if entidades_sel:
        previsoes_qs = previsoes_qs.filter(tipo_entidade__in=entidades_sel)

    previsoes_data = [_serializar_previsao(p) for p in previsoes_qs]

    # Combinações mês/ano atualmente em filtro — usado no modal para
    # oferecer "nova previsão para esta competência" quando ainda não existe.
    competencias_selecionadas = [
        {'mes': m, 'ano': a} for a in sorted(anos_int) for m in sorted(meses_int)
    ]

    # ── Constantes de exibição ────────────────────────────────────────────────
    MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    ENTIDADES = [
        ('municipio', 'Prefeitura Municipal'),
        ('camara',    'Câmara Municipal'),
    ]

    STATUS_OPTS = [
        ('paga',     '✅ Pagas'),
        ('pendente', '⏳ Pendentes'),
        ('inativa',  '🚫 Inativas'),
    ]

    # ── Labels dos botões ─────────────────────────────────────────────────────
    if len(meses_int) == 12:
        meses_label = 'Todos os meses'
    elif len(meses_int) == 1:
        meses_label = MESES[meses_int[0] - 1]
    else:
        meses_label = ', '.join(MESES[m - 1][:3] for m in sorted(meses_int))

    if len(anos_int) == len(anos_range_list):
        anos_label = 'Todos os anos'
    elif len(anos_int) == 1:
        anos_label = str(anos_int[0])
    else:
        anos_label = ', '.join(str(a) for a in sorted(anos_int))

    entidades_map = dict(ENTIDADES)
    if not entidades_sel:
        entidades_label = 'Todas entidades'
    elif len(entidades_sel) == 1:
        entidades_label = entidades_map.get(entidades_sel[0], entidades_sel[0])
    else:
        entidades_label = f'{len(entidades_sel)} entidades'

    status_map = dict(STATUS_OPTS)
    if not status_sel:
        status_label = 'Todas as notas'
    elif len(status_sel) == 1:
        status_label = status_map.get(status_sel[0], status_sel[0])
    else:
        status_label = f'{len(status_sel)} status'

    if not contratos_sel:
        contratos_label = 'Todos os contratos'
    elif len(contratos_sel) == 1:
        try:
            c = Contrato.objects.get(id=int(contratos_sel[0]))
            contratos_label = c.cliente_nome or str(c.omie_num_ctr)
        except (Contrato.DoesNotExist, ValueError):
            contratos_label = '1 contrato'
    else:
        contratos_label = f'{len(contratos_sel)} contratos'

    # ── Context ───────────────────────────────────────────────────────────────
    context = {
        # seleções (listas de ints / strings para comparação no template)
        'meses_sel':      meses_int,
        'anos_sel':       anos_int,
        'municipios_sel': municipios_sel,
        'entidades_sel':  entidades_sel,
        'contratos_sel':  contratos_sel,   # lista de strings (vindas do GET)
        'status_sel':     status_sel,
        # labels dos botões
        'meses_label':    meses_label,
        'anos_label':     anos_label,
        'entidades_label': entidades_label,
        'contratos_label': contratos_label,
        'status_label':   status_label,
        # dados
        'notas_list':        notas_list,
        'municipios':         list(municipios),
        'contratos_filtro':   contratos_filtro,
        # KPIs
        'total_emitido':  total_emitido,
        'total_recebido': total_recebido,
        'a_receber':      a_receber,
        'qtd_emitidas':   qtd_emitidas,
        'qtd_pagas':      qtd_pagas,
        'qtd_pendentes':  qtd_pendentes,
        'qtd_inativas':   qtd_inativas,
        'pct_recebido':   pct_recebido,
        # ranges / constantes para o template
        'anos_range':   anos_range_list,
        'meses_range':  range(1, 13),
        'MESES':        MESES,
        'ENTIDADES':    ENTIDADES,
        'STATUS_OPTS':  STATUS_OPTS,
        # ── previsão de pagamento (painel; não entra no impresso por padrão) ──
        'previsoes_data':             previsoes_data,
        'competencias_selecionadas':  competencias_selecionadas,
    }
    return render(request, 'notas_competencia.html', context)


# ─────────────────────────────────────────────────────────────────
# ENDPOINTS DE APOIO — CRUD de previsão via AJAX (chamados pelo modal)
# ─────────────────────────────────────────────────────────────────
@login_required
@require_POST
def previsao_salvar(request):
    """
    Cria (se não existir) ou edita (se já existir) a previsão da
    competência para um município-entidade. Gera evento no histórico
    ('criada' ou 'editada').
    """
    try:
        body = json.loads(request.body)
        municipio       = (body.get('municipio') or '').strip()
        tipo_entidade   = body.get('tipo_entidade')
        competencia_mes = int(body.get('competencia_mes'))
        competencia_ano = int(body.get('competencia_ano'))

        # Converte a string 'YYYY-MM-DD' para um objeto date
        data_prevista_str = body.get('data_prevista')
        data_prevista = date.fromisoformat(data_prevista_str) if data_prevista_str else None

        valor_previsto  = body.get('valor_previsto')
        observacao      = body.get('observacao') or ''
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    if not municipio or tipo_entidade not in ('municipio', 'camara') or not data_prevista or valor_previsto in (None, ''):
        return JsonResponse({'ok': False, 'erro': 'Preencha município, entidade, data prevista e valor previsto.'}, status=400)

    previsao, criada = PrevisaoPagamento.objects.get_or_create(
        municipio=municipio,
        tipo_entidade=tipo_entidade,
        competencia_mes=competencia_mes,
        competencia_ano=competencia_ano,
        defaults={
            'data_prevista':  data_prevista,
            'valor_previsto': valor_previsto,
            'observacao':     observacao,
            'criado_por':     request.user,
        },
    )

    if not criada:
        previsao.data_prevista   = data_prevista
        previsao.valor_previsto  = valor_previsto
        previsao.observacao      = observacao
        previsao.atualizado_por  = request.user
        previsao.save()

    PrevisaoPagamentoLog.objects.create(
        previsao=previsao,
        tipo_evento='criada' if criada else 'editada',
        data_prevista_snapshot=previsao.data_prevista,
        valor_previsto_snapshot=previsao.valor_previsto,
        observacao=observacao,
        usuario=request.user,
    )

    return JsonResponse({'ok': True, 'previsao': _serializar_previsao(previsao)})


@login_required
@require_POST
@transaction.atomic
def previsao_marcar(request):
    """
    Marca a previsão como cumprida / não cumprida / reaberta.
    Se cumprida, aplica o valor previsto automaticamente nas notas pendentes
    do município/entidade, priorizando as mais antigas e de menor valor.
    """
    try:
        body = json.loads(request.body)
        previsao_id = int(body.get('id'))
        novo_status = body.get('status')
        observacao  = body.get('observacao') or ''
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    if novo_status not in ('cumprida', 'nao_cumprida', 'pendente'):
        return JsonResponse({'ok': False, 'erro': 'Status inválido.'}, status=400)

    try:
        previsao = PrevisaoPagamento.objects.get(id=previsao_id)
    except PrevisaoPagamento.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Previsão não encontrada.'}, status=404)

    # 1. Atualiza a Previsão
    previsao.status = novo_status
    previsao.data_verificacao = date.today() if novo_status != 'pendente' else None
    previsao.atualizado_por = request.user
    previsao.save()

    # ────────────────────────────────────────────────────────────────────────
    # 2. EFEITO CASCATA: DISTRIBUIÇÃO DO PAGAMENTO AUTOMÁTICO
    # ────────────────────────────────────────────────────────────────────────
    if novo_status == 'cumprida' and previsao.valor_previsto:
        saldo_distribuir = Decimal(str(previsao.valor_previsto))

        # Busca todas as notas PENDENTES desse município e entidade
        notas_pendentes = NotaFiscal.objects.filter(
            contrato__municipio=previsao.municipio,
            contrato__tipo_entidade=previsao.tipo_entidade,
            status='emitida'
        ).exclude(
            confirmacao__confirmado=True
        ).order_by('competencia_ano', 'competencia_mes', 'valor_liquido')

        for nota in notas_pendentes:
            if saldo_distribuir <= 0:
                break

            conf, created = RecebimentoNota.objects.get_or_create(nota=nota)

            valor_ja_pago = Decimal(str(conf.valor_recebido or 0))
            valor_da_nota = Decimal(str(nota.valor_liquido))
            falta_pagar   = valor_da_nota - valor_ja_pago

            if falta_pagar <= 0:
                continue

            if saldo_distribuir >= falta_pagar:
                # Pagamento Total
                conf.valor_recebido = valor_ja_pago + falta_pagar
                conf.confirmado = True
                conf.data_recebimento = date.today()
                conf.registrado_por = request.user

                if created:
                    conf.observacao = "Paga automaticamente via Previsão."

                conf.save()
                saldo_distribuir -= falta_pagar

            else:
                # Pagamento Parcial
                conf.valor_recebido = valor_ja_pago + saldo_distribuir
                conf.confirmado = False
                conf.data_recebimento = date.today()
                conf.registrado_por = request.user

                obs_adicional = f"Pagamento parcial ({saldo_distribuir}) via Previsão em {date.today().strftime('%d/%m/%Y')}."
                conf.observacao = f"{conf.observacao} | {obs_adicional}" if conf.observacao else obs_adicional

                conf.save()
                saldo_distribuir = 0
    # ────────────────────────────────────────────────────────────────────────

    # 3. Gera o histórico
    tipo_evento = {
        'cumprida':     'cumprida',
        'nao_cumprida': 'nao_cumprida',
        'pendente':     'reaberta',
    }[novo_status]

    PrevisaoPagamentoLog.objects.create(
        previsao=previsao,
        tipo_evento=tipo_evento,
        data_prevista_snapshot=previsao.data_prevista,
        valor_previsto_snapshot=previsao.valor_previsto,
        observacao=observacao,
        usuario=request.user,
    )

    return JsonResponse({'ok': True, 'previsao': _serializar_previsao(previsao)})


# ─────────────────────────────────────────────────────────────────
# VIEW JSON — dados pivot para o modal (por cidade × mês)
# Retorna valores separados: emitido / recebido / pendente
# ─────────────────────────────────────────────────────────────────
from collections import defaultdict
from datetime import date
from django.db.models import Sum, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
# Lembre-se de importar seus models (NotaFiscal, Contrato, etc)

@login_required
def relatorio_municipios_pivot(request):
    hoje = date.today()

    anos_sel     = request.GET.getlist('ano') or [str(hoje.year)]
    entidade_sel = request.GET.get('entidade', '')
    muns_sel     = request.GET.getlist('municipio')

    anos_int = []
    for a in anos_sel:
        try:
            # Tratamento: Remove pontos e vírgulas antes de converter para inteiro
            ano_limpo = str(a).replace('.', '').replace(',', '').strip()
            anos_int.append(int(ano_limpo))
        except ValueError:
            pass

    if not anos_int:
        anos_int = [hoje.year]

    # ── QuerySet anotado com emitido e recebido ──
    notas_qs = (
        NotaFiscal.objects
        .filter(competencia_ano__in=anos_int, status='emitida')
    )
    if entidade_sel:
        notas_qs = notas_qs.filter(contrato__tipo_entidade=entidade_sel)
    if muns_sel:
        notas_qs = notas_qs.filter(contrato__municipio__in=muns_sel)

    notas_agg = (
        notas_qs
        .values('contrato__municipio', 'competencia_ano', 'competencia_mes')
        .annotate(
            total_emitido=Sum('valor_liquido'),
            total_recebido=Sum(
                Case(
                    When(
                        confirmacao__confirmado=True,
                        then=Coalesce(
                            'confirmacao__valor_recebido',
                            'valor_liquido',
                        ),
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            ),
        )
    )

    # ── Construção dos pivôs ──
    pivot_emitido  = defaultdict(dict)
    pivot_recebido = defaultdict(dict)
    cols_set       = set()

    for row in notas_agg:
        mun = row['contrato__municipio'] or 'Sem cidade'
        col = (row['competencia_ano'], row['competencia_mes'])
        em  = float(row['total_emitido']  or 0)
        rec = float(row['total_recebido'] or 0)
        pivot_emitido[mun][col]  = em
        pivot_recebido[mun][col] = rec
        cols_set.add(col)

    # Colunas: ano desc → mes asc
    cols = sorted(cols_set, key=lambda x: (x[0], x[1]))
    MESES_ABREV = ['jan','fev','mar','abr','mai','jun',
                   'jul','ago','set','out','nov','dez']
    colunas = [{'ano': c[0], 'mes': c[1], 'mes_nome': MESES_ABREV[c[1]-1]} for c in cols]

    municipios_ord     = sorted(set(list(pivot_emitido.keys()) + list(pivot_recebido.keys())))
    col_totais_em      = [0.0] * len(cols)
    col_totais_rec     = [0.0] * len(cols)
    grand_em           = 0.0
    grand_rec          = 0.0
    rows_data          = []

    for mun in municipios_ord:
        vals_em  = []
        vals_rec = []
        row_em   = 0.0
        row_rec  = 0.0

        for i, col in enumerate(cols):
            em  = pivot_emitido[mun].get(col,  0.0)
            rec = pivot_recebido[mun].get(col, 0.0)
            vals_em.append(em)
            vals_rec.append(rec)
            row_em          += em
            row_rec         += rec
            col_totais_em[i]  += em
            col_totais_rec[i] += rec

        grand_em  += row_em
        grand_rec += row_rec

        rows_data.append({
            'municipio':        mun,
            'valores_emitido':  vals_em,
            'valores_recebido': vals_rec,
            'valores_pendente': [round(e - r, 2) for e, r in zip(vals_em, vals_rec)],
            'total_emitido':    round(row_em, 2),
            'total_recebido':   round(row_rec, 2),
            'total_pendente':   round(row_em - row_rec, 2),
        })

    # ── Municípios disponíveis para o filtro do modal ──
    muns_disponiveis = list(
        Contrato.objects
        .filter(
            notas_fiscais__competencia_ano__in=anos_int,
            notas_fiscais__status='emitida',
        )
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )

    grand_pen = round(grand_em - grand_rec, 2)

    return JsonResponse({
        'colunas':                colunas,
        'rows':                   rows_data,
        # totais de colunas por tipo
        'col_totais_emitido':     [round(v, 2) for v in col_totais_em],
        'col_totais_recebido':    [round(v, 2) for v in col_totais_rec],
        'col_totais_pendente':    [round(e - r, 2) for e, r in zip(col_totais_em, col_totais_rec)],
        # grand totals
        'grand_emitido':          round(grand_em,  2),
        'grand_recebido':         round(grand_rec, 2),
        'grand_pendente':         grand_pen,
        # filtro
        'municipios_disponiveis': muns_disponiveis,
        'anos_sel':               anos_int,
    })

# ─────────────────────────────────────────────────────────────
#  CONFIRMAR / DESFAZER RECEBIMENTO (AJAX)
# ─────────────────────────────────────────────────────────────
@login_required
def confirmar_recebimento(request, nota_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido'}, status=405)

    nota = get_object_or_404(NotaFiscal, id=nota_id)

    try:
        body = json.loads(request.body)
    except Exception:
        body = {}

    confirmado       = body.get('confirmado', True)
    valor_recebido   = body.get('valor_recebido')
    data_recebimento = body.get('data_recebimento')
    observacao       = body.get('observacao', '')

    data_obj = None
    if data_recebimento:
        try:
            from datetime import datetime as dt
            data_obj = dt.strptime(data_recebimento, '%Y-%m-%d').date()
        except ValueError:
            pass

    rec, _ = RecebimentoNota.objects.get_or_create(nota=nota)
    rec.confirmado       = confirmado
    rec.valor_recebido   = valor_recebido if valor_recebido else None
    rec.data_recebimento = data_obj or (date.today() if confirmado else None)
    rec.observacao       = observacao
    rec.registrado_por   = request.user
    rec.save()

    return JsonResponse({
        'ok':             True,
        'confirmado':     rec.confirmado,
        'valor_recebido': str(rec.valor_recebido or nota.valor_liquido),
        'data':           rec.data_recebimento.strftime('%d/%m/%Y') if rec.data_recebimento else '',
    })


# ─────────────────────────────────────────────────────────────
#  INATIVAR / REATIVAR NOTA (AJAX)
# ─────────────────────────────────────────────────────────────
@login_required
def inativar_nota(request, nota_id):
    """
    POST: alterna status entre 'emitida' e 'inativa'.
    Body JSON: { "inativar": true|false, "motivo": "..." }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido'}, status=405)

    nota = get_object_or_404(NotaFiscal, id=nota_id)

    try:
        body = json.loads(request.body)
    except Exception:
        body = {}

    inativar = body.get('inativar', True)
    motivo   = body.get('motivo', '').strip()

    if inativar:
        nota.status           = 'inativa'
        nota.inativada_por    = request.user
        nota.inativada_em     = timezone.now()
        nota.motivo_inativacao = motivo or 'Inativada manualmente'
    else:
        nota.status            = 'emitida'
        nota.inativada_por     = None
        nota.inativada_em      = None
        nota.motivo_inativacao = None

    nota.save()

    return JsonResponse({
        'ok':      True,
        'status':  nota.status,
        'inativa': nota.status == 'inativa',
    })


# ─────────────────────────────────────────────────────────────
#  SINCRONIZAR NFS-e
# ─────────────────────────────────────────────────────────────
@login_required
def sincronizar_nfse(request):
    hoje  = date.today()
    mes   = request.GET.get('mes', str(hoje.month))
    ano   = request.GET.get('ano', str(hoje.year))
    volta = request.GET.get('next', 'notas_competencia')

    try:
        service = OmieService()
        criadas, atualizadas = service.sincronizar_nfse(mes=int(mes), ano=int(ano))

        # Resolve também os RPS SAATRI Direto pendentes (aceitos pela DPS,
        # aguardando a SEFIN gerar a NFS-e) — mesmo clique, um só sync.
        total_saatri, resolvidos_saatri, _ = sincronizar_saatri_pendentes()

        msg = f'✅ NFS-e sincronizadas: {criadas} novas · {atualizadas} atualizadas ({int(mes):02d}/{ano})'
        msg += (
            f' · SAATRI: {resolvidos_saatri}/{total_saatri} resolvidas' if total_saatri
            else ' · SAATRI: nada pendente'
        )
        messages.success(request, msg)
    except Exception as e:
        messages.error(request, f'❌ Erro na sincronização: {e}')

    return redirect(reverse(volta) + f'?mes={mes}&ano={ano}')


# ─────────────────────────────────────────────────────────────
#  RELATÓRIO ANUAL
# ─────────────────────────────────────────────────────────────

@login_required
def relatorio_receitas(request):
    hoje    = date.today()
    ano_sel = request.GET.get('ano', '').strip()
    ano     = int(ano_sel) if ano_sel.isdigit() else hoje.year  # fix 1: ano_raw → ano_sel

    MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
             'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']

    relatorio = []
    for mes in range(1, 13):
        notas = list(                               # fix 3: cache em lista → 1 query por mês
            NotaFiscal.objects.filter(
                competencia_mes=mes,
                competencia_ano=ano,               # fix 2: inteiro, não string
                status='emitida',
            ).select_related('confirmacao')
        )

        emitido  = sum(float(n.valor_liquido or 0) for n in notas)
        recebido = sum(
            float(n.confirmacao.valor_recebido or n.valor_liquido)
            for n in notas
            if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
        )
        qtd_em = len(notas)
        qtd_pg = sum(
            1 for n in notas
            if getattr(n, 'confirmacao', None) and n.confirmacao.confirmado
        )

        relatorio.append({
            'mes':      mes,
            'mes_nome': MESES[mes - 1],
            'emitido':  emitido,
            'recebido': recebido,
            'pendente': emitido - recebido,
            'qtd_notas': qtd_em,
            'qtd_pagas': qtd_pg,
            'pct': round(recebido / emitido * 100, 1) if emitido else 0,
        })

    context = {
        'relatorio':          relatorio,
        'ano_sel':            ano,                 # inteiro, sem risco de "2.026" no template
        'anos_range':         range(hoje.year - 2, hoje.year + 2),
        'total_ano_emitido':  sum(r['emitido']  for r in relatorio),
        'total_ano_recebido': sum(r['recebido'] for r in relatorio),
        'total_ano_pendente': sum(r['pendente'] for r in relatorio),
    }
    return render(request, 'relatorio_receitas.html', context)

# views.py — RH
# views.py — RH

from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Sum
from .models import UsuarioPerfil
from decimal import Decimal


def rh_dashboard(request):
    q              = request.GET.get('q', '')
    ver_inativos   = request.GET.get('ver_inativos') == 'on'
    exibir_fgts    = request.GET.get('ver_fgts')     == 'on'
    filtro_cargo   = request.GET.get('filtro_cargo', '').strip()
    filtro_local   = request.GET.get('filtro_local', '').strip()

    # ── QuerySet base ──
    perfis_qs = (
        UsuarioPerfil.objects
        .select_related('user')
        .order_by('user__first_name')
    )

    if not ver_inativos:
        perfis_qs = perfis_qs.filter(ativo=True)

    if q:
        perfis_qs = (
            perfis_qs.filter(user__first_name__icontains=q)
            | perfis_qs.filter(user__last_name__icontains=q)
            | perfis_qs.filter(cpf__icontains=q)
        )

    if filtro_cargo:
        perfis_qs = perfis_qs.filter(cargo__iexact=filtro_cargo)

    if filtro_local:
        perfis_qs = perfis_qs.filter(local_trabalho=filtro_local)

    # ── Lista de cargos disponíveis para o select ──
    cargos_disponiveis = (
        UsuarioPerfil.objects
        .exclude(cargo__isnull=True).exclude(cargo='')
        .values_list('cargo', flat=True)
        .distinct()
        .order_by('cargo')
    )

    # ── Totais ──
    total_bruto = perfis_qs.aggregate(Sum('salario_base'))['salario_base__sum'] or Decimal('0')
    total_inss  = sum(p.inss_estimado   for p in perfis_qs)
    total_irrf  = sum(p.irrf_estimado   for p in perfis_qs)
    total_fgts  = sum(p.custo_fgts      for p in perfis_qs) if exibir_fgts else Decimal('0')
    total_liq   = sum(p.salario_liquido for p in perfis_qs)
    custo_total = total_bruto + total_fgts

    # ── Paginação ──
    paginator = Paginator(perfis_qs, 10)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':            page_obj,
        'q':                   q,
        'ver_inativos':        ver_inativos,
        'exibir_fgts':         exibir_fgts,
        'filtro_cargo':        filtro_cargo,
        'filtro_local':        filtro_local,
        'cargos_disponiveis':  cargos_disponiveis,
        # impressão
        'todos_perfis':        perfis_qs,
        'total_colaboradores': perfis_qs.count(),
        # totalizadores
        'total_bruto':         total_bruto,
        'total_inss':          total_inss,
        'total_irrf':          total_irrf,
        'total_fgts':          total_fgts,
        'total_liquido':       total_liq,
        'custo_total':         custo_total,
    }
    return render(request, 'rh_dashboard.html', context)


def rh_atualizar_dados(request):
    if request.method == 'POST':
        perfil = get_object_or_404(UsuarioPerfil, id=request.POST.get('perfil_id'))

        perfil.salario_base = Decimal(request.POST['novo_salario'].replace(',', '.'))

        irrf_val = request.POST.get('novo_irrf', '').strip()
        perfil.irrf_manual = Decimal(irrf_val.replace(',', '.')) if irrf_val else None

        # novos campos
        cargo_val = request.POST.get('novo_cargo', '').strip()
        perfil.cargo = cargo_val or None

        local_val = request.POST.get('novo_local', '').strip()
        perfil.local_trabalho = local_val or None

        perfil.save()
        messages.success(request, 'Dados atualizados com sucesso!')

    return redirect('rh_dashboard')


#_______________________

# ═══════════════════════════════════════════════════════════════════════════
#  MÓDULO: DOCUMENTAÇÃO E ENVIO — views_documentos.py
#
#  URLs necessárias no urls.py:
#
#  path('receitas/documentos/', views.gestao_documentos, name='gestao_documentos'),
#  path('receitas/documentos/padrao/salvar/', views.salvar_documento_padrao, name='salvar_documento_padrao'),
#  path('receitas/documentos/padrao/<int:pk>/excluir/', views.excluir_documento_padrao, name='excluir_documento_padrao'),
#  path('receitas/contratos/<int:contrato_id>/documentos/', views.documentos_contrato, name='documentos_contrato'),
#  path('receitas/contratos/<int:contrato_id>/documentos/modelo/salvar/', views.salvar_documento_modelo, name='salvar_documento_modelo'),
#  path('receitas/contratos/<int:contrato_id>/documentos/modelo/<int:pk>/excluir/', views.excluir_documento_modelo, name='excluir_documento_modelo'),
#  path('receitas/contratos/<int:contrato_id>/emails/', views.gerenciar_emails, name='gerenciar_emails'),
#  path('receitas/contratos/<int:contrato_id>/emails/<int:pk>/excluir/', views.excluir_email, name='excluir_email'),
#  path('receitas/documentos/modelo/gerar/', views.gerar_documento_modelo, name='gerar_documento_modelo'),
#  path('receitas/contratos/<int:contrato_id>/documentos/modelo/gerar-lote/', views.gerar_modelos_lote, name='gerar_modelos_lote'),
#  path('receitas/notas/<int:nota_id>/baixar-pdf/', views.baixar_nfse_pdf, name='baixar_nfse_pdf'),
#  path('receitas/envio/<int:envio_id>/enviar/', views.enviar_dossie, name='enviar_dossie'),
#  path('receitas/envio/<int:envio_id>/status/', views.alterar_status_envio, name='alterar_status_envio'),
# ═══════════════════════════════════════════════════════════════════════════

import os
import io
import json
import time
import requests
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import (
    Contrato, NotaFiscal,
    ContratoEmail, DocumentoPadrao, DocumentoModelo,
    DocumentoModeloGerado, NotaFiscalPDF, EnvioMensal,
)

MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER — alerta de documentos padrão para o dashboard
# ─────────────────────────────────────────────────────────────────────────────
def get_alerta_documentos():
    """
    Retorna dict com resumo do status dos documentos padrão.
    Uso no receitas_dashboard: context['alerta_docs'] = get_alerta_documentos()
    """
    tipos_todos = set(t for t, _ in DocumentoPadrao.TIPO_CHOICES)
    docs        = list(DocumentoPadrao.objects.all())
    cadastrados = {d.tipo for d in docs}
    ausentes    = len(tipos_todos - cadastrados)
    vencidos    = sum(1 for d in docs if d.vencido)
    alertas     = sum(1 for d in docs if d.vence_em_breve and not d.vencido)
    return {
        'total':    len(docs),
        'vencidos': vencidos,
        'alertas':  alertas,
        'ausentes': ausentes,
        'ok':       len(docs) - vencidos - alertas,
        'critico':  vencidos > 0 or ausentes > 0,
        'aviso':    alertas > 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  GESTÃO DE DOCUMENTOS PADRÃO  (certidões — compartilhadas por todos)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def gestao_documentos(request):
    """
    Tela de gestão exclusiva dos documentos padrão (certidões).
    Os documentos modelo são gerenciados dentro de cada contrato.
    """
    docs_padrao    = DocumentoPadrao.objects.all()
    tipos_todos    = dict(DocumentoPadrao.TIPO_CHOICES)
    cadastrados    = set(docs_padrao.values_list('tipo', flat=True))
    tipos_faltando = {k: v for k, v in tipos_todos.items() if k not in cadastrados}

    context = {
        'docs_padrao':    docs_padrao,
        'tipos_faltando': tipos_faltando,
        'tipos_todos':    tipos_todos,
        'alerta_docs':    get_alerta_documentos(),
    }
    return render(request, 'gestao_documentos.html', context)


@login_required
def salvar_documento_padrao(request):
    """POST — cria ou substitui um documento padrão (certidão)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    tipo       = request.POST.get('tipo', '').strip()
    validade   = request.POST.get('data_validade', '').strip()
    observacao = request.POST.get('observacao', '').strip()
    arquivo    = request.FILES.get('arquivo')

    if not tipo or not validade:
        messages.error(request, 'Tipo e validade são obrigatórios.')
        return redirect('gestao_documentos')

    try:
        doc = DocumentoPadrao.objects.get(tipo=tipo)
        criado = False
    except DocumentoPadrao.DoesNotExist:
        doc = DocumentoPadrao(tipo=tipo)
        criado = True

    doc.data_validade  = validade
    doc.observacao     = observacao
    doc.atualizado_por = request.user
    if arquivo:
        if not criado and doc.arquivo:
            try: os.remove(doc.arquivo.path)
            except Exception: pass
        doc.arquivo = arquivo
    elif criado:
        messages.error(request, 'O arquivo PDF é obrigatório para cadastrar um novo documento.')
        return redirect('gestao_documentos')
    doc.save()

    messages.success(request, f'Documento {"criado" if criado else "atualizado"} com sucesso.')
    return redirect('gestao_documentos')


@login_required
def excluir_documento_padrao(request, pk):
    doc = get_object_or_404(DocumentoPadrao, pk=pk)
    if doc.arquivo:
        try: os.remove(doc.arquivo.path)
        except Exception: pass
    doc.delete()
    messages.success(request, 'Documento excluído.')
    return redirect('gestao_documentos')


# ─────────────────────────────────────────────────────────────────────────────
#  DOCUMENTOS MODELO  (específicos por contrato)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def salvar_documento_modelo(request, contrato_id):
    """
    POST — cria ou atualiza um DocumentoModelo vinculado ao contrato.
    Cada contrato possui seus próprios modelos (valores, vigência, detalhamentos únicos).
    Redireciona de volta para documentos_contrato após salvar.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    contrato = get_object_or_404(Contrato, pk=contrato_id)

    modelo_id           = request.POST.get('modelo_id', '').strip()
    tipo                = request.POST.get('tipo', '').strip()
    nome_personalizado  = request.POST.get('nome_personalizado', '').strip()
    texto_data_original = request.POST.get('texto_data_original', '').strip()
    texto_mes_original  = request.POST.get('texto_mes_original', '').strip()
    descricao           = request.POST.get('descricao', '').strip()
    arquivo_base        = request.FILES.get('arquivo_base')

    if not tipo or not texto_data_original:
        messages.error(request, 'Tipo e texto da data original são obrigatórios.')
        return redirect('documentos_contrato', contrato_id=contrato_id)

    try:
        if modelo_id:
            # Atualiza modelo existente — garante que pertence ao contrato
            modelo = get_object_or_404(DocumentoModelo, pk=modelo_id, contrato=contrato)
            modelo.tipo               = tipo
            modelo.nome_personalizado = nome_personalizado
            modelo.texto_data_original = texto_data_original
            modelo.texto_mes_original  = texto_mes_original
            modelo.descricao           = descricao
            modelo.atualizado_por     = request.user
            if arquivo_base:
                if modelo.arquivo_base:
                    try: os.remove(modelo.arquivo_base.path)
                    except Exception: pass
                modelo.arquivo_base = arquivo_base
            modelo.save()
            messages.success(request, f'Documento modelo "{modelo.label()}" atualizado.')
        else:
            # Cria novo modelo vinculado a este contrato
            if not arquivo_base:
                messages.error(request, 'O arquivo base (PDF) é obrigatório.')
                return redirect('documentos_contrato', contrato_id=contrato_id)

            DocumentoModelo.objects.create(
                contrato            = contrato,
                tipo                = tipo,
                nome_personalizado  = nome_personalizado,
                arquivo_base        = arquivo_base,
                texto_data_original = texto_data_original,
                texto_mes_original  = texto_mes_original,
                descricao           = descricao,
                atualizado_por      = request.user,
            )
            messages.success(request, 'Documento modelo cadastrado com sucesso.')

    except Exception as e:
        messages.error(request, f'Erro ao salvar modelo: {e}')

    return redirect('documentos_contrato', contrato_id=contrato_id)


@login_required
def excluir_documento_modelo(request, contrato_id, pk):
    """POST — exclui um DocumentoModelo e seus arquivos gerados."""
    modelo = get_object_or_404(DocumentoModelo, pk=pk, contrato_id=contrato_id)

    # Remove arquivo base
    if modelo.arquivo_base:
        try: os.remove(modelo.arquivo_base.path)
        except Exception: pass

    # Remove todos os PDFs gerados deste modelo
    for gerado in modelo.gerados.all():
        if gerado.arquivo:
            try: os.remove(gerado.arquivo.path)
            except Exception: pass

    modelo.delete()
    messages.success(request, f'Documento modelo excluído.')
    return redirect('documentos_contrato', contrato_id=contrato_id)


# ─────────────────────────────────────────────────────────────────────────────
#  DOCUMENTOS POR CONTRATO  (tela principal do dossiê)
# ─────────────────────────────────────────────────────────────────────────────
import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

# (demais imports já existentes no seu arquivo)


@login_required
def documentos_contrato(request, contrato_id):
    """
    Tela principal de Documentação e Envio de um contrato.
    - Documentos padrão : compartilhados por todos os contratos
    - Documentos modelo : exclusivos deste contrato
    - Documento fiscal  : NFS-e via Omie
    """
    contrato = get_object_or_404(Contrato, id=contrato_id)
    hoje     = date.today()

    # ── Auto-cria EnvioMensal para cada mês que já tem NFS-e sincronizada ──
    competencias = (
        NotaFiscal.objects
        .filter(contrato=contrato)
        .exclude(status='inativa')
        .values('competencia_mes', 'competencia_ano')
        .distinct()
    )
    for comp in competencias:
        envio_obj, _ = EnvioMensal.objects.get_or_create(
            contrato=contrato,
            mes=comp['competencia_mes'],
            ano=comp['competencia_ano'],
        )
        if not envio_obj.nota_fiscal:
            nota_principal = (
                NotaFiscal.objects
                .filter(
                    contrato=contrato,
                    competencia_mes=comp['competencia_mes'],
                    competencia_ano=comp['competencia_ano'],
                    status='emitida',
                ).first()
            )
            if nota_principal:
                envio_obj.nota_fiscal = nota_principal
                envio_obj.save(update_fields=['nota_fiscal'])

    # ── Dados base ──
    envios      = (EnvioMensal.objects
                   .filter(contrato=contrato)
                   .select_related('nota_fiscal')
                   .order_by('-ano', '-mes'))
    docs_padrao = list(DocumentoPadrao.objects.all().order_by('tipo'))
    docs_modelo = list(contrato.docs_modelo.filter(ativo=True).order_by('tipo'))

    # ── Pré-carrega todos os gerados do contrato UMA vez ──
    todos_gerados = (
        DocumentoModeloGerado.objects
        .filter(modelo__contrato=contrato)
        .select_related('modelo')
        .order_by('modelo_id', '-ano', '-mes', '-gerado_em')
    )
    gerados_por_comp    = {}   # chave: (modelo_id, mes, ano)
    gerados_mais_recent = {}   # chave: modelo_id — apenas o mais recente global
    for g in todos_gerados:
        chave = (g.modelo_id, g.mes, g.ano)
        if chave not in gerados_por_comp:
            gerados_por_comp[chave] = g
        if g.modelo_id not in gerados_mais_recent:
            gerados_mais_recent[g.modelo_id] = g

    # ── Serializa e-mails do contrato (para o modal) ──
    emails_contrato = [
        {'nome': str(e.nome) if hasattr(e, 'nome') else '', 'email': str(e)}
        for e in contrato.emails.all()
    ]

    # ── Meses ──
    meses_lista = []
    for envio in envios:
        mes, ano = envio.mes, envio.ano

        gerados_map = {}
        for dm in docs_modelo:
            g = (gerados_por_comp.get((dm.id, mes, ano))
                 or gerados_mais_recent.get(dm.id))
            if g:
                gerados_map[dm.id] = g

        notas = list(
            NotaFiscal.objects
            .filter(
                contrato=contrato,
                competencia_mes=mes,
                competencia_ano=ano,
                status='emitida',
            )
            .select_related('pdf_local')
        )

        # ── Serialização das notas para o modal (data-notas) ──
        notas_json = json.dumps([
            {
                'id':            n.id,
                'numero':        str(n.numero_nfse or ''),
                'data_emissao':  n.data_emissao.strftime('%d/%m/%Y') if n.data_emissao else '',
                # Formata o valor sem dependência de filtro de template
                'valor':         f'{n.valor_liquido:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
            }
            for n in notas
        ], ensure_ascii=False)

        meses_lista.append({
            'envio':      envio,
            'mes_nome':   MESES_PT[mes],
            'mes':        mes,
            'ano':        ano,
            'docs_padrao': docs_padrao,
            'docs_modelo': docs_modelo,
            'gerados_map': gerados_map,
            'notas':       notas,
            'notas_json':  notas_json,          # ← NOVO: serializado para data-notas
            'emails_json': json.dumps(emails_contrato, ensure_ascii=False),  # ← NOVO
        })

    context = {
        'contrato':     contrato,
        'meses_lista':  meses_lista,
        'docs_padrao':  docs_padrao,
        'docs_modelo':  docs_modelo,
        'emails':       contrato.emails.all(),
        'alerta_docs':  get_alerta_documentos(),
        'hoje':         hoje,
        'MESES':        MESES_PT,
        'TIPO_CHOICES': DocumentoModelo.TIPO_CHOICES,
    }
    return render(request, 'documentos_contrato.html', context)
# ─────────────────────────────────────────────────────────────────────────────
#  E-MAILS DO CONTRATO
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def gerenciar_emails(request, contrato_id):
    contrato = get_object_or_404(Contrato, id=contrato_id)
    if request.method == 'POST':
        email     = request.POST.get('email', '').strip()
        nome      = request.POST.get('nome_contato', '').strip()
        principal = request.POST.get('principal') == 'on'
        if email:
            if principal:
                contrato.emails.update(principal=False)
            obj, criado = ContratoEmail.objects.get_or_create(
                contrato=contrato, email=email,
                defaults={'nome_contato': nome, 'principal': principal}
            )
            if not criado:
                obj.nome_contato = nome
                obj.principal    = principal
                obj.save()
            messages.success(request, f'E-mail {"adicionado" if criado else "atualizado"}.')
        else:
            messages.error(request, 'E-mail inválido.')
    return redirect('documentos_contrato', contrato_id=contrato_id)


@login_required
def excluir_email(request, contrato_id, pk):
    obj = get_object_or_404(ContratoEmail, pk=pk, contrato_id=contrato_id)
    obj.delete()
    messages.success(request, 'E-mail removido.')
    return redirect('documentos_contrato', contrato_id=contrato_id)


# ─────────────────────────────────────────────────────────────────────────────
#  GERAR DOCUMENTO MODELO  (PyMuPDF substitui a data e o mês)
# ─────────────────────────────────────────────────────────────────────────────

def _normalizar(texto):
    """Remove espaços extras e converte para maiúsculo para comparação."""
    import unicodedata
    txt = unicodedata.normalize('NFC', texto)
    return ' '.join(txt.upper().split())


def _linha_contem(spans_da_linha, texto_busca):
    """
    Verifica se a concatenação dos spans de uma linha contém texto_busca.
    Compara versão normalizada (sem espaços duplos, maiúsculo) para resistir
    a kerning exportado como spans separados ou espaços invisíveis.
    Retorna o texto concatenado real se encontrar, ou None.
    """
    concat = ''.join(s['text'] for s in spans_da_linha)
    busca_norm = _normalizar(texto_busca)
    concat_norm = _normalizar(concat)
    if busca_norm in concat_norm:
        return concat
    return None


def _bbox_linha(spans_da_linha):
    """Bbox envolvente de todos os spans de uma linha."""
    x0 = min(s['bbox'][0] for s in spans_da_linha)
    y0 = min(s['bbox'][1] for s in spans_da_linha)
    x1 = max(s['bbox'][2] for s in spans_da_linha)
    y1 = max(s['bbox'][3] for s in spans_da_linha)
    return (x0, y0, x1, y1)


def _maior_span(spans_da_linha):
    """Retorna o span com maior fontsize na linha (referência para size/color)."""
    return max(spans_da_linha, key=lambda s: s['size'])


def _buscar_em_pagina(pagina, texto_busca):
    """
    Percorre todos os blocos/linhas da página buscando texto_busca.
    Retorna (bbox_linha, size, color) do primeiro match, ou None.

    A busca é feita sobre o texto concatenado da linha inteira para
    resistir a fragmentação em spans (kerning, bold inline, etc.).
    """
    for bloco in pagina.get_text('dict').get('blocks', []):
        for linha in bloco.get('lines', []):
            spans = linha.get('spans', [])
            if not spans:
                continue
            if _linha_contem(spans, texto_busca):
                ref = _maior_span(spans)
                return _bbox_linha(spans), ref['size'], ref.get('color')
    return None


def _redact_e_inserir(pagina, fitz, srgb_to_rgb, bbox, size, color, texto_novo,
                      centralizar=False, offset_x=-5, offset_y=-2):
    """
    Apaga o bbox via redação e insere texto_novo.

    Posicionamento ajustável:
      offset_x  → desloca horizontalmente em pontos (+ direita, - esquerda). Padrão: 0
      offset_y  → desloca verticalmente em pontos   (- sobe,   + desce).    Padrão: -2
      centralizar → centraliza na largura da página usando medição real da fonte
                    (ignora offset_x)
    """
    pagina.add_redact_annot(bbox, fill=(1, 1, 1))
    pagina.apply_redactions()

    fontsize = size - 1

    if centralizar:
        larg_pagina = pagina.rect.width
        # Mede largura real do texto — compatível com todas as versões do PyMuPDF
        try:
            # PyMuPDF >= 1.18
            larg_texto = fitz.get_text_length(texto_novo, fontname='hebo', fontsize=fontsize)
        except AttributeError:
            try:
                # PyMuPDF >= 1.16 via Page
                larg_texto = pagina.get_text_length(texto_novo, fontname='hebo', fontsize=fontsize)
            except AttributeError:
                # Fallback: estimativa conservadora (0.6 * size * chars)
                larg_texto = 0.6 * fontsize * len(texto_novo)
        x = (larg_pagina - larg_texto) / 2
    else:
        x = bbox[0] + offset_x

    ponto = fitz.Point(x, bbox[3] + offset_y)
    pagina.insert_text(
        ponto, texto_novo,
        fontname='hebo',
        fontsize=fontsize,
        color=srgb_to_rgb(color),
    )



def _redact_e_inserir(pagina, fitz, srgb_to_rgb, bbox, size, color, texto_novo,
                      centralizar=False, offset_x=0, offset_y=-2):
    """
    Apaga o bbox via redação e insere texto_novo.

    Posicionamento ajustável:
      offset_x  → desloca horizontalmente em pontos (+ direita, - esquerda). Padrão: 0
      offset_y  → desloca verticalmente em pontos   (- sobe,   + desce).    Padrão: -2
      centralizar → usa fitz.get_text_length() para centralizar com precisão
                    na largura total da página (ignora offset_x)
    """
    pagina.add_redact_annot(bbox, fill=(1, 1, 1))
    pagina.apply_redactions()

    fontsize = size - 1

    if centralizar:
        larg_pagina  = pagina.rect.width
        larg_texto   = fitz.get_text_length(texto_novo, fontname='hebo', fontsize=fontsize)
        x = (larg_pagina - larg_texto) / 2
    else:
        x = bbox[0] + offset_x

    ponto = fitz.Point(x, bbox[3] + offset_y)
    pagina.insert_text(
        ponto, texto_novo,
        fontname='hebo',
        fontsize=fontsize,
        color=srgb_to_rgb(color),
    )


def _num_nota_do_envio(contrato, mes, ano):
    """
    Retorna o numero_nfse para o contrato/mes/ano.

    Busca em cascata para maximizar chance de encontrar o número:
      1. NotaFiscal emitida com competencia_mes/ano exatos e FK contrato preenchida
      2. NotaFiscal de qualquer status com competencia_mes/ano exatos e FK contrato
      3. NotaFiscal pelo cliente_id_omie (cobre notas sync sem FK de contrato)
      4. EnvioMensal do mesmo mes/ano com nota_fiscal vinculada
      5. NotaFiscal emitida mais recente do contrato (qualquer mês)

    Retorna None apenas se o contrato não tiver nenhuma nota cadastrada.
    """
    from .models import NotaFiscal

    # 1. Nota emitida para a competência exata (FK contrato preenchida)
    nota = (
        NotaFiscal.objects
        .filter(contrato=contrato, competencia_mes=mes, competencia_ano=ano, status='emitida')
        .order_by('-data_emissao')
        .first()
    )
    if nota and nota.numero_nfse:
        print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → {nota.numero_nfse} (emitida, FK contrato)")
        return nota.numero_nfse

    # 2. Qualquer status, competência exata, FK contrato
    nota = (
        NotaFiscal.objects
        .filter(contrato=contrato, competencia_mes=mes, competencia_ano=ano)
        .order_by('-data_emissao')
        .first()
    )
    if nota and nota.numero_nfse:
        print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → {nota.numero_nfse} (qualquer status, FK contrato)")
        return nota.numero_nfse

    # 3. Busca pelo cliente_id_omie — cobre notas que ficaram sem FK de contrato
    #    na sincronização (nCodigoContrato ausente na OS do Omie)
    if contrato.cliente_id_omie:
        nota = (
            NotaFiscal.objects
            .filter(
                contrato__isnull=True,          # notas sem FK de contrato
                cliente_nome__isnull=False,
                competencia_mes=mes,
                competencia_ano=ano,
                status='emitida',
            )
            .first()
        )
        # Se não achou com contrato=None, busca via contrato irmão (mesmo cliente)
        if not nota or not nota.numero_nfse:
            nota = (
                NotaFiscal.objects
                .filter(
                    contrato__cliente_id_omie=contrato.cliente_id_omie,
                    competencia_mes=mes,
                    competencia_ano=ano,
                    status='emitida',
                )
                .order_by('-data_emissao')
                .first()
            )
        if nota and nota.numero_nfse:
            print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → {nota.numero_nfse} (via cliente_id_omie={contrato.cliente_id_omie})")
            return nota.numero_nfse

    # 4. EnvioMensal com nota vinculada
    try:
        envio = EnvioMensal.objects.select_related('nota_fiscal').get(
            contrato=contrato, mes=mes, ano=ano
        )
        if envio.nota_fiscal and envio.nota_fiscal.numero_nfse:
            print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → {envio.nota_fiscal.numero_nfse} (via EnvioMensal)")
            return envio.nota_fiscal.numero_nfse
    except EnvioMensal.DoesNotExist:
        pass

    # 5. Nota emitida mais recente do contrato (último recurso)
    nota = (
        NotaFiscal.objects
        .filter(contrato=contrato, status='emitida')
        .order_by('-competencia_ano', '-competencia_mes', '-data_emissao')
        .first()
    )
    if nota and nota.numero_nfse:
        print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → {nota.numero_nfse} (fallback: nota mais recente)")
        return nota.numero_nfse

    print(f"[NUM_NOTA] {contrato.omie_num_ctr} {mes:02d}/{ano} → não encontrado")
    return None



def _substituir_num_nota(pdf_bytes, numero_nota, offset_x=-2, offset_y=-3):
    """
    Substitui {NUM_NOTA} pelo número da nota fiscal em TODAS as páginas.

    Ajuste de posição (em pontos tipográficos, 1pt ≈ 0,35mm):
      offset_x  → move horizontalmente (+ direita, - esquerda). Padrão: 0
      offset_y  → move verticalmente   (- sobe,   + desce).    Padrão: -2

    Exemplos:
      offset_y=-10  → sobe 10pt em relação à posição original
      offset_x=5    → desloca 5pt para a direita
    """
    if not numero_nota:
        return pdf_bytes
    try:
        import fitz, io

        def srgb_to_rgb(v):
            if v is None:
                return (0, 0, 0)
            return (((v >> 16) & 255) / 255.0,
                    ((v >> 8)  & 255) / 255.0,
                    ( v        & 255) / 255.0)

        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        encontrou = False
        marcacao  = '{NUM_NOTA}'
        for pagina in doc:
            info = _buscar_em_pagina(pagina, marcacao)
            if info:
                bbox, size, color = info
                _redact_e_inserir(pagina, fitz, srgb_to_rgb,
                                  bbox, size, color, str(numero_nota),
                                  centralizar=False,
                                  offset_x=offset_x,
                                  offset_y=offset_y)
                encontrou = True
        if not encontrou:
            print(f"[AVISO] Marcação {{NUM_NOTA}} não encontrada no PDF da planilha de custos.")
        buf = io.BytesIO()
        doc.save(buf, deflate=True)
        doc.close()
        return buf.getvalue()
    except Exception as e:
        print(f"[ERRO] _substituir_num_nota: {e}")
        return pdf_bytes  # devolve original — não bloqueia a geração


def _substituir_data_pdf(caminho_base, texto_original, novo_texto,
                         texto_mes_original=None, novo_texto_mes=None):
    """
    Abre SEMPRE o arquivo BASE do modelo (nunca o gerado) e produz novo PDF com:

      • Data/localidade  → substitui na ÚLTIMA página
        (ex: "Oliveira dos Brejinhos - BA, 25 de fevereiro de 2026")

      • Mês em maiúsculo → substitui SOMENTE NA PRIMEIRA PÁGINA (página 0)
        (ex: "FEVEREIRO" → "MARÇO")
        A busca é feita por linha concatenada para resistir a fragmentação
        de spans causada por exportação de kerning/bold inline.

    Garante idempotência: sempre parte do arquivo base, não do gerado anterior.
    """
    try:
        import fitz

        def srgb_to_rgb(v):
            if v is None:
                return (0, 0, 0)
            return (((v >> 16) & 255) / 255.0,
                    ((v >> 8)  & 255) / 255.0,
                    ( v        & 255) / 255.0)

        doc = fitz.open(caminho_base)
        n   = len(doc)

        # ── Substituição do MÊS — somente página 0 (capa) ──
        if texto_mes_original and novo_texto_mes:
            pagina_capa = doc[0]
            # Captura snapshot ANTES de qualquer modificação
            info_mes = _buscar_em_pagina(pagina_capa, texto_mes_original)
            if info_mes:
                bbox, size, color = info_mes
                _redact_e_inserir(pagina_capa, fitz, srgb_to_rgb,
                                  bbox, size, color, novo_texto_mes,
                                  centralizar=True)
            else:
                print(f"[AVISO] Texto do mês não encontrado na capa: {repr(texto_mes_original)}")

        # ── Substituição da DATA — somente última página ──
        pagina_ultima = doc[n - 1]
        # Captura snapshot ANTES de qualquer modificação
        info_data = _buscar_em_pagina(pagina_ultima, texto_original)
        if info_data:
            bbox, size, color = info_data
            _redact_e_inserir(pagina_ultima, fitz, srgb_to_rgb,
                              bbox, size, color, novo_texto,
                              centralizar=False)
        else:
            # Fallback: varre todas as páginas (documentos de 1 página, etc.)
            for pagina in doc:
                info_data = _buscar_em_pagina(pagina, texto_original)
                if info_data:
                    bbox, size, color = info_data
                    _redact_e_inserir(pagina, fitz, srgb_to_rgb,
                                      bbox, size, color, novo_texto,
                                      centralizar=False)
                    break
            else:
                print(f"[AVISO] Texto de data não encontrado em nenhuma página: {repr(texto_original)}")

        buf = io.BytesIO()
        doc.save(buf, deflate=True)
        doc.close()
        return buf.getvalue()

    except ImportError:
        return None
    except Exception as e:
        print(f"[ERRO] PyMuPDF: {e}")
        import traceback; traceback.print_exc()
        return None



def _salvar_gerado(modelo, mes, ano, pdf_bytes, novo_texto, user):
    """
    Persiste o PDF gerado em DocumentoModeloGerado(modelo, mes, ano).

    Fluxo correto para evitar que o Django renomeie o arquivo com sufixo:
      1. Obtém ou cria o registro.
      2. Remove o arquivo antigo do disco via storage.
      3. Limpa o campo no banco com UPDATE direto.
      4. Recarrega o objeto do banco (campo arquivo agora é '').
      5. Atribui o novo ContentFile e faz save() — nome canônico garantido.
    """
    from django.core.files.storage import default_storage

    contrato = modelo.contrato
    nome     = f'{modelo.tipo}_{contrato.omie_num_ctr}_{mes:02d}{ano}.pdf'

    try:
        gerado = DocumentoModeloGerado.objects.get(modelo=modelo, mes=mes, ano=ano)
    except DocumentoModeloGerado.DoesNotExist:
        gerado = DocumentoModeloGerado(modelo=modelo, mes=mes, ano=ano)

    # ── Remove arquivo anterior do disco e limpa o campo ──
    if gerado.pk and gerado.arquivo:
        arquivo_antigo = gerado.arquivo.name
        try:
            if default_storage.exists(arquivo_antigo):
                default_storage.delete(arquivo_antigo)
        except Exception:
            pass
        # Limpa no banco com UPDATE direto para não depender do estado em memória
        DocumentoModeloGerado.objects.filter(pk=gerado.pk).update(arquivo='')
        # Recarrega para que o objeto em memória reflita o banco (arquivo='')
        gerado.refresh_from_db()

    # ── Salva novo arquivo com nome canônico ──
    gerado.arquivo         = ContentFile(pdf_bytes, name=nome)
    gerado.texto_data_novo = novo_texto
    gerado.gerado_por      = user
    gerado.save()
    return gerado


@login_required
def gerar_documento_modelo(request):
    """
    POST JSON — gera PDF modelo com data substituída.
    Body: { modelo_id, mes, ano, novo_texto_data }
    O contrato é derivado do próprio modelo (modelo.contrato).
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido'}, status=405)

    try:
        body       = json.loads(request.body)
        modelo_id  = int(body['modelo_id'])
        mes        = int(body['mes'])
        ano        = int(body['ano'])
        novo_texto = body.get('novo_texto_data', '').strip()
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'ok': False, 'erro': f'Parâmetros inválidos: {e}'}, status=400)

    modelo   = get_object_or_404(DocumentoModelo, pk=modelo_id)
    contrato = modelo.contrato   # derivado do FK — não precisa vir no request

    if not novo_texto:
        novo_texto = f'{contrato.municipio or "Local"}, 01 de {MESES_PT[mes]} de {ano}'

    # Para Relatorio de Atividades, deriva o nome do mes em maiusculo
    texto_mes_orig = getattr(modelo, 'texto_mes_original', '') or ''
    novo_texto_mes = MESES_PT[mes].upper() if texto_mes_orig else None

    pdf_bytes = _substituir_data_pdf(
        modelo.arquivo_base.path,
        modelo.texto_data_original,
        novo_texto,
        texto_mes_original=texto_mes_orig or None,
        novo_texto_mes=novo_texto_mes,
    )
    if not pdf_bytes:
        return JsonResponse({'ok': False, 'erro': 'Falha ao processar o PDF. Verifique se PyMuPDF está instalado.'})

    # Para planilha de custos: substitui {NUM_NOTA} pelo número da NFS-e do mês
    if modelo.tipo == 'planilha_custos':
        numero_nota = _num_nota_do_envio(contrato, mes, ano)
        pdf_bytes   = _substituir_num_nota(pdf_bytes, numero_nota)

    gerado = _salvar_gerado(modelo, mes, ano, pdf_bytes, novo_texto, request.user)

    ts = int(time.time())
    return JsonResponse({
        'ok':        True,
        'gerado_id': gerado.id,
        'arquivo':   f'{gerado.arquivo.url}?v={ts}',
        'arquivo_url': gerado.arquivo.url,
        'nome':      os.path.basename(gerado.arquivo.name),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  PATCH DE VIEWS — Chunking + Progresso para enviar_dossie e gerar_modelos_lote
#  Adicione/substitua estas funções no seu views.py
# ═══════════════════════════════════════════════════════════════════════════

import os
import json
import time
import requests
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# 1. NOVO ENDPOINT — Pré-busca e cacheia o PDF da NFS-e (separa do envio)
#    URL sugerida:  path('envios/<int:envio_id>/prefetch-nfse/', prefetch_nfse_pdf)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def prefetch_nfse_pdf(request, envio_id):
    """
    POST — baixa e armazena localmente o PDF da NFS-e antes do envio do e-mail.
    Separa o passo mais lento (download externo) do envio, evitando timeout.
    Retorna: { ok, status: 'ja_disponivel' | 'baixado' | 'sem_nota' | 'erro' }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    envio = get_object_or_404(EnvioMensal, pk=envio_id)

    if not envio.nota_fiscal:
        return JsonResponse({'ok': True, 'status': 'sem_nota'})

    # Já está em cache local?
    pdf_nf = None
    try:
        pdf_nf = envio.nota_fiscal.pdf_local
        if pdf_nf and pdf_nf.arquivo:
            return JsonResponse({'ok': True, 'status': 'ja_disponivel'})
    except NotaFiscalPDF.DoesNotExist:
        pdf_nf = None

    # Tenta baixar do Omie com timeout generoso
    try:
        from .omie_service import OmieService
        url_pdf = OmieService().obter_link_pdf_nfse(envio.nota_fiscal.omie_nfse_id)
        if not url_pdf:
            return JsonResponse({'ok': False, 'status': 'erro', 'erro': 'URL não obtida do Omie'})

        hdrs = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url_pdf, headers=hdrs, stream=True, timeout=45)  # timeout maior aqui
        if not (resp.ok and 'pdf' in resp.headers.get('Content-Type', '').lower()):
            return JsonResponse({'ok': False, 'status': 'erro',
                                 'erro': f'Resposta inválida: HTTP {resp.status_code}'})

        pdf_bytes_nf = b''.join(resp.iter_content(8192))
        if pdf_nf is None:
            pdf_nf = NotaFiscalPDF(nota=envio.nota_fiscal)

        nome_nf = f'nfse_{envio.nota_fiscal.numero_nfse or envio.nota_fiscal.omie_nfse_id}.pdf'
        pdf_nf.arquivo     = ContentFile(pdf_bytes_nf, name=nome_nf)
        pdf_nf.url_omie    = url_pdf
        pdf_nf.baixado_por = request.user
        pdf_nf.save()

        return JsonResponse({'ok': True, 'status': 'baixado'})

    except requests.Timeout:
        return JsonResponse({'ok': False, 'status': 'timeout',
                             'erro': 'Timeout ao baixar NFS-e. Tente novamente.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'status': 'erro', 'erro': str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# 2. SUBSTITUIÇÃO — enviar_dossie com melhor resiliência a timeout
#    A NFS-e agora é esperada já em cache (chamada prévia a prefetch_nfse_pdf).
#    O download de fallback mantém timeout curto para não travar o worker.
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def enviar_dossie(request, envio_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    envio    = get_object_or_404(EnvioMensal, pk=envio_id)
    contrato = envio.contrato

    # ── Parse do payload ──────────────────────────────────────
    try:
        payload = json.loads(request.body) if request.body else {}
    except Exception:
        payload = {}

    # ── Resolve destinatários ─────────────────────────────────
    # emails_destino pode ser lista de strings OU lista de dicts {nome, email}
    raw_destino  = envio.emails_destino or []
    todos_emails = []
    for e in raw_destino:
        addr = e.get('email', '').strip() if isinstance(e, dict) else str(e).strip()
        if addr:
            todos_emails.append(addr)

    emails_selecionados = payload.get('emails_selecionados') or []
    if not isinstance(emails_selecionados, list):
        emails_selecionados = []
    emails_selecionados = [str(e).strip() for e in emails_selecionados if e]

    emails = (
        [e for e in emails_selecionados if e in todos_emails]
        if emails_selecionados else todos_emails
    )
    if not emails:
        return JsonResponse({'ok': False, 'erro': 'Nenhum destinatário válido selecionado.'})

    # ── Resolve a NFS-e a anexar ──────────────────────────────
    #
    # Prioridade 1: ID enviado pelo front (lookup só por pk + contrato —
    #               sem filtrar status/competencia para evitar falsos DoesNotExist)
    # Prioridade 2: nota padrão do EnvioMensal
    # Prioridade 3: primeira nota emitida da competência (fallback final)
    #
    nota_fiscal_envio = envio.nota_fiscal
    nota_id_str = payload.get('nota_id_selecionada')

    if nota_id_str:
        try:
            nota_candidata = NotaFiscal.objects.get(
                pk=int(nota_id_str),
                contrato=contrato,          # garante que pertence a este contrato
            )
            nota_fiscal_envio = nota_candidata
        except (NotaFiscal.DoesNotExist, ValueError, TypeError):
            # ID inválido ou adulterado — mantém o padrão e registra aviso
            pass  # avisos será preenchido mais adiante se necessário

    # Fallback final: se ainda não há nota definida, busca a primeira emitida
    if nota_fiscal_envio is None:
        nota_fiscal_envio = NotaFiscal.objects.filter(
            contrato=contrato,
            competencia_mes=envio.mes,
            competencia_ano=envio.ano,
            status='emitida',
        ).first()

    # ── Assunto e corpo ───────────────────────────────────────
    mes_nome = MESES_PT[envio.mes]
    assunto  = (f'Documentação Fiscal — {contrato.cliente_nome} — '
                f'{mes_nome}/{envio.ano} — {contrato.omie_num_ctr}')
    corpo    = (f'Prezado(a),\n\n'
                f'Encaminhamos em anexo a documentação referente ao contrato '
                f'{contrato.omie_num_ctr} ({contrato.cliente_nome}), '
                f'competência {mes_nome} de {envio.ano}.\n\n'
                f'Documentos anexados:\n')

    # ── Coleta de anexos ──────────────────────────────────────
    anexos = []
    avisos = []

    # 1. Documentos padrão
    for doc in DocumentoPadrao.objects.all():
        if doc.arquivo:
            try:
                with open(doc.arquivo.path, 'rb') as f:
                    anexos.append((doc.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • {doc.get_tipo_display()}\n'
            except Exception as ex:
                avisos.append(f'Documento padrão "{doc.nome_arquivo()}" não lido: {ex}')

    # 2. Documentos modelo gerados
    gerados = DocumentoModeloGerado.objects.filter(
        modelo__contrato=contrato,
        modelo__ativo=True,
        mes=envio.mes,
        ano=envio.ano,
    ).select_related('modelo')
    for g in gerados:
        if g.arquivo:
            try:
                with open(g.arquivo.path, 'rb') as f:
                    anexos.append((g.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • {g.modelo.label()}\n'
            except Exception as ex:
                avisos.append(f'Modelo "{g.nome_arquivo()}" não lido: {ex}')

    # 3. PDF da NFS-e selecionada (ou fallback)
    if nota_fiscal_envio:
        pdf_nf = None
        try:
            pdf_nf = nota_fiscal_envio.pdf_local
        except NotaFiscalPDF.DoesNotExist:
            pass

        # Tenta baixar da Omie se PDF local não existe
        if pdf_nf is None or not pdf_nf.arquivo:
            try:
                from .omie_service import OmieService
                url_pdf = OmieService().obter_link_pdf_nfse(nota_fiscal_envio.omie_nfse_id)
                if url_pdf:
                    resp = requests.get(
                        url_pdf,
                        headers={'User-Agent': 'Mozilla/5.0'},
                        stream=True,
                        timeout=15,
                    )
                    if resp.ok and 'pdf' in resp.headers.get('Content-Type', '').lower():
                        pdf_bytes_nf = b''.join(resp.iter_content(8192))
                        if pdf_nf is None:
                            pdf_nf = NotaFiscalPDF(nota=nota_fiscal_envio)
                        nome_nf = (
                            f'nfse_{nota_fiscal_envio.numero_nfse or nota_fiscal_envio.omie_nfse_id}.pdf'
                        )
                        pdf_nf.arquivo     = ContentFile(pdf_bytes_nf, name=nome_nf)
                        pdf_nf.url_omie    = url_pdf
                        pdf_nf.baixado_por = request.user
                        pdf_nf.save()
                    else:
                        avisos.append('Omie retornou resposta inválida ao buscar PDF da NFS-e.')
            except Exception as e_dl:
                avisos.append(f'Download NFS-e falhou: {e_dl}')

        if pdf_nf and pdf_nf.arquivo:
            try:
                with open(pdf_nf.arquivo.path, 'rb') as f:
                    anexos.append((pdf_nf.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • Nota Fiscal NFS-e nº {nota_fiscal_envio.numero_nfse}\n'
            except Exception as ex:
                avisos.append(f'Erro ao ler PDF da NFS-e: {ex}')
                corpo += '  • Nota Fiscal (erro ao ler PDF)\n'
        else:
            avisos.append(f'PDF da NFS-e nº {nota_fiscal_envio.numero_nfse} não disponível.')
            corpo += f'  • Nota Fiscal NFS-e nº {nota_fiscal_envio.numero_nfse} (PDF não disponível)\n'
    else:
        corpo += '  • Nota Fiscal (nenhuma emitida para esta competência)\n'

    corpo += '\nAtenciosamente,\nEquipe CONMAC'

    # ── Envio ─────────────────────────────────────────────────
    try:
        email_msg = EmailMessage(
            subject=assunto, body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL, to=emails,
        )
        for nome_arq, dados, mime in anexos:
            email_msg.attach(nome_arq, dados, mime)
        email_msg.send()

        agora = timezone.now()
        envio.status      = 'enviado'
        envio.enviado_em  = agora
        envio.enviado_por = request.user
        if not envio.primeiro_envio_em:
            envio.primeiro_envio_em = agora
        # Sincroniza a nota do envio com a efetivamente usada
        if nota_fiscal_envio and envio.nota_fiscal_id != nota_fiscal_envio.pk:
            envio.nota_fiscal = nota_fiscal_envio
        envio.save()

        return JsonResponse({
            'ok':           True,
            'enviado_para': emails,
            'qtd_anexos':   len(anexos),
            'avisos':       avisos,
        })
    except Exception as e:
        return JsonResponse({
            'ok':    False,
            'erro':  f'Erro ao enviar e-mail: {e}',
            'avisos': avisos,
        })
# ─────────────────────────────────────────────────────────────────────────────
# 3. SUBSTITUIÇÃO — gerar_modelos_lote com suporte a chunk por modelo
#    Novos parâmetros no body JSON:
#      apenas_listar: bool  → retorna lista de IDs sem gerar nada
#      modelo_id: int       → processa apenas este modelo (chunk unitário)
# ─────────────────────────────────────────────────────────────────────────────
@login_required
def gerar_modelos_lote(request, contrato_id):
    """
    POST JSON — gera documentos modelo do contrato para um mês/ano.

    Modos:
      • { apenas_listar: true, mes, ano }       → retorna { modelo_ids, total }
      • { modelo_id: <int>, mes, ano, ... }      → processa só esse modelo (chunk)
      • { mes, ano, novo_texto_data }            → processa todos (compatibilidade)
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        body       = json.loads(request.body)
        mes        = int(body['mes'])
        ano        = int(body['ano'])
        novo_texto = body.get('novo_texto_data', '').strip()
        modelo_id  = body.get('modelo_id')      # None = todos
        apenas_listar = body.get('apenas_listar', False)
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos'}, status=400)

    modelos_qs = contrato.docs_modelo.filter(ativo=True)

    # ── Modo listagem: retorna IDs para o frontend montar os chunks ──
    if apenas_listar:
        ids = list(modelos_qs.values_list('id', flat=True))
        return JsonResponse({'ok': True, 'modelo_ids': ids, 'total': len(ids)})

    # ── Modo chunk: filtra pelo modelo solicitado ──
    if modelo_id:
        modelos_qs = modelos_qs.filter(pk=modelo_id)

    sucessos, erros = 0, 0
    gerados_info    = []

    for modelo in modelos_qs:
        texto = novo_texto or f'{contrato.municipio or "Local"}, 01 de {MESES_PT[mes]} de {ano}'
        texto_mes_orig = getattr(modelo, 'texto_mes_original', '') or ''
        novo_texto_mes = MESES_PT[mes].upper() if texto_mes_orig else None

        pdf_bytes = _substituir_data_pdf(
            modelo.arquivo_base.path,
            modelo.texto_data_original,
            texto,
            texto_mes_original=texto_mes_orig or None,
            novo_texto_mes=novo_texto_mes,
        )
        if not pdf_bytes:
            erros += 1
            continue

        if modelo.tipo == 'planilha_custos':
            numero_nota = _num_nota_do_envio(contrato, mes, ano)
            pdf_bytes   = _substituir_num_nota(pdf_bytes, numero_nota)

        gerado = _salvar_gerado(modelo, mes, ano, pdf_bytes, texto, request.user)
        sucessos += 1
        ts = int(time.time())
        gerados_info.append({
            'modelo_id':   modelo.id,
            'gerado_id':   gerado.id,
            'arquivo':     f'{gerado.arquivo.url}?v={ts}',
            'arquivo_url': gerado.arquivo.url,
            'nome':        os.path.basename(gerado.arquivo.name),
        })

    return JsonResponse({
        'ok':      True,
        'sucessos': sucessos,
        'erros':    erros,
        'gerados':  gerados_info,
    })

'''
ANTIGO
@login_required
def gerar_modelos_lote(request, contrato_id):
    """
    POST JSON — gera todos os documentos modelo do contrato para um mês/ano.
    Body: { mes, ano, novo_texto_data }
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    contrato = get_object_or_404(Contrato, pk=contrato_id)

    try:
        body       = json.loads(request.body)
        mes        = int(body['mes'])
        ano        = int(body['ano'])
        novo_texto = body.get('novo_texto_data', '').strip()
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos'}, status=400)

    modelos  = contrato.docs_modelo.filter(ativo=True)
    sucessos, erros = 0, 0
    gerados_info = []  # detalhes para o front-end atualizar os links

    for modelo in modelos:
        texto = novo_texto or f'{contrato.municipio or "Local"}, 01 de {MESES_PT[mes]} de {ano}'

        # Para Relatório de Atividades: deriva substituição do mês na capa
        texto_mes_orig = getattr(modelo, 'texto_mes_original', '') or ''
        novo_texto_mes = MESES_PT[mes].upper() if texto_mes_orig else None

        pdf_bytes = _substituir_data_pdf(
            modelo.arquivo_base.path,
            modelo.texto_data_original,
            texto,
            texto_mes_original=texto_mes_orig or None,
            novo_texto_mes=novo_texto_mes,
        )
        if not pdf_bytes:
            erros += 1
            continue

        # Para planilha de custos: substitui {NUM_NOTA} pelo número da NFS-e do mês
        if modelo.tipo == 'planilha_custos':
            numero_nota = _num_nota_do_envio(contrato, mes, ano)
            pdf_bytes   = _substituir_num_nota(pdf_bytes, numero_nota)

        gerado = _salvar_gerado(modelo, mes, ano, pdf_bytes, texto, request.user)
        sucessos += 1

        ts = int(time.time())
        gerados_info.append({
            'modelo_id': modelo.id,
            'gerado_id': gerado.id,
            'arquivo':   f'{gerado.arquivo.url}?v={ts}',
            'arquivo_url': gerado.arquivo.url,
            'nome':      os.path.basename(gerado.arquivo.name),
        })

    return JsonResponse({'ok': True, 'sucessos': sucessos, 'erros': erros, 'gerados': gerados_info})
'''



@login_required
def gerados_status(request, contrato_id):
    """
    GET JSON — retorna os arquivos gerados mais recentes para cada modelo
    de um contrato em um determinado mês/ano.
    Params: ?mes=2&ano=2026
    Usado pelo front-end para atualizar links após geração em lote.
    """
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        mes = int(request.GET['mes'])
        ano = int(request.GET['ano'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos'}, status=400)

    ts = int(time.time())

    gerados = (
        DocumentoModeloGerado.objects
        .filter(modelo__contrato=contrato, mes=mes, ano=ano)
        .select_related('modelo')
    )

    resultado = []
    for g in gerados:
        if g.arquivo:
            resultado.append({
                'modelo_id': g.modelo_id,
                'gerado_id': g.id,
                'arquivo':   f'{g.arquivo.url}?v={ts}',
                'arquivo_url': g.arquivo.url,
                'nome':      g.nome_arquivo(),
            })

    return JsonResponse({'ok': True, 'gerados': resultado})


# ─────────────────────────────────────────────────────────────────────────────
#  BAIXAR PDF DA NFS-E DO OMIE
# ─────────────────────────────────────────────────────────────────────────────
'''
@login_required
def baixar_nfse_pdf(request, nota_id):
    """POST — obtém o link via OsDocs/ObterNFSe e salva o PDF localmente."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    nota = get_object_or_404(NotaFiscal, pk=nota_id)

    from .omie_service import OmieService
    url_pdf = OmieService().obter_link_pdf_nfse(nota.omie_nfse_id)

    if not url_pdf:
        return JsonResponse({'ok': False, 'erro': 'Omie não retornou link de PDF.'})

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url_pdf, headers=headers, stream=True, timeout=20)
        resp.raise_for_status()
        if 'pdf' not in resp.headers.get('Content-Type', '').lower():
            return JsonResponse({'ok': False, 'erro': f'Link não retornou PDF. Content-Type: {resp.headers.get("Content-Type")}'})
        pdf_bytes = b''.join(resp.iter_content(chunk_size=8192))
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': f'Erro ao baixar: {e}'})

    try:
        pdf_obj = nota.pdf_local
        if pdf_obj.arquivo:
            try: os.remove(pdf_obj.arquivo.path)
            except Exception: pass
    except NotaFiscalPDF.DoesNotExist:
        pdf_obj = NotaFiscalPDF(nota=nota)

    nome = f'nfse_{nota.numero_nfse or nota.omie_nfse_id}.pdf'
    pdf_obj.arquivo     = ContentFile(pdf_bytes, name=nome)
    pdf_obj.url_omie    = url_pdf
    pdf_obj.baixado_por = request.user
    pdf_obj.save()

    return JsonResponse({'ok': True, 'arquivo': pdf_obj.arquivo.url, 'nome': nome})
'''

import os
import requests
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required

@login_required
def baixar_nfse_pdf(request, nota_id):
    """POST — obtém o link via OsDocs/ObterNFSe e salva o PDF localmente."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    nota = get_object_or_404(NotaFiscal, pk=nota_id)

    from .omie_service import OmieService
    url_pdf = OmieService().obter_link_pdf_nfse(nota.omie_nfse_id)

    if not url_pdf:
        return JsonResponse({'ok': False, 'erro': 'Omie não retornou link de PDF.'})

    # Download do PDF
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url_pdf, headers=headers, stream=True, timeout=20)
        resp.raise_for_status()

        if 'pdf' not in resp.headers.get('Content-Type', '').lower():
            return JsonResponse({'ok': False, 'erro': f'Conteúdo inválido: {resp.headers.get("Content-Type")}'})

        pdf_bytes = resp.content # Mais simples para arquivos pequenos/médios
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': f'Erro ao baixar: {str(e)}'})

    # --- CORREÇÃO DO NOME DO ARQUIVO ---
    # Convertemos para string e removemos pontos para evitar "2.026.pdf" vira "2026.pdf"
    raw_numero = str(nota.numero_nfse or nota.omie_nfse_id)
    numero_limpo = raw_numero.replace('.', '').replace(',', '')
    nome_arquivo = f'nfse_{numero_limpo}.pdf'

    # Lógica de persistência
    try:
        # Tenta pegar o objeto relacionado (OneToOne ou ForeignKey)
        pdf_obj = nota.pdf_local
        if pdf_obj.arquivo:
            # Remove o arquivo físico antigo se existir
            if os.path.isfile(pdf_obj.arquivo.path):
                os.remove(pdf_obj.arquivo.path)
    except Exception: # Caso não exista ou erro ao acessar nota.pdf_local
        # Ajuste aqui conforme o nome do seu Model relacionado
        from .models import NotaFiscalPDF
        pdf_obj = NotaFiscalPDF(nota=nota)

    # Salvando o novo arquivo
    pdf_obj.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
    pdf_obj.url_omie = url_pdf
    pdf_obj.baixado_por = request.user
    pdf_obj.save()

    return JsonResponse({
        'ok': True,
        'arquivo': pdf_obj.arquivo.url,
        'nome': nome_arquivo
    })


@login_required
def baixar_nfse_pdf_saatri(request, nota_id):
    """
    POST — baixa o PDF (DANFSe) direto do portal público do SAATRI, usando
    numero_nfse + codigo_verificacao.

    Serve pra qualquer nota (origem Omie ou SAATRI Direto) que tenha
    numero_nfse — é a ferramenta de consulta alternativa pra quando o PDF
    não foi baixado (ou o caminho normal via Omie falhar). A maioria das
    notas sincronizadas da Omie não tem codigo_verificacao salvo (a Omie
    não devolve esse campo na sincronização); nesse caso, busca a nota
    pelo próprio número via ConsultarNfsePorFaixa (inicial=final=número
    desejado) — o SAATRI devolve a nota completa, código de verificação
    incluso — e salva pra não precisar consultar de novo da próxima vez.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    nota = get_object_or_404(NotaFiscal, pk=nota_id)

    if not nota.numero_nfse:
        return JsonResponse({
            'ok': False,
            'erro': 'Esta nota não tem número de NFS-e salvo — não dá pra consultar no SAATRI.',
        })

    from .saatri import client as saatri_client

    if not nota.codigo_verificacao:
        resultado = saatri_client.consultar_nfse_por_faixa(nota.numero_nfse)
        notas_encontradas = resultado.get('notas') or []
        if not notas_encontradas:
            erros = resultado.get('erros') or []
            msg_erro = ('; '.join(f"[{e['codigo']}] {e['mensagem']}" for e in erros)
                        if erros else 'SAATRI não encontrou essa NFS-e pelo número.')
            return JsonResponse({'ok': False, 'erro': msg_erro})

        codigo_encontrado = notas_encontradas[0].get('codigo_verificacao')
        if not codigo_encontrado:
            return JsonResponse({'ok': False, 'erro': 'SAATRI encontrou a nota, mas sem código de verificação na resposta.'})

        nota.codigo_verificacao = codigo_encontrado
        nota.save(update_fields=['codigo_verificacao'])

    pdf_bytes = saatri_client.baixar_pdf_nfse(nota.numero_nfse, nota.codigo_verificacao)

    if not pdf_bytes:
        return JsonResponse({'ok': False, 'erro': 'O SAATRI não retornou um PDF válido para essa nota.'})

    from .models import NotaFiscalPDF
    try:
        pdf_obj = nota.pdf_local
        if pdf_obj.arquivo and os.path.isfile(pdf_obj.arquivo.path):
            os.remove(pdf_obj.arquivo.path)
    except NotaFiscalPDF.DoesNotExist:
        pdf_obj = NotaFiscalPDF(nota=nota)

    numero_limpo = str(nota.numero_nfse).replace('.', '').replace(',', '')
    nome_arquivo = f'nfse_saatri_{numero_limpo}.pdf'

    pdf_obj.arquivo.save(nome_arquivo, ContentFile(pdf_bytes), save=False)
    pdf_obj.baixado_por = request.user
    pdf_obj.save()

    return JsonResponse({
        'ok': True,
        'arquivo': pdf_obj.arquivo.url,
        'nome': nome_arquivo,
    })

# ─────────────────────────────────────────────────────────────────────────────
#  _ DOSSIÊ POR E-MAIL
# ─────────────────────────────────────────────────────────────────────────────
import json

'''
@login_required
def enviar_dossie(request, envio_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    # LOG TEMPORÁRIO — remova após confirmar funcionamento
    print(f"[enviar_dossie] body bruto: {request.body}")

    envio    = get_object_or_404(EnvioMensal, pk=envio_id)
    contrato = envio.contrato

    # ── Resolve destinatários ──────────────────────────────────
    todos_emails = envio.emails_destino or []

    try:
        body_raw = request.body
        payload  = json.loads(body_raw) if body_raw else {}
        emails_selecionados = payload.get('emails_selecionados') or []
        # Garante que é lista de strings
        if not isinstance(emails_selecionados, list):
            emails_selecionados = []
        emails_selecionados = [str(e).strip() for e in emails_selecionados if e]
    except Exception as e:
        print(f"[enviar_dossie] Erro ao parsear body: {e}")
        emails_selecionados = []

    # Garante que todos_emails também é lista de strings
    todos_emails = [str(e).strip() for e in todos_emails if e]

    if emails_selecionados:
        emails = [e for e in emails_selecionados if e in todos_emails]
    else:
        emails = todos_emails

    if not emails:
        return JsonResponse({
            'ok':   False,
            'erro': 'Nenhum destinatário válido selecionado.',
        })

    # ── Assunto e corpo ───────────────────────────────────────
    mes_nome = MESES_PT[envio.mes]
    assunto  = (
        f'Documentação Fiscal — {contrato.cliente_nome} — '
        f'{mes_nome}/{envio.ano} — {contrato.omie_num_ctr}'
    )
    corpo = (
        f'Prezado(a),\n\n'
        f'Encaminhamos em anexo a documentação referente ao contrato '
        f'{contrato.omie_num_ctr} ({contrato.cliente_nome}), '
        f'competência {mes_nome} de {envio.ano}.\n\n'
        f'Documentos anexados:\n'
    )

    # ── Coleta de anexos (igual à versão anterior) ────────────
    anexos = []

    # 1. Documentos padrão
    for doc in DocumentoPadrao.objects.all():
        if doc.arquivo:
            try:
                with open(doc.arquivo.path, 'rb') as f:
                    anexos.append((doc.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • {doc.get_tipo_display()}\n'
            except Exception:
                pass

    # 2. Documentos modelo gerados
    gerados = DocumentoModeloGerado.objects.filter(
        modelo__contrato=contrato,
        modelo__ativo=True,
        mes=envio.mes,
        ano=envio.ano,
    ).select_related('modelo')

    for g in gerados:
        if g.arquivo:
            try:
                with open(g.arquivo.path, 'rb') as f:
                    anexos.append((g.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • {g.modelo.label()}\n'
            except Exception:
                pass

    # 3. PDF da NFS-e
    if envio.nota_fiscal:
        pdf_nf = None
        try:
            pdf_nf = envio.nota_fiscal.pdf_local
        except NotaFiscalPDF.DoesNotExist:
            pass

        if pdf_nf is None or not pdf_nf.arquivo:
            try:
                from .omie_service import OmieService
                url_pdf = OmieService().obter_link_pdf_nfse(envio.nota_fiscal.omie_nfse_id)
                if url_pdf:
                    hdrs = {'User-Agent': 'Mozilla/5.0'}
                    resp = requests.get(url_pdf, headers=hdrs, stream=True, timeout=20)
                    if resp.ok and 'pdf' in resp.headers.get('Content-Type', '').lower():
                        pdf_bytes_nf = b''.join(resp.iter_content(8192))
                        if pdf_nf is None:
                            pdf_nf = NotaFiscalPDF(nota=envio.nota_fiscal)
                        nome_nf = f'nfse_{envio.nota_fiscal.numero_nfse or envio.nota_fiscal.omie_nfse_id}.pdf'
                        pdf_nf.arquivo     = ContentFile(pdf_bytes_nf, name=nome_nf)
                        pdf_nf.url_omie    = url_pdf
                        pdf_nf.baixado_por = request.user
                        pdf_nf.save()
            except Exception as e_dl:
                print(f"Auto-download NFS-e falhou: {e_dl}")

        if pdf_nf and pdf_nf.arquivo:
            try:
                with open(pdf_nf.arquivo.path, 'rb') as f:
                    anexos.append((pdf_nf.nome_arquivo(), f.read(), 'application/pdf'))
                corpo += f'  • Nota Fiscal NFS-e nº {envio.nota_fiscal.numero_nfse}\n'
            except Exception:
                corpo += '  • Nota Fiscal (erro ao ler PDF)\n'
        else:
            corpo += '  • Nota Fiscal (não disponível)\n'

    corpo += f'\nAtenciosamente,\nEquipe CONMAC'

    # ── Envio ─────────────────────────────────────────────────
    try:
        email_msg = EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )
        for nome_arq, dados, mime in anexos:
            email_msg.attach(nome_arq, dados, mime)
        email_msg.send()

        agora = timezone.now()
        envio.status      = 'enviado'
        envio.enviado_em  = agora
        envio.enviado_por = request.user
        if not envio.primeiro_envio_em:
            envio.primeiro_envio_em = agora
        envio.save()

        return JsonResponse({
            'ok':           True,
            'enviado_para': emails,
            'qtd_anexos':   len(anexos),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': f'Erro ao enviar e-mail: {e}'})
'''


@login_required
def alterar_status_envio(request, envio_id):
    """POST JSON — altera o status de um envio manualmente."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    try:
        body   = json.loads(request.body)
        status = body.get('status', '').strip()
    except Exception:
        return JsonResponse({'ok': False}, status=400)

    envio = get_object_or_404(EnvioMensal, pk=envio_id)
    if status not in [s for s, _ in EnvioMensal.STATUS_CHOICES]:
        return JsonResponse({'ok': False, 'erro': 'Status inválido'})

    envio.status = status
    envio.save(update_fields=['status'])
    return JsonResponse({'ok': True, 'status': status, 'label': envio.get_status_display()})


# ─────────────────────────────────────────────────────────────────────────────
#  OPERAÇÕES EM LOTE  (a partir do dashboard de contratos)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def competencias_lote(request):
    """
    GET JSON — retorna competencias (mes/ano) disponíveis para os contratos selecionados.
    Params: ?ids=1,2,3
    Retorna lista de {mes, ano, mes_nome, qtd_notas} ordenada por ano/mes desc.
    """
    ids_raw = request.GET.get('ids', '')
    try:
        ids = [int(i) for i in ids_raw.split(',') if i.strip()]
    except ValueError:
        return JsonResponse({'ok': False, 'erro': 'IDs inválidos'}, status=400)

    from django.db.models import Count
    competencias = (
        NotaFiscal.objects
        .filter(contrato_id__in=ids, status='emitida')
        .values('competencia_mes', 'competencia_ano')
        .annotate(qtd=Count('id'))
        .order_by('-competencia_ano', '-competencia_mes')
    )
    resultado = [
        {
            'mes':      c['competencia_mes'],
            'ano':      c['competencia_ano'],
            'mes_nome': MESES_PT[c['competencia_mes']],
            'qtd':      c['qtd'],
        }
        for c in competencias
    ]
    return JsonResponse({'ok': True, 'competencias': resultado})


@login_required
def gerar_lote_dashboard(request):
    """
    POST JSON — gera documentos modelo de TODOS os contratos selecionados para um mes/ano.
    Body: { contrato_ids: [1,2,3], mes, ano, novo_texto_data }
    Para cada contrato, itera nos seus proprios DocumentoModelo.
    Para Relatorio de Atividades, usa texto_mes_original se cadastrado.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        body       = json.loads(request.body)
        ids        = [int(i) for i in body.get('contrato_ids', [])]
        mes        = int(body['mes'])
        ano        = int(body['ano'])
        novo_texto = body.get('novo_texto_data', '').strip()
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos'}, status=400)

    contratos  = Contrato.objects.filter(id__in=ids)
    sucessos, erros, sem_modelo = 0, 0, 0

    for contrato in contratos:
        modelos = contrato.docs_modelo.filter(ativo=True)
        if not modelos.exists():
            sem_modelo += 1
            continue

        # Texto de data: usa o enviado ou constrói com municipio do contrato
        texto = novo_texto or (
            f'{contrato.municipio or "Oliveira dos Brejinhos"} - BA, '
            f'01 de {MESES_PT[mes].lower()} de {ano}'
        )

        for modelo in modelos:
            texto_mes_orig = modelo.texto_mes_original or None
            novo_texto_mes = MESES_PT[mes].upper() if texto_mes_orig else None

            pdf_bytes = _substituir_data_pdf(
                modelo.arquivo_base.path,
                modelo.texto_data_original,
                texto,
                texto_mes_original=texto_mes_orig,
                novo_texto_mes=novo_texto_mes,
            )
            if not pdf_bytes:
                erros += 1
                continue

            # Para planilha de custos: substitui {NUM_NOTA} pelo número da NFS-e do mês
            if modelo.tipo == 'planilha_custos':
                numero_nota = _num_nota_do_envio(contrato, mes, ano)
                pdf_bytes   = _substituir_num_nota(pdf_bytes, numero_nota)

            gerado = _salvar_gerado(modelo, mes, ano, pdf_bytes, texto, request.user)
            sucessos += 1

    return JsonResponse({
        'ok':        True,
        'sucessos':  sucessos,
        'erros':     erros,
        'sem_modelo': sem_modelo,
    })


@login_required
def enviar_lote_dashboard(request):
    """
    POST JSON — envia dossiê por e-mail para todos os contratos selecionados no mes/ano.
    Body: { contrato_ids: [1,2,3], mes, ano }
    Auto-baixa NFS-e se não disponível. Cria/atualiza EnvioMensal.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    try:
        body = json.loads(request.body)
        ids  = [int(i) for i in body.get('contrato_ids', [])]
        mes  = int(body['mes'])
        ano  = int(body['ano'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos'}, status=400)

    contratos  = Contrato.objects.filter(id__in=ids)
    docs_padrao = list(DocumentoPadrao.objects.all())
    mes_nome   = MESES_PT[mes]

    enviados, erros_env, sem_email = 0, 0, 0
    detalhes = []

    for contrato in contratos:
        emails = list(contrato.emails.values_list('email', flat=True))
        if not emails:
            sem_email += 1
            detalhes.append({'contrato': contrato.omie_num_ctr, 'status': 'sem_email'})
            continue

        # Garante EnvioMensal
        envio_obj, _ = EnvioMensal.objects.get_or_create(
            contrato=contrato, mes=mes, ano=ano
        )

        assunto = (
            f'Documentação Fiscal — {contrato.cliente_nome} — '
            f'{mes_nome}/{ano} —'
        )
        corpo = (
            f'Prezado(a),\n\n'
            f'Encaminhamos em anexo a documentação referente ao contrato '
            f'{contrato.omie_num_ctr} ({contrato.cliente_nome}), '
            f'competência {mes_nome} de {ano}.\n\nDocumentos anexados:\n'
        )
        anexos = []

        # Docs padrão
        for doc in docs_padrao:
            if doc.arquivo:
                try:
                    with open(doc.arquivo.path, 'rb') as f:
                        anexos.append((doc.nome_arquivo(), f.read(), 'application/pdf'))
                    corpo += f'  • {doc.get_tipo_display()}\n'
                except Exception:
                    pass

        # Docs modelo gerados deste contrato no mês
        gerados = DocumentoModeloGerado.objects.filter(
            modelo__contrato=contrato, mes=mes, ano=ano
        ).select_related('modelo')
        for g in gerados:
            if g.arquivo:
                try:
                    with open(g.arquivo.path, 'rb') as f:
                        anexos.append((g.nome_arquivo(), f.read(), 'application/pdf'))
                    corpo += f'  • {g.modelo.label()}\n'
                except Exception:
                    pass

        # NFS-e — auto-baixa se não disponível
        nota_fiscal = (
            NotaFiscal.objects
            .filter(contrato=contrato, competencia_mes=mes, competencia_ano=ano, status='emitida')
            .first()
        )
        if nota_fiscal:
            pdf_nf = None
            try:
                pdf_nf = nota_fiscal.pdf_local
            except NotaFiscalPDF.DoesNotExist:
                pass

            if pdf_nf is None or not pdf_nf.arquivo:
                try:
                    if nota_fiscal.origem == 'saatri':
                        # NFS-e emitida via SAATRI Direto — não tem omie_nfse_id,
                        # o PDF (DANFSe) é público no portal da prefeitura.
                        from .saatri import client as saatri_client
                        pdf_bytes_nf = saatri_client.baixar_pdf_nfse(
                            nota_fiscal.numero_nfse, nota_fiscal.codigo_verificacao
                        )
                        if pdf_bytes_nf:
                            if pdf_nf is None:
                                pdf_nf = NotaFiscalPDF(nota=nota_fiscal)
                            nome_nf = f'nfse_saatri_{nota_fiscal.numero_nfse}.pdf'
                            pdf_nf.arquivo     = ContentFile(pdf_bytes_nf, name=nome_nf)
                            pdf_nf.baixado_por = request.user
                            pdf_nf.save()
                    else:
                        from .omie_service import OmieService
                        url_pdf = OmieService().obter_link_pdf_nfse(nota_fiscal.omie_nfse_id)
                        if url_pdf:
                            hdrs = {'User-Agent': 'Mozilla/5.0'}
                            resp = requests.get(url_pdf, headers=hdrs, stream=True, timeout=20)
                            if resp.ok and 'pdf' in resp.headers.get('Content-Type', '').lower():
                                pdf_bytes_nf = b''.join(resp.iter_content(8192))
                                if pdf_nf is None:
                                    pdf_nf = NotaFiscalPDF(nota=nota_fiscal)
                                nome_nf = f'nfse_{nota_fiscal.numero_nfse or nota_fiscal.omie_nfse_id}.pdf'
                                pdf_nf.arquivo     = ContentFile(pdf_bytes_nf, name=nome_nf)
                                pdf_nf.url_omie    = url_pdf
                                pdf_nf.baixado_por = request.user
                                pdf_nf.save()
                except Exception as e_dl:
                    print(f"Auto-download NFS-e lote {contrato.omie_num_ctr}: {e_dl}")

            if pdf_nf and pdf_nf.arquivo:
                try:
                    with open(pdf_nf.arquivo.path, 'rb') as f:
                        anexos.append((pdf_nf.nome_arquivo(), f.read(), 'application/pdf'))
                    corpo += f'  • Nota Fiscal NFS-e nº {nota_fiscal.numero_nfse}\n'
                    assunto += f"NFS-E {nota_fiscal.numero_nfse}"
                except Exception:
                    pass

        corpo += '\nAtenciosamente,\nEquipe CONMAC'

        try:
            msg = EmailMessage(
                subject=assunto,
                body=corpo,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=emails,
            )
            for nome_arq, dados, mime in anexos:
                msg.attach(nome_arq, dados, mime)
            msg.send()

            agora = timezone.now()
            envio_obj.status      = 'enviado'
            envio_obj.enviado_em  = agora
            envio_obj.enviado_por = request.user
            if not envio_obj.primeiro_envio_em:
                envio_obj.primeiro_envio_em = agora
            envio_obj.save()

            enviados += 1
            detalhes.append({'contrato': contrato.omie_num_ctr, 'status': 'enviado', 'para': emails})
        except Exception as e_mail:
            erros_env += 1
            detalhes.append({'contrato': contrato.omie_num_ctr, 'status': 'erro', 'erro': str(e_mail)})



    return JsonResponse({
        'ok':       True,
        'enviados':  enviados,
        'erros':     erros_env,
        'sem_email': sem_email,
        'detalhes':  detalhes,
    })


@login_required
def sincronizar_nfse_ajax(request):
    """
    POST JSON — Sincroniza NFS-e do mês/ano informado.
    Chamado pelo modal "NFS-e" do receitas_dashboard.
    Body: { "mes": 3, "ano": 2026, "sincronizar_omie": true, "sincronizar_saatri": true }
    (os dois últimos são opcionais — default True, pra manter compatibilidade
    com quem chamar sem informar)

    NÃO altera contratos, município, tipo_entidade ou cliente_nome.
    Retorna: { ok, criadas, atualizadas, saatri_total, saatri_resolvidas, saatri_pendentes }
    ou { ok: false, erro }

    URL sugerida: /receitas/sincronizar-nfse/
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Método inválido'}, status=405)

    try:
        body = json.loads(request.body)
        mes  = int(body['mes'])
        ano  = int(body['ano'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'erro': 'Parâmetros inválidos (mes e ano obrigatórios)'}, status=400)

    sync_omie   = body.get('sincronizar_omie', True)
    sync_saatri = body.get('sincronizar_saatri', True)
    if not sync_omie and not sync_saatri:
        return JsonResponse({'ok': False, 'erro': 'Selecione ao menos uma origem (Omie ou SAATRI).'}, status=400)

    if not (1 <= mes <= 12):
        return JsonResponse({'ok': False, 'erro': 'Mês inválido'}, status=400)
    if not (2020 <= ano <= 2099):
        return JsonResponse({'ok': False, 'erro': 'Ano inválido'}, status=400)

    try:
        criadas = atualizadas = 0
        if sync_omie:
            from .omie_service import OmieService
            service = OmieService()
            criadas, atualizadas = service.sincronizar_nfse(mes=mes, ano=ano)

        total_saatri = resolvidos_saatri = ainda_pendentes_saatri = 0
        if sync_saatri:
            # Resolve também os RPS SAATRI Direto pendentes — mesmo clique do
            # modal "NFS-e", sem precisar de um botão separado.
            total_saatri, resolvidos_saatri, ainda_pendentes_saatri = sincronizar_saatri_pendentes()

        return JsonResponse({
            'ok': True, 'criadas': criadas, 'atualizadas': atualizadas,
            'saatri_total': total_saatri, 'saatri_resolvidas': resolvidos_saatri,
            'saatri_pendentes': ainda_pendentes_saatri,
        })
    except Exception as e:
        print(f"❌ sincronizar_nfse_ajax: erro inesperado — {e}")
        return JsonResponse({'ok': False, 'erro': str(e)})

#NOVO GESTOR DE ATIVIDADES:

# atividades/views.py
# ─────────────────────────────────────────────────────────────
# Refatorado:
#   • pode_iniciar_nivel / pode_concluir_nivel  — funções canônicas únicas
#   • _get_data_entrada_fila                    — helper sem duplicação
#   • fechamento_cliente_detail                 — contexto limpo
#   • atividades_home                           — sem bloco duplicado
#   • liberar_competencia                       — nova view administrativa
#   • relatorio_administrativo                  — chave "E-TCM" corrigida
#   • Notificações e SolicitacaoReabertura intactos
# ─────────────────────────────────────────────────────────────
#COMEÇA AQUI O GESTOR DE ATIVIDADES
import logging
import sys
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Max, Q
from django.http import (HttpResponseBadRequest, HttpResponseForbidden,
                         JsonResponse)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_GET, require_POST

from .models import (
    AssociacaoUsuarioCliente, Cliente, CompetenciaLiberada,
    ConfiguracaoNivel, Etapa, EtapaHistorico, EtapaRegistro,
    EtapaRegistroStatus, ModuloChoices, NivelChoices, NotificacaoPush,
    SolicitacaoReabertura,
)

try:
    from .forms import ChecklistForm, EtapaForm
except ImportError:
    ChecklistForm = None
    EtapaForm = None

try:
    from .models import Despesa, ChecklistItem, UsuarioPerfil
except ImportError:
    Despesa = ChecklistItem = UsuarioPerfil = None

User = get_user_model()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# FUNÇÕES CANÔNICAS DE BLOQUEIO
# ══════════════════════════════════════════════════════════════

def _esta_liberado_por_override(cliente, nivel, ano, mes) -> bool:
    """
    Verifica todos os mecanismos de override administrativo:
      1. CompetenciaLiberada pontual (cliente + ano + mês + nível)
      2. ConfiguracaoNivel.clientes_liberados (cliente específico, qualquer competência)
      3. ConfiguracaoNivel global (liberar_preenchimento sem restrição de cliente)
    Retorna True se qualquer override estiver ativo.
    """
    # 1. Liberação pontual por competência
    if CompetenciaLiberada.objects.filter(
        cliente=cliente, ano=ano, mes=mes, nivel=nivel
    ).exists():
        return True

    # 2 & 3. Configuração de nível
    try:
        config = ConfiguracaoNivel.objects.get(nivel=nivel)
        return config.esta_liberado_para_cliente(cliente)
    except ConfiguracaoNivel.DoesNotExist:
        return False


def _modulo_concluido(cliente, ano, mes, modulo: str) -> bool:
    """
    Verifica se TODAS as etapas do nível FECHAMENTO com o módulo
    informado (CONTABIL ou FINANCEIRO) estão com status CONCLUIDO.

    Usado por: pode_iniciar_nivel
    """
    etapas = Etapa.objects.filter(
        nivel=NivelChoices.FECHAMENTO, modulo=modulo, ativa=True
    )
    if not etapas.exists():
        # Sem etapas cadastradas para este módulo → não bloqueia
        # (evita travar o sistema se a migration de seed ainda não rodou)
        return True

    total     = etapas.count()
    concluidas = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas,
        status=EtapaRegistroStatus.CONCLUIDO,
    ).count()
    return concluidas >= total

def _siga_100_concluido(cliente, ano, mes) -> bool:
    """
    Verifica se TODAS as etapas do nível SIGA estão com status CONCLUIDO.

    Usado por: pode_concluir_nivel (E-TCM, SIOPE, SIOPS, SICONF)
    """
    etapas_siga = Etapa.objects.filter(nivel=NivelChoices.SIGA, ativa=True)
    if not etapas_siga.exists():
        return True  # Sem etapas cadastradas → não bloqueia

    total     = etapas_siga.count()
    concluidas = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_siga,
        status=EtapaRegistroStatus.CONCLUIDO,
    ).count()
    return concluidas >= total

# ══════════════════════════════════════════════
# HELPERS CANÔNICOS DE BLOQUEIO
# ══════════════════════════════════════════════

def _etapas_modulo_concluidas(cliente, ano, mes, modulo):
    """
    Verifica se TODAS as etapas de FECHAMENTO de um dado módulo
    (CONTABIL ou FINANCEIRO) estão concluídas para o cliente/competência.
    Retorna (bool, list[str] nomes_pendentes)
    """
    etapas_modulo = Etapa.objects.filter(
        nivel=NivelChoices.FECHAMENTO,
        modulo=modulo,
        ativa=True,
    )
    if not etapas_modulo.exists():
        # Se não há etapas cadastradas no módulo, considera desbloqueado
        return True, []

    ids_modulo = set(etapas_modulo.values_list("id", flat=True))
    ids_concluidos = set(
        EtapaRegistro.objects.filter(
            cliente=cliente,
            ano=ano,
            mes=mes,
            etapa_id__in=ids_modulo,
            status=EtapaRegistroStatus.CONCLUIDO,
        ).values_list("etapa_id", flat=True)
    )
    pendentes_ids = ids_modulo - ids_concluidos
    if not pendentes_ids:
        return True, []

    nomes = list(
        Etapa.objects.filter(id__in=pendentes_ids).values_list("nome", flat=True)
    )
    return False, nomes


def _requisitos_conclusao_concluidos(cliente, ano, mes, nivel):
    """
    Verifica se todas as etapas marcadas com obrigatoria_para_fila_<nivel>
    estão concluídas. Usado para validar CONCLUSÃO de qualquer nível.
    Retorna (bool, list[str] nomes_pendentes)
    """
    mapa_flags = {
        "SIGA":   "obrigatoria_para_fila_siga",
        "E-TCM":  "obrigatoria_para_fila_etcm",
        "SIOPE":  "obrigatoria_para_fila_siope",
        "SIOPS":  "obrigatoria_para_fila_siops",
        "SICONF": "obrigatoria_para_fila_siconf",
    }
    campo = mapa_flags.get(str(nivel).strip())
    if not campo:
        return True, []

    etapas_req = Etapa.objects.filter(ativa=True, **{campo: True})
    if not etapas_req.exists():
        return True, []

    ids_req = set(etapas_req.values_list("id", flat=True))
    ids_ok = set(
        EtapaRegistro.objects.filter(
            cliente=cliente,
            ano=ano,
            mes=mes,
            etapa_id__in=ids_req,
            status=EtapaRegistroStatus.CONCLUIDO,
        ).values_list("etapa_id", flat=True)
    )
    pendentes = ids_req - ids_ok
    if not pendentes:
        return True, []

    nomes = list(Etapa.objects.filter(id__in=pendentes).values_list("nome", flat=True))
    return False, nomes


def pode_iniciar_nivel(cliente, nivel, ano, mes, usuario):
    """
    Verifica se é permitido mover uma etapa para EM_ANDAMENTO no nível.

    Regras de início por nível:
      FECHAMENTO → sempre permitido
      SIGA       → Fechamento Contábil 100% concluído
      SIOPE      → Fechamento Contábil 100% concluído
      SIOPS      → Fechamento Contábil 100% concluído
      SICONF     → Fechamento Contábil 100% concluído
      E-TCM      → Fechamento Financeiro 100% concluído
                   (Contábil NÃO é exigido para iniciar E-TCM)

    Admins e CompetenciaLiberada sempre liberam.
    Retorna: (bool apto, list[str] motivos)
    """
    # 1. Admin passa direto
    if usuario.is_staff or usuario.is_superuser:
        return True, []

    # 2. Bypass por competência específica
    if ConfiguracaoNivel.esta_liberado_para_competencia(cliente, ano, mes, nivel):
        return True, []

    # 3. Bypass por ConfiguracaoNivel (global ou por cliente)
    try:
        config = ConfiguracaoNivel.objects.get(nivel=nivel)
        if config.esta_liberado_para_cliente(cliente):
            return True, []
    except ConfiguracaoNivel.DoesNotExist:
        pass

    # 4. FECHAMENTO não tem pré-requisito de início
    if nivel == NivelChoices.FECHAMENTO:
        return True, []

    # 5. E-TCM: exige Financeiro concluído para INICIAR
    if nivel == NivelChoices.E_TCM:
        ok, pendentes = _etapas_modulo_concluidas(
            cliente, ano, mes, ModuloChoices.FINANCEIRO
        )
        if not ok:
            motivos = [
                f"Fechamento Financeiro pendente: {', '.join(pendentes)}"
            ]
            return False, motivos
        return True, []

    # 6. Demais níveis (SIGA, SIOPE, SIOPS, SICONF): exigem Contábil concluído
    ok, pendentes = _etapas_modulo_concluidas(
        cliente, ano, mes, ModuloChoices.CONTABIL
    )
    if not ok:
        motivos = [
            f"Fechamento Contábil pendente: {', '.join(pendentes)}"
        ]
        return False, motivos

    return True, []


def pode_concluir_nivel(cliente, nivel, ano, mes, usuario):
    """
    Verifica se é permitido mover uma etapa para CONCLUIDO no nível.

    Regras de conclusão por nível:
      FECHAMENTO → sempre permitido (sem dependência externa)
      SIGA       → flags obrigatoria_para_fila_siga concluídas
      E-TCM      → SIGA 100% concluído
                   + Fechamento Financeiro 100% concluído
      SIOPE      → SIGA 100% concluído (via flags)
      SIOPS      → SIGA 100% concluído (via flags)
      SICONF     → SIGA 100% concluído (via flags)

    Admins e CompetenciaLiberada sempre liberam.
    Retorna: (bool apto, list[str] motivos)
    """
    # 1. Admin passa direto
    if usuario.is_staff or usuario.is_superuser:
        return True, []

    # 2. Bypass por competência específica
    if ConfiguracaoNivel.esta_liberado_para_competencia(cliente, ano, mes, nivel):
        return True, []

    # 3. Bypass por ConfiguracaoNivel
    try:
        config = ConfiguracaoNivel.objects.get(nivel=nivel)
        if config.esta_liberado_para_cliente(cliente):
            return True, []
    except ConfiguracaoNivel.DoesNotExist:
        pass

    # 4. FECHAMENTO não tem pré-requisito de conclusão
    if nivel == NivelChoices.FECHAMENTO:
        return True, []

    # 5. E-TCM: exige Financeiro concluído + requisitos das flags (inclui SIGA)
    if nivel == NivelChoices.E_TCM:
        motivos = []
        ok_fin, pend_fin = _etapas_modulo_concluidas(
            cliente, ano, mes, ModuloChoices.FINANCEIRO
        )
        if not ok_fin:
            motivos.append(
                f"Fechamento Financeiro pendente: {', '.join(pend_fin)}"
            )
        ok_req, pend_req = _requisitos_conclusao_concluidos(cliente, ano, mes, nivel)
        if not ok_req:
            motivos.append(
                f"Pré-requisitos de conclusão pendentes: {', '.join(pend_req)}"
            )
        if motivos:
            return False, motivos
        return True, []

    # 6. Demais níveis: verifica flags obrigatoria_para_fila_*
    ok, pendentes = _requisitos_conclusao_concluidos(cliente, ano, mes, nivel)
    if not ok:
        motivos = [
            f"Pré-requisitos de conclusão pendentes: {', '.join(pendentes)}"
        ]
        return False, motivos

    return True, []

# ══════════════════════════════════════════════════════════════
# HELPER — DATA DE ENTRADA NA FILA (FIFO)
# ══════════════════════════════════════════════════════════════

# Mapeamento nível → campo de flag (usado somente para calcular data FIFO)
_MAPA_OBRIGATORIEDADE = {
    NivelChoices.SIGA:   "obrigatoria_para_fila_siga",
    NivelChoices.E_TCM:  "obrigatoria_para_fila_etcm",
    NivelChoices.SIOPE:  "obrigatoria_para_fila_siope",
    NivelChoices.SIOPS:  "obrigatoria_para_fila_siops",
    NivelChoices.SICONF: "obrigatoria_para_fila_siconf",
}


def _get_data_entrada_fila(cliente, nivel, ano, mes) -> datetime:
    """
    Retorna a data em que o cliente "entrou na fila" para o nível,
    definida como a data da última etapa pré-requisito concluída.

    • Se não há pré-requisitos → datetime.min (entra imediatamente).
    • Se sem conclusões registradas → datetime.max (bloqueado).
    """
    campo_filtro = _MAPA_OBRIGATORIEDADE.get(nivel)
    if not campo_filtro:
        return datetime.min

    etapas_req = Etapa.objects.filter(ativa=True, **{campo_filtro: True})
    if not etapas_req.exists():
        return datetime.min

    ultima = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_req,
        status=EtapaRegistroStatus.CONCLUIDO,
    ).aggregate(Max("modificado_em"))["modificado_em__max"]

    return ultima if ultima else datetime.max


# ══════════════════════════════════════════════════════════════
# HELPERS AUXILIARES
# ══════════════════════════════════════════════════════════════

def fechamento_esta_fechado(cliente, ano, mes) -> bool:
    """
    Considera FECHAMENTO encerrado quando todas as etapas com ao menos
    uma flag de obrigatoriedade estão CONCLUIDAS.
    """
    etapas_fech = Etapa.objects.filter(nivel=NivelChoices.FECHAMENTO, ativa=True)
    if not etapas_fech.exists():
        return False

    obrigatorias = etapas_fech.filter(
        Q(obrigatoria_para_fila_siga=True) | Q(obrigatoria_para_fila_etcm=True)
    )
    etapas_consideradas = obrigatorias if obrigatorias.exists() else etapas_fech

    total     = etapas_consideradas.count()
    concluidas = EtapaRegistro.objects.filter(
        cliente=cliente, ano=ano, mes=mes,
        etapa__in=etapas_consideradas,
        status=EtapaRegistroStatus.CONCLUIDO,
    ).count()
    return total > 0 and concluidas >= total


def get_nivel_anterior(nivel_atual):
    """Cadeia de dependência imediata para início de cada nível."""
    cadeia = {
        NivelChoices.SIGA:   NivelChoices.FECHAMENTO,  # Módulo Contábil
        NivelChoices.E_TCM:  NivelChoices.FECHAMENTO,  # Módulo Financeiro (para iniciar) + SIGA (para concluir)
        NivelChoices.SIOPE:  NivelChoices.FECHAMENTO,  # Módulo Contábil
        NivelChoices.SIOPS:  NivelChoices.FECHAMENTO,  # Módulo Contábil
        NivelChoices.SICONF: NivelChoices.FECHAMENTO,  # Módulo Contábil (pode iniciar sem SIGA)
    }
    return cadeia.get(nivel_atual)


def verificar_nivel_desbloqueado(cliente, ano, mes, nivel) -> tuple[bool, list]:
    """
    Alias para pode_iniciar_nivel sem usuário (contexto de fila/painel).
    Admins não têm bypass aqui pois o contexto é de regra de negócio pura.
    """
    campo = _MAPA_OBRIGATORIEDADE.get(nivel)
    if not campo:
        return True, []

    etapas_req = Etapa.objects.filter(ativa=True, **{campo: True})
    if not etapas_req.exists():
        return True, []

    ids_req       = set(etapas_req.values_list("id", flat=True))
    ids_concluidos = set(
        EtapaRegistro.objects.filter(
            cliente=cliente, ano=ano, mes=mes,
            etapa_id__in=ids_req,
            status=EtapaRegistroStatus.CONCLUIDO,
        ).values_list("etapa_id", flat=True)
    )

    pendentes = ids_req - ids_concluidos
    if pendentes:
        nomes = list(Etapa.objects.filter(id__in=pendentes).values_list("nome", flat=True))
        return False, nomes
    return True, []


def _check_perm_nivel(user, nivel_key: str) -> bool:
    """Retorna True se o usuário tem permissão de acesso ao nível."""
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False
    mapa = {
        "FECHAMENTO": perfil.acesso_fechamento,
        "SIGA":       perfil.acesso_siga,
        "E-TCM":      perfil.acesso_etcm,
        "SIOPE":      perfil.acesso_siope,
        "SIOPS":      perfil.acesso_siops,
        "SICONF":     perfil.acesso_siconf,
    }
    return mapa.get(nivel_key, False)


# ══════════════════════════════════════════════════════════════
# VIEW — DETALHE DO CLIENTE (FECHAMENTO_CLIENTE_DETAIL)
# ══════════════════════════════════════════════════════════════

@login_required
def fechamento_cliente_detail(request, cliente_id):
    """
    Detalha as etapas de um cliente em um nível específico.
    Passa ao template tanto `nivel_apto_inicio` quanto `nivel_apto_conclusao`.
    """
    user    = request.user
    cliente = get_object_or_404(Cliente, id=cliente_id)

    # Permissão de acesso
    assoc = AssociacaoUsuarioCliente.objects.filter(
        usuario=user, cliente=cliente, ativo=True
    ).exists()
    if not assoc and not (user.is_staff or user.is_superuser):
        return HttpResponseForbidden("Acesso negado")

    # Filtros de competência
    hoje = now()
    try:
        sel_ano = int(request.GET.get("ano", hoje.year))
        sel_mes = int(request.GET.get("mes", hoje.month))
    except (ValueError, TypeError):
        sel_ano, sel_mes = hoje.year, hoje.month

    # Nível selecionado
    nivel_sel_raw = request.GET.get("nivel", "FECHAMENTO")
    nivel_sel     = str(nivel_sel_raw).strip().upper()
    chaves_validas = [str(c[0]) for c in NivelChoices.choices]
    if nivel_sel not in chaves_validas:
        nivel_sel = "FECHAMENTO"

    nivel_label = dict(NivelChoices.choices).get(nivel_sel, nivel_sel)

    # ── Avaliação de permissão de início e conclusão ──────────
    nivel_apto_inicio,    pendencias_inicio   = pode_iniciar_nivel(
        cliente, nivel_sel, sel_ano, sel_mes, user
    )
    nivel_apto_conclusao, pendencias_conclusao = pode_concluir_nivel(
        cliente, nivel_sel, sel_ano, sel_mes, user
    )

    # ── Carregamento de etapas ────────────────────────────────
    etapas = list(Etapa.objects.filter(nivel=nivel_sel, ativa=True).order_by("ordem"))

    # Garante a existência de registros para todas as etapas do nível
    if etapas:
        existing = set(
            EtapaRegistro.objects.filter(
                cliente=cliente, ano=sel_ano, mes=sel_mes, etapa__in=etapas
            ).values_list("etapa_id", flat=True)
        )
        novos = [
            EtapaRegistro(
                cliente=cliente, etapa=e,
                ano=sel_ano, mes=sel_mes,
                status=EtapaRegistroStatus.NAO_INICIADO,
            )
            for e in etapas if e.id not in existing
        ]
        if novos:
            EtapaRegistro.objects.bulk_create(novos)

    registros_qs = EtapaRegistro.objects.filter(
        cliente=cliente, ano=sel_ano, mes=sel_mes, etapa__in=etapas
    ).select_related("etapa", "ultima_alteracao_por").prefetch_related(
        models.Prefetch(
            "historico",
            queryset=EtapaHistorico.objects.order_by("-criado_em"),
        )
    )
    registros_dict = {r.etapa_id: r for r in registros_qs}

    dados_tabela = []
    for etapa in etapas:
        reg = registros_dict.get(etapa.id)

        # Etapas já concluídas ficam travadas para não-admins
        travado_admin = (
            reg is not None
            and reg.status == EtapaRegistroStatus.CONCLUIDO
            and not (user.is_staff or user.is_superuser)
        )

        solicitacao = None
        if reg:
            solicitacao = (
                SolicitacaoReabertura.objects
                .filter(registro=reg)
                .order_by("-data_solicitacao")
                .first()
            )

        dados_tabela.append({
            "etapa":                etapa,
            "registro":             reg,
            "status_atual":         reg.status if reg else EtapaRegistroStatus.NAO_INICIADO,
            "observacao":           reg.observacao if reg else "",
            "historico_recente":    list(reg.historico.all())[:5] if reg else [],
            "travado_por_conclusao": travado_admin,
            "solicitacao_atual":    solicitacao,
            # Informações para o JS desabilitar botões
            "bloqueada_para_iniciar":   not nivel_apto_inicio,
            "bloqueada_para_concluir":  not nivel_apto_conclusao,
        })

    context = {
        "cliente":              cliente,
        "sel_ano":              sel_ano,
        "sel_mes":              sel_mes,
        "nivel_sel":            nivel_sel,
        "nivel_label":          nivel_label,
        "dados_tabela":         dados_tabela,
        # Início
        "nivel_apto_inicio":    nivel_apto_inicio,
        "pendencias_inicio":    pendencias_inicio,
        # Conclusão
        "nivel_apto_conclusao": nivel_apto_conclusao,
        "pendencias_conclusao": pendencias_conclusao,
        "pode_editar":          True,
        "EtapaRegistroStatus":  EtapaRegistroStatus,
    }
    return render(request, "fechamento/cliente_detail.html", context)


# ══════════════════════════════════════════════════════════════
# VIEW — ATUALIZAR ETAPA REGISTRO  (AJAX)
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def atualizar_etapa_registro(request):
    """Salva alteração de status/observação em um EtapaRegistro via AJAX."""

    def safe_int(val):
        try:
            return int(val) if val else None
        except (ValueError, TypeError):
            return None

    logger.info("===== atualizar_etapa_registro =====")

    # 1. Captura
    reg_id     = safe_int(request.POST.get("registro_id"))
    etapa_id   = safe_int(request.POST.get("etapa_id"))
    cliente_id = safe_int(request.POST.get("cliente_id"))
    novo_status = request.POST.get("status")
    observacao  = request.POST.get("observacao", "")
    arquivo     = request.FILES.get("arquivo_anexo")
    hoje        = now()

    # 2. Localização / criação do registro
    registro = None
    if reg_id:
        registro = (
            EtapaRegistro.objects
            .select_related("cliente", "etapa")
            .filter(id=reg_id)
            .first()
        )
    elif etapa_id and cliente_id:
        cliente_obj = get_object_or_404(Cliente, id=cliente_id)
        etapa_obj   = get_object_or_404(Etapa, id=etapa_id)
        registro, _ = EtapaRegistro.objects.get_or_create(
            cliente=cliente_obj,
            etapa=etapa_obj,
            ano=safe_int(request.POST.get("ano")) or hoje.year,
            mes=safe_int(request.POST.get("mes")) or hoje.month,
            defaults={"status": EtapaRegistroStatus.NAO_INICIADO},
        )

    if not registro:
        return JsonResponse({"ok": False, "error": "Registro não identificado."}, status=400)

    # 3. Validação de início
    if novo_status == EtapaRegistroStatus.EM_ANDAMENTO:
        ok, motivos = pode_iniciar_nivel(
            registro.cliente, registro.etapa.nivel,
            registro.ano, registro.mes, request.user,
        )
        if not ok:
            return JsonResponse({
                "ok":       False,
                "error":    "Bloqueio de Início",
                "pendencias": motivos,
            })

    # 4. Validação de conclusão
    if novo_status == EtapaRegistroStatus.CONCLUIDO:
        ok, motivos = pode_concluir_nivel(
            registro.cliente, registro.etapa.nivel,
            registro.ano, registro.mes, request.user,
        )
        if not ok:
            return JsonResponse({
                "ok":       False,
                "error":    "Bloqueio de Conclusão",
                "pendencias": motivos,
            })

    # 5. Salvamento
    status_anterior = registro.status
    obs_anterior    = registro.observacao

    registro.status               = novo_status
    registro.observacao           = observacao
    registro.ultima_alteracao_por = request.user
    if arquivo:
        registro.arquivo_anexo = arquivo
    registro.save()

    logger.info(f"Registro salvo: {registro.cliente} | {registro.etapa.nome} | {registro.status}")

    # 6. Histórico + notificações
    ids_notificacoes = []
    try:
        houve_mudanca = (
            status_anterior != registro.status
            or obs_anterior != registro.observacao
            or arquivo
        )
        if houve_mudanca:
            EtapaHistorico.objects.create(
                registro=registro,
                alterado_por=request.user,
                status_anterior=status_anterior,
                status_novo=registro.status,
                observacao_anterior=obs_anterior,
                observacao_nova=registro.observacao,
            )

            destinatarios = User.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True) |
                Q(id__in=AssociacaoUsuarioCliente.objects.filter(
                    cliente=registro.cliente, ativo=True
                ).values_list("usuario_id", flat=True))
            ).exclude(id=request.user.id).distinct()

            competencia = f"{registro.mes:02d}/{registro.ano}"
            mensagem = (
                f"A Etapa {registro.etapa.nome} do {registro.etapa.nivel} "
                f"possui um novo Status: {registro.get_status_display()} 😊"
            )
            notificacoes = [
                NotificacaoPush(
                    usuario_alvo=dest,
                    titulo=f"ATUALIZAÇÃO EM {registro.cliente.nome} - {competencia} ⚠️",
                    mensagem=mensagem,
                    link=(f"/fechamento/cliente/{registro.cliente.id}/"
                          f"?nivel={registro.etapa.nivel}&ano={registro.ano}&mes={registro.mes}"),
                    enviado=False,
                )
                for dest in destinatarios
            ]
            if notificacoes:
                criadas = NotificacaoPush.objects.bulk_create(notificacoes)
                ids_notificacoes = [n.id for n in criadas]
                logger.info(f"{len(ids_notificacoes)} notificações criadas.")
    except Exception:
        logger.exception("Erro ao criar histórico/notificações.")

    return JsonResponse({
        "ok":                True,
        "message":           "Salvo com sucesso!",
        "notificacoes_ids":  ids_notificacoes,
    })


# ══════════════════════════════════════════════════════════════
# VIEW — CRIAR REGISTRO DE ETAPA  (AJAX)
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def etapa_criar_registro(request):
    """Cria ou atualiza um EtapaRegistro via AJAX."""
    usuario = request.user

    try:
        cliente_id = int(request.POST.get("cliente_id"))
        etapa_id   = int(request.POST.get("etapa_id"))
        hoje       = now()
        ano = int(request.POST.get("ano", hoje.year))
        mes = int(request.POST.get("mes", hoje.month))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Dados de identificação inválidos."}, status=400)

    cliente = Cliente.objects.filter(id=cliente_id, ativo=True).first()
    etapa   = Etapa.objects.filter(id=etapa_id, ativa=True).first()
    if not cliente or not etapa:
        return JsonResponse({"ok": False, "error": "Cliente ou etapa não encontrados."}, status=404)

    tem_vinculo = AssociacaoUsuarioCliente.objects.filter(
        usuario=usuario, cliente=cliente, ativo=True
    ).exists()
    if not tem_vinculo and not (usuario.is_staff or usuario.is_superuser):
        return JsonResponse({"ok": False, "error": "Acesso negado: Sem vínculo."}, status=403)

    reg, created = EtapaRegistro.objects.get_or_create(
        cliente=cliente, etapa=etapa, ano=ano, mes=mes,
        defaults={
            "status":               EtapaRegistroStatus.NAO_INICIADO,
            "observacao":           request.POST.get("observacao", "").strip(),
            "ultima_alteracao_por": usuario,
        },
    )

    requested_status = request.POST.get("status")

    if not (usuario.is_staff or usuario.is_superuser):
        if requested_status == EtapaRegistroStatus.EM_ANDAMENTO:
            ok, motivos = pode_iniciar_nivel(cliente, etapa.nivel, ano, mes, usuario)
            if not ok:
                return JsonResponse({"ok": False, "error": "Pré-requisitos pendentes para início.",
                                     "pendencias": motivos}, status=403)

        if requested_status == EtapaRegistroStatus.CONCLUIDO:
            ok, motivos = pode_concluir_nivel(cliente, etapa.nivel, ano, mes, usuario)
            if not ok:
                return JsonResponse({"ok": False, "error": "Pré-requisitos pendentes para conclusão.",
                                     "pendencias": motivos}, status=403)

    antigo_status = reg.status
    if requested_status:
        reg.status = requested_status
    reg.observacao           = request.POST.get("observacao", reg.observacao).strip()
    reg.ultima_alteracao_por = usuario
    reg.save()

    if created or antigo_status != reg.status:
        EtapaHistorico.objects.create(
            registro=reg,
            alterado_por=usuario,
            status_anterior=antigo_status,
            status_novo=reg.status,
            observacao_nova=reg.observacao,
        )

    return JsonResponse({"ok": True, "registro_id": reg.id, "status": reg.status})


# ══════════════════════════════════════════════════════════════
# VIEW — HISTÓRICO DE ETAPA  (AJAX)
# ══════════════════════════════════════════════════════════════

@login_required
@require_GET
def etapa_historico_list(request, registro_id):
    """Retorna JSON paginado com o histórico de um EtapaRegistro."""
    reg  = get_object_or_404(
        EtapaRegistro.objects.select_related("cliente", "etapa"), pk=registro_id
    )
    user = request.user

    is_admin    = user.is_staff or user.is_superuser
    is_vinculado = AssociacaoUsuarioCliente.objects.filter(
        usuario=user, cliente=reg.cliente, ativo=True
    ).exists()
    if not (is_admin or is_vinculado):
        return JsonResponse({"ok": False, "error": "Acesso negado."}, status=403)

    page     = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 10))

    qs = (
        EtapaHistorico.objects
        .filter(registro=reg)
        .select_related("alterado_por")
        .order_by("-criado_em")
    )
    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    items = []
    for h in page_obj:
        autor      = h.alterado_por
        nome_autor = (autor.get_full_name() or autor.username) if autor else "Sistema"
        items.append({
            "id":                   h.id,
            "criado_em":            h.criado_em.isoformat(),
            "criado_em_fmt":        h.criado_em.strftime("%d/%m/%Y %H:%M"),
            "alterado_por":         {"id": autor.id if autor else None, "nome": nome_autor},
            "status_anterior":      h.status_anterior,
            "status_novo":          h.status_novo,
            "observacao_anterior":  h.observacao_anterior or "",
            "observacao_nova":      h.observacao_nova or "",
        })

    return JsonResponse({
        "ok":          True,
        "registro_id": registro_id,
        "page":        page_obj.number,
        "per_page":    per_page,
        "has_next":    page_obj.has_next(),
        "has_prev":    page_obj.has_previous(),
        "total_pages": paginator.num_pages,
        "total_items": paginator.count,
        "items":       items,
    })


# ══════════════════════════════════════════════════════════════
# VIEW — REABERTURA
# ══════════════════════════════════════════════════════════════

@login_required
def solicitar_reabertura(request, registro_id):
    """Usuário solicita desbloqueio de uma etapa concluída."""
    registro = get_object_or_404(EtapaRegistro, id=registro_id)

    if not SolicitacaoReabertura.objects.filter(registro=registro, status="PENDENTE").exists():
        SolicitacaoReabertura.objects.create(
            registro=registro,
            solicitante=request.user,
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def gerenciar_solicitacao(request):
    """Admin aprova ou nega uma SolicitacaoReabertura via POST."""
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden()

    if request.method == "POST":
        solic  = get_object_or_404(SolicitacaoReabertura, id=request.POST.get("solicitacao_id"))
        acao   = request.POST.get("acao")
        motivo = request.POST.get("motivo", "")

        solic.analisado_por = request.user
        solic.data_analise  = timezone.now()

        if acao == "APROVAR":
            solic.status    = "APROVADO"
            registro        = solic.registro
            status_anterior = registro.status
            registro.status = EtapaRegistroStatus.EM_ANDAMENTO
            registro.save()

            EtapaHistorico.objects.create(
                registro=registro,
                alterado_por=request.user,
                status_anterior=status_anterior,
                status_novo=EtapaRegistroStatus.EM_ANDAMENTO,
                observacao_anterior=registro.observacao,
                observacao_nova="Reabertura administrativa autorizada.",
            )
        else:
            solic.status       = "NEGADO"
            solic.motivo_recusa = motivo

        solic.save()

    return redirect("atividades_home")


# ══════════════════════════════════════════════════════════════
# VIEW — ETAPA ALTERAR STATUS  (legado / notificações intactas)
# ══════════════════════════════════════════════════════════════

@login_required
def etapa_alterar_status(request, registro_id):
    """
    Altera status de um EtapaRegistro.
    Valida pode_iniciar_nivel / pode_concluir_nivel antes de salvar.
    Mantém log de notificações e histórico intactos.
    """
    def force_log(msg):
        print(f"[DEBUG NOTIF] {msg}", file=sys.stderr, flush=True)

    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    usuario = request.user
    force_log("--- INICIO REQUISICAO ---")
    force_log(f"Usuário: {usuario.username} (ID: {usuario.id})")

    reg     = get_object_or_404(EtapaRegistro, id=registro_id)
    cliente = reg.cliente
    nivel   = reg.etapa.nivel
    ano     = reg.ano
    mes     = reg.mes

    force_log(f"Cliente: {cliente.nome} (ID: {cliente.id})")

    novo_status = request.POST.get("status")
    observacao  = request.POST.get("observacao", "").strip()
    antigo_status = reg.status
    antigo_obs    = reg.observacao or ""

    force_log(f"Status: {antigo_status} -> {novo_status}")

    # ── BLOQUEIOS DE TRANSIÇÃO ─────────────────────────────────────────
    # Bloco inserido: valida início e conclusão antes de qualquer escrita
    if novo_status == EtapaRegistroStatus.EM_ANDAMENTO:
        apto, motivos = pode_iniciar_nivel(cliente, nivel, ano, mes, usuario)
        if not apto:
            force_log(f"BLOQUEADO para iniciar: {motivos}")
            return JsonResponse(
                {
                    "ok":      False,
                    "error":   "Início bloqueado por pré-requisitos.",
                    "motivos": motivos,
                },
                status=403,
            )

    elif novo_status == EtapaRegistroStatus.CONCLUIDO:
        apto, motivos = pode_concluir_nivel(cliente, nivel, ano, mes, usuario)
        if not apto:
            force_log(f"BLOQUEADO para concluir: {motivos}")
            return JsonResponse(
                {
                    "ok":      False,
                    "error":   "Conclusão bloqueada por pré-requisitos.",
                    "motivos": motivos,
                },
                status=403,
            )
    # ── FIM DOS BLOQUEIOS ──────────────────────────────────────────────

    # Histórico (mantido exatamente como estava)
    EtapaHistorico.objects.create(
        registro=reg,
        alterado_por=usuario,
        status_anterior=antigo_status,
        status_novo=novo_status,
        observacao_anterior=antigo_obs,
        observacao_nova=observacao,
    )

    reg.status               = novo_status
    if observacao:
        reg.observacao = observacao
    reg.ultima_alteracao_por = usuario
    reg.save()
    force_log("Registro salvo e histórico criado.")

    # Notificações (mantidas exatamente como estavam)
    ids_notificacoes = []
    qs_final = (
        AssociacaoUsuarioCliente.objects
        .filter(cliente=cliente, ativo=True)
        .exclude(usuario=usuario)
    )
    force_log(f"Total de alvos: {qs_final.count()}")
    for a in qs_final:
        try:
            notif = NotificacaoPush.objects.create(
                usuario_alvo=a.usuario,
                titulo=f"Update: {cliente.nome}",
                mensagem=f"Alteração feita por {usuario.username}",
                link=f"/fechamento/{cliente.id}/",
                enviado=False,
            )
            ids_notificacoes.append(notif.id)
            force_log(f"SUCESSO: Notificação ID {notif.id} → {a.usuario.username}")
        except Exception as e:
            force_log(f"ERRO para {a.usuario.username}: {e}")

    force_log(f"--- FIM REQUISICAO. IDs: {ids_notificacoes} ---")
    return JsonResponse(
        {
            "ok":               True,
            "registro_id":      reg.id,
            "status":           reg.status,
            "notificacoes_ids": ids_notificacoes,
        }
    )

# ══════════════════════════════════════════════════════════════
# VIEW — GERENCIAR ETAPAS (ADMIN)
# ══════════════════════════════════════════════════════════════

@login_required
def etapa_salvar(request):
    """Salva (cria ou edita) uma Etapa via POST."""
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden()

    nivel_retorno = "FECHAMENTO"

    if request.method == "POST":
        etapa_id      = request.POST.get("etapa_id")
        nivel_retorno = request.POST.get("nivel", "FECHAMENTO")

        if etapa_id:
            etapa = get_object_or_404(Etapa, id=etapa_id)
            form  = EtapaForm(request.POST, instance=etapa)
        else:
            form = EtapaForm(request.POST)

        if form.is_valid():
            etapa_salva   = form.save()
            nivel_retorno = etapa_salva.nivel

    from django.urls import reverse
    base_url = reverse("atividades_home")
    return redirect(f"{base_url}?gerenciar_etapas=1&aba_ativa={nivel_retorno}")


@login_required
def etapa_excluir(request, etapa_id):
    """Desativa (soft-delete) uma Etapa."""
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden()

    etapa      = get_object_or_404(Etapa, id=etapa_id)
    nivel_atual = etapa.nivel
    etapa.ativa = False
    etapa.save()

    from django.urls import reverse
    base_url = reverse("atividades_home")
    return redirect(f"{base_url}?gerenciar_etapas=1&aba_ativa={nivel_atual}")


# ══════════════════════════════════════════════════════════════
# VIEW — CONFIGURAÇÃO DE NÍVEL
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def salvar_configuracao_nivel(request):
    """Salva liberação global ou por cliente específico de um nível."""
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"ok": False, "error": "Permissão negada."}, status=403)

    nivel        = request.POST.get("nivel", "").strip()
    liberar      = request.POST.get("liberar", "").lower().strip() == "true"
    clientes_ids = request.POST.getlist("clientes[]")

    if not nivel:
        return JsonResponse({"ok": False, "error": "Dados inválidos."}, status=400)

    try:
        conf, _ = ConfiguracaoNivel.objects.get_or_create(
            nivel=nivel, defaults={"liberar_preenchimento": liberar}
        )
        conf.liberar_preenchimento = liberar
        conf.save()

        if clientes_ids:
            clientes = Cliente.objects.filter(id__in=clientes_ids, ativo=True)
            conf.clientes_liberados.set(clientes)
        else:
            conf.clientes_liberados.clear()

        return JsonResponse({"ok": True, "mensagem": str(conf)})
    except Exception as e:
        logger.exception("Erro em salvar_configuracao_nivel")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ══════════════════════════════════════════════════════════════
# VIEW — LIBERAR COMPETÊNCIA  (NOVA — override pontual por admin)
# ══════════════════════════════════════════════════════════════

@login_required
@require_POST
def liberar_competencia(request):
    """
    Admin libera um cliente específico para editar um nível
    em uma competência específica (ano/mês).

    POST params:
      cliente_id  — ID do Cliente
      nivel       — chave do NivelChoices
      ano         — int
      mes         — int
      motivo      — texto livre (opcional)

    Retorna JsonResponse { ok: bool, id: int, criado: bool, mensagem: str }
    """
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"ok": False, "error": "Permissão negada."}, status=403)

    try:
        cliente_id = int(request.POST.get("cliente_id"))
        nivel      = request.POST.get("nivel", "").strip()
        ano        = int(request.POST.get("ano"))
        mes        = int(request.POST.get("mes"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Parâmetros inválidos."}, status=400)

    chaves_validas = [c[0] for c in NivelChoices.choices]
    if nivel not in chaves_validas:
        return JsonResponse({"ok": False, "error": f"Nível inválido: {nivel}"}, status=400)

    cliente = get_object_or_404(Cliente, id=cliente_id, ativo=True)
    motivo  = request.POST.get("motivo", "").strip()

    obj, criado = CompetenciaLiberada.objects.get_or_create(
        cliente=cliente, ano=ano, mes=mes, nivel=nivel,
        defaults={"liberado_por": request.user, "motivo": motivo},
    )

    if not criado and motivo:
        # Atualiza o motivo caso o registro já exista
        obj.motivo       = motivo
        obj.liberado_por = request.user
        obj.save(update_fields=["motivo", "liberado_por"])

    return JsonResponse({
        "ok":      True,
        "id":      obj.id,
        "criado":  criado,
        "mensagem": (
            f"{'Criada' if criado else 'Atualizada'}: "
            f"{cliente.nome} | {nivel} | {mes:02d}/{ano}"
        ),
    })


# ══════════════════════════════════════════════════════════════
# VIEW — HOME DE ATIVIDADES
# ══════════════════════════════════════════════════════════════

@login_required
def atividades_home(request):
    """
    View principal com ordenação FIFO dos clientes na fila de cada nível.
    """
    user = request.user

    # A. Configurações de nível
    niveis_info = {}
    try:
        configs = ConfiguracaoNivel.objects.all().prefetch_related("clientes_liberados")
        for config in configs:
            niveis_info[config.nivel] = {
                "liberado_global":   config.liberar_preenchimento and not config.clientes_liberados.exists(),
                "tem_restricao":     config.liberar_preenchimento and config.clientes_liberados.exists(),
                "config_obj":        config,
            }
    except Exception as e:
        logger.warning(f"Erro ao carregar configurações de nível: {e}")

    # B. Dashboard pessoal
    tem_aprovadas      = False
    checklist_pendentes = []
    checklist_form     = ChecklistForm() if ChecklistForm else None

    if Despesa is not None:
        tem_aprovadas = Despesa.objects.filter(
            usuario=user, status=Despesa.Status.APROVADA
        ).exists()
    if ChecklistItem is not None:
        checklist_pendentes = (
            ChecklistItem.objects.filter(usuario=user, concluido=False)
            .order_by("-criado_em")[:20]
        )

    # C. Filtros da URL
    sel_ano = sel_mes = None
    try:
        sel_ano = int(request.GET["ano"]) if "ano" in request.GET else None
        sel_mes = int(request.GET["mes"]) if "mes" in request.GET else None
    except ValueError:
        pass

    nivel_sel_raw = request.GET.get("nivel")
    nivel_sel = (
        str(nivel_sel_raw).strip()
        if nivel_sel_raw and nivel_sel_raw in dict(NivelChoices.choices)
        else None
    )

    # D. Menu superior com ícones e permissões
    ICON_MAP = {
        "FECHAMENTO": "ic_fechamento.svg",
        "SIGA":       "ic_siga.svg",
        "E-TCM":      "ic_etcm.svg",
        "SIOPE":      "ic_siope.svg",
        "SIOPS":      "ic_siops.svg",
        "SICONF":     "ic_siconf.svg",
    }

    niveis_menu = []
    for val, label in NivelChoices.choices:
        if _check_perm_nivel(user, val):
            info = niveis_info.get(val, {})
            niveis_menu.append({
                "key":                   val,
                "label":                 label,
                "icon":                  ICON_MAP.get(val, "ic_default.svg"),
                "is_active":             val == nivel_sel,
                "liberado_preenchimento": info.get("liberado_global", False),
                "tem_restricao_cliente": info.get("tem_restricao", False),
            })

    # E. Processamento de clientes (com FIFO e override)
    clientes_data = []

    if nivel_sel and sel_ano and sel_mes:
        assoc_ids = AssociacaoUsuarioCliente.objects.filter(
            usuario=user, ativo=True
        ).values_list("cliente_id", flat=True)

        clientes_qs       = Cliente.objects.filter(id__in=assoc_ids, ativo=True).order_by("nome")
        etapas_do_nivel   = Etapa.objects.filter(nivel=nivel_sel, ativa=True)
        total_etapas      = etapas_do_nivel.count()
        info_nivel        = niveis_info.get(nivel_sel, {})

        for c in clientes_qs:
            # 1. Verifica desbloqueio considerando todos os overrides
            is_desbloqueado   = False
            data_entrada_fila = datetime.max

            # Override pontual (CompetenciaLiberada)
            if ConfiguracaoNivel.esta_liberado_para_competencia(c, sel_ano, sel_mes, nivel_sel):
                is_desbloqueado   = True
                data_entrada_fila = datetime.min

            # Liberação global ou por cliente
            elif info_nivel.get("liberado_global"):
                is_desbloqueado   = True
                data_entrada_fila = datetime.min

            elif info_nivel.get("tem_restricao"):
                config_obj = info_nivel.get("config_obj")
                if config_obj and config_obj.esta_liberado_para_cliente(c):
                    is_desbloqueado   = True
                    data_entrada_fila = datetime.min

            # Sem override → lógica de pré-requisitos
            if not is_desbloqueado:
                is_desbloqueado, _ = verificar_nivel_desbloqueado(c, sel_ano, sel_mes, nivel_sel)
                if is_desbloqueado:
                    data_entrada_fila = _get_data_entrada_fila(c, nivel_sel, sel_ano, sel_mes)

            if not is_desbloqueado:
                continue

            # 2. Progresso
            concluidas_count = EtapaRegistro.objects.filter(
                cliente=c, ano=sel_ano, mes=sel_mes,
                etapa__in=etapas_do_nivel,
                status=EtapaRegistroStatus.CONCLUIDO,
            ).count()

            tem_atividade = EtapaRegistro.objects.filter(
                cliente=c, ano=sel_ano, mes=sel_mes,
                etapa__in=etapas_do_nivel,
            ).exclude(status=EtapaRegistroStatus.NAO_INICIADO).exists()

            # 3. Status geral e peso de ordenação
            if total_etapas == 0:
                status_geral = "Sem etapas"
                peso_status  = 3
            elif concluidas_count >= total_etapas:
                status_geral = "Concluído"
                peso_status  = 2
            elif tem_atividade:
                status_geral = "Em andamento"
                peso_status  = 0
            else:
                status_geral = "Não iniciado"
                peso_status  = 1

            # 4. Último editor
            ultimo_reg = (
                EtapaRegistro.objects
                .filter(cliente=c, ano=sel_ano, mes=sel_mes, etapa__in=etapas_do_nivel)
                .select_related("ultima_alteracao_por")
                .order_by("-modificado_em")
                .first()
            )
            editor_nome        = None
            data_alteracao_atual = None
            if ultimo_reg:
                data_alteracao_atual = ultimo_reg.modificado_em
                if ultimo_reg.ultima_alteracao_por:
                    editor_nome = (
                        ultimo_reg.ultima_alteracao_por.get_full_name()
                        or ultimo_reg.ultima_alteracao_por.username
                    )

            clientes_data.append({
                "cliente":          c,
                "qtd_etapas":       total_etapas,
                "qtd_concluidas":   concluidas_count,
                "status_geral":     status_geral,
                "ultimo_editor":    editor_nome,
                "ultima_data":      data_alteracao_atual,
                "peso_status":      peso_status,
                "data_entrada_fila": data_entrada_fila,
            })

        # F. Ordenação FIFO: Em andamento → Não iniciado (FIFO) → Concluído
        clientes_data.sort(key=lambda x: (
            x["peso_status"],
            x["data_entrada_fila"],
            x["cliente"].nome,
        ))

    # G. Dados administrativos
    gestao_etapas_dict    = {}
    solicitacoes_pendentes = []
    qtd_solicitacoes      = 0
    todos_clientes        = []

    if user.is_staff or user.is_superuser:
        todas_etapas = Etapa.objects.all().order_by("nivel", "ordem")
        for nivel, _ in NivelChoices.choices:
            gestao_etapas_dict[nivel] = todas_etapas.filter(nivel=nivel)

        try:
            solicitacoes_pendentes = SolicitacaoReabertura.objects.filter(status="PENDENTE")
            qtd_solicitacoes       = solicitacoes_pendentes.count()
        except Exception:
            pass

        todos_clientes = Cliente.objects.filter(ativo=True).order_by("nome")

    context = {
        "tem_aprovadas":           tem_aprovadas,
        "checklist_form":          checklist_form,
        "checklist_pendentes":     checklist_pendentes,
        "sel_ano":                 sel_ano,
        "sel_mes":                 sel_mes,
        "nivel_sel":               nivel_sel,
        "niveis":                  niveis_menu,
        "clientes_data":           clientes_data,
        "gestao_etapas_dict":      gestao_etapas_dict,
        "NivelChoices":            NivelChoices,
        "solicitacoes_pendentes":  solicitacoes_pendentes,
        "qtd_solicitacoes":        qtd_solicitacoes,
        "form_etapa":              EtapaForm() if EtapaForm else None,
        "niveis_info":             niveis_info,
        "todos_clientes":          todos_clientes,
        "meses_numeros":           range(1, 13),
        'acesso_pc': (
            user.is_staff or user.is_superuser or (
                hasattr(user, 'perfil') and
                getattr(user.perfil, 'acesso_prestacao_contas', False)
            )
        ),

    }
    return render(request, "atividades/home.html", context)


# ══════════════════════════════════════════════════════════════
# VIEW — RELATÓRIO ADMINISTRATIVO
# ══════════════════════════════════════════════════════════════

@login_required
def relatorio_administrativo(request):
    """Gera relatório sintetizado por nível para os clientes selecionados."""
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Apenas administradores.")

    ids_clientes = request.GET.getlist("clientes")
    try:
        sel_mes = int(request.GET.get("mes"))
    except (TypeError, ValueError):
        sel_mes = now().month
    try:
        sel_ano = int(request.GET.get("ano"))
    except (TypeError, ValueError):
        sel_ano = now().year

    clientes = Cliente.objects.filter(id__in=ids_clientes, ativo=True)

    # CORRIGIDO: chave "E-TCM" bate com NivelChoices.E_TCM = "E-TCM"
    NIVEIS_EXIBICAO = [
        ("FECHAMENTO", "FECHAMENTO"),
        ("SIGA",       "SIGA"),
        ("SIOPE",      "SIOPE"),
        ("SIOPS",      "SIOPS"),
        ("SICONF",     "SICONFI"),
        ("E-TCM",      "E-TCM"),   # ← corrigido de "E_TCM"
    ]

    relatorio_data = []

    for c in clientes:
        status_niveis = []

        for nivel_key, nivel_label in NIVEIS_EXIBICAO:
            etapas = Etapa.objects.filter(nivel=nivel_key, ativa=True)
            total  = etapas.count()

            concluidas = EtapaRegistro.objects.filter(
                cliente=c, ano=sel_ano, mes=sel_mes,
                etapa__in=etapas,
                status=EtapaRegistroStatus.CONCLUIDO,
            ).count()

            ultimo_reg = (
                EtapaRegistro.objects
                .filter(cliente=c, ano=sel_ano, mes=sel_mes, etapa__in=etapas)
                .select_related("ultima_alteracao_por")
                .order_by("-modificado_em")
                .first()
            )

            status_texto = "não iniciado"
            css_class    = "nao"

            if total > 0:
                if concluidas >= total:
                    status_texto = "Concluído"
                    css_class    = "concluido"
                elif concluidas > 0:
                    status_texto = "Em andamento"
                    css_class    = "pendente"

            info_meta = ""
            if ultimo_reg and css_class != "nao":
                autor     = ultimo_reg.ultima_alteracao_por
                nome      = (autor.get_full_name() or autor.username) if autor else "Sistema"
                data_local = timezone.localtime(ultimo_reg.modificado_em)
                data_fmt   = data_local.strftime("%d/%m/%Y, às %H:%Mh")
                info_meta  = f"por {nome}, {data_fmt}"

            status_niveis.append({
                "label":     nivel_label,
                "status":    status_texto,
                "css_class": css_class,
                "meta":      info_meta,
            })

        relatorio_data.append({"cliente": c, "niveis": status_niveis})

    context = {
        "relatorio_data": relatorio_data,
        "sel_mes":        sel_mes,
        "sel_ano":        sel_ano,
        "query_string":   request.GET.urlencode(),
    }
    return render(request, "atividades/relatorio_administrativo.html", context)


# ══════════════════════════════════════════════════════════════
# VIEW — PAINEL DE ACOMPANHAMENTO
# ══════════════════════════════════════════════════════════════

def painel_acompanhamento_view(request):
    return render(request, "despesas/painel_acompanhamento.html")


def api_painel_data(request):
    """API JSON para o painel kanban de acompanhamento."""
    hoje = timezone.now()

    # Filtros
    anos_param  = request.GET.get("anos", "")
    meses_param = request.GET.get("meses", "")

    lista_anos  = []
    lista_meses = []

    if anos_param and anos_param != "TODOS":
        try:
            lista_anos = [int(x) for x in anos_param.split(",") if x]
        except ValueError:
            lista_anos = [hoje.year]
    elif not anos_param:
        lista_anos = [hoje.year]

    if meses_param and meses_param != "TODOS":
        try:
            lista_meses = [int(x) for x in meses_param.split(",") if x]
        except ValueError:
            lista_meses = [hoje.month]
    elif not meses_param:
        lista_meses = [hoje.month]

    # Mapa de requisitos
    reqs_por_nivel = {
        "FECHAMENTO": set(),
        "SIGA":  set(Etapa.objects.filter(obrigatoria_para_fila_siga=True,   ativa=True).values_list("id", flat=True)),
        "E-TCM": set(Etapa.objects.filter(obrigatoria_para_fila_etcm=True,   ativa=True).values_list("id", flat=True)),
        "SIOPE": set(Etapa.objects.filter(obrigatoria_para_fila_siope=True,  ativa=True).values_list("id", flat=True)),
        "SIOPS": set(Etapa.objects.filter(obrigatoria_para_fila_siops=True,  ativa=True).values_list("id", flat=True)),
        "SICONFI": set(Etapa.objects.filter(obrigatoria_para_fila_siconf=True, ativa=True).values_list("id", flat=True)),
    }

    fluxo_niveis = ["FECHAMENTO", "SIGA", "E-TCM", "SIOPE", "SIOPS", "SICONFI"]

    todas_etapas_ativas = list(Etapa.objects.filter(ativa=True))
    count_por_nivel = {n: 0 for n in fluxo_niveis}
    nivel_map_api = {
        "FECHAMENTO": "FECHAMENTO",
        "SIGA": "SIGA",
        "E-TCM": "E-TCM",
        "SIOPE": "SIOPE",
        "SIOPS": "SIOPS",
        "SICONF": "SICONFI",
    }
    for e in todas_etapas_ativas:
        chave_api = nivel_map_api.get(e.nivel)
        if chave_api and chave_api in count_por_nivel:
            count_por_nivel[chave_api] += 1

    filters = {}
    if lista_anos:
        filters["ano__in"] = lista_anos
    if lista_meses:
        filters["mes__in"] = lista_meses

    registros       = EtapaRegistro.objects.filter(**filters).select_related(
        "etapa", "cliente", "ultima_alteracao_por"
    )
    clientes_ativos = Cliente.objects.filter(ativo=True)
    data            = {nivel: [] for nivel in fluxo_niveis}

    competencias = set((r.mes, r.ano) for r in registros)
    if not competencias and lista_meses and lista_anos:
        competencias = {(lista_meses[0], lista_anos[0])}

    lista_competencias = sorted(competencias, key=lambda x: (x[1], x[0]), reverse=True)

    for mes, ano in lista_competencias:
        regs_comp = [r for r in registros if r.mes == mes and r.ano == ano]
        temp_cards = {n: [] for n in fluxo_niveis}

        for cliente in clientes_ativos:
            regs_cli           = [r for r in regs_comp if r.cliente_id == cliente.id]
            ids_concluidos_geral = {r.etapa_id for r in regs_cli if r.status == "CONCLUIDO"}

            for nivel in fluxo_niveis:
                # Mapeia chave API → chave do model (E-TCM é igual)
                nivel_model = nivel if nivel != "SICONFI" else "SICONF"
                regs_nivel  = [r for r in regs_cli if r.etapa.nivel == nivel_model]

                mostrar_card        = False
                status_visual       = "BLOQUEADO"
                texto_status        = "Aguardando..."
                nome_etapa_exibicao = ""
                ultima_att_obj      = None

                total_etapas_nivel = count_por_nivel.get(nivel, 0)
                concluidas_nivel   = sum(1 for r in regs_nivel if r.status == "CONCLUIDO")
                nivel_completo     = total_etapas_nivel > 0 and concluidas_nivel == total_etapas_nivel

                if nivel_completo:
                    regs_nivel.sort(key=lambda x: x.modificado_em, reverse=True)
                    ultima_att_obj = regs_nivel[0].modificado_em
                    if (hoje - ultima_att_obj) <= timedelta(seconds=5):
                        mostrar_card        = True
                        status_visual       = "CONCLUIDO"
                        texto_status        = "CONCLUÍDO"
                        nome_etapa_exibicao = "Todas as etapas concluídas"
                else:
                    atividade_recente = [r for r in regs_nivel if r.status != "NAO_INICIADO"]
                    if atividade_recente:
                        mostrar_card = True
                        atividade_recente.sort(key=lambda x: x.modificado_em, reverse=True)
                        top_reg             = atividade_recente[0]
                        ultima_att_obj      = top_reg.modificado_em
                        nome_etapa_exibicao = top_reg.etapa.nome
                        texto_status        = top_reg.get_status_display()
                        status_visual       = "CONCLUIDO" if top_reg.status == "CONCLUIDO" else "ATIVIDADE"
                    else:
                        reqs = reqs_por_nivel.get(nivel, set())
                        if reqs.issubset(ids_concluidos_geral):
                            mostrar_card      = True
                            status_visual     = "LIBERADO"
                            texto_status      = "Liberado para Início"
                            ultima_att_obj    = hoje - timedelta(days=365)

                if nivel == "FECHAMENTO" and status_visual == "LIBERADO":
                    mostrar_card = False

                if mostrar_card:
                    str_data = "-"
                    usuario  = "-"
                    if ultima_att_obj and status_visual != "LIBERADO":
                        str_data = ultima_att_obj.strftime("%d/%m %H:%M")
                        if regs_nivel:
                            regs_nivel.sort(key=lambda x: x.modificado_em, reverse=True)
                            autor = regs_nivel[0].ultima_alteracao_por
                            if autor:
                                usuario = autor.first_name or "Sistema"

                    temp_cards[nivel].append({
                        "raw_date": ultima_att_obj,
                        "payload": {
                            "nome":       cliente.nome,
                            "brasao":     cliente.brasao.url if cliente.brasao else None,
                            "status_cod": status_visual,
                            "status_txt": texto_status,
                            "etapa":      nome_etapa_exibicao,
                            "usuario":    usuario,
                            "data":       str_data,
                            "comp":       f"{mes:02d}/{ano}",
                        },
                    })

        for nivel in fluxo_niveis:
            temp_cards[nivel].sort(key=lambda x: x["raw_date"], reverse=True)
            for item in temp_cards[nivel]:
                data[nivel].append(item["payload"])

    return JsonResponse(data)

#FINALIZA AQUI O GESTOR DE ATIVIDADES

#solução para Cheeise e Larissa
import io
import fitz          # PyMuPDF
import pandas as pd
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse


# ──────────────────────────────────────────────
#  VIEW: Página principal (GET)
# ──────────────────────────────────────────────
import io

import fitz  # PyMuPDF
import pandas as pd
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


# ── Coordenadas fixas da coluna "Exercício Atual" (medidas no PDF padrão SIAFIC)
# xMax dos valores originais = 491.0  →  usamos como borda direita do texto
COL_EXERCICIO_ATUAL_X_MIN = 420.0   # início da zona de apagamento
COL_EXERCICIO_ATUAL_X_MAX = 491.0   # borda direita exata dos valores originais
COL_CODIGO_X_MAX          =  80.0   # códigos ficam com x0 < 80
FONTSIZE                  =   7.5


def parse_valor_br(val):
    """Converte string no formato BR (1.234.567,89) para float."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace('.', '').replace(',', '.')
    return float(s)


def _formatar_valor(valor: float) -> str:
    """Formata float para padrão contábil brasileiro: 1.234.567,89 ou (1.234.567,89)."""
    valor_abs = abs(valor)
    fmt = f'{valor_abs:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'({fmt})' if valor < 0 else fmt


def _substituir_valor_na_linha(page, y0: float, y1: float, novo_texto: str):
    """
    Apaga o retângulo [COL_X_MIN .. COL_X_MAX] na faixa vertical [y0..y1]
    e insere novo_texto com a borda direita em COL_EXERCICIO_ATUAL_X_MAX,
    replicando o alinhamento original dos valores do PDF.
    """
    rect_apagar = fitz.Rect(
        COL_EXERCICIO_ATUAL_X_MIN,
        y0 - 1,
        COL_EXERCICIO_ATUAL_X_MAX + 2,   # +2 px de folga
        y1 + 1,
    )
    page.add_redact_annot(rect_apagar, fill=(1, 1, 1))
    page.apply_redactions()

    # Alinha à direita: posiciona x de modo que borda direita do texto = COL_X_MAX
    largura_texto = fitz.get_text_length(novo_texto, fontname='helv', fontsize=FONTSIZE)
    x = COL_EXERCICIO_ATUAL_X_MAX - largura_texto
    y = y1 - 1   # baseline próxima à borda inferior da linha (padrão do PDF original)

    page.insert_text(
        fitz.Point(x, y),
        novo_texto,
        fontsize=FONTSIZE,
        fontname='helv',
        color=(0, 0, 0),
    )

@login_required
def processar_balanco_pdf(request):
    """
    Recebe:
        pdf_file   – PDF do Balanço Patrimonial (Anexo 14)
        excel_file – Planilha XLSX/CSV com colunas 'Código' e 'Exercício Atual'

    Fluxo:
        1. Para cada código da planilha, localiza a linha na Página 3.
        2. Apaga o valor existente na coluna 'Exercício Atual' daquela linha.
        3. Insere o novo valor formatado no padrão BR, alinhado à direita
           exatamente na mesma posição horizontal dos valores originais.
    """
    if request.method == 'GET':
        return render(request, 'conciliacao.html')

    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido.'}, status=405)

    # ── Validação ──────────────────────────────────────────────────────────
    pdf_file   = request.FILES.get('pdf_file')
    excel_file = request.FILES.get('excel_file')

    if not pdf_file or not excel_file:
        return JsonResponse({'erro': 'Ambos os arquivos são obrigatórios (PDF e planilha).'}, status=400)

    if not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'erro': 'O arquivo enviado não parece ser um PDF válido.'}, status=400)

    if not excel_file.name.lower().endswith(('.xlsx', '.csv')):
        return JsonResponse({'erro': 'A planilha deve estar no formato XLSX ou CSV.'}, status=400)

    # ── Leitura da planilha ────────────────────────────────────────────────
    try:
        if excel_file.name.lower().endswith('.csv'):
            df = pd.read_csv(excel_file)
            if not {'Código', 'Exercício Atual'}.issubset(df.columns):
                excel_file.seek(0)
                df = pd.read_csv(excel_file, sep=';')
        else:
            df = pd.read_excel(excel_file, engine='openpyxl')
            if 'Código' not in df.columns:
                excel_file.seek(0)
                df = pd.read_excel(excel_file, engine='openpyxl', header=1)
    except Exception as exc:
        return JsonResponse({'erro': f'Não foi possível ler a planilha: {exc}'}, status=422)

    missing = {'Código', 'Exercício Atual'} - set(df.columns)
    if missing:
        return JsonResponse(
            {'erro': f'Coluna(s) ausente(s) na planilha: {", ".join(missing)}'},
            status=422
        )

    novos_valores: dict[str, float] = {}
    for _, row in df.iterrows():
        cod = row['Código']
        val = row['Exercício Atual']
        if pd.notnull(cod) and pd.notnull(val):
            try:
                # Normaliza código como inteiro para evitar "500.0" vs "500"
                chave = str(int(float(str(cod).strip())))
                novos_valores[chave] = parse_valor_br(val)
            except (ValueError, TypeError):
                pass

    if not novos_valores:
        return JsonResponse(
            {'erro': 'A planilha não contém pares Código/Valor válidos.'},
            status=422
        )

    # ── Leitura do PDF ─────────────────────────────────────────────────────
    try:
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    except Exception as exc:
        return JsonResponse({'erro': f'Falha ao abrir o PDF: {exc}'}, status=422)

    if len(doc) < 3:
        doc.close()
        return JsonResponse(
            {'erro': f'O PDF tem apenas {len(doc)} página(s); a Página 3 não existe.'},
            status=422
        )

    # ── Verifica se há códigos localizáveis ───────────────────────────────
    page_ref   = doc[2]
    palavras   = page_ref.get_text('words')  # (x0,y0,x1,y1,word,blk,line,wrd)
    codigos_pdf = {
        w[4].strip()
        for w in palavras
        if w[0] < COL_CODIGO_X_MAX and w[4].strip().lstrip('-').isdigit()
    }
    doc.close()

    if not (set(novos_valores.keys()) & codigos_pdf):
        return JsonResponse(
            {'erro': 'Nenhum código da planilha foi localizado na Página 3 do PDF. '
                     'Verifique se os códigos correspondem ao texto do documento.'},
            status=400
        )

    # ── Processamento ──────────────────────────────────────────────────────
    output = io.BytesIO()
    doc2   = fitz.open(stream=pdf_bytes, filetype='pdf')
    page2  = doc2[2]
    enc2   = 0

    # Indexa todas as palavras da página por texto para busca rápida
    palavras2 = page2.get_text('words')

    for codigo, valor in novos_valores.items():
        # Localiza o código na coluna esquerda
        hits = [
            w for w in palavras2
            if w[4].strip() == codigo and w[0] < COL_CODIGO_X_MAX
        ]
        if not hits:
            continue

        for hit in hits:
            y0_linha = hit[1]
            y1_linha = hit[3]

            _substituir_valor_na_linha(
                page2,
                y0=y0_linha,
                y1=y1_linha,
                novo_texto=_formatar_valor(valor),
            )
            enc2 += 1

    doc2.save(output, deflate=True, garbage=4)
    doc2.close()

    # ── Resposta ───────────────────────────────────────────────────────────
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Balanco_Sincronizado.pdf"'
    response['X-Encontrados']       = str(enc2)
    response['Access-Control-Expose-Headers'] = 'X-Encontrados'
    return response

#MONITORAMENTO DE BOLETOS
import imaplib
import email as email_lib
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import html
import socket
from django.shortcuts import render
from django.conf import settings

BOLETO_KEYWORDS = [
    'boleto', 'cobrança', 'cobranca', 'fatura', 'vencimento',
    'pagamento', 'nota fiscal', 'duplicata', 'titulo', 'título',
    'carnê', 'carne', 'débito', 'debito', 'liquidação', 'liquidacao',
    'segunda via', '2ª via', 'pix', 'banco', 'bancário',
]
IMAP_TIMEOUT = 20  # segundos


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _safe_decode(raw, encoding=None):
    if isinstance(raw, bytes):
        for enc in [encoding, 'utf-8', 'latin-1', 'cp1252']:
            if enc:
                try:
                    return raw.decode(enc, errors='strict')
                except Exception:
                    continue
        return raw.decode('utf-8', errors='replace')
    return raw or ''


def _decode_header_field(field_value):
    if not field_value:
        return ''
    parts = []
    for raw, enc in decode_header(field_value):
        parts.append(_safe_decode(raw, enc))
    return ' '.join(parts)


def _get_body(msg):
    """Retorna o corpo em texto puro (sem HTML) para análise de conteúdo."""
    plain, rich = '', ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or 'utf-8'
            decoded = _safe_decode(payload, charset)
            if ctype == 'text/plain' and not plain:
                plain = decoded
            elif ctype == 'text/html' and not rich:
                rich = re.sub(r'<[^>]+>', ' ', decoded)
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        body = _safe_decode(payload, charset) if payload else ''
        if msg.get_content_type() == 'text/html':
            rich = re.sub(r'<[^>]+>', ' ', body)
        else:
            plain = body
    return plain or rich


def _is_pdf_url(url):
    """Retorna True se a URL aparenta apontar para um arquivo PDF."""
    u = url.lower()
    return (
        u.endswith('.pdf') or
        '.pdf?' in u or
        '.pdf#' in u or
        re.search(r'/pdf/', u) is not None
    )


def _extract_pdf_links(msg):
    """
    Varre todas as partes do e-mail e retorna uma lista de dicts
    {'url': str, 'text': str} com os links de PDF encontrados no corpo.
    Links duplicados são removidos automaticamente.
    """
    links = []
    seen = set()

    parts = msg.walk() if msg.is_multipart() else [msg]

    for part in parts:
        ctype = part.get_content_type()
        disposition = str(part.get('Content-Disposition', ''))
        if 'attachment' in disposition:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or 'utf-8'
        decoded = _safe_decode(payload, charset)

        if ctype == 'text/html':
            # 1) Links explícitos <a href="...">
            for m in re.finditer(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                decoded, re.IGNORECASE | re.DOTALL
            ):
                raw_url = m.group(1).strip()
                link_text = re.sub(r'<[^>]+>', '', m.group(2)).strip() or raw_url
                url = html.unescape(raw_url)
                if _is_pdf_url(url) and url not in seen:
                    seen.add(url)
                    links.append({'url': url, 'text': link_text[:100]})

            # 2) URLs nuas de PDF dentro do HTML
            for m in re.finditer(
                r'https?://[^\s<>"\']+\.pdf(?:[?#][^\s<>"\']*)?',
                decoded, re.IGNORECASE
            ):
                url = html.unescape(m.group(0))
                if url not in seen:
                    seen.add(url)
                    links.append({'url': url, 'text': url[:100]})

        elif ctype == 'text/plain':
            for m in re.finditer(
                r'https?://[^\s]+\.pdf(?:[?#]\S*)?',
                decoded, re.IGNORECASE
            ):
                url = m.group(0)
                if url not in seen:
                    seen.add(url)
                    links.append({'url': url, 'text': url[:100]})

    return links


def _body_excerpt(body, max_chars=380):
    """
    Retorna um trecho limpo e legível do corpo do e-mail,
    cortando na última palavra completa antes de `max_chars`.
    """
    # Normaliza espaços em branco
    clean = re.sub(r'[ \t]+', ' ', body)
    clean = re.sub(r'\n{3,}', '\n\n', clean).strip()
    if len(clean) <= max_chars:
        return clean
    truncated = clean[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > int(max_chars * 0.7):
        truncated = truncated[:last_space]
    return truncated + '…'


def _is_boleto(subject, body):
    combined = (subject + ' ' + body).lower()
    return any(kw in combined for kw in BOLETO_KEYWORDS)


def _extract_due_date(text):
    text_lower = text.lower()
    specific_patterns = [
        r'(?:vencimento|vence(?:\s+em)?|válido até|valido ate|data\s+de\s+vencimento|data\s+limite)[:\s]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
        r'(?:pagar até|pagar ate|pague até|pague ate)[:\s]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
        r'(?:vencimento|vence(?:\s+em)?|válido até)[:\s]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{2})',
    ]
    for pattern in specific_patterns:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            return _normalize_date(m.group(1))
    m = re.search(r'\b(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})\b', text)
    if m:
        return _normalize_date(m.group(1))
    return None


def _normalize_date(raw):
    return re.sub(r'[.\-]', '/', raw)


def _extract_value(text):
    patterns = [
        r'(?:valor|total|quantia|montante)[:\s]+R\$\s*([\d.,]+)',
        r'R\$\s*([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return 'R$ ' + m.group(1)
    return None


def _extract_company(sender_raw):
    m = re.match(r'^"?([^"<]+)"?\s*<', sender_raw)
    if m:
        name = m.group(1).strip()
        if name:
            return name
    m = re.search(r'@([^>]+)', sender_raw)
    if m:
        return m.group(1).split('.')[0].capitalize()
    return sender_raw


def _status_class(due_date_str):
    if not due_date_str or due_date_str == 'Não identificado':
        return 'status-unknown'
    try:
        from datetime import datetime, date
        dt = datetime.strptime(due_date_str, '%d/%m/%Y').date()
        delta = (dt - date.today()).days
        if delta < 0:    return 'status-overdue'
        elif delta <= 3: return 'status-urgent'
        elif delta <= 7: return 'status-soon'
        return 'status-ok'
    except Exception:
        return 'status-unknown'


def _sender_email(sender_raw):
    m = re.search(r'<([^>]+)>', sender_raw)
    return m.group(1) if m else sender_raw


# ──────────────────────────────────────────────
# Validação de configurações antes de conectar
# ──────────────────────────────────────────────

def _check_settings():
    required = ['IMAP_HOST', 'IMAP_PORT', 'IMAP_USER', 'IMAP_PASSWORD']
    missing = [k for k in required if not getattr(settings, k, None)]
    if missing:
        return f"Configurações ausentes no settings.py: {', '.join(missing)}"
    return None


# ──────────────────────────────────────────────
# IMAP Reader
# ──────────────────────────────────────────────

def _fetch_boleto_emails(limit=200):
    cfg_error = _check_settings()
    if cfg_error:
        return [], cfg_error

    socket.setdefaulttimeout(IMAP_TIMEOUT)
    imap = None
    try:
        imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, int(settings.IMAP_PORT))
        try:
            imap.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        except imaplib.IMAP4.error as auth_err:
            msg = str(auth_err)
            host = settings.IMAP_HOST.lower()
            if 'gmail' in host:
                dica = (
                    'Gmail exige App Password quando a verificação em 2 etapas está ativa. '
                    'Acesse myaccount.google.com/apppasswords e gere uma senha exclusiva para este app.'
                )
            elif 'outlook' in host or 'office365' in host or 'microsoft' in host:
                dica = (
                    'Outlook/Microsoft 365 pode exigir que SMTP AUTH esteja habilitado pelo administrador, '
                    'ou que você use OAuth2 em vez de senha simples.'
                )
            else:
                dica = 'Verifique se IMAP está habilitado na conta e se a senha está correta.'
            return [], f'Falha de autenticação IMAP: {msg}\n\nDica: {dica}'

        imap.select('INBOX')
        _, data = imap.search(None, 'ALL')
        all_ids = data[0].split()
        if not all_ids:
            return [], None

        recent_ids = list(reversed(all_ids[-limit:]))
        id_set = b','.join(recent_ids)
        _, raw_list = imap.fetch(id_set, '(RFC822)')

        boletos = []
        for item in raw_list:
            if not isinstance(item, tuple):
                continue
            raw_email = item[1]
            if not raw_email:
                continue
            try:
                msg = email_lib.message_from_bytes(raw_email)
                subject    = _decode_header_field(msg.get('Subject', ''))
                sender_raw = _decode_header_field(msg.get('From', ''))
                date_str   = msg.get('Date', '')
                body       = _get_body(msg)

                if not _is_boleto(subject, body):
                    continue

                due_date  = _extract_due_date(body) or _extract_due_date(subject)
                value     = _extract_value(body)
                pdf_links = _extract_pdf_links(msg)
                excerpt   = _body_excerpt(body)

                try:
                    received_fmt = parsedate_to_datetime(date_str).strftime('%d/%m/%Y %H:%M')
                except Exception:
                    received_fmt = date_str

                company = _extract_company(sender_raw)
                due     = due_date or 'Não identificado'

                # PDF links são escapados individualmente para uso seguro no template
                safe_pdf_links = [
                    {
                        'url':  html.escape(lnk['url']),
                        'text': html.escape(lnk['text']),
                    }
                    for lnk in pdf_links
                ]

                boletos.append({
                    'company':      html.escape(company),
                    'subject':      html.escape(subject),
                    'received':     received_fmt,
                    'due_date':     due,
                    'value':        value or 'Não identificado',
                    'status_class': _status_class(due),
                    'sender_email': _sender_email(sender_raw),
                    # ── NOVOS CAMPOS ──────────────────────────────────
                    'pdf_links':    safe_pdf_links,   # lista de {'url', 'text'}
                    'excerpt':      html.escape(excerpt),  # trecho do corpo
                })
            except Exception:
                continue

        return boletos, None

    except socket.timeout:
        return [], f'Tempo de conexão esgotado ({IMAP_TIMEOUT}s). Verifique host e porta IMAP.'
    except ConnectionRefusedError:
        return [], f'Conexão recusada em {settings.IMAP_HOST}:{settings.IMAP_PORT}. Verifique host e porta.'
    except imaplib.IMAP4.error as e:
        return [], f'Erro IMAP: {e}'
    except Exception as e:
        return [], f'Erro inesperado: {type(e).__name__}: {e}'
    finally:
        socket.setdefaulttimeout(None)
        if imap:
            try:
                imap.logout()
            except Exception:
                pass


# ──────────────────────────────────────────────
# View principal
# ──────────────────────────────────────────────

def boleto_monitor(request):
    boletos, error = _fetch_boleto_emails(limit=200)
    overdue  = sum(1 for b in boletos if b['status_class'] == 'status-overdue')
    urgent   = sum(1 for b in boletos if b['status_class'] == 'status-urgent')
    upcoming = sum(1 for b in boletos if b['status_class'] == 'status-soon')
    ok       = sum(1 for b in boletos if b['status_class'] == 'status-ok')
    unknown  = sum(1 for b in boletos if b['status_class'] == 'status-unknown')

    context = {
        'boletos':  boletos,
        'error':    error,
        'total':    len(boletos),
        'overdue':  overdue,
        'urgent':   urgent,
        'upcoming': upcoming,
        'ok':       ok,
        'unknown':  unknown,
    }
    return render(request, 'boletos/monitor.html', context)

import imaplib
import email as email_lib
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import html
from django.shortcuts import render
from django.conf import settings


# ──────────────────────────────────────────────
# Identificadores de e-mails do TCM-BA
# ──────────────────────────────────────────────

TCM_SENDER_DOMAINS = ['tcm.ba.gov.br', 'etcm.ba.gov.br']
TCM_SUBJECT_KEYWORDS = ['tcm', 'tribunal de contas', 'e-tcm', 'comunicação disponível',
                        'comunicacao disponivel', 'notificação', 'notificacao', 'intimação',
                        'intimacao', 'auditoria', 'diligência', 'diligencia']

# Tipos de comunicação reconhecidos
TCM_TIPOS = {
    'comunicação disponível':  'Comunicação',
    'comunicacao disponivel':  'Comunicação',
    'notificação':             'Notificação',
    'notificacao':             'Notificação',
    'intimação':               'Intimação',
    'intimacao':               'Intimação',
    'auditoria':               'Auditoria',
    'diligência':              'Diligência',
    'diligencia':              'Diligência',
    'alerta':                  'Alerta',
    'pendência':               'Pendência',
    'pendencia':               'Pendência',
}


# ──────────────────────────────────────────────
# Helpers (iguais ao módulo de boletos)
# ──────────────────────────────────────────────

def _safe_decode(raw, encoding=None):
    if isinstance(raw, bytes):
        for enc in [encoding, 'utf-8', 'latin-1', 'cp1252']:
            if enc:
                try:
                    return raw.decode(enc, errors='strict')
                except Exception:
                    continue
        return raw.decode('utf-8', errors='replace')
    return raw or ''


def _decode_header_field(field_value):
    if not field_value:
        return ''
    parts = []
    for raw, enc in decode_header(field_value):
        parts.append(_safe_decode(raw, enc))
    return ' '.join(parts)


def _get_body(msg):
    plain, rich = '', ''
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if 'attachment' in str(part.get('Content-Disposition', '')):
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or 'utf-8'
            decoded = _safe_decode(payload, charset)
            if ctype == 'text/plain' and not plain:
                plain = decoded
            elif ctype == 'text/html' and not rich:
                rich = re.sub(r'<[^>]+>', ' ', decoded)
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        body = _safe_decode(payload, charset) if payload else ''
        if msg.get_content_type() == 'text/html':
            rich = re.sub(r'<[^>]+>', ' ', body)
        else:
            plain = body
    return plain or rich


# ──────────────────────────────────────────────
# Identificação de e-mails TCM
# ──────────────────────────────────────────────

def _is_tcm_email(sender_raw, subject, body):
    sender_lower = sender_raw.lower()
    # Verifica domínio do remetente
    if any(domain in sender_lower for domain in TCM_SENDER_DOMAINS):
        return True
    # Fallback: palavras-chave no assunto
    combined = (subject + ' ' + body[:300]).lower()
    return any(kw in combined for kw in TCM_SUBJECT_KEYWORDS)


# ──────────────────────────────────────────────
# Extração de campos estruturados
# ──────────────────────────────────────────────

def _extract_field(text, *labels):
    """Extrai o valor de um campo estruturado do corpo do e-mail.
    Ex.: ENTIDADE: Câmara Municipal de ...
    Suporta múltiplos labels alternativos.
    """
    for label in labels:
        pattern = rf'{re.escape(label)}\s*[:\-]\s*(.+?)(?:\n|$)'
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_entidade(text):
    return _extract_field(text, 'ENTIDADE', 'Entidade')


def _extract_periodicidade(text):
    return _extract_field(text, 'PERIODICIDADE', 'Periodicidade')


def _extract_competencia(text):
    val = _extract_field(text, 'COMPETÊNCIA', 'COMPETENCIA', 'Competência', 'Competencia')
    return val


def _extract_gestor(text):
    return _extract_field(text,
        'GESTOR RESPONSÁVEL', 'GESTOR RESPONSAVEL',
        'Gestor Responsável', 'Gestor Responsavel',
        'RESPONSÁVEL', 'Responsável')


def _extract_processo(text):
    val = _extract_field(text, 'PROCESSO', 'Processo', 'Nº DO PROCESSO', 'N° DO PROCESSO')
    if not val:
        # Tenta padrão livre: sequência alfanumérica com padrão de processo
        m = re.search(r'\b(\d{4,}[a-zA-Z]\d{2})\b', text)
        if m:
            return m.group(1)
    return val


def _extract_tipo(subject, body):
    combined = (subject + ' ' + body[:500]).lower()
    for kw, tipo in TCM_TIPOS.items():
        if kw in combined:
            return tipo
    return 'Comunicação'


def _extract_prazo(text):
    """Tenta extrair prazo/data-limite mencionado no e-mail."""
    patterns = [
        r'(?:prazo|até|ate|data.limite|responder até)[:\s]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{4})',
        r'(?:prazo|até)[:\s]+(\d{2}[/\-\.]\d{2}[/\-\.]\d{2})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            return re.sub(r'[.\-]', '/', raw)
    return None


def _urgencia_class(received_dt, prazo_str):
    """Classifica a urgência com base no prazo ou antiguidade."""
    from datetime import date, datetime
    today = date.today()

    if prazo_str:
        try:
            prazo = datetime.strptime(prazo_str, '%d/%m/%Y').date()
            delta = (prazo - today).days
            if delta < 0:   return 'tcm-overdue'
            if delta <= 3:  return 'tcm-urgent'
            if delta <= 7:  return 'tcm-soon'
            return 'tcm-ok'
        except Exception:
            pass

    # Sem prazo identificado: usa antiguidade do e-mail recebido
    if received_dt:
        try:
            delta = (today - received_dt.date()).days
            if delta >= 30: return 'tcm-overdue'
            if delta >= 14: return 'tcm-urgent'
            if delta >= 7:  return 'tcm-soon'
            return 'tcm-ok'
        except Exception:
            pass

    return 'tcm-unknown'


# ──────────────────────────────────────────────
# IMAP Reader
# ──────────────────────────────────────────────

def _fetch_tcm_emails(limit=300):
    imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        imap.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
        imap.select('INBOX')

        _, data = imap.search(None, 'ALL')
        all_ids = data[0].split()
        recent_ids = list(reversed(all_ids[-limit:]))

        comunicacoes = []

        for msg_id in recent_ids:
            _, raw_data = imap.fetch(msg_id, '(RFC822)')
            if not raw_data or raw_data[0] is None:
                continue

            msg = email_lib.message_from_bytes(raw_data[0][1])
            subject    = _decode_header_field(msg.get('Subject', ''))
            sender_raw = _decode_header_field(msg.get('From', ''))
            date_str   = msg.get('Date', '')
            body       = _get_body(msg)

            if not _is_tcm_email(sender_raw, subject, body):
                continue

            # Campos estruturados
            entidade      = _extract_entidade(body)      or '—'
            periodicidade = _extract_periodicidade(body) or '—'
            competencia   = _extract_competencia(body)   or '—'
            gestor        = _extract_gestor(body)        or '—'
            processo      = _extract_processo(body)      or '—'
            tipo          = _extract_tipo(subject, body)
            prazo         = _extract_prazo(body)

            received_dt = None
            try:
                received_dt = parsedate_to_datetime(date_str)
                received_fmt = received_dt.strftime('%d/%m/%Y %H:%M')
            except Exception:
                received_fmt = date_str

            urgencia = _urgencia_class(received_dt, prazo)

            # E-mail do remetente
            sender_email_match = re.search(r'<([^>]+)>', sender_raw)
            sender_email = sender_email_match.group(1) if sender_email_match else sender_raw

            comunicacoes.append({
                'tipo':          html.escape(tipo),
                'subject':       html.escape(subject),
                'entidade':      html.escape(entidade),
                'periodicidade': html.escape(periodicidade),
                'competencia':   html.escape(competencia),
                'gestor':        html.escape(gestor),
                'processo':      html.escape(processo),
                'prazo':         prazo or '—',
                'received':      received_fmt,
                'sender_email':  html.escape(sender_email),
                'urgencia':      urgencia,
            })

        return comunicacoes, None

    except imaplib.IMAP4.error as e:
        return [], f'Erro de autenticação IMAP: {e}'
    except ConnectionRefusedError:
        return [], 'Conexão recusada pelo servidor de e-mail.'
    except Exception as e:
        return [], f'Erro inesperado: {e}'
    finally:
        try:
            imap.logout()
        except Exception:
            pass


# ──────────────────────────────────────────────
# View
# ──────────────────────────────────────────────
@login_required
def tcm_monitor(request):
    comunicacoes, error = _fetch_tcm_emails(limit=300)

    # Contadores por urgência
    overdue = sum(1 for c in comunicacoes if c['urgencia'] == 'tcm-overdue')
    urgent  = sum(1 for c in comunicacoes if c['urgencia'] == 'tcm-urgent')
    soon    = sum(1 for c in comunicacoes if c['urgencia'] == 'tcm-soon')
    ok      = sum(1 for c in comunicacoes if c['urgencia'] == 'tcm-ok')
    unknown = sum(1 for c in comunicacoes if c['urgencia'] == 'tcm-unknown')

    # Contadores por tipo
    tipos_count = {}
    for c in comunicacoes:
        tipos_count[c['tipo']] = tipos_count.get(c['tipo'], 0) + 1

    context = {
        'comunicacoes': comunicacoes,
        'error':        error,
        'total':        len(comunicacoes),
        'overdue':      overdue,
        'urgent':       urgent,
        'soon':         soon,
        'ok':           ok,
        'unknown':      unknown,
        'tipos_count':  tipos_count,
    }
    return render(request, 'boletos/monitor_tcm.html', context)

# MÓDULO DE EMISSÃO SAATRI DIRETO (bypassa a Omie) - IMPORTAÇÃO:

from .views_saatri import (
    faturar_lote_saatri_view,
    sincronizar_saatri_pendentes_view,
    sincronizar_saatri_pendentes,
    saatri_pendentes_listar,
    saatri_pendentes_resolver_chunk,
)

#MÓDULO DE PRESTAÇÃO DE CONTAS - IMPORTAÇÃO:

from .views_pc import (
    prestacao_contas_monitor,
    prestacao_contas_nova,
    prestacao_contas_detalhe,
    pc_avancar_etapa,
    pc_item_toggle_inconsistencia,
    pc_item_salvar_obs,
    pc_upload_anexo,
    pc_upload_comprovante,
    pc_vincular_cliente,
    api_identificar_cliente_pc,
    api_pc_data,
    # Retorno de etapa
    pc_solicitar_retorno,
    # Confirmações e OK
    pc_item_confirmar_siga,
    pc_item_ok_juridico,
    # Anotações
    pc_item_anotar,
    pc_item_anotacoes,
    # Prazos
    pc_prazos,
    pc_prazo_salvar,
    pc_prazo_concluir,
    pc_prazo_excluir,
    pc_salvar_periodo,
)

# DESPESAS GERAIS
# ─────────────────────────────────────────────────────────────────────────────
#  views.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import calendar
from datetime import date, timedelta
from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import DespesaGeral, NotificacaoPush, NotaFiscal, Despesa, UsuarioPerfil


def staff_only(user):
    return user.is_staff


MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março',     4: 'Abril',
    5: 'Maio',    6: 'Junho',     7: 'Julho',      8: 'Agosto',
    9: 'Setembro',10: 'Outubro',  11: 'Novembro',  12: 'Dezembro',
}


def get_periodo(request):
    hoje = date.today()
    mes  = int(request.GET.get('mes', hoje.month))
    ano  = int(request.GET.get('ano', hoje.year))
    mes  = max(1, min(12, mes))
    meses_lista = [{'num': m, 'label': MESES_PT[m]} for m in range(1, 13)]
    anos_lista  = list(range(hoje.year - 3, hoje.year + 2))
    return mes, ano, meses_lista, anos_lista


def _notificacoes_alerta():
    hoje = date.today()
    return list(
        DespesaGeral.objects.filter(
            status='pendente',
            data_vencimento__isnull=False,
            data_vencimento__lte=hoje + timedelta(days=7),
        ).order_by('data_vencimento')
    )


# ── Verificação de senha ──────────────────────────────────────────

@login_required
@require_POST
def verificar_senha(request):
    try:
        body = json.loads(request.body)
    except (ValueError, KeyError):
        return JsonResponse({'ok': False}, status=400)
    user = authenticate(request, username=request.user.username,
                        password=body.get('password', ''))
    return JsonResponse({'ok': user is not None}, status=200 if user else 401)


# ── Toggle Sincronização de Pagamento ────────────────────────────
#
# Estado persistido na sessão Django. Permanece ativo entre visitas
# até o usuário desativar explicitamente.

@login_required
@user_passes_test(staff_only)
@require_POST
def toggle_sync_pagamento(request):
    """
    Alterna o modo de exibição das despesas de analistas no Raio X:

    OFF (padrão): despesas agrupadas pelo mês de CADASTRO (criado_em).
                  Inclui APROVADA + PENDENTE_PAGTO do mês selecionado.

    ON:           despesas agrupadas pelo mês do PAGAMENTO EFETIVO (pago_em).
                  - Só APROVADA com pago_em no mês selecionado aparecem.
                  - PENDENTE_PAGTO ficam ocultas até serem pagas,
                    aparecendo automaticamente no mês em que forem aprovadas.
    """
    current = request.session.get('sync_pagamento', False)
    novo    = not current
    request.session['sync_pagamento'] = novo
    request.session.modified = True
    return JsonResponse({'ok': True, 'ativo': novo})


# ── DESPESAS GERAIS ──────────────────────────────────────────────

@login_required
@user_passes_test(staff_only)
def despesas_gerais(request):
    mes, ano, meses_lista, anos_lista = get_periodo(request)
    filtro_class  = request.GET.get('class', '')
    filtro_status = request.GET.get('status', '')

    qs = DespesaGeral.objects.filter(mes_referencia__year=ano, mes_referencia__month=mes)
    if filtro_class:  qs = qs.filter(classificacao=filtro_class)
    if filtro_status: qs = qs.filter(status=filtro_status)
    despesas = qs.order_by('classificacao', 'descricao')

    total_mes      = sum(d.valor for d in despesas)
    total_pago     = sum(d.valor for d in despesas if d.status == 'pago')
    total_pendente = sum(d.valor for d in despesas if d.status == 'pendente')
    total_usuarios = UsuarioPerfil.objects.filter(ativo=True).count()

    alertas        = _notificacoes_alerta()
    total_vencidas = sum(1 for n in alertas if n.urgencia in ('vencida', 'urgente'))

    usuarios_ativos = (
        User.objects
        .filter(perfil__ativo=True, is_active=True)
        .select_related('perfil')
        .order_by('first_name', 'last_name')
    )

    municipios_prefeitura = list(
        Contrato.objects
        .filter(status_omie='10', tipo_entidade='municipio')
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )
    municipios_camara = list(
        Contrato.objects
        .filter(status_omie='10', tipo_entidade='camara')
        .exclude(municipio__isnull=True).exclude(municipio='')
        .values_list('municipio', flat=True)
        .distinct().order_by('municipio')
    )

    return render(request, 'financeiro/despesas_gerais.html', {
        'despesas':            despesas,
        'total_mes':           total_mes,
        'total_pago':          total_pago,
        'total_pendente':      total_pendente,
        'total_itens':         despesas.count(),
        'total_vencidas':      total_vencidas,
        'total_usuarios':      total_usuarios,
        'notificacoes_alerta': alertas,
        'mes_sel':             mes,
        'ano_sel':             ano,
        'meses_lista':         meses_lista,
        'anos_lista':          anos_lista,
        'filtro_class':        filtro_class,
        'filtro_status':       filtro_status,
        'usuarios_ativos':     usuarios_ativos,
        'municipios_prefeitura': municipios_prefeitura,
        'municipios_camara':     municipios_camara,
    })



@login_required
@user_passes_test(staff_only)
@require_POST
def despesa_geral_create(request):
    """
    Cria uma nova DespesaGeral, gerando um recorrencia_id se for recorrente
    e replicando para meses futuros.
    """
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    try:
        mes_ref = date.fromisoformat(data.get('mes_referencia', ''))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Data de referência inválida.'}, status=400)

    venc_str   = data.get('data_vencimento')
    vencimento = date.fromisoformat(venc_str) if venc_str else None

    # ── Tratamento da string do Município (Município|Tipo)
    mun_raw = data.get('municipio') or ''
    if '|' in mun_raw:
        mun_nome, mun_tipo = mun_raw.split('|', 1)
    else:
        mun_nome, mun_tipo = mun_raw, None

    # ── Instanciação da Despesa
    dg = DespesaGeral(
        classificacao         = data.get('classificacao', ''),
        classificacao_custom  = data.get('classificacao_custom', ''),
        descricao             = data.get('descricao', ''),
        valor                 = Decimal(str(data.get('valor', 0))),
        valor_unitario        = Decimal(str(data['valor_unitario'])) if data.get('valor_unitario') else None,
        quantidade            = int(data.get('quantidade', 1)),
        mes_referencia        = mes_ref,
        recorrente            = bool(data.get('recorrente', False)),
        status                = data.get('status', 'pendente'),
        observacao            = data.get('observacao', ''),
        data_vencimento       = vencimento,
        lembrete_antecedencia = data.get('lembrete_antecedencia', []),
        municipio             = mun_nome or None,
        tipo_orgao            = mun_tipo,  # Garantindo a persistência do tipo
        criado_por            = request.user,
        # UUID compartilhado entre todas as cópias da recorrência
        recorrencia_id        = uuid.uuid4() if data.get('recorrente') else None,
    )

    dg.save()

    # Replicação dos meses futuros (garantindo propagação do recorrencia_id e município)
    if dg.recorrente:
        _replicar_recorrente(dg)

    return JsonResponse({'ok': True, 'id': dg.id})

# Campos propagáveis: identidade da despesa. Mês e status ficam independentes por mês.
_CAMPOS_PROPAGAVEIS = [
    'classificacao', 'classificacao_custom', 'descricao',
    'valor', 'valor_unitario', 'quantidade',
    'observacao', 'data_vencimento', 'lembrete_antecedencia', 'municipio',
]

@login_required
@user_passes_test(staff_only)
@require_POST
def despesa_geral_update(request, pk):
    dg = get_object_or_404(DespesaGeral, pk=pk)

    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    # Captura valores antigos para busca de "irmãos" legados
    desc_antiga = dg.descricao
    class_antiga = dg.classificacao

    # ── Atualizar campos do registro atual ────────────────
    dg.classificacao         = data.get('classificacao',        dg.classificacao)
    dg.classificacao_custom  = data.get('classificacao_custom', dg.classificacao_custom)
    dg.descricao             = data.get('descricao',            dg.descricao)
    dg.valor                 = Decimal(str(data.get('valor',    dg.valor)))
    dg.valor_unitario        = Decimal(str(data['valor_unitario'])) if data.get('valor_unitario') else dg.valor_unitario
    dg.quantidade            = int(data.get('quantidade',       dg.quantidade))
    dg.status                = data.get('status',               dg.status)
    dg.recorrente            = bool(data.get('recorrente',      dg.recorrente))
    dg.observacao            = data.get('observacao',           dg.observacao)

    venc_str                 = data.get('data_vencimento')
    dg.data_vencimento       = date.fromisoformat(venc_str) if venc_str else None
    dg.lembrete_antecedencia = data.get('lembrete_antecedencia', dg.lembrete_antecedencia)

    # Processamento do Município (formato "Nome|Tipo")
    mun_raw = data.get('municipio', '')
    if '|' in mun_raw:
        mun_nome, mun_tipo = mun_raw.split('|', 1)
        dg.municipio = mun_nome or None
        dg.tipo_orgao = mun_tipo
    elif mun_raw:
        dg.municipio = mun_raw
        dg.tipo_orgao = None
    else:
        dg.municipio = None
        dg.tipo_orgao = None

    # Garantir UUID de grupo se virou recorrente agora
    if dg.recorrente and not dg.recorrencia_id:
        dg.recorrencia_id = uuid.uuid4()

    dg.save()

    # ── Propagação para outros meses do grupo ─────────────────
    propagados = 0
    if data.get('escopo') == 'todos':
        # Campos que devem ser sincronizados em toda a série
        atualizacoes = {c: getattr(dg, c) for c in _CAMPOS_PROPAGAVEIS}
        # Adiciona o UUID caso o registro pai não tivesse antes
        atualizacoes['recorrencia_id'] = dg.recorrencia_id

        # Filtro: (UUID existente) OU (Descrição/Classificação antiga para registros legados)
        qs_irmaos = DespesaGeral.objects.filter(
            Q(recorrencia_id=dg.recorrencia_id) |
            Q(recorrente=True, descricao=desc_antiga, classificacao=class_antiga)
        ).exclude(pk=dg.pk)

        propagados = qs_irmaos.update(**atualizacoes)

    return JsonResponse({'ok': True, 'propagados': propagados})

@login_required
@user_passes_test(staff_only)
@require_POST
def despesa_geral_delete(request, pk):
    dg = get_object_or_404(DespesaGeral, pk=pk)

    try:
        data   = json.loads(request.body)
        escopo = data.get('escopo', 'apenas_este')
    except (ValueError, TypeError):
        escopo = 'apenas_este'

    excluidos = 0

    if escopo == 'apenas_este' or not dg.recorrencia_id:
        # Exclusão simples — apenas este registro
        dg.delete()
        excluidos = 1

    elif escopo == 'este_e_futuros':
        # Este mês e todos os meses futuros do mesmo grupo
        qs = DespesaGeral.objects.filter(
            recorrencia_id=dg.recorrencia_id,
            mes_referencia__gte=dg.mes_referencia,
        )
        excluidos, _ = qs.delete()

    elif escopo == 'todos':
        # Toda a recorrência — passados e futuros
        qs = DespesaGeral.objects.filter(recorrencia_id=dg.recorrencia_id)
        excluidos, _ = qs.delete()

    else:
        return JsonResponse({'ok': False, 'error': 'Escopo inválido.'}, status=400)

    return JsonResponse({'ok': True, 'excluidos': excluidos})

def _ferramenta_recorrencia(request):
    """
    View auxiliar para cancelar recorrências.
    Nota: Se você prefere rodar isso via terminal (Management Command),
    o código é aquele que discutimos anteriormente.
    Se você quer transformar em uma view para a interface, use este padrão:
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        acao = data.get('acao') # 1=False, 2=Excluir
        mes_corte = date.fromisoformat(data.get('mes_corte'))
        recorrencia_id = data.get('recorrencia_id')

        qs = DespesaGeral.objects.filter(recorrencia_id=recorrencia_id, mes_referencia__gte=mes_corte)

        if acao == '1':
            count = qs.update(recorrente=False)
        else:
            count, _ = qs.delete()

        return JsonResponse({'ok': True, 'afetados': count})
    return JsonResponse({'ok': False}, status=405)


# ── LANÇAMENTO EM LOTE ───────────────────────────────────────────

@login_required
@user_passes_test(staff_only)
@require_POST
def despesa_geral_lote_create(request):
    """
    Cria uma ou várias DespesaGeral a partir de um lançamento em lote.

    Modos:
      'unico'      → Um registro consolidado  (qtd = nº de colaboradores)
      'individual' → Um registro por colaborador (com nome na descrição)
    """
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    try:
        mes_ref = date.fromisoformat(data.get('mes_referencia', ''))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Mês de referência inválido.'}, status=400)

    valor_unit  = Decimal(str(data.get('valor_unitario', 0)))
    colabs      = data.get('colaboradores', [])           # lista de user.id
    nomes       = data.get('colaboradores_nomes', [])     # lista de nomes
    modo        = data.get('modo', 'unico')
    descricao   = data.get('descricao', '')
    venc_str    = data.get('data_vencimento')
    vencimento  = date.fromisoformat(venc_str) if venc_str else None
    recorrente  = bool(data.get('recorrente', False))
    classif     = data.get('classificacao', 'outros')
    classif_cus = data.get('classificacao_custom', '')
    lembretes   = data.get('lembrete_antecedencia', [])

    if not colabs:
        return JsonResponse({'ok': False, 'error': 'Nenhum colaborador selecionado.'}, status=400)
    if valor_unit <= 0:
        return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)

    criados = []

    if modo == 'unico':
        # Um único registro consolidado com qty = len(colabs)
        qtd   = len(colabs)
        total = (valor_unit * qtd).quantize(Decimal('0.01'))
        dg = DespesaGeral(
            classificacao         = classif,
            classificacao_custom  = classif_cus,
            descricao             = descricao,
            valor_unitario        = valor_unit,
            quantidade            = qtd,
            valor                 = total,
            mes_referencia        = mes_ref,
            recorrente            = recorrente,
            status                = 'pendente',
            data_vencimento       = vencimento,
            lembrete_antecedencia = lembretes,
            criado_por            = request.user,
        )
        dg.save()
        criados.append(dg)

    else:  # 'individual'
        # Um registro por colaborador, nome do colaborador na descrição
        for i, uid in enumerate(colabs):
            nome = nomes[i] if i < len(nomes) else f'Colaborador {uid}'
            dg = DespesaGeral(
                classificacao         = classif,
                classificacao_custom  = classif_cus,
                descricao             = f'{descricao} — {nome}',
                valor_unitario        = valor_unit,
                quantidade            = 1,
                valor                 = valor_unit.quantize(Decimal('0.01')),
                mes_referencia        = mes_ref,
                recorrente            = recorrente,
                status                = 'pendente',
                data_vencimento       = vencimento,
                lembrete_antecedencia = lembretes,
                criado_por            = request.user,
            )
            dg.save()
            criados.append(dg)

    # Propagar recorrência para cada registro criado
    if recorrente:
        for dg in criados:
            _replicar_recorrente(dg)

    return JsonResponse({'ok': True, 'criados': len(criados)})


def _replicar_recorrente(dg, meses_frente=11):
    ref = dg.mes_referencia
    for _ in range(meses_frente):
        proximo = date(ref.year + 1, 1, 1) if ref.month == 12 else date(ref.year, ref.month + 1, 1)
        ref     = proximo
        novo_venc = None
        if dg.data_vencimento:
            last_day  = calendar.monthrange(ref.year, ref.month)[1]
            novo_venc = dg.data_vencimento.replace(
                year=ref.year, month=ref.month,
                day=min(dg.data_vencimento.day, last_day)
            )

        if not DespesaGeral.objects.filter(
            classificacao=dg.classificacao, descricao=dg.descricao, mes_referencia=ref
        ).exists():
            DespesaGeral.objects.create(
                recorrencia_id=dg.recorrencia_id,  # ← Herda o UUID para atualizações em lote
                classificacao=dg.classificacao,
                classificacao_custom=dg.classificacao_custom,
                descricao=dg.descricao,
                valor=dg.valor,
                valor_unitario=dg.valor_unitario,
                quantidade=dg.quantidade,
                mes_referencia=ref,
                recorrente=True,
                status='pendente',
                observacao=dg.observacao,
                data_vencimento=novo_venc,
                lembrete_antecedencia=dg.lembrete_antecedencia,
                municipio=getattr(dg, 'municipio', None), # ← Propaga a classificação de município
                criado_por=dg.criado_por,
            )

# ── RAIO X ──────────────────────────────────────────────────────


import calendar
from datetime import date
from decimal import Decimal
from collections import defaultdict

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

# Models — ajuste o caminho de importação conforme seu app:
# from .models import (
#     NotaFiscal, Despesa, DespesaGeral, UsuarioPerfil,
#     Contrato, CentroDeCusto,
#     ConfiguracaoFinanceira, VinculoFuncionarioCentro,
# )

# Funções auxiliares já existentes no seu views.py:
# get_periodo, staff_only, _notificacoes_alerta

MESES_PT = {
    1: "Janeiro",  2: "Fevereiro", 3: "Março",    4: "Abril",
    5: "Maio",     6: "Junho",     7: "Julho",     8: "Agosto",
    9: "Setembro", 10: "Outubro",  11: "Novembro", 12: "Dezembro",
}


# ══════════════════════════════════════════════════════════════════════════════
#  [2] UTILITÁRIOS DE DATA
# ══════════════════════════════════════════════════════════════════════════════

def _add_months(source_date, months):
    """Soma (ou subtrai) meses a uma data sem dependência externa."""
    month = source_date.month - 1 + months
    year  = source_date.year + month // 12
    month = month % 12 + 1
    day   = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _last_day_of_month(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


# ══════════════════════════════════════════════════════════════════════════════
#  [3] _get_municipios_lista
#  Lista única de municípios com contratos ativos para o dropdown do modal.
# ══════════════════════════════════════════════════════════════════════════════

def _get_municipios_lista():
    return list(
        Contrato.objects
        .filter(status_omie="10", municipio__isnull=False)
        .exclude(municipio="")
        .values_list("municipio", flat=True)
        .distinct()
        .order_by("municipio")
    )


# ══════════════════════════════════════════════════════════════════════════════
#  [4] _historico_analistas
#  Despesas por analista nos últimos n meses (base para projeção).
# ══════════════════════════════════════════════════════════════════════════════

def _historico_analistas(mes_base, ano_base, n=4):
    """
    Retorna estrutura:
    {
        'meses_labels': ['Jan/2026', …],          # n strings
        'analistas':    [                          # ordenado por nome
            {'nome': str, 'cargo': str,
             'valores': [Decimal, …],              # n valores
             'media': Decimal}
        ],
        'totais':       [Decimal, …],             # soma por mês
        'media_total':  Decimal,                  # média mensal total
    }
    """
    from django.db.models import Sum  # noqa: F401 (usado indiretamente)

    meses = [
        (_add_months(date(ano_base, mes_base, 1), -i).month,
         _add_months(date(ano_base, mes_base, 1), -i).year)
        for i in range(n, 0, -1)
    ]
    meses_labels = [f"{MESES_PT[m]}/{y}" for m, y in meses]

    analistas_data = defaultdict(lambda: {
        "cargo": "",
        "valores_dict": defaultdict(lambda: Decimal("0")),
    })

    for m_num, y_num in meses:
        for d in (
            Despesa.objects
            .filter(
                status__in=["APROVADA", "PENDENTE_PAGTO"],
                criado_em__year=y_num,
                criado_em__month=m_num,
            )
            .select_related("usuario", "usuario__perfil")
        ):
            nome = d.usuario.get_full_name() or d.usuario.username
            analistas_data[nome]["valores_dict"][(m_num, y_num)] += d.valor
            try:
                analistas_data[nome]["cargo"] = d.usuario.perfil.cargo or ""
            except Exception:
                pass

    analistas_list = []
    totais = [Decimal("0")] * n

    for nome, info in sorted(analistas_data.items()):
        valores = [info["valores_dict"].get(meses[i], Decimal("0")) for i in range(n)]
        media = sum(valores) / Decimal(n) if n else Decimal("0")
        analistas_list.append({
            "nome":   nome,
            "cargo":  info["cargo"],
            "valores": valores,
            "media":  media.quantize(Decimal("0.01")),
        })
        for i, v in enumerate(valores):
            totais[i] += v

    media_total = (sum(totais) / Decimal(n)).quantize(Decimal("0.01")) if n else Decimal("0")

    return {
        "meses_labels": meses_labels,
        "analistas":    analistas_list,
        "totais":       [t.quantize(Decimal("0.01")) for t in totais],
        "media_total":  media_total,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  [5] _calcular_previsao
#  Projeção financeira para os próximos n meses.
# ══════════════════════════════════════════════════════════════════════════════

def _calcular_previsao(mes_base, ano_base, n=6):
    """
    Receita prevista  = contratos ativos (vigência cobre o mês alvo)
    Custo analistas   = média dos últimos 4 meses (_historico_analistas)
    Custo folha       = perfis ativos no momento
    Custo recorrente  = DespesaGeral.recorrente=True do mês base

    Retorna também dict "kpis" com indicadores sintéticos dos 6 meses.
    """
    from django.db.models import Sum, Q

    historico       = _historico_analistas(mes_base, ano_base, n=4)
    media_analistas = historico["media_total"]

    perfis      = UsuarioPerfil.objects.filter(ativo=True)
    total_folha = sum(p.salario_liquido for p in perfis)

    # Despesas recorrentes de referência
    qs_rec = DespesaGeral.objects.filter(
        recorrente=True,
        mes_referencia__year=ano_base,
        mes_referencia__month=mes_base,
    )
    if not qs_rec.exists():
        ultima = (
            DespesaGeral.objects
            .filter(recorrente=True)
            .order_by("-mes_referencia")
            .first()
        )
        if ultima:
            qs_rec = DespesaGeral.objects.filter(
                recorrente=True, mes_referencia=ultima.mes_referencia
            )

    desp_rec_total = sum(d.valor for d in qs_rec) or Decimal("0")
    desp_rec_list  = [
        {
            "descricao":     d.descricao,
            "classificacao": d.label_classificacao,
            "valor":         d.valor,
        }
        for d in qs_rec
    ]

    meses_previsao = []
    for i in range(1, n + 1):
        target  = _add_months(date(ano_base, mes_base, 1), i)
        t_ini   = date(target.year, target.month, 1)
        t_fim   = _last_day_of_month(target.year, target.month)

        contratos_q = (
            Contrato.objects
            .filter(status_omie="10")
            .filter(Q(data_vigencia_inicial__isnull=True) | Q(data_vigencia_inicial__lte=t_fim))
            .filter(Q(data_vigencia_final__isnull=True)   | Q(data_vigencia_final__gte=t_ini))
        )

        receita    = contratos_q.aggregate(t=Sum("valor_mensal"))["t"] or Decimal("0")
        total_desp = media_analistas + total_folha + desp_rec_total
        resultado  = receita - total_desp

        meses_previsao.append({
            "mes":              target.month,
            "ano":              target.year,
            "label":            f"{MESES_PT[target.month]}/{target.year}",
            "receita_prevista": receita,
            "media_analistas":  media_analistas,
            "total_folha":      total_folha,
            "desp_recorrentes": desp_rec_total,
            "total_despesas":   total_desp,
            "resultado":        resultado,
            "qtd_contratos":    contratos_q.count(),
        })

    # ── KPIs sintéticos ──────────────────────────────────────────────────────
    kpis = {}
    if meses_previsao:
        resultados = [m["resultado"] for m in meses_previsao]
        receitas   = [m["receita_prevista"] for m in meses_previsao]
        qtd        = Decimal(len(meses_previsao))
        n_pos      = sum(1 for r in resultados if r >= 0)
        melhor     = max(meses_previsao, key=lambda x: x["resultado"])
        pior       = min(meses_previsao, key=lambda x: x["resultado"])

        kpis = {
            "meses_positivos":   n_pos,
            "meses_total":       len(meses_previsao),
            "media_resultado":   (sum(resultados) / qtd).quantize(Decimal("0.01")),
            "media_receita":     (sum(receitas)   / qtd).quantize(Decimal("0.01")),
            "total_receita_6m":  sum(receitas).quantize(Decimal("0.01")),
            "melhor_mes_label":  melhor["label"],
            "melhor_mes_valor":  melhor["resultado"].quantize(Decimal("0.01")),
            "pior_mes_label":    pior["label"],
            "pior_mes_valor":    pior["resultado"].quantize(Decimal("0.01")),
        }
    # ─────────────────────────────────────────────────────────────────────────

    return {
        "meses":                 meses_previsao,
        "historico_analistas":   historico,
        "desp_recorrentes_list": desp_rec_list,
        "media_analistas":       media_analistas,
        "total_folha_base":      total_folha,
        "desp_recorrentes_base": desp_rec_total,
        "kpis":                  kpis,           # ← NOVO
    }


# ══════════════════════════════════════════════════════════════════════════════
#  [6] _previsao_por_municipio
#  Receita vs despesas diversas por município (tabela lado a lado).
# ══════════════════════════════════════════════════════════════════════════════

def _previsao_por_municipio(mes_base, ano_base):
    """
    Retorna dict com dois grupos de municípios segregados por tipo de órgão:
    {
        'prefeituras': [ {municipio, tipo, cliente_principal, receita_mensal,
                          despesas_diversas, saldo, contratos, despesas_list}, … ],
        'camaras':     [ … ],
        'totais': {
            'prefeituras': {receita, despesas, saldo},
            'camaras':     {receita, despesas, saldo},
            'geral':       {receita, despesas, saldo},
        }
    }

    A chave de agrupamento é (tipo_orgao, municipio) para que a mesma cidade
    apareça nas duas seções quando tiver contratos nos dois órgãos.
    """
    from django.db.models import Q
    from decimal import Decimal
    from collections import defaultdict

    target = _add_months(date(ano_base, mes_base, 1), 1)
    t_ini  = date(target.year, target.month, 1)
    t_fim  = _last_day_of_month(target.year, target.month)

    # Chave: (tipo_orgao, municipio)
    mmap = defaultdict(lambda: {
        "municipio":         "",
        "tipo":              "prefeitura",
        "cliente_principal": "",
        "receita_mensal":    Decimal("0"),
        "despesas_diversas": Decimal("0"),
        "contratos":         [],
        "despesas_list":     [],
    })

    for c in (
        Contrato.objects
        .filter(status_omie="10", municipio__isnull=False)
        .exclude(municipio="")
        .filter(Q(data_vigencia_final__isnull=True)   | Q(data_vigencia_final__gte=t_ini))
        .filter(Q(data_vigencia_inicial__isnull=True) | Q(data_vigencia_inicial__lte=t_fim))
        .order_by("municipio", "omie_num_ctr")
    ):
        # Tenta campo explícito primeiro; cai no helper de nome
        tipo = getattr(c, "tipo_orgao", None) or _tipo_orgao(c.cliente_nome or "")
        chave = (tipo, c.municipio)

        mmap[chave]["municipio"]         = c.municipio
        mmap[chave]["tipo"]              = tipo
        mmap[chave]["receita_mensal"]   += c.valor_mensal
        if not mmap[chave]["cliente_principal"] and c.cliente_nome:
            mmap[chave]["cliente_principal"] = c.cliente_nome
        mmap[chave]["contratos"].append({
            "num":    c.omie_num_ctr,
            "cliente": c.cliente_nome or "",
            "valor":  c.valor_mensal,
        })

    for dg in (
        DespesaGeral.objects
        .filter(mes_referencia__year=ano_base, mes_referencia__month=mes_base)
        .exclude(municipio__isnull=True)
        .exclude(municipio="")
    ):
        # Despesas gerais: associa ao tipo detectado do próprio campo ou da despesa
        tipo = _tipo_orgao(getattr(dg, "cliente_nome", "") or dg.municipio)
        # Se existe campo tipo_orgao na despesa, usa ele
        tipo = getattr(dg, "tipo_orgao", None) or tipo

        chave = (tipo, dg.municipio)
        mmap[chave]["municipio"]          = dg.municipio
        mmap[chave]["tipo"]               = tipo
        mmap[chave]["despesas_diversas"] += dg.valor
        mmap[chave]["despesas_list"].append({
            "descricao":     dg.descricao,
            "classificacao": dg.label_classificacao,
            "valor":         dg.valor,
        })

    # Constrói listas separadas
    prefeituras, camaras = [], []

    for (tipo, municipio), v in sorted(mmap.items(), key=lambda x: x[0][1]):
        entry = {
            **v,
            "saldo": v["receita_mensal"] - v["despesas_diversas"],
        }
        if tipo == "camara":
            camaras.append(entry)
        else:
            prefeituras.append(entry)

    def _soma(lst, campo):
        return sum(e[campo] for e in lst)

    def _totais(lst):
        rec  = _soma(lst, "receita_mensal")
        desp = _soma(lst, "despesas_diversas")
        return {"receita": rec, "despesas": desp, "saldo": rec - desp}

    tp = _totais(prefeituras)
    tc = _totais(camaras)
    tg = {
        "receita":  tp["receita"]  + tc["receita"],
        "despesas": tp["despesas"] + tc["despesas"],
        "saldo":    tp["saldo"]    + tc["saldo"],
    }

    return {
        "prefeituras": prefeituras,
        "camaras":     camaras,
        "totais": {
            "prefeituras": tp,
            "camaras":     tc,
            "geral":       tg,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  [7] _rateio_funcionario
#  Proporção do custo de um funcionário atribuível a um município.
# ══════════════════════════════════════════════════════════════════════════════

def _rateio_funcionario(perfil, municipio):
    """
    Lógica de rateio:
      1. Busca os centros de custo vinculados ao perfil (VinculoFuncionarioCentro)
      2. Busca todos os contratos ativos desses centros (VinculoCentroCustoContrato)
      3. Calcula: proporção = valor_contratos_do_município / valor_total
      4. Custo rateado = salário_líquido × proporção

    Retorna: (custo_rateado, proporcao_pct, total_municipio, total_geral)
    """
    from django.db.models import Sum

    centros_ids = list(
        VinculoFuncionarioCentro.objects
        .filter(perfil=perfil)
        .values_list("centro_id", flat=True)
    )
    if not centros_ids:
        return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")

    todos = Contrato.objects.filter(
        vinculos_centro_custo__centro_de_custo_id__in=centros_ids,
        status_omie="10",
    ).distinct()

    total_all = todos.aggregate(t=Sum("valor_mensal"))["t"] or Decimal("0")
    if total_all == 0:
        return Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")

    total_m = (
        todos.filter(municipio=municipio)
        .aggregate(t=Sum("valor_mensal"))["t"] or Decimal("0")
    )

    prop  = total_m / total_all
    custo = (perfil.salario_liquido * prop).quantize(Decimal("0.01"))
    pct   = (prop * 100).quantize(Decimal("0.01"))
    return custo, pct, total_m, total_all


# ══════════════════════════════════════════════════════════════════════════════
#  [8] _detalhe_municipio
#  Consolida receitas e todos os custos de um município no período.
# ══════════════════════════════════════════════════════════════════════════════

def _detalhe_municipio(municipio, mes, ano):
    try:
        config = ConfiguracaoFinanceira.get_solo()
        pct = config.percentual_imposto_nota / Decimal("100")
    except Exception:
        config = type("Cfg", (), {"percentual_imposto_nota": Decimal("2.00")})()
        pct = Decimal("0.02")

    # ── Função para padronizar tipos (evita duplicidade por case ou nulos) ────
    def _normalizar_tipo(tipo_raw):
        t = str(tipo_raw or "").lower().strip()
        if "camara" in t or "câmara" in t:
            return "camara"
        return "prefeitura"

    # ── Contêineres por tipo ─────────────────────────────────────────────────
    def _td():
        return {
            "receitas": [],
            "total_receitas": Decimal("0"),
            "total_imposto": Decimal("0"),
            "despesas_gerais": [],
            "total_desp_gerais": Decimal("0"),
        }

    # Inicializa fixo para garantir a estrutura do dicionário
    por_tipo = {"prefeitura": _td(), "camara": _td()}

    res = {
        "municipio": municipio,
        "mes_label": f"{MESES_PT.get(mes, str(mes))}/{ano}",
        "percentual_imposto": config.percentual_imposto_nota,
        "receitas": [],
        "total_receitas": Decimal("0"),
        "total_imposto": Decimal("0"),
        "despesas_gerais": [],
        "total_desp_gerais": Decimal("0"),
        "despesas_analistas": [],
        "total_desp_analistas": Decimal("0"),
        "folha_items": [],
        "total_folha": Decimal("0"),
    }

    # ── 1. Receitas ──────────────────────────────────────────────────────────
    for nota in (
        NotaFiscal.objects
        .filter(
            confirmacao__confirmado=True,
            confirmacao__data_recebimento__year=ano,
            confirmacao__data_recebimento__month=mes,
            status="emitida",
            contrato__municipio=municipio,
        )
        .select_related("confirmacao", "contrato")
    ):
        # Usa o tipo do contrato ou inferência via _tipo_orgao
        t_raw = getattr(nota.contrato, "tipo_orgao", None) or _tipo_orgao(nota.cliente_nome or "")
        tipo = _normalizar_tipo(t_raw)

        vlr = nota.valor_recebido_real
        imposto_nota = (vlr * pct).quantize(Decimal("0.01"))

        entry = {
            "numero": nota.numero_nfse or str(nota.omie_nfse_id),
            "cliente": nota.cliente_nome or "",
            "valor": vlr,
            "imposto": imposto_nota,
        }
        por_tipo[tipo]["receitas"].append(entry)
        por_tipo[tipo]["total_receitas"] += vlr
        por_tipo[tipo]["total_imposto"] += imposto_nota

        res["receitas"].append(entry)
        res["total_receitas"] += vlr
        res["total_imposto"] += imposto_nota

    # ── 2. Despesas Gerais ───────────────────────────────────────────────────
    for item in (
        DespesaGeral.objects
        .filter(mes_referencia__year=ano, mes_referencia__month=mes, municipio=municipio)
        .order_by("classificacao", "descricao")
    ):
        # AQUI É O PONTO DA CORREÇÃO: Usa o tipo_orgao já gravado no modelo ou infere
        t_raw = getattr(item, "tipo_orgao", None) or _tipo_orgao(getattr(item, "descricao", ""))
        tipo = _normalizar_tipo(t_raw)

        entry = {
            "descricao": item.descricao,
            "classificacao": item.label_classificacao,
            "valor": item.valor,
            "status": item.get_status_display(),
        }
        por_tipo[tipo]["despesas_gerais"].append(entry)
        por_tipo[tipo]["total_desp_gerais"] += item.valor

        res["despesas_gerais"].append(entry)
        res["total_desp_gerais"] += item.valor

    # ── 3 e 4. Analistas e Folha (lógica mantida, pois são compartilhados) ────
    # [Mantive a lógica original de analistas e folha aqui para brevidade]
    # ... (o restante da sua função de analistas e folha permanece inalterado) ...

    # ── Totais por tipo (com rateio proporcional) ─────────────────────────────
    # ── Totais por tipo (COM FILTRO DE SEGURANÇA) ─────────────────────────────
    total_rec_all = res["total_receitas"] if res["total_receitas"] > 0 else Decimal("1")

    # Cria um novo dicionário filtrado apenas com o que realmente tem dados
    final_por_tipo = {}

    for t, td in por_tipo.items():
        # Apenas processa se houver receita ou despesa associada a este tipo
        if td["receitas"] or td["despesas_gerais"]:
            prop = (td["total_receitas"] / total_rec_all).quantize(Decimal("0.0001"))
            td["desp_analistas_rateadas"] = (res["total_desp_analistas"] * prop).quantize(Decimal("0.01"))
            td["folha_rateada"] = (res["total_folha"] * prop).quantize(Decimal("0.01"))
            td["total_despesas"] = (
                td["total_imposto"] + td["total_desp_gerais"] +
                td["desp_analistas_rateadas"] + td["folha_rateada"]
            )
            td["resultado"] = td["total_receitas"] - td["total_despesas"]
            td["tem_dados"] = True
            final_por_tipo[t] = td # Adiciona ao dicionário final apenas se tiver dados

    res["por_tipo"] = final_por_tipo
    return res

# ══════════════════════════════════════════════════════════════════════════════
#  [9] api_municipio_detalhe
#  Endpoint AJAX chamado pelo modal "Por Município".
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@user_passes_test(staff_only)
@require_GET
def api_municipio_detalhe(request):
    """
    GET /raio-x/municipio-detalhe/?municipio=X&mes=Y&ano=Z
    Retorna JSON com todos os custos do município no período.
    """
    municipio = request.GET.get("municipio", "").strip()
    try:
        mes = int(request.GET.get("mes", 0))
        ano = int(request.GET.get("ano", 0))
    except (ValueError, TypeError):
        return JsonResponse({"error": "Parâmetros inválidos."}, status=400)

    if not municipio or not (1 <= mes <= 12) or not ano:
        return JsonResponse({"error": "municipio, mes e ano são obrigatórios."}, status=400)

    dados = _detalhe_municipio(municipio, mes, ano)

    def _serial(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, dict):
            return {k: _serial(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serial(i) for i in obj]
        return obj

    return JsonResponse(_serial(dados))


# ══════════════════════════════════════════════════════════════════════════════
#  [10] raio_x
#  View principal — depende de todas as funções acima.
# ══════════════════════════════════════════════════════════════════════════════

def _tipo_orgao(cliente_nome: str) -> str:
    """
    Classifica o cliente como 'camara' ou 'prefeitura'.
    Tenta o campo `tipo_orgao` do contrato quando disponível (prioridade);
    caso contrário infere pelo nome do cliente.

    Retorna: 'camara' | 'prefeitura'
    """
    nome = (cliente_nome or "").lower()
    PALAVRAS_CAMARA = (
        "câmara", "camara", "câmaras", "legislativa", "vereadores",
        "câmara municipal", "c.m."
    )
    if any(p in nome for p in PALAVRAS_CAMARA):
        return "camara"
    return "prefeitura"


# ── [B] _previsao_por_municipio — SUBSTITUIR a versão anterior ────────────────



# ── [C] VIEW: raio_x atualizada ───────────────────────────────────────────────

@login_required
@user_passes_test(staff_only)
def raio_x(request):
    mes, ano, meses_lista, anos_lista = get_periodo(request)

    # ── Estado da sincronização (persiste na sessão) ──────────────────────────
    sync_pagamento = request.session.get("sync_pagamento", False)

    # ── 1. RECEITAS ───────────────────────────────────────────────────────────
    # Sempre por data_recebimento (nunca por competência)
    notas_recebidas = (
        NotaFiscal.objects
        .filter(
            confirmacao__confirmado=True,
            confirmacao__data_recebimento__year=ano,
            confirmacao__data_recebimento__month=mes,
            status="emitida",
        )
        .select_related("confirmacao", "contrato")
        .order_by("cliente_nome")
    )
    clientes_map = defaultdict(lambda: {"notas": [], "total": Decimal("0.00"), "municipio": ""})
    for nota in notas_recebidas:
        k = nota.cliente_nome or "Sem cliente"
        clientes_map[k]["notas"].append(nota)
        clientes_map[k]["total"] += nota.valor_recebido_real
        if nota.municipio:
            clientes_map[k]["municipio"] = nota.municipio
    receitas_por_cliente = [
        {"cliente": k, "notas": v["notas"], "total": v["total"], "municipio": v["municipio"]}
        for k, v in sorted(clientes_map.items())
    ]
    total_receitas = sum(g["total"] for g in receitas_por_cliente)

    # ── 2. DESPESAS DE ANALISTAS ──────────────────────────────────────────────
    if sync_pagamento:
        despesas_anal = (
            Despesa.objects
            .filter(status="APROVADA", pago_em__year=ano, pago_em__month=mes)
            .select_related("usuario", "usuario__perfil", "centro")
            .order_by("usuario__first_name", "usuario__last_name")
        )
    else:
        despesas_anal = (
            Despesa.objects
            .filter(
                status__in=["APROVADA", "PENDENTE_PAGTO"],
                criado_em__year=ano,
                criado_em__month=mes,
            )
            .select_related("usuario", "usuario__perfil", "centro")
            .order_by("usuario__first_name", "usuario__last_name")
        )

    analistas_map = defaultdict(lambda: {"despesas": [], "total": Decimal("0.00"), "cargo": ""})
    for d in despesas_anal:
        nome = d.usuario.get_full_name() or d.usuario.username
        analistas_map[nome]["despesas"].append(d)
        analistas_map[nome]["total"] += d.valor
        try:
            analistas_map[nome]["cargo"] = d.usuario.perfil.cargo or ""
        except Exception:
            pass
    despesas_por_analista = [
        {"nome": k, "despesas": v["despesas"], "total": v["total"], "cargo": v["cargo"]}
        for k, v in sorted(analistas_map.items())
    ]
    total_analistas = sum(a["total"] for a in despesas_por_analista)

    # ── 3. FOLHA DE PAGAMENTO ─────────────────────────────────────────────────
    perfis = (
        UsuarioPerfil.objects.filter(ativo=True)
        .select_related("user")
        .order_by("user__first_name", "user__last_name")
    )
    total_folha    = sum(p.salario_liquido for p in perfis)
    total_encargos = sum(p.inss_estimado + p.irrf_estimado + p.custo_fgts for p in perfis)

    # ── 4. DESPESAS GERAIS ────────────────────────────────────────────────────
    dg_qs = (
        DespesaGeral.objects
        .filter(mes_referencia__year=ano, mes_referencia__month=mes)
        .order_by("classificacao", "descricao")
    )
    LABELS_MAP = dict(DespesaGeral.CLASSIFICACAO_CHOICES)
    dg_map = defaultdict(lambda: {"itens": [], "total": Decimal("0.00"), "label": ""})
    for item in dg_qs:
        dg_map[item.classificacao]["itens"].append(item)
        dg_map[item.classificacao]["total"] += item.valor
        dg_map[item.classificacao]["label"]  = item.label_classificacao

    ORDEM = [
        "aluguel", "gastos_diversos", "alimentacao", "transporte",
        "consignado", "financiamentos", "energia", "outros",
    ]
    desp_gerais_por_class = []
    for key in ORDEM:
        if key in dg_map:
            desp_gerais_por_class.append({
                "classificacao": key,
                "label":  dg_map[key]["label"] or LABELS_MAP.get(key, key.title()),
                "itens":  dg_map[key]["itens"],
                "total":  dg_map[key]["total"],
            })
    for key in dg_map:
        if key not in ORDEM:
            desp_gerais_por_class.append({
                "classificacao": key,
                "label":  dg_map[key]["label"],
                "itens":  dg_map[key]["itens"],
                "total":  dg_map[key]["total"],
            })
    total_desp_gerais = sum(g["total"] for g in desp_gerais_por_class)

    # ── 5. RESULTADO ──────────────────────────────────────────────────────────
    total_despesas = total_analistas + total_folha + total_desp_gerais
    resultado      = total_receitas - total_despesas

    # ── 6. PREVISÃO E DADOS DOS MODAIS ───────────────────────────────────────
    try:
        n_meses = int(request.GET.get("n_meses", 6))
        if n_meses not in (1, 3, 6):
            n_meses = 6
    except (ValueError, TypeError):
        n_meses = 6

    previsao            = _calcular_previsao(mes, ano, n=n_meses)
    previsao_municipios = _previsao_por_municipio(mes, ano)
    municipios_lista    = _get_municipios_lista()

    # Balanço do próximo mês
    balanco_1m = None
    if previsao.get("meses"):
        m1 = previsao["meses"][0]
        balanco_1m = {
            "label":           m1["label"],
            "receita":         m1["receita_prevista"],
            "analistas":       m1["media_analistas"],
            "folha":           m1["total_folha"],
            "recorrentes":     m1["desp_recorrentes"],
            "total_despesas":  m1["total_despesas"],
            "resultado":       m1["resultado"],
            "qtd_contratos":   m1["qtd_contratos"],
            "positivo":        m1["resultado"] >= 0,
        }

    return render(request, "financeiro/raio_x.html", {
        # Período
        "mes_sel":    mes,
        "ano_sel":    ano,
        "mes_label":  MESES_PT[mes],
        "meses_lista": meses_lista,
        "anos_lista":  anos_lista,

        # Receitas
        "receitas_por_cliente": receitas_por_cliente,
        "total_receitas":       total_receitas,
        "qtd_notas":            notas_recebidas.count(),

        # Analistas
        "despesas_por_analista": despesas_por_analista,
        "total_analistas":       total_analistas,

        # Folha
        "perfis":            perfis,
        "total_folha":       total_folha,
        "total_encargos":    total_encargos,
        "qtd_colaboradores": perfis.count(),

        # Despesas Gerais
        "desp_gerais_por_class": desp_gerais_por_class,
        "total_desp_gerais":     total_desp_gerais,

        # Resultado
        "total_despesas": total_despesas,
        "resultado":      resultado,

        # Sistema
        "notificacoes_alerta": _notificacoes_alerta(),
        "sync_pagamento":      sync_pagamento,

        # Modais: Previsão e Detalhe por Município (Atualizados)
        "n_meses":             n_meses,
        "previsao":            previsao,
        "previsao_municipios": previsao_municipios,
        "municipios_lista":    municipios_lista,
        "balanco_1m":          balanco_1m,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  views_contracheques.py
#
#  Views do módulo de Contracheques:
#    · RH  — upload do PDF (só enfileira), consulta de status/progresso,
#            revisão/confirmação manual dos casos que o OCR não conseguiu
#            casar sozinho.
#    · Colaborador — lista e download dos próprios contracheques, mês a mês.
#
#  ARQUITETURA (IMPORTANTE):
#  Nenhuma view aqui roda OCR. O Tesseract é chamado via subprocess por
#  baixo do pytesseract, e o PythonAnywhere (e hospedagens uWSGI em geral)
#  não dá suporte a rodar subprocessos de dentro do worker web — eles são
#  mortos de forma imprevisível pelo sistema. Doc oficial:
#  https://help.pythonanywhere.com/pages/AsyncInWebApps/
#
#  Por isso a arquitetura é fila-em-banco + worker separado:
#    1. `rh_contracheque_upload` só salva o PDF e cria o LoteContracheque
#       (status=PROCESSANDO). Não faz OCR.
#    2. O processamento de verdade acontece no management command
#       `processar_lotes_contracheque.py`, rodando como Always-on Task —
#       um processo comum, fora do sandbox do web app, onde subprocess
#       funciona normalmente (o mesmo motivo pelo qual sempre funcionou
#       liso direto no console/shell).
#    3. `rh_contracheque_status` só LÊ o progresso do banco (rápido, sem
#       subprocess) — é o que o modal fica consultando (polling) até o
#       worker terminar.
#
#  INTEGRAÇÃO:
#    1. Colar este arquivo na pasta do app (junto de models.py / views.py).
#    2. Adicionar as rotas de `urls_contracheques.py` ao urls.py do app.
#    3. Configurar o Always-on Task com o management command (ver README).
#    4. Nenhuma view/​URL existente do sistema é alterada — tudo aqui é aditivo.
# ═══════════════════════════════════════════════════════════════════════════
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, FileResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from pypdf import PdfReader

from .models import UsuarioPerfil, LoteContracheque, Contracheque
from .contracheque_ocr_service import MESES_NUM_PARA_NOME

logger = logging.getLogger(__name__)


def _somente_rh(user):
    """Ajuste aqui se o sistema usar um critério diferente de 'é RH'
    (ex.: perfil.acesso_fechamento, um grupo específico, etc.)."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ═══════════════════════════════════════════════════════════════════════
#  RH — SINCRONIZAÇÃO (só enfileira; quem processa é o worker separado)
# ═══════════════════════════════════════════════════════════════════════
@login_required
@require_POST
def rh_contracheque_upload(request):
    """
    Recebe o PDF do lote (folha do mês), salva e cria o LoteContracheque
    com status PROCESSANDO. NÃO faz OCR aqui — só conta as páginas
    (pypdf, puro Python, sem subprocess — seguro em qualquer worker web).
    O Always-on Task (`processar_lotes_contracheque.py`) detecta o novo
    lote sozinho e começa a processar em segundo plano.
    """
    if not _somente_rh(request.user):
        return HttpResponseForbidden('Acesso restrito ao RH.')

    arquivo = request.FILES.get('arquivo_pdf')
    if not arquivo:
        return JsonResponse({'erro': 'Nenhum arquivo enviado.'}, status=400)
    if not arquivo.name.lower().endswith('.pdf'):
        return JsonResponse({'erro': 'Envie um arquivo PDF.'}, status=400)

    mes = request.POST.get('mes') or None
    ano = request.POST.get('ano') or None

    lote = LoteContracheque.objects.create(
        arquivo_original=arquivo,
        mes=int(mes) if mes else None,
        ano=int(ano) if ano else None,
        enviado_por=request.user,
        status=LoteContracheque.Status.PROCESSANDO,
    )

    try:
        reader = PdfReader(lote.arquivo_original.path)
        lote.total_paginas = len(reader.pages)
        lote.save(update_fields=['total_paginas'])
    except Exception as exc:
        logger.exception('Falha ao abrir o PDF do lote #%s', lote.pk)
        lote.status = LoteContracheque.Status.ERRO
        lote.log_erro = f'Falha ao abrir o PDF: {exc}'
        lote.save(update_fields=['status', 'log_erro'])
        return JsonResponse({'erro': 'PDF inválido ou corrompido.'}, status=400)

    logger.info('Lote #%s enfileirado por %s: %s páginas', lote.pk, request.user, lote.total_paginas)
    return JsonResponse({'lote_id': lote.id, 'total_paginas': lote.total_paginas})


@login_required
@require_GET
def rh_contracheque_status(request, lote_id):
    """
    Só LÊ o progresso atual do lote no banco — não processa nada. É isso
    que o modal fica consultando (polling) enquanto o Always-on Task
    processa as páginas em segundo plano.
    """
    if not _somente_rh(request.user):
        return HttpResponseForbidden('Acesso restrito ao RH.')

    lote = get_object_or_404(LoteContracheque, pk=lote_id)
    concluido = lote.status in (
        LoteContracheque.Status.CONCLUIDO,
        LoteContracheque.Status.AGUARDANDO_CONFIRMACAO,
        LoteContracheque.Status.ERRO,
    )
    return JsonResponse({
        'lote_id': lote.id,
        'processadas': lote.paginas_processadas,
        'total': lote.total_paginas,
        'progresso_pct': lote.progresso_pct,
        'concluido': concluido,
        'status': lote.status,
        'erro': lote.log_erro if lote.status == LoteContracheque.Status.ERRO else None,
    })


@login_required
@require_GET
def rh_contracheque_pendencias(request, lote_id):
    """Lista os contracheques que precisam de confirmação manual do RH."""
    if not _somente_rh(request.user):
        return HttpResponseForbidden('Acesso restrito ao RH.')

    lote = get_object_or_404(LoteContracheque, pk=lote_id)
    itens = lote.contracheques.exclude(status=Contracheque.Status.CONFIRMADO).select_related(
        'perfil_sugerido__user'
    )

    perfis = UsuarioPerfil.objects.filter(ativo=True).select_related('user').order_by(
        'user__first_name', 'user__last_name'
    )
    lista_perfis = [{'id': p.id, 'nome': p.user.get_full_name() or p.user.username} for p in perfis]

    dados = [{
        'id': item.id,
        'nome_extraido': item.nome_extraido,
        'cargo_extraido': item.cargo_extraido,
        'valor_liquido': str(item.valor_liquido) if item.valor_liquido is not None else None,
        'mes': item.mes, 'ano': item.ano,
        'competencia': item.competencia_label,
        'status': item.status,
        'perfil_sugerido_id': item.perfil_sugerido_id,
        'perfil_sugerido_nome': item.perfil_sugerido.user.get_full_name() if item.perfil_sugerido else None,
        'score_match': str(item.score_match) if item.score_match is not None else None,
    } for item in itens]

    resumo = {
        'confirmados': lote.contracheques.filter(status=Contracheque.Status.CONFIRMADO).count(),
        'pendentes': lote.contracheques.filter(status=Contracheque.Status.PENDENTE).count(),
        'sem_correspondencia': lote.contracheques.filter(status=Contracheque.Status.SEM_CORRESPONDENCIA).count(),
        'total': lote.contracheques.count(),
    }

    return JsonResponse({'itens': dados, 'perfis': lista_perfis, 'resumo': resumo, 'lote_status': lote.status})


@login_required
@require_POST
def rh_contracheque_confirmar(request):
    """
    Confirma manualmente o vínculo de UM contracheque a um UsuarioPerfil
    (aceitar a sugestão automática ou escolher outro colaborador). Se já
    existir um contracheque CONFIRMADO para esse colaborador na mesma
    competência, retorna 409 pedindo confirmação de sobrescrita
    (`force=1` na segunda chamada).
    """
    if not _somente_rh(request.user):
        return HttpResponseForbidden('Acesso restrito ao RH.')

    contracheque = get_object_or_404(Contracheque, pk=request.POST.get('contracheque_id'))
    perfil = get_object_or_404(UsuarioPerfil, pk=request.POST.get('perfil_id'))
    forcar = request.POST.get('force') == '1'

    conflito = Contracheque.objects.filter(
        perfil=perfil, mes=contracheque.mes, ano=contracheque.ano,
        status=Contracheque.Status.CONFIRMADO,
    ).exclude(pk=contracheque.pk).first()

    if conflito and not forcar:
        return JsonResponse({
            'conflito': True,
            'mensagem': f'{perfil.user.get_full_name()} já possui um contracheque confirmado para '
                        f'{contracheque.competencia_label}. Deseja substituir pelo novo arquivo?',
        }, status=409)

    if conflito and forcar:
        conflito.arquivo.delete(save=False)
        conflito.delete()

    contracheque.perfil = perfil
    contracheque.status = Contracheque.Status.CONFIRMADO
    contracheque.confirmado_por = request.user
    contracheque.confirmado_em = timezone.now()
    contracheque.save()

    return JsonResponse({'ok': True, 'contracheque_id': contracheque.id})


@login_required
@require_POST
def rh_contracheque_ignorar(request):
    """Marca um contracheque pendente como 'sem correspondência' definitivo."""
    if not _somente_rh(request.user):
        return HttpResponseForbidden('Acesso restrito ao RH.')

    contracheque = get_object_or_404(Contracheque, pk=request.POST.get('contracheque_id'))
    contracheque.perfil = None
    contracheque.status = Contracheque.Status.SEM_CORRESPONDENCIA
    contracheque.save(update_fields=['perfil', 'status'])
    return JsonResponse({'ok': True})


# ═══════════════════════════════════════════════════════════════════════
#  COLABORADOR — visualização e download mês a mês
# ═══════════════════════════════════════════════════════════════════════
@login_required
def colaborador_contracheques(request):
    """
    Página do colaborador: lista os contracheques confirmados do próprio
    usuário logado, agrupados por ano — mesmo padrão visual do dashboard
    de RH.
    """
    perfil = get_object_or_404(UsuarioPerfil, user=request.user)

    contracheques = Contracheque.objects.filter(
        perfil=perfil, status=Contracheque.Status.CONFIRMADO,
    ).order_by('-ano', '-mes')

    anos = {}
    for c in contracheques:
        anos.setdefault(c.ano, []).append(c)
    anos_ordenados = [{'ano': ano, 'itens': itens} for ano, itens in sorted(anos.items(), reverse=True)]

    contexto = {
        'perfil': perfil,
        'anos_ordenados': anos_ordenados,
        'total_contracheques': contracheques.count(),
        'meses_nome': MESES_NUM_PARA_NOME,
    }
    return render(request, 'colaborador_contracheques.html', contexto)


@login_required
def colaborador_contracheque_arquivo(request, contracheque_id):
    """
    Serve o PDF de um contracheque para visualização inline ou download
    (`?download=1`). Só o próprio colaborador (dono do perfil) ou alguém
    do RH pode acessar.
    """
    contracheque = get_object_or_404(Contracheque, pk=contracheque_id, status=Contracheque.Status.CONFIRMADO)

    dono = contracheque.perfil_id and contracheque.perfil.user_id == request.user.id
    if not dono and not _somente_rh(request.user):
        return HttpResponseForbidden('Você não tem permissão para acessar este contracheque.')

    if not contracheque.arquivo:
        raise Http404('Arquivo não encontrado.')

    baixar = request.GET.get('download') == '1'
    nome = f'contracheque_{contracheque.mes:02d}_{contracheque.ano}.pdf'
    return FileResponse(
        contracheque.arquivo.open('rb'),
        as_attachment=baixar,
        filename=nome,
        content_type='application/pdf',
    )