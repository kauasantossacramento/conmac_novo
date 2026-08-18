'''
#importação:

import csv
import hashlib
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ── Ajuste o import abaixo para o nome real do seu app ──────────────────────
from despesas.models import Contrato, NotaFiscal, RecebimentoNota
# ─────────────────────────────────────────────────────────────────────────────

ALIAS_MUNICIPIOS = {
    "MUQUÉM DE SÃO FRANCISCO":  "MUQUÉM DO SÃO FRANCISCO",
    "MUQUEM DE SAO FRANCISCO":  "MUQUÉM DO SÃO FRANCISCO",
    "SANTO ESTÊVÃO":            "SANTO ESTEVÃO",
    "JIQUIRIÇÁ":                "JEQUIRIÇA",
    "JIQUIRIÇA":                "JEQUIRIÇA",
}

def _detect_encoding(caminho: str) -> str:
    with open(caminho, 'rb') as f:
        raw = f.read(10000)
    if b'\xef\xbb\xbf' in raw:
        return 'utf-8-sig'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'windows-1252'

def _sem_acento(texto: str) -> str:
    if not texto: return ""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _normalizar_municipio(nome: str) -> str:
    if not nome: return ""
    nome = nome.strip().upper()
    nome = ALIAS_MUNICIPIOS.get(nome, nome)
    import unicodedata
    return unicodedata.normalize("NFC", nome)

def _parse_valor(valor_str) -> Decimal:
    if valor_str is None or str(valor_str).strip() in ("", "nan", "None"):
        return Decimal("0.00")
    v = str(valor_str).strip().replace(",", ".")
    try:
        return Decimal(v).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")

def _parse_data(data_str) -> "date | None":
    if not data_str or str(data_str).strip() in ("", "nan", "None"):
        return None
    s = str(data_str).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _sintetico_id(numero_nfse, data_str, municipio, tipo_entidade, valor) -> int:
    chave = f"{numero_nfse}|{data_str}|{municipio}|{tipo_entidade}|{valor}"
    h = int(hashlib.md5(chave.encode("utf-8")).hexdigest(), 16) % (10**15)
    return -h

def _ler_csv(caminho: str) -> list[dict]:
    linhas = []
    encoding = _detect_encoding(caminho)
    with open(caminho, newline="", encoding=encoding, errors="replace") as f:
        amostra = f.read(4096)
        f.seek(0)
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimitador)
        for row in reader:
            nova_row = {}
            for k, v in row.items():
                if k:
                    k_norm = _sem_acento(k.strip().lower()).replace(" ", "_")
                    nova_row[k_norm] = v.strip() if v else ""
            linhas.append(nova_row)
    return linhas

class IndiceContratos:
    def __init__(self, linhas_csv: list[dict]):
        self._idx_exato = {}
        self._idx_mun_tipo = {}

        for row in linhas_csv:
            pk = self._int(row.get("id"))
            if pk is None: continue
            mun = _normalizar_municipio(row.get("municipio", ""))
            tipo = (row.get("tipo_entidade") or "").strip().lower()
            valor = _parse_valor(row.get("valor_mensal"))

            self._idx_exato[(mun, tipo, valor)] = pk
            self._idx_mun_tipo.setdefault((mun, tipo), []).append(pk)

    @staticmethod
    def _int(v):
        try: return int(str(v).strip())
        except: return None

    def buscar(self, municipio_nota: str, tipo_entidade: str, valor: Decimal):
        mun = _normalizar_municipio(municipio_nota)
        tipo = (tipo_entidade or "").strip().lower()

        # REGRA CUSTOMIZADA: ITABUNA -> ID 103
        if mun == "ITABUNA":
            return 103, "regra_customizada_itabuna"

        if pk := self._idx_exato.get((mun, tipo, valor)):
            return pk, "exato"
        if lista := self._idx_mun_tipo.get((mun, tipo)):
            return lista[0], "municipio+tipo"
        return None, "sem_match"

class Command(BaseCommand):
    help = "Importa notas fiscais e concilia pagamentos, listando exceções."

    def add_arguments(self, parser):
        parser.add_argument("notas_csv", type=str)
        parser.add_argument("contratos_csv", type=str)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        notas_path = options["notas_csv"]
        contratos_path = options["contratos_csv"]
        dry_run = options["dry_run"]

        base_dir = Path(__file__).parent
        if not Path(notas_path).is_absolute(): 
            notas_path = str(base_dir / notas_path)
        if not Path(contratos_path).is_absolute(): 
            contratos_path = str(base_dir / contratos_path)

        for p in (notas_path, contratos_path):
            if not os.path.exists(p):
                raise CommandError(f"\nArquivo não encontrado: {p}\n")

        linhas_notas = _ler_csv(notas_path)
        linhas_contratos = _ler_csv(contratos_path)
        indice = IndiceContratos(linhas_contratos)

        contadores = {
            "criadas": 0, "existentes": 0, "pagamentos_confirmados": 0,
            "sem_contrato": 0, "itabuna_processadas": 0, "itabuna_pagas": 0
        }

        log_sem_contrato = []
        log_nao_pagas = []

        with transaction.atomic():
            for row in linhas_notas:
                num = row.get("numero_nfse", "").strip()
                if not num: continue

                mun = row.get("municipio", "").strip()
                tipo_ent = row.get("tipo_entidade", "").strip().lower()
                data_str = row.get("data_emissao", "").strip()
                valor_str = row.get("valor_mensal", "").strip()
                pago_str = str(row.get("pago_ou_nao", "")).strip().upper()

                data_emissao = _parse_data(data_str)
                valor = _parse_valor(valor_str)
                pago = (pago_str == "SIM")

                if not pago:
                    log_nao_pagas.append((num, mun, data_str, valor))

                if _normalizar_municipio(mun) == "ITABUNA":
                    contadores["itabuna_processadas"] += 1
                    if pago: contadores["itabuna_pagas"] += 1

                id_sintetico = _sintetico_id(num, data_str, mun, tipo_ent, valor_str)
                nota_obj = NotaFiscal.objects.filter(omie_nfse_id=id_sintetico).first()

                if not nota_obj:
                    contrato_pk, _ = indice.buscar(mun, tipo_ent, valor)
                    contrato_obj = Contrato.objects.filter(pk=contrato_pk).first() if contrato_pk else None
                    
                    if not contrato_obj: 
                        contadores["sem_contrato"] += 1
                        log_sem_contrato.append((num, mun, tipo_ent, valor))

                    nota_obj = NotaFiscal(
                        omie_nfse_id=id_sintetico, numero_nfse=num, contrato=contrato_obj,
                        cliente_nome=row.get("cliente_nome", "") or (contrato_obj.cliente_nome if contrato_obj else ""),
                        valor_bruto=valor, valor_liquido=valor, data_emissao=data_emissao,
                        competencia_mes=data_emissao.month if data_emissao else 1, 
                        competencia_ano=data_emissao.year if data_emissao else 2025,
                        descricao="Importado via CSV histórico"
                    )
                    if not dry_run: 
                        nota_obj.save()
                    contadores["criadas"] += 1
                else:
                    contadores["existentes"] += 1

                if pago:
                    if not dry_run and nota_obj.pk:
                        recebimento, created = RecebimentoNota.objects.get_or_create(
                            nota=nota_obj,
                            defaults={'confirmado': True, 'valor_recebido': valor, 'observacao': 'Confirmado via CSV'}
                        )
                        if created or not recebimento.confirmado:
                            recebimento.confirmado = True
                            recebimento.save()
                            contadores["pagamentos_confirmados"] += 1
                    elif dry_run:
                        contadores["pagamentos_confirmados"] += 1

            if dry_run: transaction.set_rollback(True)

        self.stdout.write(self.style.MIGRATE_HEADING("\n─── Resultado Geral ───"))
        self.stdout.write(f"  Notas Criadas/Processadas:    {contadores['criadas']}")
        self.stdout.write(f"  Notas Já Existentes (Puladas):{contadores['existentes']}")
        self.stdout.write(self.style.SUCCESS(f"  Pagamentos Confirmados:       {contadores['pagamentos_confirmados']}"))
        
        self.stdout.write(self.style.MIGRATE_HEADING("\n─── Verificação Itabuna ───"))
        self.stdout.write(f"  Notas de Itabuna encontradas: {contadores['itabuna_processadas']}")
        self.stdout.write(f"  Notas de Itabuna com 'Sim':   {contadores['itabuna_pagas']}")

        if log_sem_contrato:
            self.stdout.write(self.style.ERROR(f"\n─── Notas Sem Contrato Vinculado ({len(log_sem_contrato)}) ───"))
            for num, mun, tipo, val in log_sem_contrato:
                self.stdout.write(f"  NF: {num:>6} | Município: {mun[:20]:<20} | Entidade: {tipo:<10} | Valor: R$ {val}")

        if log_nao_pagas:
            self.stdout.write(self.style.WARNING(f"\n─── Notas Não Pagas ({len(log_nao_pagas)}) ───"))
            for num, mun, data, val in log_nao_pagas:
                self.stdout.write(f"  NF: {num:>6} | Município: {mun[:20]:<20} | Data: {data:<10} | Valor: R$ {val}")

        self.stdout.write(self.style.SUCCESS(f"\n═══ IMPORTAÇÃO {'DRY-RUN' if dry_run else 'CONCLUÍDA'} ═══\n"))
'''
#limpeza:

'''
import csv
import hashlib
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ── Ajuste o import abaixo para o nome real do seu app ──────────────────────
from despesas.models import NotaFiscal  # ← mude "conmac" se necessário
# ─────────────────────────────────────────────────────────────────────────────

def _detect_encoding(caminho: str) -> str:
    with open(caminho, 'rb') as f:
        raw = f.read(10000)
    if b'\xef\xbb\xbf' in raw:
        return 'utf-8-sig'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'windows-1252'

def _sem_acento(texto: str) -> str:
    if not texto: return ""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _sintetico_id(numero_nfse, data_str, municipio, tipo_entidade, valor) -> int:
    chave = f"{numero_nfse}|{data_str}|{municipio}|{tipo_entidade}|{valor}"
    h = int(hashlib.md5(chave.encode("utf-8")).hexdigest(), 16) % (10**15)
    return -h

def _ler_csv(caminho: str) -> list[dict]:
    linhas = []
    encoding = _detect_encoding(caminho)
    with open(caminho, newline="", encoding=encoding, errors="replace") as f:
        amostra = f.read(4096)
        f.seek(0)
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimitador)
        for row in reader:
            nova_row = {}
            for k, v in row.items():
                if k:
                    k_norm = _sem_acento(k.strip().lower()).replace(" ", "_")
                    nova_row[k_norm] = v.strip() if v else ""
            linhas.append(nova_row)
    return linhas

class Command(BaseCommand):
    help = "Remove notas fiscais que foram importadas com o status de pagamento em branco (canceladas)."

    def add_arguments(self, parser):
        parser.add_argument("notas_csv", type=str)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        notas_path = options["notas_csv"]
        dry_run = options["dry_run"]

        base_dir = Path(__file__).parent
        if not Path(notas_path).is_absolute(): 
            notas_path = str(base_dir / notas_path)

        if not os.path.exists(notas_path):
            raise CommandError(f"Arquivo não encontrado: {notas_path}")

        linhas_notas = _ler_csv(notas_path)
        
        removidas = 0
        nao_encontradas = 0

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n═══ LIMPANDO NOTAS CANCELADAS (Vazias no CSV) ═══"))
        if dry_run:
            self.stdout.write(self.style.WARNING("  ⚠  MODO DRY-RUN — nada será excluído.\n"))

        with transaction.atomic():
            for row in linhas_notas:
                pago_str = str(row.get("pago_ou_nao", "")).strip().upper()
                
                # Regra: Se estiver em branco, é cancelada e deve ser removida
                if pago_str in ("", "NAN", "NONE"):
                    num = row.get("numero_nfse", "").strip()
                    mun = row.get("municipio", "").strip()
                    tipo = row.get("tipo_entidade", "").strip().lower()
                    data = row.get("data_emissao", "").strip()
                    val = row.get("valor_mensal", "").strip()

                    id_sintetico = _sintetico_id(num, data, mun, tipo, val)
                    
                    nota = NotaFiscal.objects.filter(omie_nfse_id=id_sintetico).first()
                    
                    if nota:
                        if not dry_run:
                            nota.delete()
                        removidas += 1
                    else:
                        nao_encontradas += 1

            if dry_run: transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(f"\n  Notas removidas: {removidas}"))
        self.stdout.write(f"  Notas vazias no CSV que não estavam no banco: {nao_encontradas}")
        self.stdout.write(self.style.SUCCESS(f"\n═══ LIMPEZA {'DRY-RUN' if dry_run else 'CONCLUÍDA'} ═══\n"))
'''

#importar pendências:

import csv
import hashlib
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# ── Ajuste o import abaixo para o nome real do seu app ──────────────────────
from despesas.models import Contrato, NotaFiscal, RecebimentoNota
# ─────────────────────────────────────────────────────────────────────────────

ALIAS_MUNICIPIOS = {
    "JIQUIRIÇÁ":                "JEQUIRIÇA",
    "JIQUIRIÇA":                "JEQUIRIÇA",
    "CONCEIÇÃO DA FEIRA":       "CONCEIÇÃO DA FEIRA",
}

# Cidades alvo desta importação específica (nomes já normalizados)
ALVOS_IMPORTACAO = ["JEQUIRIÇA", "CONCEIÇÃO DA FEIRA"]

def _detect_encoding(caminho: str) -> str:
    with open(caminho, 'rb') as f:
        raw = f.read(10000)
    if b'\xef\xbb\xbf' in raw:
        return 'utf-8-sig'
    try:
        raw.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        return 'windows-1252'

def _sem_acento(texto: str) -> str:
    if not texto: return ""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _normalizar_municipio(nome: str) -> str:
    if not nome: return ""
    nome = nome.strip().upper()
    nome = ALIAS_MUNICIPIOS.get(nome, nome)
    import unicodedata
    return unicodedata.normalize("NFC", nome)

def _parse_valor(valor_str) -> Decimal:
    if valor_str is None or str(valor_str).strip() in ("", "nan", "None"):
        return Decimal("0.00")
    v = str(valor_str).strip().replace(",", ".")
    try:
        return Decimal(v).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")

def _parse_data(data_str) -> "date | None":
    if not data_str or str(data_str).strip() in ("", "nan", "None"):
        return None
    s = str(data_str).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _sintetico_id(numero_nfse, data_str, municipio, tipo_entidade, valor) -> int:
    chave = f"{numero_nfse}|{data_str}|{municipio}|{tipo_entidade}|{valor}"
    h = int(hashlib.md5(chave.encode("utf-8")).hexdigest(), 16) % (10**15)
    return -h

def _ler_csv(caminho: str) -> list[dict]:
    linhas = []
    encoding = _detect_encoding(caminho)
    with open(caminho, newline="", encoding=encoding, errors="replace") as f:
        amostra = f.read(4096)
        f.seek(0)
        delimitador = ";" if amostra.count(";") > amostra.count(",") else ","
        reader = csv.DictReader(f, delimiter=delimitador)
        for row in reader:
            nova_row = {}
            for k, v in row.items():
                if k:
                    k_norm = _sem_acento(k.strip().lower()).replace(" ", "_")
                    nova_row[k_norm] = v.strip() if v else ""
            linhas.append(nova_row)
    return linhas

class IndiceContratos:
    def __init__(self, linhas_csv: list[dict]):
        self._idx_exato = {}
        self._idx_mun_tipo = {}

        for row in linhas_csv:
            pk = self._int(row.get("id"))
            if pk is None: continue
            mun = _normalizar_municipio(row.get("municipio", ""))
            tipo = (row.get("tipo_entidade") or "").strip().lower()
            valor = _parse_valor(row.get("valor_mensal"))

            self._idx_exato[(mun, tipo, valor)] = pk
            self._idx_mun_tipo.setdefault((mun, tipo), []).append(pk)

    @staticmethod
    def _int(v):
        try: return int(str(v).strip())
        except: return None

    def buscar(self, municipio_nota: str, tipo_entidade: str, valor: Decimal):
        mun = _normalizar_municipio(municipio_nota)
        tipo = (tipo_entidade or "").strip().lower()

        if pk := self._idx_exato.get((mun, tipo, valor)):
            return pk, "exato"
        if lista := self._idx_mun_tipo.get((mun, tipo)):
            return lista[0], "municipio+tipo"
        return None, "sem_match"

class Command(BaseCommand):
    help = "Importa EXCLUSIVAMENTE notas de Conceição da Feira e Jiquiriçá."

    def add_arguments(self, parser):
        parser.add_argument("notas_csv", type=str)
        parser.add_argument("contratos_csv", type=str)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        notas_path = options["notas_csv"]
        contratos_path = options["contratos_csv"]
        dry_run = options["dry_run"]

        base_dir = Path(__file__).parent
        if not Path(notas_path).is_absolute(): notas_path = str(base_dir / notas_path)
        if not Path(contratos_path).is_absolute(): contratos_path = str(base_dir / contratos_path)

        linhas_notas = _ler_csv(notas_path)
        linhas_contratos = _ler_csv(contratos_path)
        indice = IndiceContratos(linhas_contratos)

        contadores = {"criadas": 0, "existentes": 0, "pagamentos_confirmados": 0, "sem_contrato": 0}
        log_processadas = []

        self.stdout.write(self.style.MIGRATE_HEADING("\n═══ IMPORTAÇÃO FOCADA (Conceição da Feira e Jiquiriçá) ═══"))

        with transaction.atomic():
            for row in linhas_notas:
                mun_cru = row.get("municipio", "").strip()
                mun_norm = _normalizar_municipio(mun_cru)

                # FILTRO PRINCIPAL: Pula qualquer cidade que não seja os nossos alvos
                if mun_norm not in ALVOS_IMPORTACAO:
                    continue

                num = row.get("numero_nfse", "").strip()
                pago_str = str(row.get("pago_ou_nao", "")).strip().upper()

                # IGNORA CANCELADAS (Vazias)
                if pago_str in ("", "NAN", "NONE") or not num:
                    continue

                tipo_ent = row.get("tipo_entidade", "").strip().lower()
                data_str = row.get("data_emissao", "").strip()
                valor_str = row.get("valor_mensal", "").strip()
                
                data_emissao = _parse_data(data_str)
                valor = _parse_valor(valor_str)
                pago = (pago_str == "SIM")

                id_sintetico = _sintetico_id(num, data_str, mun_norm, tipo_ent, valor_str)
                nota_obj = NotaFiscal.objects.filter(omie_nfse_id=id_sintetico).first()

                if not nota_obj:
                    contrato_pk, _ = indice.buscar(mun_cru, tipo_ent, valor)
                    contrato_obj = Contrato.objects.filter(pk=contrato_pk).first() if contrato_pk else None
                    
                    if not contrato_obj: 
                        contadores["sem_contrato"] += 1
                        log_processadas.append(f"⚠️ SEM CONTRATO - NF {num}: {mun_norm} | R$ {valor}")
                    else:
                        log_processadas.append(f"✅ OK - NF {num}: {mun_norm} | R$ {valor}")

                    nota_obj = NotaFiscal(
                        omie_nfse_id=id_sintetico, numero_nfse=num, contrato=contrato_obj,
                        cliente_nome=row.get("cliente_nome", "") or (contrato_obj.cliente_nome if contrato_obj else ""),
                        valor_bruto=valor, valor_liquido=valor, data_emissao=data_emissao,
                        competencia_mes=data_emissao.month if data_emissao else 1,
                        competencia_ano=data_emissao.year if data_emissao else 2025,
                        status='emitida', descricao="Importado via CSV (Script Pendentes)"
                    )
                    if not dry_run: nota_obj.save()
                    contadores["criadas"] += 1
                else:
                    contadores["existentes"] += 1
                    log_processadas.append(f"🔄 JÁ EXISTE - NF {num}: {mun_norm}")

                # Processa Recebimento
                if pago:
                    if not dry_run and nota_obj.pk:
                        recebimento, created = RecebimentoNota.objects.get_or_create(
                            nota=nota_obj,
                            defaults={'confirmado': True, 'valor_recebido': valor, 'observacao': 'Confirmado via Script Pendentes'}
                        )
                        if not created and not recebimento.confirmado:
                            recebimento.confirmado = True
                            recebimento.save()
                        contadores["pagamentos_confirmados"] += 1
                    elif dry_run:
                        contadores["pagamentos_confirmados"] += 1

            if dry_run: transaction.set_rollback(True)

        self.stdout.write(self.style.MIGRATE_HEADING("\n─── Detalhes das Notas Processadas ───"))
        for log in log_processadas:
            if "✅" in log: self.stdout.write(self.style.SUCCESS(f"  {log}"))
            elif "⚠️" in log: self.stdout.write(self.style.ERROR(f"  {log}"))
            else: self.stdout.write(self.style.WARNING(f"  {log}"))

        self.stdout.write(self.style.MIGRATE_HEADING("\n─── Resultado Final ───"))
        self.stdout.write(f"  Novas Notas (Conceição/Jiquiriçá): {contadores['criadas']}")
        self.stdout.write(f"  Notas Já Existentes (Puladas):     {contadores['existentes']}")
        self.stdout.write(self.style.SUCCESS(f"  Pagamentos Confirmados:            {contadores['pagamentos_confirmados']}"))
        self.stdout.write(self.style.ERROR(f"  Sem Contrato Vinculado:            {contadores['sem_contrato']}"))
        
        self.stdout.write(self.style.SUCCESS(f"\n═══ IMPORTAÇÃO {'DRY-RUN' if dry_run else 'CONCLUÍDA'} ═══\n"))