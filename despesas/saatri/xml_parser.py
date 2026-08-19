"""
Parser de respostas XML do Web Service NFS-e SAATRI.

Portado do nfse_project — já inclui a correção para respostas sem CDATA
(o WCF as vezes serializa outputXML com entidades XML escapadas em vez de
CDATA; sem o unescape() o parser falhava silenciosamente mesmo em sucesso).
"""
import re
from decimal import Decimal, InvalidOperation
from xml.sax.saxutils import unescape
from lxml import etree
import logging

logger = logging.getLogger(__name__)

NS = {"nfse": "http://www.abrasf.org.br/nfse.xsd"}


def _safe_decimal(text):
    try:
        return Decimal(text.strip()) if text else Decimal("0")
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def _safe_text(el, xpath, default=""):
    found = el.find(xpath, NS)
    if found is not None and found.text:
        return found.text.strip()
    return default


def extrair_xml_negocio(soap_response_text):
    """Extrai o XML de negocio de dentro do outputXML da resposta SOAP."""
    match = re.search(
        r"<outputXML[^>]*>\s*<!\[CDATA\[\s*(.*?)\s*\]\]>\s*</outputXML>",
        soap_response_text,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    match = re.search(
        r"<outputXML[^>]*>(.*?)</outputXML>",
        soap_response_text,
        re.DOTALL,
    )
    if match:
        return unescape(match.group(1).strip())

    logger.warning("Não foi possível extrair outputXML da resposta SOAP.")
    return soap_response_text


def parse_lista_nfse(xml_text):
    """Retorna lista de dicts com dados de cada NFS-e (ListaNfse/CompNfse)."""
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        logger.error("Erro de parse XML: %s", e)
        return []

    notas = []
    for comp in root.iter("{http://www.abrasf.org.br/nfse.xsd}CompNfse"):
        nfse_el = comp.find("nfse:Nfse", NS)
        if nfse_el is None:
            continue
        inf = nfse_el.find("nfse:InfNfse", NS)
        if inf is None:
            continue

        nota = {
            "numero": _safe_text(inf, "nfse:Numero"),
            "codigo_verificacao": _safe_text(inf, "nfse:CodigoVerificacao"),
            "data_emissao": _safe_text(inf, "nfse:DataEmissao"),
            "base_calculo": _safe_decimal(_safe_text(inf, "nfse:ValoresNfse/nfse:BaseCalculo", "0")),
            "aliquota": _safe_decimal(_safe_text(inf, "nfse:ValoresNfse/nfse:Aliquota", "0")),
            "valor_iss": _safe_decimal(_safe_text(inf, "nfse:ValoresNfse/nfse:ValorIss", "0")),
            "valor_liquido": _safe_decimal(_safe_text(inf, "nfse:ValoresNfse/nfse:ValorLiquidoNfse", "0")),
        }

        rps_el = inf.find(".//nfse:DeclaracaoPrestacaoServico//nfse:IdentificacaoRps", NS)
        if rps_el is not None:
            nota["rps_numero"] = _safe_text(rps_el, "nfse:Numero")
            nota["rps_serie"] = _safe_text(rps_el, "nfse:Serie")
            nota["rps_tipo"] = _safe_text(rps_el, "nfse:Tipo")

        # ── Dados do tomador e do serviço (usados na Importação Manual) ──
        cnpj_tomador = _safe_text(inf, ".//nfse:Tomador/nfse:IdentificacaoTomador/nfse:CpfCnpj/nfse:Cnpj")
        if not cnpj_tomador:
            cnpj_tomador = _safe_text(inf, ".//nfse:Tomador/nfse:IdentificacaoTomador/nfse:CpfCnpj/nfse:Cpf")
        nota["cnpj_tomador"] = cnpj_tomador
        nota["cliente_nome"] = _safe_text(inf, ".//nfse:Tomador/nfse:RazaoSocial")
        nota["descricao"] = _safe_text(inf, ".//nfse:Servico/nfse:Discriminacao")
        nota["valor_bruto"] = _safe_decimal(_safe_text(inf, ".//nfse:Servico/nfse:Valores/nfse:ValorServicos", "0"))
        nota["competencia"] = _safe_text(inf, ".//nfse:Competencia") or nota["data_emissao"]

        nota["xml_completo"] = etree.tostring(comp, encoding="unicode", pretty_print=True)
        notas.append(nota)

    return notas


def parse_lista_mensagens(xml_text):
    """Extrai mensagens de retorno (erro ou informativas) da resposta."""
    mensagens = []
    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except etree.XMLSyntaxError:
        return mensagens

    for msg in root.iter("{http://www.abrasf.org.br/nfse.xsd}MensagemRetorno"):
        mensagens.append({
            "codigo": _safe_text(msg, "nfse:Codigo"),
            "mensagem": _safe_text(msg, "nfse:Mensagem"),
            "correcao": _safe_text(msg, "nfse:Correcao"),
        })

    return mensagens


def parse_resposta_generica(xml_text):
    """
    Parse genérico de GerarNfse/ConsultarNfsePorRps: separa notas, erros e
    mensagens informativas (Código "0" = DPS aceita, NFS-e sai depois via
    SEFIN no Ambiente Nacional — não é erro).
    """
    notas = parse_lista_nfse(xml_text)
    todas_mensagens = parse_lista_mensagens(xml_text)
    erros = [m for m in todas_mensagens if m["codigo"] != "0"]
    info = [m for m in todas_mensagens if m["codigo"] == "0"]

    return {"notas": notas, "erros": erros, "info": info}
