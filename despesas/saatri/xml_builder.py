"""
Geracao de XML para o Web Service NFS-e SAATRI (ABRASF 2.03).

Portado do projeto nfse_project (ja testado em producao contra o WS real
de Oliveira dos Brejinhos), adaptado para trabalhar com dicts simples
(rps_data / tomador_data) em vez de instancias de model Django, já que
aqui os dados de RPS/tomador nascem da Omie a cada emissao.

Bugs ja corrigidos e validados no nfse_project (ver historico de testes
reais em producao) e replicados aqui:
  - Complemento/Telefone do tomador só entram no XML se preenchidos
    (o XSD aceita omitir a tag, mas rejeita tag vazia — erro E160).
  - ResponsavelRetencao só entra no XML quando IssRetido="1" (Sim) —
    do contrario dispara erro E333 para Sociedade de Profissionais.
"""
from decimal import Decimal

from . import config

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_NFSE = "http://nfse.abrasf.org.br"
NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
PASSWORD_TYPE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText"


def _fmt_decimal(v):
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return f"{float(v or 0):.2f}"


def _fmt_aliquota(v):
    if isinstance(v, Decimal):
        return f"{v:.10f}"
    return f"{float(v or 0):.10f}"


def _fmt_date(d):
    """Aceita date/datetime ou string 'YYYY-MM-DD' e devolve 'YYYY-MM-DD'."""
    if isinstance(d, str):
        return d[:10]
    return d.isoformat()[:10]


def build_cabecalho():
    return (
        '<cabecalho xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns="http://www.abrasf.org.br/nfse.xsd" versao="2.01">'
        "<versaoDados>2.03</versaoDados>"
        "</cabecalho>"
    )


def build_soap_envelope(metodo_request, dados_xml):
    """Monta o envelope SOAP com WS-Security e os dois blocos CDATA."""
    prestador = config.PRESTADOR
    cabecalho = build_cabecalho()

    return (
        f'<soapenv:Envelope xmlns:soapenv="{NS_SOAP}" xmlns:nfse="{NS_NFSE}">'
        f"<soapenv:Header>"
        f'<wsse:Security soapenv:mustUnderstand="1" '
        f'xmlns:wsse="{NS_WSSE}" xmlns:wsu="{NS_WSU}">'
        f'<wsse:UsernameToken wsu:Id="UsernameToken-1">'
        f"<wsse:Username>{prestador['ws_usuario']}</wsse:Username>"
        f'<wsse:Password Type="{PASSWORD_TYPE}">{prestador["ws_senha"]}</wsse:Password>'
        f"</wsse:UsernameToken>"
        f"</wsse:Security>"
        f"</soapenv:Header>"
        f"<soapenv:Body>"
        f"<nfse:{metodo_request}>"
        f"<nfseCabecMsg><![CDATA[{cabecalho}]]></nfseCabecMsg>"
        f"<nfseDadosMsg><![CDATA[{dados_xml}]]></nfseDadosMsg>"
        f"</nfse:{metodo_request}>"
        f"</soapenv:Body>"
        f"</soapenv:Envelope>"
    )


def _build_tomador_xml(tomador):
    """
    tomador: dict com chaves cpf_cnpj, is_cpf, razao_social, logradouro,
    numero, complemento, bairro, codigo_municipio, uf, codigo_pais, cep,
    telefone, email, inscricao_municipal (opcional).
    """
    cpf_cnpj_tag = "Cpf" if tomador.get("is_cpf") else "Cnpj"
    im = ""
    if tomador.get("inscricao_municipal"):
        im = f"<InscricaoMunicipal>{tomador['inscricao_municipal']}</InscricaoMunicipal>"
    complemento = ""
    if tomador.get("complemento"):
        complemento = f"<Complemento>{tomador['complemento']}</Complemento>"
    telefone = ""
    if tomador.get("telefone"):
        telefone = f"<Telefone>{tomador['telefone']}</Telefone>"

    return (
        f"<Tomador>"
        f"<IdentificacaoTomador>"
        f"<CpfCnpj><{cpf_cnpj_tag}>{tomador['cpf_cnpj']}</{cpf_cnpj_tag}></CpfCnpj>"
        f"{im}"
        f"</IdentificacaoTomador>"
        f"<RazaoSocial>{tomador['razao_social']}</RazaoSocial>"
        f"<Endereco>"
        f"<Endereco>{tomador['logradouro']}</Endereco>"
        f"<Numero>{tomador['numero']}</Numero>"
        f"{complemento}"
        f"<Bairro>{tomador['bairro']}</Bairro>"
        f"<CodigoMunicipio>{tomador['codigo_municipio']}</CodigoMunicipio>"
        f"<Uf>{tomador['uf']}</Uf>"
        f"<CodigoPais>{tomador.get('codigo_pais', '1058')}</CodigoPais>"
        f"<Cep>{tomador['cep']}</Cep>"
        f"</Endereco>"
        f"<Contato>"
        f"{telefone}"
        f"<Email>{tomador['email']}</Email>"
        f"</Contato>"
        f"</Tomador>"
    )


def _build_inf_declaracao(rps, tomador):
    """
    rps: dict com numero, serie, tipo, status_rps, data_emissao,
    competencia, valor_servicos, valor_deducoes, valor_pis, valor_cofins,
    valor_inss, valor_ir, valor_csll, outras_retencoes, valor_iss,
    aliquota, desconto_incondicionado, desconto_condicionado, iss_retido,
    responsavel_retencao, item_lista_servico, codigo_nbs, discriminacao,
    codigo_municipio_prestacao, exigibilidade_iss, municipio_incidencia.
    """
    prestador = config.PRESTADOR

    codigo_nbs = ""
    if rps.get("codigo_nbs"):
        codigo_nbs = f"<CodigoNbs>{rps['codigo_nbs']}</CodigoNbs>"

    responsavel_retencao = ""
    if rps.get("iss_retido") == "1" and rps.get("responsavel_retencao"):
        responsavel_retencao = f"<ResponsavelRetencao>{rps['responsavel_retencao']}</ResponsavelRetencao>"

    return (
        f'<InfDeclaracaoPrestacaoServico Id="Declaracao_{prestador["cnpj"]}">'
        f'<Rps Id="RPS_{rps["numero"]}{rps["serie"]}{rps["tipo"]}">'
        f"<IdentificacaoRps>"
        f"<Numero>{rps['numero']}</Numero>"
        f"<Serie>{rps['serie']}</Serie>"
        f"<Tipo>{rps['tipo']}</Tipo>"
        f"</IdentificacaoRps>"
        f"<DataEmissao>{_fmt_date(rps['data_emissao'])}</DataEmissao>"
        f"<Status>{rps.get('status_rps', '1')}</Status>"
        f"</Rps>"
        f"<Competencia>{_fmt_date(rps['competencia'])}</Competencia>"
        f"<Servico>"
        f"<Valores>"
        f"<ValorServicos>{_fmt_decimal(rps['valor_servicos'])}</ValorServicos>"
        f"<ValorDeducoes>{_fmt_decimal(rps.get('valor_deducoes', 0))}</ValorDeducoes>"
        f"<ValorPis>{_fmt_decimal(rps.get('valor_pis', 0))}</ValorPis>"
        f"<ValorCofins>{_fmt_decimal(rps.get('valor_cofins', 0))}</ValorCofins>"
        f"<ValorInss>{_fmt_decimal(rps.get('valor_inss', 0))}</ValorInss>"
        f"<ValorIr>{_fmt_decimal(rps.get('valor_ir', 0))}</ValorIr>"
        f"<ValorCsll>{_fmt_decimal(rps.get('valor_csll', 0))}</ValorCsll>"
        f"<OutrasRetencoes>{_fmt_decimal(rps.get('outras_retencoes', 0))}</OutrasRetencoes>"
        f"<ValorIss>{_fmt_decimal(rps['valor_iss'])}</ValorIss>"
        f"<Aliquota>{_fmt_aliquota(rps['aliquota'])}</Aliquota>"
        f"<DescontoIncondicionado>{_fmt_decimal(rps.get('desconto_incondicionado', 0))}</DescontoIncondicionado>"
        f"<DescontoCondicionado>{_fmt_decimal(rps.get('desconto_condicionado', 0))}</DescontoCondicionado>"
        f"</Valores>"
        f"<IssRetido>{rps.get('iss_retido', '2')}</IssRetido>"
        f"{responsavel_retencao}"
        f"<ItemListaServico>{rps['item_lista_servico']}</ItemListaServico>"
        f"{codigo_nbs}"
        f"<Discriminacao>{rps['discriminacao']}</Discriminacao>"
        f"<CodigoMunicipio>{prestador['codigo_municipio']}</CodigoMunicipio>"
        f"<CodigoPais>{prestador['codigo_pais']}</CodigoPais>"
        f"<ExigibilidadeISS>{rps.get('exigibilidade_iss', '1')}</ExigibilidadeISS>"
        f"<MunicipioIncidencia>{prestador['codigo_municipio']}</MunicipioIncidencia>"
        f"</Servico>"
        f"<Prestador>"
        f"<CpfCnpj><Cnpj>{prestador['cnpj']}</Cnpj></CpfCnpj>"
        f"<InscricaoMunicipal>{prestador['inscricao_municipal']}</InscricaoMunicipal>"
        f"</Prestador>"
        f"{_build_tomador_xml(tomador)}"
        f"<RegimeEspecialTributacao>{prestador['regime_especial_tributacao']}</RegimeEspecialTributacao>"
        f"<OptanteSimplesNacional>{prestador['optante_simples']}</OptanteSimplesNacional>"
        f"<IncentivoFiscal>{prestador['incentivo_fiscal']}</IncentivoFiscal>"
        f"</InfDeclaracaoPrestacaoServico>"
    )


def build_gerar_nfse(rps, tomador):
    """Monta o XML de GerarNfseEnvio (emissao avulsa de um RPS)."""
    inf = _build_inf_declaracao(rps, tomador)
    return (
        '<GerarNfseEnvio xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns="http://www.abrasf.org.br/nfse.xsd">'
        f"<Rps>{inf}</Rps>"
        "</GerarNfseEnvio>"
    )


def build_consultar_nfse_por_rps(numero_rps, serie, tipo="1"):
    prestador = config.PRESTADOR
    return (
        '<ConsultarNfseRpsEnvio xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns="http://www.abrasf.org.br/nfse.xsd">'
        "<IdentificacaoRps>"
        f"<Numero>{numero_rps}</Numero>"
        f"<Serie>{serie}</Serie>"
        f"<Tipo>{tipo}</Tipo>"
        "</IdentificacaoRps>"
        "<Prestador>"
        f"<CpfCnpj><Cnpj>{prestador['cnpj']}</Cnpj></CpfCnpj>"
        f"<InscricaoMunicipal>{prestador['inscricao_municipal']}</InscricaoMunicipal>"
        "</Prestador>"
        "</ConsultarNfseRpsEnvio>"
    )


def build_consultar_nfse_faixa(nfse_inicial, nfse_final=None, pagina=1):
    """
    Consulta por FAIXA de número da própria NFS-e (não RPS) — útil quando
    só se sabe o número da nota (ex.: notas antigas sincronizadas da Omie,
    que não têm o código de verificação salvo localmente). Passando
    inicial=final=<número desejado>, devolve só essa nota, com o
    CompNfse completo (inclui CodigoVerificacao).
    """
    prestador = config.PRESTADOR
    nfse_final = nfse_final if nfse_final is not None else nfse_inicial
    return (
        '<ConsultarNfseFaixaEnvio xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns="http://www.abrasf.org.br/nfse.xsd">'
        "<Prestador>"
        f"<CpfCnpj><Cnpj>{prestador['cnpj']}</Cnpj></CpfCnpj>"
        f"<InscricaoMunicipal>{prestador['inscricao_municipal']}</InscricaoMunicipal>"
        "</Prestador>"
        "<Faixa>"
        f"<NumeroNfseInicial>{nfse_inicial}</NumeroNfseInicial>"
        f"<NumeroNfseFinal>{nfse_final}</NumeroNfseFinal>"
        "</Faixa>"
        f"<Pagina>{pagina}</Pagina>"
        "</ConsultarNfseFaixaEnvio>"
    )
