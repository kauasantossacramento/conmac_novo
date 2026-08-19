from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

from django.utils.text import slugify
# despesas/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# atividades/models.py (ou onde estiver seu model)


from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

# models.py — adicionar os dois campos a UsuarioPerfil

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class UsuarioPerfil(models.Model):

    LOCAL_CHOICES = [
        ('nucleo',  'Núcleo'),
        ('externo', 'Externo'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    cpf  = models.CharField("CPF", max_length=14, unique=True, blank=True, null=True)

    # --- FINANCEIRO ---
    salario_base  = models.DecimalField("Salário Base", max_digits=10, decimal_places=2, default=0.00)
    irrf_manual   = models.DecimalField("IRRF Manual",  max_digits=10, decimal_places=2, null=True, blank=True)
    data_admissao = models.DateField("Data de Admissão", null=True, blank=True)
    ativo         = models.BooleanField("Funcionário Ativo", default=True)

    # --- NOVOS CAMPOS ---
    cargo         = models.CharField("Cargo", max_length=120, blank=True, null=True)
    local_trabalho = models.CharField("Local de Trabalho", max_length=20,
                                      choices=LOCAL_CHOICES, blank=True, null=True)

    # --- PERMISSÕES ---
    acesso_fechamento = models.BooleanField("Acesso Fechamento", default=False)
    acesso_siga       = models.BooleanField("Acesso SIGA",       default=False)
    acesso_siope      = models.BooleanField("Acesso SIOPE",      default=False)
    acesso_siops      = models.BooleanField("Acesso SIOPS",      default=False)
    acesso_siconf     = models.BooleanField("Acesso SICONFI",    default=False)
    acesso_etcm       = models.BooleanField("Acesso E-TCM",      default=False)

    PERFIL_PC_CHOICES = [
        ('JURIDICO', 'Jurídico'),
        ('ANALISE',  'Análise'),
    ]
    acesso_prestacao_contas = models.BooleanField(
        "Acesso Prestação de Contas", default=False
    )
    perfil_pc = models.CharField(
        "Perfil no módulo PC",
        max_length=20,
        choices=PERFIL_PC_CHOICES,
        blank=True, null=True,
    )

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def inss_estimado(self):
        return (self.salario_base * Decimal('0.11')).quantize(Decimal('0.01'))

    @property
    def irrf_estimado(self):
        if self.irrf_manual is not None:
            return self.irrf_manual

        desc_simplificado = Decimal('607.20')
        base_calculo = self.salario_base - max(self.inss_estimado, desc_simplificado)

        if base_calculo <= Decimal('2428.80'):
            ir_bruto = Decimal('0.00')
        elif base_calculo <= Decimal('2826.65'):
            ir_bruto = (base_calculo * Decimal('0.075')) - Decimal('182.16')
        elif base_calculo <= Decimal('3751.05'):
            ir_bruto = (base_calculo * Decimal('0.15')) - Decimal('394.16')
        elif base_calculo <= Decimal('4664.68'):
            ir_bruto = (base_calculo * Decimal('0.225')) - Decimal('675.49')
        else:
            ir_bruto = (base_calculo * Decimal('0.275')) - Decimal('908.73')

        if self.salario_base <= Decimal('5000.00'):
            return Decimal('0.00')

        if Decimal('5000.01') <= self.salario_base <= Decimal('7350.00'):
            reducao = Decimal('978.62') - (Decimal('0.133145') * self.salario_base)
            ir_bruto -= reducao

        return max(Decimal('0.00'), ir_bruto).quantize(Decimal('0.01'))

    @property
    def salario_liquido(self):
        return (self.salario_base - self.inss_estimado - self.irrf_estimado).quantize(Decimal('0.01'))

    @property
    def custo_fgts(self):
        return (self.salario_base * Decimal('0.08')).quantize(Decimal('0.01'))


class CentroDeCusto(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Centro de Custo"
        verbose_name_plural = "Centros de Custo"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class AssociacaoCentroCusto(models.Model):
    """Liga colaborador a um Centro de Custo (definido pelo Admin)."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="associacoes_cc")
    centro = models.ForeignKey(CentroDeCusto, on_delete=models.CASCADE, related_name="associados")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "centro")
        verbose_name = "Associação a Centro de Custo"
        verbose_name_plural = "Associações a Centros de Custo"

    def __str__(self):
        return f"{self.usuario} → {self.centro}"


class Despesa(models.Model):
    class Status(models.TextChoices):
        PENDENTE        = "PENDENTE", "Pendente (não analisada)"
        PENDENTE_PAGTO  = "PENDENTE_PAGTO", "Pendente de pagamento"   # NOVO
        APROVADA        = "APROVADA", "Aprovada (paga)"
        REPROVADA       = "REPROVADA", "Reprovada"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="despesas")
    centro = models.ForeignKey(CentroDeCusto, on_delete=models.PROTECT, related_name="despesas")
    titulo = models.CharField(max_length=160)
    data_fato = models.DateField(help_text="Data do gasto (nota/comprovante)")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.TextField(blank=True)
    comprovante = models.FileField(upload_to="receipts/%Y/%m/", blank=True, null=True)
    comprovante_pagamento = models.FileField(upload_to="reembolsos/%Y/%m/", blank=True, null=True)
    pago_em = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)   # mês de CADASTRO (regra do Admin)
    atualizado_em = models.DateTimeField(auto_now=True)
    observacao_admin = models.TextField(blank=True)

        # NOVOS CAMPOS
    foi_avaliada = models.BooleanField(default=False)          # vira True na 1ª mudança feita pelo admin
    primeira_analise_em = models.DateTimeField(null=True, blank=True)
    edit_count = models.PositiveIntegerField(default=0)        # conta edições do colaborador APÓS a 1ª análise

        # helper opcional
    def atingiu_limite_edicao(self, max_ed=2):
        return self.foi_avaliada and self.edit_count >= max_ed

    def status_label_para_usuario(self, is_staff: bool) -> str:
        if is_staff:
            return self.get_status_display()
        # colaborador enxerga ambos como "Pendente"
        if self.status in (self.Status.PENDENTE, self.Status.PENDENTE_PAGTO):
            return "Pendente"
        return self.get_status_display()

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.titulo} - {self.valor} ({self.centro})"

    @property
    def mes_ano_cadastro(self):
        return self.criado_em.strftime("%m/%Y")


class LoteReembolso(models.Model):
    """
    Reembolso criado pelo Admin POR CENTRO DE CUSTO (pode agrupar várias despesas).
    """
    centro = models.ForeignKey(CentroDeCusto, on_delete=models.PROTECT, related_name="lotes_reembolso")
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name="lotes_criados")
    periodo_ref = models.CharField(max_length=7, help_text="Formato MM/AAAA (relatório/consulta)")
    despesas = models.ManyToManyField(Despesa, blank=True, related_name="lotes")

    comprovante_reembolso = models.FileField(upload_to="reembolsos/%Y/%m/", blank=True, null=True)
    pago_em = models.DateField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lote de Reembolso"
        verbose_name_plural = "Lotes de Reembolso"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"Lote {self.pk} - {self.centro} - {self.periodo_ref}"

class ChecklistItem(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="checklist")
    texto = models.CharField(max_length=255)
    criado_em = models.DateTimeField(auto_now_add=True)
    concluido = models.BooleanField(default=False)
    concluido_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["concluido", "-criado_em"]

    def __str__(self):
        return f"{self.texto} ({'ok' if self.concluido else 'pendente'})"


#COMEÇA AQUI O SISTEMA DE ATIVIDADES
# despesas/models.py
# ─────────────────────────────────────────────────────────────
# ARQUIVO ÚNICO — substitui completamente o models.py anterior.
# Não há imports duplicados nem classes duplicadas.
# app_label implícito = "despesas" (nome do diretório/app no INSTALLED_APPS)
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator

try:
    from push_notifications.models import WebPushDevice as _WebPushDevice
except ImportError:
    _WebPushDevice = None

AUTH_USER = settings.AUTH_USER_MODEL


# ══════════════════════════════════════════════
# CLIENTE
# ══════════════════════════════════════════════

class Cliente(models.Model):
    nome           = models.CharField(max_length=200)
    brasao         = models.ImageField(upload_to="brasoes/", blank=True, null=True)
    codigo_externo = models.CharField(max_length=100, blank=True, null=True)
    ativo          = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Cliente"
        verbose_name_plural = "Clientes"
        ordering            = ["nome"]

    def __str__(self):
        return self.nome


class AssociacaoUsuarioCliente(models.Model):
    usuario   = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE,
                                  related_name="associacoes_clientes")
    cliente   = models.ForeignKey(Cliente, on_delete=models.CASCADE,
                                  related_name="associacoes_usuarios")
    ativo     = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Associação Usuário-Cliente"
        verbose_name_plural = "Associações Usuário-Cliente"
        unique_together     = ("usuario", "cliente")


# ══════════════════════════════════════════════
# CHOICES
# ══════════════════════════════════════════════

class NivelChoices(models.TextChoices):
    FECHAMENTO = "FECHAMENTO", "FECHAMENTO"
    SIGA       = "SIGA",       "SIGA"
    SIOPS      = "SIOPS",      "SIOPS"
    SIOPE      = "SIOPE",      "SIOPE"
    SICONF     = "SICONF",     "SICONFI"
    E_TCM      = "E-TCM",      "E-TCM"


class ModuloChoices(models.TextChoices):
    """Sub-módulo das etapas de FECHAMENTO."""
    CONTABIL   = "CONTABIL",   "Contábil"
    FINANCEIRO = "FINANCEIRO", "Financeiro"


# ══════════════════════════════════════════════
# ETAPA
# ══════════════════════════════════════════════

class Etapa(models.Model):
    """
    Etapa genérica por nível.

    Campo `modulo` — exclusivo para etapas de FECHAMENTO:
      CONTABIL   → habilita INÍCIO de SIGA, SIOPE, SIOPS, SICONF
      FINANCEIRO → habilita INÍCIO do E-TCM
    Para todos os outros níveis, deixar em branco.

    Flags `obrigatoria_para_fila_*` — marcam esta etapa como
    pré-requisito de CONCLUSÃO do módulo correspondente.
    """

    nivel   = models.CharField(max_length=30, choices=NivelChoices.choices,
                                db_index=True)
    modulo  = models.CharField(
        max_length=20,
        choices=ModuloChoices.choices,
        blank=True,
        default="",
        verbose_name="Módulo (somente FECHAMENTO)",
        help_text=(
            "Preencher apenas para etapas do nível FECHAMENTO. "
            "CONTABIL libera SIGA/SIOPE/SIOPS/SICONF para iniciar. "
            "FINANCEIRO libera E-TCM para iniciar."
        ),
    )
    nome      = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    ordem     = models.PositiveIntegerField(default=0,
                help_text="Ordem de apresentação na tela (menor primeiro).")

    obrigatoria_para_fila_siga   = models.BooleanField(default=False)
    obrigatoria_para_fila_etcm   = models.BooleanField(default=False)
    obrigatoria_para_fila_siope  = models.BooleanField(default=False)
    obrigatoria_para_fila_siops  = models.BooleanField(default=False)
    obrigatoria_para_fila_siconf = models.BooleanField(default=False)

    exige_anexo = models.BooleanField(
        default=False,
        verbose_name="Exige Anexo (PDF/Img)",
        help_text="O usuário deve anexar um arquivo para concluir esta etapa.",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Etapa"
        verbose_name_plural = "Etapas"
        ordering            = ["nivel", "ordem", "nome"]
        unique_together     = ("nivel", "nome")

    def __str__(self):
        mod = f" [{self.get_modulo_display()}]" if self.modulo else ""
        return f"{self.get_nivel_display()}{mod} — {self.nome}"


# ══════════════════════════════════════════════
# REGISTRO DE ETAPA
# ══════════════════════════════════════════════

class EtapaRegistroStatus(models.TextChoices):
    NAO_INICIADO = "NAO_INICIADO", "Não iniciado"
    EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
    CONCLUIDO    = "CONCLUIDO",    "Concluído"
    PENDENTE     = "PENDENTE",     "Pendente"


class EtapaRegistro(models.Model):
    cliente              = models.ForeignKey(Cliente, on_delete=models.CASCADE,
                                             related_name="registros_etapas")
    etapa                = models.ForeignKey(Etapa, on_delete=models.PROTECT,
                                             related_name="registros")
    ano                  = models.PositiveIntegerField()
    mes                  = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    status               = models.CharField(max_length=30,
                                            choices=EtapaRegistroStatus.choices,
                                            default=EtapaRegistroStatus.NAO_INICIADO)
    observacao           = models.TextField(blank=True)
    ultima_alteracao_por = models.ForeignKey(AUTH_USER, on_delete=models.SET_NULL,
                                             null=True, blank=True)
    arquivo_anexo        = models.FileField(
        upload_to="comprovantes_etapas/%Y/%m/",
        null=True, blank=True,
        verbose_name="Comprovante",
    )
    criado_em    = models.DateTimeField(auto_now_add=True)
    modificado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Registro de Etapa"
        verbose_name_plural = "Registros de Etapas"
        unique_together     = ("cliente", "etapa", "ano", "mes")
        ordering            = ["cliente", "-ano", "-mes", "etapa__ordem"]

    def __str__(self):
        return f"{self.cliente} — {self.etapa.nome} ({self.ano}/{self.mes})"

    def to_dict(self):
        return {
            "cliente_id": self.cliente_id,
            "etapa_id":   self.etapa_id,
            "ano":        self.ano,
            "mes":        self.mes,
            "status":     self.status,
            "observacao": self.observacao,
        }


class EtapaHistorico(models.Model):
    registro            = models.ForeignKey(EtapaRegistro, on_delete=models.CASCADE,
                                            related_name="historico")
    alterado_por        = models.ForeignKey(AUTH_USER, on_delete=models.SET_NULL,
                                            null=True, blank=True)
    status_anterior     = models.CharField(max_length=30, choices=EtapaRegistroStatus.choices)
    status_novo         = models.CharField(max_length=30, choices=EtapaRegistroStatus.choices)
    observacao_anterior = models.TextField(blank=True)
    observacao_nova     = models.TextField(blank=True)
    criado_em           = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Histórico de Etapa"
        verbose_name_plural = "Históricos de Etapas"
        ordering            = ["-criado_em"]


# ══════════════════════════════════════════════
# CONFIGURAÇÃO DE NÍVEL  (bloqueio / liberação)
# ══════════════════════════════════════════════

class CompetenciaLiberada(models.Model):
    """
    Override pontual por admin: libera um cliente/nível em uma
    competência específica (ano+mês), sem afetar outros clientes.
    Sobrepõe qualquer bloqueio por periodicidade ou dependência.
    """
    cliente      = models.ForeignKey(Cliente, on_delete=models.CASCADE,
                                     related_name="competencias_liberadas_set")
    ano          = models.PositiveIntegerField()
    mes          = models.PositiveIntegerField()
    nivel        = models.CharField(max_length=30, choices=NivelChoices.choices)
    liberado_por = models.ForeignKey(AUTH_USER, on_delete=models.SET_NULL,
                                     null=True, related_name="competencias_liberadas")
    criado_em    = models.DateTimeField(auto_now_add=True)
    motivo       = models.TextField(blank=True)

    class Meta:
        unique_together     = ("cliente", "ano", "mes", "nivel")
        verbose_name        = "Competência Liberada"
        verbose_name_plural = "Competências Liberadas"
        ordering            = ["-ano", "-mes"]

    def __str__(self):
        return f"{self.cliente} | {self.nivel} | {self.mes:02d}/{self.ano}"


class ConfiguracaoNivel(models.Model):
    """
    Configuração global de bloqueio/liberação por nível.

    Hierarquia (mais específica → mais ampla):
      1. CompetenciaLiberada — cliente + ano + mês + nível
      2. clientes_liberados  — cliente específico, qualquer competência
      3. liberar_preenchimento sem clientes — liberação global
    """
    nivel                 = models.CharField(max_length=30,
                                             choices=NivelChoices.choices,
                                             unique=True)
    liberar_preenchimento = models.BooleanField(default=False)

    # ─── CAMPO JÁ EXISTENTE NO BANCO — não recriar em migration ───
    clientes_liberados = models.ManyToManyField(
        Cliente,
        blank=True,
        related_name="niveis_liberados",
        verbose_name="Clientes com liberação específica",
    )

    class Meta:
        verbose_name        = "Configuração de Nível"
        verbose_name_plural = "Configurações de Nível"

    def __str__(self):
        estado = "Liberado" if self.liberar_preenchimento else "Bloqueado"
        return f"{self.nivel} — {estado}"

    def esta_liberado_para_cliente(self, cliente) -> bool:
        if not self.liberar_preenchimento:
            return False
        if not self.clientes_liberados.exists():
            return True
        return self.clientes_liberados.filter(pk=cliente.pk).exists()

    @staticmethod
    def esta_liberado_para_competencia(cliente, ano, mes, nivel) -> bool:
        return CompetenciaLiberada.objects.filter(
            cliente=cliente, ano=ano, mes=mes, nivel=nivel
        ).exists()


# ══════════════════════════════════════════════
# FILA AUTOMÁTICA
# ══════════════════════════════════════════════

class FilaAutomatica(models.Model):
    nome          = models.CharField(max_length=80,
                                     help_text="Ex.: fila_siga, fila_etcm")
    cliente       = models.ForeignKey(Cliente, on_delete=models.CASCADE,
                                      related_name="filas")
    nivel         = models.CharField(max_length=30, choices=NivelChoices.choices)
    data_entrada  = models.DateTimeField(default=timezone.now)
    motivo        = models.CharField(max_length=255, blank=True)
    ordem_entrada = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Ordem sequencial de entrada na fila (1 = primeiro)",
    )

    class Meta:
        verbose_name        = "Fila automática"
        verbose_name_plural = "Filas automáticas"
        ordering            = ["data_entrada"]
        unique_together     = ("nome", "cliente", "nivel")

    def __str__(self):
        return f"{self.nome} - {self.cliente} - {self.data_entrada.date()}"


# ══════════════════════════════════════════════
# NOTIFICAÇÕES
# ══════════════════════════════════════════════

class NotificacaoConfig(models.Model):
    chave      = models.CharField(max_length=100, unique=True)
    descricao  = models.CharField(max_length=255)
    habilitado = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Configuração de Notificação"
        verbose_name_plural = "Configurações de Notificações"

    def __str__(self):
        return f"{self.descricao} ({'Ativo' if self.habilitado else 'Inativo'})"


# UserDevice e NotificationMessage dependem de push_notifications instalado
if _WebPushDevice is not None:
    class UserDevice(models.Model):
        usuario   = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE)
        device    = models.OneToOneField(_WebPushDevice, on_delete=models.CASCADE)
        criado_em = models.DateTimeField(auto_now_add=True)

        class Meta:
            app_label = "despesas"

        def __str__(self):
            return f"{self.usuario} — dispositivo {self.device.name}"

    class NotificationMessage(models.Model):
        title      = models.CharField(max_length=200)
        body       = models.TextField()
        created_at = models.DateTimeField(auto_now_add=True)
        sent_at    = models.DateTimeField(null=True, blank=True)
        sent       = models.BooleanField(default=False)

        class Meta:
            app_label = "despesas"

        def __str__(self):
            return f"{self.title} ({'Enviado' if self.sent else 'Pendente'})"

        def send_to_all(self):
            payload = {"title": self.title, "body": self.body,
                       "icon": "/static/img/icon-192.png", "url": "/"}
            for dev in _WebPushDevice.objects.filter(active=True):
                try:
                    dev.send_message(payload)
                except Exception as e:
                    print("Erro ao enviar para device:", dev.id, e)
            from django.utils.timezone import now
            self.sent    = True
            self.sent_at = now()
            self.save()


class NotificacaoPush(models.Model):
    """Fila de notificações push por usuário-alvo."""

    usuario_alvo = models.ForeignKey(AUTH_USER, on_delete=models.SET_NULL, null=True, blank=True, related_name="notificacoes_push")
    titulo    = models.CharField(max_length=200)
    mensagem  = models.TextField()
    link      = models.CharField(max_length=500, blank=True)
    enviado   = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"[{'✓' if self.enviado else '…'}] {self.titulo} → {self.usuario_alvo}"


# ══════════════════════════════════════════════
# REABERTURA
# ══════════════════════════════════════════════

class SolicitacaoReabertura(models.Model):
    STATUS_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("APROVADO", "Aprovado"),
        ("NEGADO",   "Negado"),
    ]

    registro         = models.ForeignKey("EtapaRegistro", on_delete=models.CASCADE,
                                         related_name="solicitacoes")
    solicitante      = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE,
                                         related_name="solicitacoes_reabertura")
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES,
                                        default="PENDENTE")
    analisado_por    = models.ForeignKey(AUTH_USER, on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         related_name="analises_realizadas")
    data_analise     = models.DateTimeField(null=True, blank=True)
    motivo_recusa    = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-data_solicitacao"]

    def __str__(self):
        return f"{self.registro} - {self.get_status_display()}"





#conmacfest2025


# eventos/models.py
from django.db import models

class Rsvp(models.Model):
    nome = models.CharField("Nome completo", max_length=200)
    vai_ir = models.BooleanField("Vai comparecer?", default=False)  # True = sim, False = não
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} — {'SIM' if self.vai_ir else 'NÃO'}"


#---------------------


from django.db import models
from django.conf import settings

class FCMToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:20]}..."



# despesas/models.py
from django.db import models
from django.conf import settings

# ... seu model FCMToken já existe aqui ...

# --- COLOCAR NO FINAL DO ARQUIVO models.py ---

from django.db.models.signals import post_save
from django.dispatch import receiver
# Importação feita aqui para evitar erro de ciclo (Circular Import)
from . import utils

@receiver(post_save, sender=NotificacaoPush)
def disparar_notificacao_apos_salvar(sender, instance, created, **kwargs):
    """
    Gatilho automático: Assim que o registro é criado no banco,
    chamamos o utils para tentar enviar ao Firebase.
    """
    # Só dispara se acabou de ser criado (created=True) e ainda não foi enviado
    if created and not instance.enviado:
        print(f"🔔 [SIGNAL] Nova notificação detectada (ID: {instance.id}). Iniciando envio...")
        try:
            # Chama a função que criamos no passo anterior
            utils.tentar_enviar_notificacao_existente(instance.id)
        except Exception as e:
            print(f"❌ [ERRO SIGNAL] Falha ao disparar envio: {e}")



# despesas/models.py
from django.db import models
from django.contrib.auth.models import User


from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Prefeitura(models.Model):
    """
    Controla as entidades que acessarão o formulário.
    """
    nome = models.CharField("Nome da Prefeitura", max_length=200, help_text="Ex: Prefeitura Municipal de Salvador")
    slug = models.SlugField("Identificador na URL", unique=True, help_text="Identificador único para o link (ex: salvador)")
    brasao = models.ImageField("Brasão/Logo", upload_to='brasoes/', blank=True, null=True)

    # Personalização da Saudação
    nome_responsavel_recepcao = models.CharField("Nome do Responsável na Saudação", max_length=150,
                                                 help_text="Nome que aparecerá no 'Olá, [Nome]'. Ex: Conmac Gestão")

    # Controles de Acesso
    ativo = models.BooleanField("Formulário Ativo?", default=True,
                                help_text="Desmarque para bloquear o acesso a este formulário imediatamente.")

    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Prefeitura / Entidade"
        verbose_name_plural = "Prefeituras / Entidades"


class QuestionarioSIOPS(models.Model):
    """
    Armazena as respostas do formulário SIOPS baseadas no PDF.
    """
    prefeitura = models.OneToOneField(Prefeitura, on_delete=models.CASCADE, related_name='questionario',
                                      verbose_name="Prefeitura Vinculada")
    data_envio = models.DateTimeField("Data do Envio", auto_now_add=True)

    # =========================================================================
    # BLOCO 1: GESTORES (Baseado nas páginas 1 e 2 do PDF)
    # =========================================================================
    # Dados do Prefeito [cite: 9]
    prefeito_nome = models.CharField("Nome do Prefeito", max_length=200)
    prefeito_endereco = models.CharField("Endereço do Prefeito", max_length=255)
    prefeito_telefone = models.CharField("Telefone do Prefeito", max_length=20)
    prefeito_email = models.EmailField("E-mail do Prefeito")

    # Dados do Secretário de Saúde [cite: 11]
    secretario_nome = models.CharField("Nome do Secretário de Saúde", max_length=200)
    secretario_endereco = models.CharField("Endereço do Secretário", max_length=255)
    secretario_telefone = models.CharField("Telefone do Secretário", max_length=20)
    secretario_email = models.EmailField("E-mail do Secretário")

    # =========================================================================
    # BLOCO 2: CONSELHO DE SAÚDE - DADOS GERAIS (Páginas 2 e 3)
    # =========================================================================
    conselho_data_criacao = models.DateField("Data de Criação do Conselho [cite: 16]", null=True, blank=True)
    conselho_instrumento = models.CharField("Instrumento de Criação", max_length=200, help_text="Lei, Decreto, Portaria ou Outro [cite: 17]")
    conselho_endereco = models.CharField("Endereço do Conselho", max_length=255)
    conselho_periodicidade = models.CharField("Periodicidade das Reuniões", max_length=100)

    # Presidente do Conselho
    presidente_nome = models.CharField("Nome do Presidente do Conselho [cite: 23]", max_length=200)

    SEGMENTOS_CHOICES = [
        ('GOV', 'Governo'),
        ('USU', 'Usuário'),
        ('TRAB', 'Trabalhador de Saúde'),
        ('PRES', 'Prestador de Serviço'),
    ]
    presidente_segmento = models.CharField("Segmento do Presidente [cite: 24, 43]", max_length=5, choices=SEGMENTOS_CHOICES)
    presidente_endereco = models.CharField("Endereço do Presidente", max_length=255)
    presidente_email = models.EmailField("E-mail do Presidente")
    presidente_telefone = models.CharField("Telefone do Presidente", max_length=20)

    # Responsável pelas informações do Conselho [cite: 32]
    responsavel_info_nome = models.CharField("Responsável pelas Informações", max_length=200)
    responsavel_info_email = models.EmailField("E-mail do Responsável Info")
    responsavel_info_telefone = models.CharField("Telefone do Responsável Info", max_length=20)

    # =========================================================================
    # BLOCO 3: ATUAÇÃO DO CONSELHO (Perguntas Sim/Não - Páginas 4, 5 e 6)
    # =========================================================================
    # [cite: 49, 52, 55, 58, 61, 66, 71, 77]
    fiscaliza_fundo = models.BooleanField("Acompanha e fiscaliza o Fundo em caráter permanente?", default=False)
    parecer_plano = models.BooleanField("Emite Parecer ao Plano de Saúde?", default=False)
    parecer_ppa = models.BooleanField("Emite Parecer à Proposta de PPA?", default=False)
    delibera_programacao = models.BooleanField("Delibera a Programação Anual?", default=False)
    delibera_loa = models.BooleanField("Delibera sobre a Proposta da LOA?", default=False)
    delibera_relatorio_gestao = models.BooleanField("Delibera o Relatório de Gestão?", default=False)
    parecer_relatorio_gestao = models.BooleanField("Emite Parecer no Relatório de Gestão (Anual)?", default=False)
    parecer_contas_quadrimestre = models.BooleanField("Emite Parecer nas contas de cada quadrimestre?", default=False)

    # =========================================================================
    # BLOCO 4: FUNDO DE SAÚDE (Páginas 5 e 6)
    # =========================================================================
    fundo_cnpj = models.CharField("CNPJ Utilizado [cite: 99]", max_length=20)

    TIPO_GESTAO_CHOICES = [
        ('PREF', 'Prefeitura'),
        ('FUNDO', 'Fundo de Saúde'),
        ('FUNDACAO', 'Fundação'),
        ('SEC', 'Sec. de Saúde'),
        ('OUTRA_SEC', 'Outra Secretaria'),
        ('OUTRO', 'Outro'),
    ]
    fundo_tipo_gestao = models.CharField("Gestão do CNPJ [cite: 88]", max_length=15, choices=TIPO_GESTAO_CHOICES)
    fundo_endereco = models.CharField("Endereço do Fundo", max_length=255)

    fundo_responsavel_nome = models.CharField("Responsável pelo Fundo", max_length=200)
    fundo_responsavel_email = models.EmailField("E-mail Responsável Fundo")
    fundo_responsavel_telefone = models.CharField("Telefone Responsável Fundo", max_length=20)

    # Informações Bancárias [cite: 106]
    banco_nome = models.CharField("Banco", max_length=100)
    banco_agencia = models.CharField("Agência", max_length=20)
    banco_conta = models.CharField("Conta", max_length=20)

    # Perguntas Adicionais do Fundo (Página 6 - Tabela "Demais Perguntas") [cite: 111]
    fundo_pleno_funcionamento = models.BooleanField("O Fundo está em pleno funcionamento?", default=True)
    fundo_nome_gestor = models.CharField("Nome do Gestor do Fundo", max_length=200)

    ADMIN_FUNDO_CHOICES = [
        ('SAUDE', 'Secretaria de Saúde'),
        ('FAZENDA', 'Secretaria da Fazenda'),
        ('OUTROS', 'Outros'),
    ]
    fundo_local_administracao = models.CharField("Onde está a administração do Fundo?", max_length=20, choices=ADMIN_FUNDO_CHOICES)

    # Recursos Financeiros (Com Percentual) [cite: 111]
    recursos_proprios_aplicados = models.BooleanField("Recursos próprios são aplicados através do FUNDO?", default=False)
    recursos_proprios_percentual = models.DecimalField("Percentual Recursos Próprios (%)", max_digits=5, decimal_places=2, null=True, blank=True)

    recursos_sus_aplicados = models.BooleanField("Recursos do SUS são aplicados através do Fundo?", default=False)
    recursos_sus_percentual = models.DecimalField("Percentual Recursos SUS (%)", max_digits=5, decimal_places=2, null=True, blank=True)

    # =========================================================================
    # BLOCO 5: CONSÓRCIO DE SAÚDE (Página 7)
    # =========================================================================
    # [cite: 143]
    possui_consorcio = models.BooleanField("O município participa de Consórcio de Saúde?", default=False)
    consorcio_nome = models.CharField("Nome do Consórcio", max_length=200, blank=True, null=True)
    consorcio_cnpj = models.CharField("CNPJ do Consórcio", max_length=20, blank=True, null=True)
    consorcio_responsavel = models.CharField("Responsável do Consórcio", max_length=200, blank=True, null=True)
    consorcio_email = models.EmailField("E-mail do Consórcio", blank=True, null=True)
    consorcio_telefone = models.CharField("Telefone do Consórcio", max_length=20, blank=True, null=True)

    def __str__(self):
        return f"Respostas SIOPS - {self.prefeitura.nome}"

    class Meta:
        verbose_name = "Questionário Respondido"
        verbose_name_plural = "Questionários Respondidos"

'''
#indicando liberação ou nao para determinado nível:
class ConfiguracaoNivel(models.Model):
    nivel = models.CharField(max_length=30, choices=NivelChoices.choices, unique=True)
    liberar_preenchimento = models.BooleanField(default=False, verbose_name="Liberar para preenchimento?")

    def __str__(self):
        return f"{self.get_nivel_display()} - {'Liberado' if self.liberar_preenchimento else 'Bloqueado'}"
'''

# ============================================================================
# MODELS.PY - ADICIONAR AO SEU ARQUIVO EXISTENTE
# ============================================================================

from django.db import models

from django.db import models
from django.contrib.auth.models import User
# Mantenha suas importações atuais do app despesas aqui...

# --- NOVOS MODELS PARA O MÓDULO DE CONTRATOS ---

class Contrato(models.Model):
    """
    Armazena dados sincronizados da API de Contratos do Omie.
    Documentação base: contrato_api.pdf
    """
    # Identificadores Omie
    omie_cod_ctr = models.BigIntegerField(unique=True, verbose_name="Cód. Contrato Omie (nCodCtr)")
    omie_num_ctr = models.CharField(max_length=60, verbose_name="Número do Contrato")

    # Dados do Cliente (Enriquecidos com a Opção A)
    cliente_id_omie = models.BigIntegerField(verbose_name="ID Cliente Omie (nCodCli)")
    cliente_nome = models.CharField(max_length=255, verbose_name="Nome do Cliente", blank=True, null=True)

    # Valores e Vigência
    valor_mensal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Mensal (nValTotMes)")
    data_vigencia_inicial = models.DateField(null=True, blank=True)
    data_vigencia_final = models.DateField(null=True, blank=True)

    # Status (cCodSit: '10' = Ativo, etc - conforme doc)
    status_omie = models.CharField(max_length=20, default='Desconhecido')
    TIPO_ENTIDADE_CHOICES = [

         ('municipio', 'Prefeitura'),
         ('camara',    'Câmara Municipal'),
     ]

    municipio = models.CharField(
         "Município",
         max_length=120, blank=True, null=True,
         help_text="Cidade do cliente. Usado para agrupar NFS-e no relatório.",
     )

    tipo_entidade = models.CharField(
         "Tipo de Entidade",
         max_length=20,
         choices=TIPO_ENTIDADE_CHOICES,
         blank=True, null=True,
         help_text="Município = Prefeitura/Órgão municipal. Câmara = Câmara Municipal.",
     )

    # Controle Interno
    atualizado_em = models.DateTimeField(auto_now=True)

    municipio = models.CharField(
       "Município",
        max_length=120,
        blank=True,
        null=True,
        help_text="Município do cliente/contrato. Usado para agrupar NFS-e no relatório."
    )

    # ── Cache local dos dados de emissão (independente da Omie) ──────────
    # Preenchido/atualizado toda vez que o contrato é editado com
    # "Sincronizar com Omie" ligado. Permite emitir via SAATRI Direto sem
    # depender de uma consulta ao vivo na Omie a cada nota — evita o
    # throttling "REDUNDANT" (65s de espera por chamada) que a Omie aplica
    # quando o lote é grande. `valor_mensal` acima já serve como o valor de
    # emissão; os campos abaixo completam o que falta.
    descricao_servico = models.TextField(
        "Descrição do Serviço (cache local)", blank=True, default="",
        help_text="Cópia local da descrição usada na nota. Atualizada junto com a Omie "
                   "quando 'Sincronizar com Omie' está ligado, ou só localmente quando desligado.",
    )
    item_lista_servico = models.CharField(
        "Item Lista Serviço (cache local)", max_length=8, blank=True, default="17.19.01",
    )
    codigo_nbs = models.CharField(
        "Código NBS (cache local)", max_length=9, blank=True, default="113022100",
    )
    aliquota_iss = models.DecimalField(
        "Alíquota ISS % (cache local)", max_digits=14, decimal_places=10,
        default=Decimal("2.00"),
    )
    dados_tomador = models.JSONField(
        "Dados Fiscais do Tomador (cache local)", default=dict, blank=True,
        help_text="Cópia local do cadastro fiscal do cliente na Omie (CNPJ/CPF, endereço, "
                   "município IBGE, telefone, e-mail) — mesmo formato usado pelo emissor SAATRI. "
                   "Só é atualizado quando 'Sincronizar com Omie' está ligado (é sempre lido "
                   "da Omie, nunca editado manualmente).",
    )
    dados_locais_atualizados_em = models.DateTimeField(
        "Cache local atualizado em", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Contrato Omie"
        verbose_name_plural = "Contratos Omie"

    def __str__(self):
        return f"{self.omie_num_ctr} - {self.cliente_nome or 'Cliente Desconhecido'}"

class ServicoExtra(models.Model):
    """
    Representa serviços fora do contrato (notas avulsas) ou adicionais.
    Pode ser vinculado a um contrato ou ser avulso.
    """
    contrato = models.ForeignKey(Contrato, on_delete=models.SET_NULL, null=True, blank=True, related_name="servicos_extras")
    descricao = models.CharField(max_length=255, verbose_name="Descrição do Serviço")
    valor = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor")
    data_servico = models.DateField(verbose_name="Data do Serviço")

    # Se futuramente integrar com Ordens de Serviço (API os-cadastro), guardamos o ID aqui
    omie_os_id = models.BigIntegerField(null=True, blank=True, verbose_name="ID OS Omie")

    criado_por = models.ForeignKey(User, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Serviço Extra"
        verbose_name_plural = "Serviços Extras"


# models.py — adicione estas classes ao arquivo existente
# Mantém Contrato e ServicoExtra já existentes.

from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
#  NOTA FISCAL (NFS-e)
# ─────────────────────────────────────────────────────────────────────────────
class NotaFiscal(models.Model):

    STATUS_CHOICES = [
        ('emitida',   'Emitida'),
        ('cancelada', 'Cancelada'),
        ('inativa',   'Inativa'),   # inativada manualmente
    ]

    # ── Vínculo ──
    contrato = models.ForeignKey(
        'Contrato', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notas_fiscais',
        verbose_name='Contrato',
    )

    # ── Origem da emissão ──
    ORIGEM_CHOICES = [
        ('omie',   'Omie'),
        ('saatri', 'SAATRI Direto'),
        ('manual', 'Importada Manualmente'),
    ]
    origem = models.CharField(
        max_length=10, choices=ORIGEM_CHOICES, default='omie',
        verbose_name='Origem da Emissão',
        help_text="'omie' = faturada/emitida pela Omie (fluxo padrão). "
                   "'saatri' = emitida direto no Web Service SAATRI, sem passar pela Omie. "
                   "'manual' = nota já existente cadastrada à mão (ex.: emitida fora do sistema).",
    )

    # ── Identificadores Omie ──
    # Nula para notas emitidas via SAATRI Direto (origem='saatri'), que não
    # têm nenhum ID Omie associado.
    omie_nfse_id = models.BigIntegerField(unique=True, null=True, blank=True, verbose_name='ID NFS-e Omie')
    numero_nfse  = models.CharField(max_length=40, blank=True, null=True, verbose_name='Número NFS-e')
    omie_os_id   = models.BigIntegerField(null=True, blank=True, verbose_name='ID OS Omie')

    # ── Identificadores SAATRI (só para origem='saatri') ──
    codigo_verificacao = models.CharField(max_length=100, blank=True, null=True, verbose_name='Código de Verificação SAATRI')
    xml_completo        = models.TextField(blank=True, null=True, verbose_name='XML Completo (SAATRI)')

    # ── Dados da Nota ──
    cliente_nome  = models.CharField(max_length=255, blank=True, null=True)
    cnpj_tomador  = models.CharField(
        max_length=20, blank=True, null=True, verbose_name='CNPJ/CPF do Tomador (cache)',
        help_text="Preenchido nas notas importadas manualmente (essencial nas 'avulsas', sem "
                   "Contrato associado) — permite localizar por CNPJ na Consulta de Notas.",
    )
    descricao     = models.TextField(blank=True, null=True)
    valor_bruto   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_iss     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_liquido = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Competência ──
    competencia_mes = models.PositiveSmallIntegerField()
    competencia_ano = models.PositiveSmallIntegerField()
    data_emissao    = models.DateField(null=True, blank=True)

    # ── Status / Inativação ──
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default='emitida')
    inativada_por      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notas_inativadas',
    )
    inativada_em       = models.DateTimeField(null=True, blank=True)
    motivo_inativacao  = models.TextField(blank=True, null=True)

    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Nota Fiscal (NFS-e)'
        verbose_name_plural = 'Notas Fiscais (NFS-e)'
        ordering            = ['-competencia_ano', '-competencia_mes', '-data_emissao']

    def __str__(self):
        return f'NFS-e {self.numero_nfse or self.omie_nfse_id} — {self.cliente_nome}'

    # ── Properties derivadas do contrato vinculado ──────────

    @property
    def municipio(self):
        """Município herdado do contrato."""
        return (self.contrato.municipio or '') if self.contrato else ''

    @property
    def tipo_entidade(self):
        """Tipo de entidade herdado do contrato ('municipio' | 'camara' | '')."""
        return (self.contrato.tipo_entidade or '') if self.contrato else ''

    @property
    def tipo_entidade_display(self):
        """Label legível do tipo de entidade."""
        MAP = {'municipio': 'Município', 'camara': 'Câmara Municipal'}
        return MAP.get(self.tipo_entidade, '')

    @property
    def foi_paga(self):
        rec = getattr(self, 'confirmacao', None)
        return rec is not None and rec.confirmado

    @property
    def valor_recebido_real(self):
        rec = getattr(self, 'confirmacao', None)
        if rec and rec.confirmado:
            return rec.valor_recebido or self.valor_liquido
        return Decimal('0.00')

    def get_link_visualizacao_saatri(self):
        """Link público de visualização (PDF) — só válido para origem='saatri'."""
        base = "https://oliveiradosbrejinhos.saatri.com.br"
        return f"{base}/Relatorio/VisualizarNotaFiscal?numero={self.numero_nfse}&codigoVerificacao={self.codigo_verificacao}"


# ─────────────────────────────────────────────────────────────────────────────
#  EMISSÃO SAATRI DIRETO (bypassa a Omie, fala direto com o Web Service da
#  prefeitura — ver despesas/saatri/). RpsSaatri é o equivalente ao "Rps" do
#  projeto nfse_project: registra cada TENTATIVA de emissão (uma malsucedida
#  fica com status='erro' e pode ser reenviada reaproveitando o mesmo número,
#  sem "queimar" numeração nova a cada erro). Quando dá certo, gera/atualiza
#  uma NotaFiscal (origem='saatri').
# ─────────────────────────────────────────────────────────────────────────────
class SaatriNumeracao(models.Model):
    """
    Singleton com o próximo número de RPS disponível para a série 9000
    (Web Service). Começa em 3260 — folga de segurança acima do RPS 3255,
    já usado nos testes reais do nfse_project (NFS-e 3254 emitida).
    """
    proximo_numero_rps = models.PositiveIntegerField(default=3260)

    class Meta:
        verbose_name = "Numeração RPS SAATRI"
        verbose_name_plural = "Numeração RPS SAATRI"

    def __str__(self):
        return f"Próximo RPS: {self.proximo_numero_rps}"

    @classmethod
    def obter(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def incrementar(self):
        numero = self.proximo_numero_rps
        self.proximo_numero_rps += 1
        self.save(update_fields=['proximo_numero_rps'])
        return numero


class ConfiguracaoSistema(models.Model):
    """
    Singleton de feature flags editáveis pelo Django admin — pra ligar/
    desligar funcionalidades experimentais sem precisar de deploy.
    """
    dashboard_mostra_status_faturamento = models.BooleanField(
        "Mostrar status de faturamento por competência no dashboard de contratos",
        default=False,
        help_text="Filtro de mês/ano + coluna 'Faturado/Não faturado' na lista de contratos "
                   "em /receitas/. Desligado por padrão — o indicador oficial de notas já "
                   "faturadas/pendentes fica no fluxo de 'Faturar em lote' (ver painel de "
                   "confirmação do modal de edição em lote).",
    )

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return "Configurações do Sistema"

    @classmethod
    def obter(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class RpsSaatri(models.Model):
    """Uma tentativa de emissão avulsa de NFS-e via SAATRI Direto."""

    STATUS_CHOICES = [
        ('rascunho',   'Rascunho'),
        ('enviado',    'Enviado (aguardando SEFIN)'),
        ('convertido', 'Convertido em NFS-e'),
        ('erro',       'Erro'),
    ]

    contrato = models.ForeignKey(
        'Contrato', on_delete=models.PROTECT, related_name='rps_saatri_list',
        verbose_name='Contrato',
    )
    nota_fiscal = models.OneToOneField(
        NotaFiscal, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rps_saatri',
    )

    numero = models.PositiveIntegerField('Número do RPS')
    serie  = models.CharField('Série', max_length=5, default='9000')
    tipo   = models.CharField('Tipo', max_length=1, default='1')

    competencia_mes = models.PositiveSmallIntegerField()
    competencia_ano = models.PositiveSmallIntegerField()

    valor_servicos = models.DecimalField(max_digits=12, decimal_places=2)
    aliquota       = models.DecimalField(max_digits=14, decimal_places=10, default=0)
    valor_iss      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discriminacao  = models.TextField()
    item_lista_servico = models.CharField(max_length=8)
    codigo_nbs         = models.CharField(max_length=9, blank=True)

    status        = models.CharField(max_length=12, choices=STATUS_CHOICES, default='rascunho')
    mensagem_erro = models.TextField(blank=True)

    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RPS SAATRI"
        verbose_name_plural = "RPS SAATRI"
        ordering = ['-criado_em']
        unique_together = ('numero', 'serie', 'tipo')

    def __str__(self):
        return f"RPS {self.numero}/{self.serie} — {self.contrato.cliente_nome}"


class LogSaatri(models.Model):
    """Auditoria de cada chamada SOAP ao Web Service SAATRI."""

    metodo      = models.CharField('Método SOAP', max_length=60)
    url         = models.URLField('URL Endpoint')
    xml_envio   = models.TextField('XML Enviado')
    xml_retorno = models.TextField('XML Retornado', blank=True)
    http_status = models.IntegerField('HTTP Status', null=True)
    sucesso     = models.BooleanField('Sucesso', default=False)
    erro        = models.TextField('Erro', blank=True)
    duracao_ms  = models.IntegerField('Duração (ms)', null=True)
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log SAATRI"
        verbose_name_plural = "Logs SAATRI"
        ordering = ['-criado_em']

    def __str__(self):
        status = "OK" if self.sucesso else "ERRO"
        return f"[{status}] {self.metodo} — {self.criado_em:%d/%m/%Y %H:%M}"


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIRMAÇÃO DE RECEBIMENTO
# ─────────────────────────────────────────────────────────────────────────────
class RecebimentoNota(models.Model):

    nota             = models.OneToOneField(NotaFiscal, on_delete=models.CASCADE, related_name='confirmacao')
    confirmado       = models.BooleanField(default=False)
    valor_recebido   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    data_recebimento = models.DateField(null=True, blank=True)
    observacao       = models.TextField(blank=True, null=True)
    registrado_por   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    registrado_em    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Confirmação de Recebimento'
        verbose_name_plural = 'Confirmações de Recebimento'

    def __str__(self):
        return f'{"✓" if self.confirmado else "○"} {self.nota}'

# ═══════════════════════════════════════════════════════════════════════════
#  MÓDULO: DOCUMENTAÇÃO E ENVIO — models_documentos.py
#  Adicione ao final do seu models.py existente (após RecebimentoNota).
#  Depois rode: python manage.py makemigrations && python manage.py migrate
# ═══════════════════════════════════════════════════════════════════════════
import os
from datetime import date, timedelta
from django.db import models
from django.contrib.auth.models import User


# ───────────────────────────────────────────────────────────────────────────
#  E-MAILS POR CONTRATO
# ───────────────────────────────────────────────────────────────────────────
class ContratoEmail(models.Model):
    """E-mails de destino para envio do dossie mensal de cada contrato."""
    contrato     = models.ForeignKey('Contrato', on_delete=models.CASCADE, related_name='emails')
    email        = models.EmailField('E-mail')
    nome_contato = models.CharField('Nome do Contato', max_length=120, blank=True)
    principal    = models.BooleanField('Principal', default=False)
    criado_em    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'E-mail do Contrato'
        verbose_name_plural = 'E-mails dos Contratos'
        ordering            = ['-principal', 'email']
        unique_together     = [['contrato', 'email']]

    def __str__(self):
        return f'{self.email} ({self.contrato.omie_num_ctr})'


# ───────────────────────────────────────────────────────────────────────────
#  DOCUMENTOS PADRAO  (certidoes — valem para todos os contratos)
# ───────────────────────────────────────────────────────────────────────────
class DocumentoPadrao(models.Model):
    """
    Certidoes e comprovacoes compartilhadas por TODOS os contratos.
    Tem validade e precisam ser renovadas periodicamente.
    """
    TIPO_CHOICES = [
        ('fgts',        'Certidao de Regularidade do FGTS'),
        ('estadual',    'Certidao Negativa Estadual'),
        ('federal',     'Certidao Negativa Federal'),
        ('municipal',   'Certidao Negativa Municipal'),
        ('trabalhista', 'Certidao Negativa Trabalhista'),
        ('simples',     'Comprovacao do Simples Nacional'),
    ]

    tipo           = models.CharField('Tipo', max_length=30, choices=TIPO_CHOICES, unique=True)
    arquivo        = models.FileField('Arquivo PDF', upload_to='docs_padrao/')
    data_validade  = models.DateField('Validade')
    observacao     = models.TextField('Observacao', blank=True)
    atualizado_em  = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='docs_padrao_atualizados')

    class Meta:
        verbose_name        = 'Documento Padrao'
        verbose_name_plural = 'Documentos Padrao'
        ordering            = ['tipo']

    def __str__(self):
        return self.get_tipo_display()

    @property
    def vencido(self):
        return self.data_validade < date.today()

    @property
    def vence_em_breve(self):
        return date.today() <= self.data_validade <= date.today() + timedelta(days=30)

    @property
    def status_validade(self):
        if self.vencido: return 'vencido'
        if self.vence_em_breve: return 'alerta'
        return 'ok'

    def nome_arquivo(self):
        return os.path.basename(self.arquivo.name) if self.arquivo else ''


# ───────────────────────────────────────────────────────────────────────────
#  DOCUMENTOS MODELO  (especificos por contrato — data substituivel via PyMuPDF)
# ───────────────────────────────────────────────────────────────────────────
class DocumentoModelo(models.Model):
    """
    Documento modelo vinculado a UM contrato especifico.

    Cada contrato possui seus proprios documentos modelo com informacoes
    unicas: valor, vigencia, detalhamentos, nome da entidade, etc.
    O arquivo base e o PDF original do documento daquele contrato.
    A data e o unico campo substituido mensalmente via PyMuPDF ao gerar
    um DocumentoModeloGerado — todo o restante permanece igual ao original.
    """
    TIPO_CHOICES = [
        ('declaracao_simples',   'Declaracao de Optante pelo Simples Nacional'),
        ('planilha_custos',      'Planilha de Custos'),
        ('relatorio_atividades', 'Relatorio de Atividades'),
        ('outro',                'Outro'),
    ]

    # vinculo obrigatorio com o contrato
    contrato = models.ForeignKey(
        'Contrato', on_delete=models.CASCADE,
        related_name='docs_modelo',
        verbose_name='Contrato',
    )

    tipo               = models.CharField('Tipo', max_length=40, choices=TIPO_CHOICES)
    nome_personalizado = models.CharField(
        'Nome personalizado', max_length=120, blank=True,
        help_text='Opcional. Sobrepe o tipo na exibicao. Ex: "Planilha de Custos — CM Apora"'
    )
    arquivo_base        = models.FileField(
        'Arquivo Base (PDF original)',
        upload_to='docs_modelo/base/',
    )
    texto_data_original = models.CharField(
        'Texto de data no PDF base', max_length=300,
        help_text='Texto exato que aparece no PDF e sera substituido mensalmente. '
                  'Ex: "Oliveira dos Brejinhos - BA, 20 de janeiro de 2026"'
    )
    # Apenas para Relatorio de Atividades: capa possui campo MES separado da data
    texto_mes_original = models.CharField(
        'Texto do mes na capa (Relatorio de Atividades)', max_length=100, blank=True,
        help_text='Texto exato do mes na capa. Ex: "JANEIRO". Deixe em branco para outros tipos.'
    )
    descricao      = models.TextField('Observacoes', blank=True)
    ativo          = models.BooleanField('Ativo', default=True)
    criado_em      = models.DateTimeField(auto_now_add=True)
    atualizado_em  = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='docs_modelo_atualizados',
    )

    class Meta:
        verbose_name        = 'Documento Modelo'
        verbose_name_plural = 'Documentos Modelo'
        ordering            = ['contrato', 'tipo']

    def __str__(self):
        return f'{self.label()} — {self.contrato.omie_num_ctr}'

    def label(self):
        return self.nome_personalizado or self.get_tipo_display()

    def nome_arquivo(self):
        return os.path.basename(self.arquivo_base.name) if self.arquivo_base else ''


# ───────────────────────────────────────────────────────────────────────────
#  DOCUMENTO MODELO GERADO  (PDF com data do mes substituida)
# ───────────────────────────────────────────────────────────────────────────
class DocumentoModeloGerado(models.Model):
    """
    PDF gerado pelo PyMuPDF a partir de um DocumentoModelo,
    com a data substituida para um determinado mes/ano.
    O contrato e derivado do proprio modelo (modelo.contrato).
    Substitui o arquivo anterior ao ser regenerado.
    """
    modelo          = models.ForeignKey(
        DocumentoModelo, on_delete=models.CASCADE, related_name='gerados',
    )
    mes             = models.PositiveSmallIntegerField('Mes')
    ano             = models.PositiveSmallIntegerField('Ano')
    arquivo         = models.FileField('Arquivo Gerado', upload_to='docs_modelo/gerados/')
    texto_data_novo = models.CharField('Texto de data substituido', max_length=300, blank=True)
    gerado_em       = models.DateTimeField(auto_now_add=True)
    gerado_por      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='docs_gerados',
    )

    class Meta:
        verbose_name        = 'Documento Modelo Gerado'
        verbose_name_plural = 'Documentos Modelo Gerados'
        unique_together     = [['modelo', 'mes', 'ano']]
        ordering            = ['-ano', '-mes']

    def __str__(self):
        return f'{self.modelo.label()} — {self.modelo.contrato.omie_num_ctr} {self.mes:02d}/{self.ano}'

    @property
    def contrato(self):
        return self.modelo.contrato

    def nome_arquivo(self):
        return os.path.basename(self.arquivo.name) if self.arquivo else ''


# ───────────────────────────────────────────────────────────────────────────
#  PDF DA NFS-E  (baixado via link do Omie e armazenado localmente)
# ───────────────────────────────────────────────────────────────────────────
class NotaFiscalPDF(models.Model):
    nota        = models.OneToOneField('NotaFiscal', on_delete=models.CASCADE, related_name='pdf_local')
    arquivo     = models.FileField('PDF da NFS-e', upload_to='docs_nfse/')
    url_omie    = models.URLField('URL original Omie', blank=True)
    baixado_em  = models.DateTimeField(auto_now_add=True)
    baixado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='nfse_pdfs_baixados')

    class Meta:
        verbose_name        = 'PDF de NFS-e'
        verbose_name_plural = 'PDFs de NFS-e'

    def __str__(self):
        return f'PDF NFS-e {self.nota.numero_nfse}'

    def nome_arquivo(self):
        return os.path.basename(self.arquivo.name) if self.arquivo else ''


# ───────────────────────────────────────────────────────────────────────────
#  ENVIO MENSAL  (dossie por contrato x mes)
# ───────────────────────────────────────────────────────────────────────────
import json

class EnvioMensal(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente de Envio'),
        ('enviado',  'Enviado'),
        ('externo',  'Envio Externo'),
    ]

    contrato    = models.ForeignKey('Contrato', on_delete=models.CASCADE, related_name='envios_mensais')
    nota_fiscal = models.ForeignKey('NotaFiscal', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='envios')
    mes         = models.PositiveSmallIntegerField('Mes')
    ano         = models.PositiveSmallIntegerField('Ano')
    status      = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='pendente')
    enviado_em        = models.DateTimeField('Ultimo envio em', null=True, blank=True)
    primeiro_envio_em = models.DateTimeField('Primeiro envio em', null=True, blank=True)
    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='envios_realizados')
    observacao  = models.TextField('Observacao', blank=True)
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Envio Mensal'
        verbose_name_plural = 'Envios Mensais'
        unique_together     = [['contrato', 'mes', 'ano']]
        ordering            = ['-ano', '-mes', 'contrato__cliente_nome']

    def __str__(self):
        return f'{self.contrato.omie_num_ctr} — {self.mes:02d}/{self.ano} [{self.get_status_display()}]'

    @property
    def emails_destino(self):
        return list(self.contrato.emails.values_list('email', flat=True))

    @property
    def contatos_destino(self):
        """Retorna lista de dicts {nome_contato, email} para o modal."""
        return list(self.contrato.emails.values('nome_contato', 'email'))

    @property
    def emails_destino_json(self):
        return json.dumps(self.contatos_destino or [])

#CARTÃO CORPORATIVO

from django.db.models import Sum


from django.db.models import Sum

from decimal import Decimal
from django.db import models
from django.db.models import Sum

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal

class CartaoCorporativo(models.Model):
    usuario = models.OneToOneField(
        'auth.User', # ou import User
        on_delete=models.CASCADE,
        related_name="cartao_corporativo",
        verbose_name="Analista"
    )
    habilitado = models.BooleanField("Habilitar Cartão Empresarial", default=False)
    limite = models.DecimalField("Limite Padrão", max_digits=10, decimal_places=2, default=1000.00)

    # NOVOS CAMPOS FÍSICOS DE ESTADO (Wallet)
    saldo_atual = models.DecimalField("Saldo Disponível", max_digits=12, decimal_places=2, default=1000.00)
    excedente = models.DecimalField("Excedente (Gasto do Bolso)", max_digits=12, decimal_places=2, default=0.00)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cartão Empresarial"
        verbose_name_plural = "Cartões Empresariais"

    def save(self, *args, **kwargs):
        # Ao criar um cartão novo, garante que ele inicie com o valor do limite
        if not self.pk and self.saldo_atual == 1000.00:
            self.saldo_atual = self.limite
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cartão de {self.usuario.username} - Saldo: R$ {self.saldo_atual}"


class TransacaoCartao(models.Model):
    """
    Guarda o histórico de como cada despesa impactou o cartão.
    Garante que se a despesa for editada ou excluída, o saldo/excedente volte corretamente.
    """
    despesa = models.OneToOneField('Despesa', on_delete=models.CASCADE, related_name="transacao_cartao")
    valor_debitado_saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    valor_jogado_excedente = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)


# ==========================================================
# GATILHOS (SIGNALS) PARA GERENCIAR O SALDO AUTOMATICAMENTE
# ==========================================================
@receiver(post_save, sender='despesas.Despesa')
def processar_despesa_cartao(sender, instance, created, **kwargs):
    cartao = getattr(instance.usuario, 'cartao_corporativo', None)
    if not cartao or not cartao.habilitado:
        return

    # Busca a transação atrelada (se for uma edição da despesa, ela já existe)
    transacao, t_created = TransacaoCartao.objects.get_or_create(despesa=instance)

    if not t_created:
        # Se for EDIÇÃO, devolvemos os valores antigos para a carteira antes de recalcular
        cartao.saldo_atual += transacao.valor_debitado_saldo
        cartao.excedente -= transacao.valor_jogado_excedente

    # ==========================================================
    # NOVA LÓGICA DEFINITIVA: TUDO OU NADA NO CARTÃO
    # ==========================================================
    if cartao.saldo_atual >= instance.valor:
        # Tem saldo suficiente -> O cartão passa. Debita tudo do cartão.
        cartao.saldo_atual -= instance.valor
        transacao.valor_debitado_saldo = instance.valor
        transacao.valor_jogado_excedente = Decimal('0.00')
    else:
        # Saldo insuficiente -> O cartão é recusado.
        # O saldo fica INTOCADO e o analista paga o valor INTEGRAL do bolso.
        transacao.valor_debitado_saldo = Decimal('0.00')
        transacao.valor_jogado_excedente = instance.valor

        cartao.excedente += instance.valor

    # Salva os estados atualizados
    transacao.save()
    cartao.save()

@receiver(post_delete, sender='despesas.Despesa')
def estornar_despesa_cartao(sender, instance, **kwargs):
    cartao = getattr(instance.usuario, 'cartao_corporativo', None)
    if not cartao:
        return
    try:
        transacao = instance.transacao_cartao
        # Devolve o saldo ou subtrai do excedente caso a despesa seja excluída
        cartao.saldo_atual += transacao.valor_debitado_saldo
        cartao.excedente -= transacao.valor_jogado_excedente
        cartao.save()
    except TransacaoCartao.DoesNotExist:
        pass

# models.py

class EmailMunicipio(models.Model):
    """
    Template de e-mail por município + tipo de entidade.
    Ao ser propagado, cria ContratoEmail em todos os contratos
    que possuem o mesmo município e tipo_entidade.
    """
    TIPO_ENTIDADE_CHOICES = [
        ('municipio', 'Prefeitura'),
        ('camara',    'Câmara Municipal'),
    ]

    municipio     = models.CharField("Município", max_length=120)
    tipo_entidade = models.CharField(
        "Tipo de Entidade",
        max_length=20,
        choices=TIPO_ENTIDADE_CHOICES,
        blank=True, null=True,
        help_text="Deixe em branco para aplicar a Prefeitura E Câmara do município.",
    )
    email         = models.EmailField("E-mail")
    nome_contato  = models.CharField("Nome do Contato", max_length=120, blank=True)
    principal     = models.BooleanField("Marcar como principal", default=False)
    criado_em     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "E-mail por Município"
        verbose_name_plural = "E-mails por Município"
        unique_together     = [["municipio", "tipo_entidade", "email"]]
        ordering            = ["municipio", "tipo_entidade", "email"]

    def __str__(self):
        entidade = dict(self.TIPO_ENTIDADE_CHOICES).get(self.tipo_entidade, "Todos")
        return f"{self.email} → {self.municipio} / {entidade}"

    def propagar(self) -> dict:
        """
        Cria ContratoEmail para cada contrato que bate com
        municipio + tipo_entidade (ou todos do município se tipo_entidade=None).
        Retorna um dict com totais para feedback ao usuário.
        """
        qs = Contrato.objects.filter(municipio__iexact=self.municipio)
        if self.tipo_entidade:
            qs = qs.filter(tipo_entidade=self.tipo_entidade)

        criados    = 0
        ignorados  = 0  # já existiam

        for contrato in qs:
            _, created = ContratoEmail.objects.get_or_create(
                contrato=contrato,
                email=self.email,
                defaults={
                    "nome_contato": self.nome_contato,
                    "principal":    self.principal,
                },
            )
            if created:
                criados += 1
            else:
                ignorados += 1

        return {
            "total_contratos": qs.count(),
            "criados":         criados,
            "ignorados":       ignorados,
        }


#prestacao_de_contas

# ═══════════════════════════════════════════════════════════════════════
# ADICIONAR AO: despesas/models.py
# Adicione estes campos ao final da classe UsuarioPerfil (após acesso_etcm)
# e cole os novos modelos ao final do arquivo models.py
# ═══════════════════════════════════════════════════════════════════════

# ── 1. NOVOS CAMPOS EM UsuarioPerfil ────────────────────────────────────
# Adicione dentro da classe UsuarioPerfil, após a linha acesso_etcm:
#
#   PERFIL_PC_CHOICES = [
#       ('JURIDICO', 'Jurídico'),
#       ('ANALISE',  'Análise'),
#   ]
#   acesso_prestacao_contas = models.BooleanField("Acesso Prestação de Contas", default=False)
#   perfil_pc = models.CharField(
#       "Perfil no módulo PC",
#       max_length=20,
#       choices=PERFIL_PC_CHOICES,
#       blank=True, null=True,
#   )
#
# Depois rode: python manage.py makemigrations despesas && python manage.py migrate
# ────────────────────────────────────────────────────────────────────────


# ── 2. NOVOS MODELOS ─────────────────────────────────────────────────────
# Cole no final de despesas/models.py


class EtapaPC(models.TextChoices):
    CADASTRO    = 'CADASTRO',    'Cadastro'
    ANALISE     = 'ANALISE',     'Análise'
    SIGA        = 'SIGA',        'Correção SIGA'
    ENVIO_FINAL = 'ENVIO_FINAL', 'Envio Final'
    CONCLUIDO   = 'CONCLUIDO',   'Concluído'


# Mapa de etapa → próxima etapa no fluxo
FLUXO_PC = {
    'CADASTRO':    'ANALISE',
    'ANALISE':     'SIGA',
    'SIGA':        'ENVIO_FINAL',
    'ENVIO_FINAL': 'CONCLUIDO',
}

# Quem pode avançar cada etapa
PERMISSAO_AVANCO = {
    'CADASTRO':    'JURIDICO',   # perfil_pc == JURIDICO
    'ANALISE':     'ANALISE',    # perfil_pc == ANALISE
    'SIGA':        'SIGA',       # acesso_siga == True
    'ENVIO_FINAL': 'JURIDICO',
}


class PrestacaoContas(models.Model):
    """Cabeçalho do processo de acompanhamento de prestação de contas."""

    PERIODO_CHOICES = [
        ('1Q',    '1º Quadrimestre'),
        ('2Q',    '2º Quadrimestre'),
        ('3Q',    '3º Quadrimestre'),
        ('ANUAL', 'Anual'),
    ]

    cliente             = models.ForeignKey(
        'Cliente', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='prestacoes_contas',
    )
    # Nome extraído do PDF antes de vincular ao cliente
    nome_unidade_pdf    = models.CharField('Unidade (PDF)', max_length=300, blank=True)
    competencia_mes     = models.PositiveIntegerField('Mês')
    competencia_ano     = models.PositiveIntegerField('Ano')
    numero_processo     = models.CharField('Nº Processo TCM', max_length=100, blank=True)
    inspetoria          = models.CharField('Inspetoria', max_length=200, blank=True)

    etapa_atual         = models.CharField(
        'Etapa atual', max_length=30,
        choices=EtapaPC.choices,
        default=EtapaPC.CADASTRO,
        db_index=True,
    )

    documento_principal = models.FileField(
        'Documento Principal (PDF)',
        upload_to='prestacao_contas/documentos/%Y/%m/',
        null=True, blank=True,
    )
    comprovante_envio   = models.FileField(
        'Comprovante de Envio',
        upload_to='prestacao_contas/comprovantes/%Y/%m/',
        null=True, blank=True,
    )

    observacao_cadastro = models.TextField('Obs. Cadastro', blank=True)
    observacao_analise  = models.TextField('Obs. Análise', blank=True)
    observacao_siga     = models.TextField('Obs. SIGA', blank=True)
    observacao_envio    = models.TextField('Obs. Envio', blank=True)

    cadastrado_por      = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_cadastradas',
    )
    ultimo_editor       = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_editadas',
    )
    criado_em           = models.DateTimeField(auto_now_add=True)
    modificado_em       = models.DateTimeField(auto_now=True)
    periodo = models.CharField(
        max_length=10, choices=PERIODO_CHOICES, blank=True, null=True
    )

    class Meta:
        verbose_name        = 'Prestação de Contas'
        verbose_name_plural = 'Prestações de Contas'
        ordering            = ['-modificado_em']

    def __str__(self):
        nome = self.cliente.nome if self.cliente else (self.nome_unidade_pdf or 'Sem cliente')
        return f'{nome} — {self.competencia_mes:02d}/{self.competencia_ano}'

    @property
    def competencia_str(self):
        return f'{self.competencia_mes:02d}/{self.competencia_ano}'

    @property
    def qtd_inconsistencias(self):
        return self.itens.filter(tem_inconsistencia=True).count()

    @property
    def proxima_etapa(self):
        return FLUXO_PC.get(self.etapa_atual)

    @property
    def concluido(self):
        return self.etapa_atual == 'CONCLUIDO'

    @property
    def etapa_label(self):
        return dict(EtapaPC.choices).get(self.etapa_atual, self.etapa_atual)

    @property
    def cor_etapa(self):
        cores = {
            'CADASTRO':    '#3b82f6',
            'ANALISE':     '#f59e0b',
            'SIGA':        '#8b5cf6',
            'ENVIO_FINAL': '#06b6d4',
            'CONCLUIDO':   '#10b981',
        }
        return cores.get(self.etapa_atual, '#6b7280')


class PCItem(models.Model):
    """Item/seção extraído do documento PDF de prestação de contas."""

    STATUS_CHOICES = [
        ('PENDENTE',        'Pendente'),
        ('INCONSISTENTE',   'Inconsistente'),
        ('OK_ANALISE',      'OK (Análise/Jurídico)'),
        ('CONFIRMADO_SIGA', 'Confirmado pelo SIGA'),
        ('DEVOLVIDO',       'Devolvido para revisão'),
    ]

    prestacao          = models.ForeignKey(
        PrestacaoContas, on_delete=models.CASCADE,
        related_name='itens',
    )
    numero             = models.CharField('Numeração', max_length=30, blank=True)
    descricao          = models.TextField('Descrição')
    nivel_hierarquico  = models.PositiveIntegerField('Nível', default=1)
    tem_inconsistencia = models.BooleanField('Tem inconsistência', default=False)
    observacao         = models.TextField('Observação de inconsistência', blank=True)
    apontado_por       = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_inconsistencias_apontadas',
    )
    apontado_em        = models.DateTimeField(null=True, blank=True)
    status_siga        = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='PENDENTE'
    )
    confirmado_por     = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_itens_confirmados',
    )
    confirmado_em      = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Item de Prestação de Contas'
        verbose_name_plural = 'Itens de Prestação de Contas'
        ordering            = ['numero', 'id']

    def __str__(self):
        return f'{self.numero} — {self.descricao[:60]}'


class PCAnexo(models.Model):
    """Arquivo anexado em qualquer etapa do processo."""
    prestacao   = models.ForeignKey(
        PrestacaoContas, on_delete=models.CASCADE,
        related_name='anexos',
    )
    # NOVO: vínculo opcional com item específico
    item        = models.ForeignKey(
        'PCItem', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='anexos',
    )
    etapa       = models.CharField('Etapa', max_length=30, choices=EtapaPC.choices)
    arquivo     = models.FileField(upload_to='prestacao_contas/anexos/%Y/%m/')
    descricao   = models.CharField('Descrição', max_length=255, blank=True)
    enviado_por = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    criado_em   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Anexo de PC'
        verbose_name_plural = 'Anexos de PC'
        ordering            = ['-criado_em']

    def __str__(self):
        item_str = f' — Item {self.item.numero}' if self.item else ''
        return f'{self.prestacao}{item_str} — {self.etapa} — {self.arquivo.name}'



class PCHistorico(models.Model):
    """Log de todas as transições de etapa do processo."""

    prestacao       = models.ForeignKey(
        PrestacaoContas, on_delete=models.CASCADE,
        related_name='historico',
    )
    etapa_anterior  = models.CharField(max_length=30, choices=EtapaPC.choices, blank=True)
    etapa_nova      = models.CharField(max_length=30, choices=EtapaPC.choices)
    alterado_por    = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    observacao      = models.TextField(blank=True)
    criado_em       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Histórico de PC'
        verbose_name_plural = 'Históricos de PC'
        ordering            = ['-criado_em']

    def __str__(self):
        return (
            f'{self.prestacao} | {self.etapa_anterior} → {self.etapa_nova} '
            f'por {self.alterado_por}'
        )

# ─────────────────────────────────────────────────────────────────────────────
#  models.py  (adicionar ao models.py existente)
# ─────────────────────────────────────────────────────────────────────────────

from datetime import date
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


class DespesaGeral(models.Model):

    CLASSIFICACAO_CHOICES = [
        ('aluguel',          'Aluguel'),
        ('gastos_diversos',  'Gastos Diversos'),
        ('alimentacao',      'Alimentação'),
        ('transporte',       'Transporte'),
        ('consignado',       'Consignado'),
        ('financiamentos',   'Financiamentos'),
        ('energia',          'Energia'),
        ('outros',           'Outros'),
    ]
    STATUS_CHOICES = [('pendente', 'Pendente'), ('pago', 'Pago')]

    classificacao         = models.CharField(max_length=20, choices=CLASSIFICACAO_CHOICES)
    classificacao_custom  = models.CharField(max_length=100, blank=True, null=True)
    descricao             = models.CharField(max_length=255)
    valor_unitario        = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quantidade            = models.PositiveIntegerField(default=1)
    valor                 = models.DecimalField(max_digits=12, decimal_places=2)
    mes_referencia        = models.DateField()
    recorrente            = models.BooleanField(default=False)
    data_vencimento       = models.DateField(null=True, blank=True)
    lembrete_antecedencia = models.JSONField(default=list, blank=True)
    status                = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pendente')
    observacao            = models.TextField(blank=True)

    recorrencia_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        verbose_name='ID de Recorrência',
        help_text='UUID compartilhado entre todas as cópias da mesma despesa recorrente.'
    )

    # ── NOVO: associa a despesa a um município para análise detalhada ──────
    municipio = models.CharField(
        "Município",
        max_length=120,
        blank=True,
        null=True,
        help_text=(
            "Associe esta despesa a um município para que ela apareça "
            "na análise detalhada por município (Raio X → Por Município)."
        ),
    )

    tipo_orgao = models.CharField("Tipo Órgão", max_length=20, blank=True, null=True)
    # ──────────────────────────────────────────────────────────────────────

    criado_por    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='despesas_gerais_criadas',
    )
    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Despesa Geral'
        verbose_name_plural = 'Despesas Gerais'
        ordering            = ['mes_referencia', 'classificacao', 'descricao']

    def __str__(self):
        return f'[{self.get_classificacao_display()}] {self.descricao} — R$ {self.valor}'

    @property
    def label_classificacao(self):
        if self.classificacao == 'outros' and self.classificacao_custom:
            return self.classificacao_custom
        return self.get_classificacao_display()

    @property
    def dias_para_vencimento(self):
        if not self.data_vencimento:
            return None
        return (self.data_vencimento - date.today()).days

    @property
    def urgencia(self):
        d = self.dias_para_vencimento
        if d is None: return None
        if d < 0:     return 'vencida'
        if d <= 3:    return 'urgente'
        if d <= 7:    return 'proximo'
        return 'ok'

    @property
    def dias_atraso(self):
        """Dias de atraso (positivo). Usa em template no lugar de |abs."""
        d = self.dias_para_vencimento
        return abs(d) if d is not None and d < 0 else 0

    @property
    def dias_restantes(self):
        d = self.dias_para_vencimento
        return d if d is not None and d >= 0 else 0

    def save(self, *args, **kwargs):
        if self.classificacao == 'transporte' and self.valor_unitario and self.quantidade:
            self.valor = (self.valor_unitario * Decimal(self.quantidade)).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

class PCItemAnotacao(models.Model):
    """
    Anotação feita por qualquer usuário em um item da PC.
    Cada anotação é imutável e identificada pelo autor.
    """
    TIPO_CHOICES = [
        ('INCONSISTENCIA', 'Inconsistência'),
        ('OK',             'OK'),
        ('OBSERVACAO',     'Observação'),
        ('CONFIRMACAO',    'Confirmação SIGA'),
        ('DEVOLUCAO',      'Devolução SIGA'),
    ]

    # Cor de fundo do badge por tipo
    TIPO_COR = {
        'INCONSISTENCIA': ('#fef2f2', '#dc2626'),
        'OK':             ('#f0fdf4', '#16a34a'),
        'OBSERVACAO':     ('#f8fafc', '#475569'),
        'CONFIRMACAO':    ('#d1fae5', '#065f46'),
        'DEVOLUCAO':      ('#fff7ed', '#c2410c'),
    }

    item       = models.ForeignKey(
        'PCItem', on_delete=models.CASCADE,
        related_name='anotacoes',
    )
    usuario    = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_anotacoes',
    )
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES,
                                  default='OBSERVACAO')
    texto      = models.TextField()
    criado_em  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Anotação de Item PC'
        verbose_name_plural = 'Anotações de Itens PC'
        ordering            = ['criado_em']

    def __str__(self):
        return (
            f'{self.get_tipo_display()} — '
            f'{self.usuario} — '
            f'{self.criado_em.strftime("%d/%m/%Y %H:%M")}'
        )

    @property
    def cor_bg(self):
        return self.TIPO_COR.get(self.tipo, ('#f8fafc', '#475569'))[0]

    @property
    def cor_texto(self):
        return self.TIPO_COR.get(self.tipo, ('#f8fafc', '#475569'))[1]


class PCPrazo(models.Model):
    """Prazo vinculado a uma prestação de contas, com lembretes push."""

    prestacao       = models.ForeignKey(
        'PrestacaoContas', on_delete=models.CASCADE,
        related_name='prazos',
    )
    descricao       = models.CharField('Descrição', max_length=255)
    data_limite     = models.DateField('Data Limite')
    dias_lembrete   = models.PositiveIntegerField(
        'Lembrete (dias antes)', default=3,
        help_text='Quantos dias antes do vencimento enviar o lembrete push.',
    )
    concluido       = models.BooleanField('Concluído', default=False)
    criado_por      = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_prazos_criados',
    )
    criado_em       = models.DateTimeField(auto_now_add=True)
    lembrete_enviado = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Prazo de PC'
        verbose_name_plural = 'Prazos de PC'
        ordering            = ['data_limite']

    def __str__(self):
        status = '✓' if self.concluido else '◷'
        return f'{status} {self.descricao} — {self.data_limite.strftime("%d/%m/%Y")}'

    @property
    def dias_restantes(self):
        from django.utils import timezone
        delta = self.data_limite - timezone.localdate()
        return delta.days

    @property
    def status_css(self):
        """Retorna classe CSS baseada na proximidade do vencimento."""
        if self.concluido:
            return 'prazo-ok'
        d = self.dias_restantes
        if d < 0:
            return 'prazo-vencido'
        if d <= 3:
            return 'prazo-urgente'
        if d <= 7:
            return 'prazo-proximo'
        return 'prazo-normal'

    @property
    def urgencia_css(self):
        """
        Retorna a classe CSS da badge de prazo no monitor:
          - urgente-hoje   → vence hoje   (vermelho)
          - urgente-amanha → vence amanhã (laranja)
        Usado apenas quando filtro_vence está ativo.
        """
        from django.utils import timezone
        hoje = timezone.localdate()
        if self.data_limite == hoje:
            return 'urgente-hoje'
        return 'urgente-amanha'

class PCRetorno(models.Model):
    """
    Solicitação de retorno de etapa feita pelo SIGA para a Análise.
    Quando aceita, a PC retrocede de SIGA para ANALISE.
    """
    prestacao      = models.ForeignKey(
        'PrestacaoContas', on_delete=models.CASCADE,
        related_name='retornos',
    )
    solicitado_por = models.ForeignKey(
        AUTH_USER, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pc_retornos_solicitados',
    )
    motivo         = models.TextField('Motivo do retorno')
    etapa_origem   = models.CharField(max_length=30, default='SIGA')
    etapa_destino  = models.CharField(max_length=30, default='ANALISE')
    processado     = models.BooleanField(default=False)
    criado_em      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Retorno de Etapa PC'
        verbose_name_plural = 'Retornos de Etapa PC'
        ordering            = ['-criado_em']

    def __str__(self):
        return (
            f'Retorno {self.etapa_origem}→{self.etapa_destino} '
            f'({self.prestacao}) por {self.solicitado_por}'
        )

#vínculo para cálculo raio X -> Dentro da Nota
class VinculoCentroCustoContrato(models.Model):
    TIPO_VINCULO_CHOICES = [
        ('PM', 'Prefeitura'),
        ('CM', 'Câmara Municipal'),
        ('AUT', 'Autarquia'),
    ]

    centro_de_custo = models.ForeignKey(
        'CentroDeCusto',
        on_delete=models.CASCADE,
        related_name='vinculos_contrato'
    )
    contrato = models.ForeignKey(
        'Contrato',
        on_delete=models.CASCADE,
        related_name='vinculos_centro_custo'
    )
    tipo_entidade = models.CharField(
        "Tipo de Entidade",
        max_length=3,
        choices=TIPO_VINCULO_CHOICES,
        blank=True,
        null=True
    )
    criado_automaticamente = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vínculo Centro de Custo x Contrato"
        verbose_name_plural = "Vínculos Centros de Custo x Contratos"
        unique_together = ('centro_de_custo', 'contrato')

    def __str__(self):
        tipo = self.get_tipo_entidade_display() or "Não Classificado"
        return f"[{tipo}] {self.centro_de_custo.nome} <-> Contrato: {self.contrato.omie_num_ctr}"



from django.db import models
from decimal import Decimal


class ConfiguracaoFinanceira(models.Model):
    """
    Singleton de configuração financeira.
    Gerenciado pelo admin: só pode existir um registro (pk=1).
    """
    percentual_imposto_nota = models.DecimalField(
        "% Imposto sobre Nota Fiscal",
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.00"),
        help_text=(
            "Percentual de imposto aplicado sobre o valor da nota fiscal "
            "na análise detalhada por município. Ex.: 2.00 para 2%."
        ),
    )

    class Meta:
        verbose_name = "Configuração Financeira"
        verbose_name_plural = "Configurações Financeiras"

    def __str__(self):
        return f"Config Financeira — ISS {self.percentual_imposto_nota}%"

    def save(self, *args, **kwargs):
        self.pk = 1  # garante singleton
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton: não deletar via código

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={"percentual_imposto_nota": Decimal("2.00")},
        )
        return obj


class VinculoFuncionarioCentro(models.Model):
    """
    Associa um funcionário (UsuarioPerfil) a um ou mais Centros de Custo.
    Usado para ratear proporcionalmente o salário entre municípios,
    com base no valor dos contratos de cada centro.
    """
    perfil = models.ForeignKey(
        "UsuarioPerfil",                      # ajuste se o app for diferente
        on_delete=models.CASCADE,
        related_name="vinculos_centro",
        verbose_name="Funcionário",
    )
    centro = models.ForeignKey(
        "CentroDeCusto",                      # ajuste se o app for diferente
        on_delete=models.CASCADE,
        related_name="vinculos_funcionario",
        verbose_name="Centro de Custo",
    )

    class Meta:
        unique_together = ("perfil", "centro")
        verbose_name = "Vínculo Funcionário × Centro de Custo"
        verbose_name_plural = "Vínculos Funcionários × Centros de Custo"
        ordering = ["perfil__user__first_name", "perfil__user__last_name", "centro"]

    def __str__(self):
        return f"{self.perfil} ↔ {self.centro}"

class PrevisaoPagamento(models.Model):
    """
    Previsão de pagamento por MUNICÍPIO-ENTIDADE, por competência.
    Uma linha "viva" por (municipio, tipo_entidade, competencia_mes, competencia_ano).
    NÃO tem FK para Contrato de propósito — é uma visão agregada por
    município-entidade, independente de quantos contratos existam ali.
    """
    STATUS_CHOICES = [
        ('pendente',      'Aguardando'),
        ('cumprida',      'Cumprida'),
        ('nao_cumprida',  'Não cumprida'),
    ]
    TIPO_ENTIDADE_CHOICES = [
        ('municipio', 'Prefeitura Municipal'),
        ('camara',    'Câmara Municipal'),
    ]

    municipio      = models.CharField(max_length=150)
    tipo_entidade  = models.CharField(max_length=20, choices=TIPO_ENTIDADE_CHOICES)

    competencia_mes = models.PositiveSmallIntegerField()
    competencia_ano = models.PositiveSmallIntegerField()

    data_prevista   = models.DateField(verbose_name='Data prevista de pagamento')
    valor_previsto  = models.DecimalField(max_digits=12, decimal_places=2)

    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    data_verificacao  = models.DateField(null=True, blank=True,
                                          verbose_name='Data em que foi marcada cumprida/não cumprida')

    observacao = models.TextField(blank=True, null=True)

    criado_por     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='previsoes_criadas')
    atualizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='previsoes_atualizadas')

    criado_em     = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Previsão de Pagamento'
        verbose_name_plural = 'Previsões de Pagamento'
        constraints = [
            models.UniqueConstraint(
                fields=['municipio', 'tipo_entidade', 'competencia_mes', 'competencia_ano'],
                name='uniq_previsao_municipio_entidade_competencia',
            )
        ]
        ordering = ['-competencia_ano', '-competencia_mes', 'municipio']

    def __str__(self):
        return f'Previsão {self.municipio} — {self.get_tipo_entidade_display()} ({self.competencia_mes}/{self.competencia_ano})'


class PrevisaoPagamentoLog(models.Model):
    """
    Histórico append-only. Toda criação, edição e mudança de status
    gera uma linha aqui — isto é o que aparece na timeline do painel.
    """
    TIPO_EVENTO = [
        ('criada',        'Previsão criada'),
        ('editada',       'Previsão editada'),
        ('cumprida',      'Marcada como cumprida'),
        ('nao_cumprida',  'Marcada como não cumprida'),
        ('reaberta',      'Reaberta (voltou a pendente)'),
    ]

    previsao = models.ForeignKey(PrevisaoPagamento, on_delete=models.CASCADE, related_name='historico')

    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO)

    # snapshot dos valores no momento do evento (para a timeline mostrar
    # "valor previsto era R$ X, virou R$ Y" sem depender do estado atual)
    data_prevista_snapshot  = models.DateField(null=True, blank=True)
    valor_previsto_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    observacao = models.TextField(blank=True, null=True)

    usuario   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Evento de Previsão'
        verbose_name_plural = 'Histórico de Previsões'


# ═══════════════════════════════════════════════════════════════════════════
#  CONTRACHEQUES  (recibos de pagamento mensais, sincronizados via OCR)
# ═══════════════════════════════════════════════════════════════════════════
#
#  ADICIONAR ESTE BLOCO AO FINAL DO models.py EXISTENTE.
#
#  Depende de: UsuarioPerfil (já existe no arquivo), User (já importado),
#  os (já importado mais acima no arquivo original, na seção do
#  DocumentoPadrao). Nenhum import novo é necessário aqui.
#
#  Depois de colar, rodar:
#      python manage.py makemigrations
#      python manage.py migrate
# ═══════════════════════════════════════════════════════════════════════════

class LoteContracheque(models.Model):
    """
    Representa UM upload do PDF da folha de pagamento (o arquivo grande,
    com várias páginas — uma por colaborador). O RH sobe esse arquivo pelo
    modal "Sincronizar Contracheques" do dashboard; o processamento (OCR +
    reconhecimento de cada colaborador) acontece em pequenos blocos de
    páginas, chamados sequencialmente pelo front-end, para não estourar o
    tempo de resposta do servidor (mesmo padrão já usado no pipeline de
    OCR/compressão de PDF do sistema).
    """

    class Status(models.TextChoices):
        PROCESSANDO            = 'PROCESSANDO', 'Processando'
        AGUARDANDO_CONFIRMACAO = 'AGUARDANDO_CONFIRMACAO', 'Aguardando Confirmação do RH'
        CONCLUIDO              = 'CONCLUIDO', 'Concluído'
        ERRO                   = 'ERRO', 'Erro no Processamento'

    arquivo_original = models.FileField('PDF Original do Lote', upload_to='contracheques/lotes/%Y/%m/')

    # Competência "informada" pelo RH no formulário de upload — usada apenas
    # como fallback quando o OCR não consegue ler o mês/ano na própria página.
    mes = models.PositiveSmallIntegerField('Mês de Referência (informado)', null=True, blank=True)
    ano = models.PositiveSmallIntegerField('Ano de Referência (informado)', null=True, blank=True)

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PROCESSANDO)
    total_paginas = models.PositiveIntegerField(default=0)
    paginas_processadas = models.PositiveIntegerField(default=0)

    log_erro = models.TextField('Log de Erro', blank=True)

    enviado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='lotes_contracheque_enviados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Lote de Contracheques'
        verbose_name_plural  = 'Lotes de Contracheques'
        ordering             = ['-criado_em']

    def __str__(self):
        ref = f'{self.mes:02d}/{self.ano}' if self.mes and self.ano else 'competência a definir'
        return f'Lote #{self.pk} — {ref} ({self.get_status_display()})'

    @property
    def progresso_pct(self):
        if not self.total_paginas:
            return 0
        return min(100, int((self.paginas_processadas / self.total_paginas) * 100))

    @property
    def pendencias_count(self):
        return self.contracheques.filter(status=Contracheque.Status.PENDENTE).count()

    @property
    def sem_correspondencia_count(self):
        return self.contracheques.filter(status=Contracheque.Status.SEM_CORRESPONDENCIA).count()

    def nome_arquivo(self):
        return os.path.basename(self.arquivo_original.name) if self.arquivo_original else ''


class Contracheque(models.Model):
    """
    Um contracheque individual — uma página (ou meia-página, em layouts
    com 2 colaboradores por folha) do PDF do lote, já identificada e
    vinculada a UM UsuarioPerfil. É o que o colaborador vê/baixa na sua
    área pessoal.

    status:
      CONFIRMADO           -> perfil preenchido, já visível para o colaborador.
      PENDENTE              -> o OCR leu um nome mas o match não foi forte o
                                bastante para confirmar sozinho; perfil_sugerido
                                traz o "melhor palpite" para o RH revisar.
      SEM_CORRESPONDENCIA   -> nenhum colaborador cadastrado bateu com o nome
                                extraído (ou o RH marcou manualmente assim).
    """

    class Status(models.TextChoices):
        PENDENTE             = 'PENDENTE', 'Aguardando Confirmação'
        CONFIRMADO           = 'CONFIRMADO', 'Confirmado'
        SEM_CORRESPONDENCIA  = 'SEM_CORRESPONDENCIA', 'Sem Correspondência'

    lote = models.ForeignKey(LoteContracheque, on_delete=models.CASCADE, related_name='contracheques')

    perfil = models.ForeignKey(
        'UsuarioPerfil', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contracheques', verbose_name='Colaborador (confirmado)',
    )
    perfil_sugerido = models.ForeignKey(
        'UsuarioPerfil', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contracheques_sugeridos', verbose_name='Colaborador (sugestão automática)',
    )

    mes = models.PositiveSmallIntegerField('Mês')
    ano = models.PositiveSmallIntegerField('Ano')
    numero_pagina = models.PositiveIntegerField('Página no PDF original')

    arquivo = models.FileField('PDF do Contracheque', upload_to='contracheques/recibos/%Y/%m/')

    # snapshot do que foi lido via OCR — fica registrado para auditoria,
    # mesmo depois que o RH confirma/ajusta o vínculo manualmente.
    nome_extraido       = models.CharField('Nome extraído (OCR)', max_length=180, blank=True)
    cargo_extraido      = models.CharField('Cargo extraído (OCR)', max_length=180, blank=True)
    codigo_funcionario  = models.CharField('Código do Funcionário (folha)', max_length=20, blank=True)

    valor_bruto      = models.DecimalField('Total de Vencimentos', max_digits=10, decimal_places=2, null=True, blank=True)
    valor_descontos  = models.DecimalField('Total de Descontos',   max_digits=10, decimal_places=2, null=True, blank=True)
    valor_liquido    = models.DecimalField('Valor Líquido',        max_digits=10, decimal_places=2, null=True, blank=True)

    score_match = models.DecimalField('Confiança do Match (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PENDENTE)

    confirmado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='contracheques_confirmados')
    confirmado_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Contracheque'
        verbose_name_plural  = 'Contracheques'
        ordering             = ['-ano', '-mes', 'perfil__user__first_name']
        constraints = [
            # Um colaborador só pode ter UM contracheque confirmado por
            # competência (mês/ano). Itens ainda não confirmados (perfil
            # nulo) não entram nessa restrição.
            models.UniqueConstraint(
                fields=['perfil', 'mes', 'ano'],
                condition=models.Q(perfil__isnull=False),
                name='uniq_contracheque_perfil_mes_ano',
            )
        ]

    def __str__(self):
        quem = self.perfil.user.get_full_name() if self.perfil else (self.nome_extraido or 'não identificado')
        return f'Contracheque — {quem} — {self.mes:02d}/{self.ano}'

    def nome_arquivo(self):
        return os.path.basename(self.arquivo.name) if self.arquivo else ''

    @property
    def mes_nome(self):
        meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        try:
            return meses[self.mes]
        except (IndexError, TypeError):
            return str(self.mes)

    @property
    def competencia_label(self):
        return f'{self.mes_nome} de {self.ano}'