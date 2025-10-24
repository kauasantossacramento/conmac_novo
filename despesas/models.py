from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

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
        PENDENTE = "PENDENTE", "Pendente (não analisada)"
        APROVADA = "APROVADA", "Aprovada (paga)"
        REPROVADA = "REPROVADA", "Reprovada"

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="despesas")
    centro = models.ForeignKey(CentroDeCusto, on_delete=models.PROTECT, related_name="despesas")
    titulo = models.CharField(max_length=160)
    data_fato = models.DateField(help_text="Data do gasto (nota/comprovante)")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.TextField(blank=True)
    comprovante = models.FileField(upload_to="receipts/%Y/%m/", blank=True, null=True)
    comprovante_pagamento = models.FileField(upload_to="reembolsos/%Y/%m/", blank=True, null=True)
    pago_em = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDENTE)
    criado_em = models.DateTimeField(auto_now_add=True)   # mês de CADASTRO (regra do Admin)
    atualizado_em = models.DateTimeField(auto_now=True)
    observacao_admin = models.TextField(blank=True)
    
    edit_count = models.PositiveSmallIntegerField(default=0)
    
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