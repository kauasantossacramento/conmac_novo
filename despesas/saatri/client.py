"""
Cliente SOAP para o Web Service NFS-e SAATRI — portado do nfse_project.

IMPORTANTE (causa raiz de um HTTP 500 já depurado em produção): o SOAPAction
precisa bater exatamente com o WSDL do serviço, incluindo o segmento
"/Infse/". Sem isso o WCF responde com SOAP Fault a:ActionNotSupported,
que o requests recebe como HTTP 500.
"""
import time
import logging
import requests

from . import config, xml_builder, xml_parser

logger = logging.getLogger(__name__)

METODOS = {
    "GerarNfse": ("http://nfse.abrasf.org.br/Infse/GerarNfse", "GerarNfseRequest"),
    "ConsultarNfsePorRps": ("http://nfse.abrasf.org.br/Infse/ConsultarNfsePorRps", "ConsultarNfsePorRpsRequest"),
}

TIMEOUT = 60


def _enviar_soap(metodo, dados_xml):
    """
    Envia a requisição SOAP e retorna (xml_negocio, log_obj_nao_salvo).
    Quem chama decide se/quando salvar o log (LogSaatri).
    """
    from ..models import LogSaatri

    soap_action, request_element = METODOS[metodo]
    endpoint = config.get_endpoint()
    envelope = xml_builder.build_soap_envelope(request_element, dados_xml)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soap_action,
    }

    log = LogSaatri(metodo=metodo, url=endpoint, xml_envio=envelope)
    inicio = time.time()

    try:
        resp = requests.post(endpoint, data=envelope.encode("utf-8"), headers=headers, timeout=TIMEOUT)
        log.duracao_ms = int((time.time() - inicio) * 1000)
        log.http_status = resp.status_code
        log.xml_retorno = resp.text

        if resp.status_code == 200:
            xml_negocio = xml_parser.extrair_xml_negocio(resp.text)
            mensagens = xml_parser.parse_lista_mensagens(xml_negocio)
            erros = [m for m in mensagens if m["codigo"] != "0"]
            log.sucesso = len(erros) == 0
            if erros:
                log.erro = "; ".join(f"[{e['codigo']}] {e['mensagem']}" for e in erros)
        else:
            log.sucesso = False
            log.erro = f"HTTP {resp.status_code}"
            xml_negocio = resp.text

    except requests.RequestException as e:
        log.duracao_ms = int((time.time() - inicio) * 1000)
        log.sucesso = False
        log.erro = str(e)
        xml_negocio = ""
        logger.exception("Erro na chamada SOAP SAATRI %s", metodo)

    log.save()
    return xml_negocio, log


def gerar_nfse(rps, tomador):
    """
    rps / tomador: dicts (ver saatri.xml_builder). Retorna dict com
    'notas' (lista, quando a resposta já vem sincrona), 'info' (mensagens
    tipo "DPS aceita, consulte em 5 min" — Ambiente Nacional/Reforma
    Tributária) e 'erros'.
    """
    dados = xml_builder.build_gerar_nfse(rps, tomador)
    xml_resp, log = _enviar_soap("GerarNfse", dados)
    resultado = xml_parser.parse_resposta_generica(xml_resp)
    resultado["log"] = log
    return resultado


def consultar_nfse_por_rps(numero_rps, serie, tipo="1"):
    dados = xml_builder.build_consultar_nfse_por_rps(numero_rps, serie, tipo)
    xml_resp, log = _enviar_soap("ConsultarNfsePorRps", dados)
    resultado = xml_parser.parse_resposta_generica(xml_resp)
    resultado["log"] = log
    return resultado


def baixar_pdf_nfse(numero_nfse, codigo_verificacao):
    """
    Baixa o DANFSe (PDF) público do portal SAATRI. Retorna bytes do PDF ou
    None se a resposta não for um PDF válido.
    """
    base = "https://oliveiradosbrejinhos.saatri.com.br"
    url = f"{base}/Relatorio/VisualizarNotaFiscal?numero={numero_nfse}&codigoVerificacao={codigo_verificacao}"
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
    except requests.RequestException:
        logger.exception("Erro ao baixar PDF da NFS-e %s", numero_nfse)
        return None

    if resp.status_code == 200 and "pdf" in resp.headers.get("Content-Type", "").lower():
        return resp.content
    return None
