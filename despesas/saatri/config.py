"""
Configuracao fixa do prestador (CONMAC) para emissao de NFS-e direto no
Web Service SAATRI/ADM Sistemas de Oliveira dos Brejinhos/BA.

Estes dados sao os mesmos ja validados e testados em producao no projeto
nfse_project (RPS 3255/serie 9000 -> NFS-e 3254 emitida com sucesso em
18/08/2026). O ISS e sempre devido no municipio do PRESTADOR (Oliveira dos
Brejinhos), independente de qual prefeitura/orgao e o TOMADOR do contrato —
por isso esses dados sao fixos e nao variam por contrato.

O TOMADOR de cada nota (cliente do contrato) e buscado dinamicamente na
Omie a cada emissao — ver OmieService.consultar_cliente_completo().
"""

PRESTADOR = {
    "cnpj": "17449551000130",
    "inscricao_municipal": "74001189",
    "razao_social": "CONMAC - SERVIÇOS CONTABEIS, TREINAMENTO E DESENVOLVIMENTO LTDA",
    "nome_fantasia": "CONMAC - CONSULTORIA CONTABIL PARA AREA MUNICIPAL",
    "logradouro": "PÇA JOÃO NERY DE SANTANA",
    "numero": "165",
    "complemento": "",
    "bairro": "CENTRO",
    "codigo_municipio": "2923209",  # Oliveira dos Brejinhos/BA (IBGE)
    "uf": "BA",
    "cep": "47530000",
    "codigo_pais": "1058",
    "telefone": "(71) 3901-0867",
    "email": "contato@conmac.com.br",
    # Credenciais WS-Security (UsernameToken) do portal SAATRI
    "ws_usuario": "00625585526",
    "ws_senha": "18181818",
    # Tributacao — confirmado com a prefeitura em 18/08/2026: "Sociedade de
    # Profissionais". NAO e optante do Simples Nacional nesse regime.
    "regime_especial_tributacao": "3",
    "optante_simples": "1",
    "incentivo_fiscal": "2",
    # Serie reservada para emissao via Web Service (a "75688" e reservada
    # para NFS-e emitidas pelo site do SAATRI — nao usar).
    "serie_rps": "9000",
    "ambiente": "producao",
}

ENDPOINTS = {
    "homologacao": "https://homologa-oliveiradosbrejinhos.saatri.com.br/servicos/nfse.svc",
    "producao": "https://oliveiradosbrejinhos.saatri.com.br/servicos/nfse.svc",
}

# Item/NBS padrao usados pela CONMAC para os servicos de assessoria/
# consultoria contabil municipal — mesmos valores ja usados no fluxo Omie
# (OmieService.alterar_contrato_lote: PADRAO_COD_SERV_MUNIC/PADRAO_NBS).
ITEM_LISTA_SERVICO_PADRAO = "17.19.01"
CODIGO_NBS_PADRAO = "113022100"
ALIQUOTA_ISS_PADRAO = "2.00"


def get_endpoint():
    return ENDPOINTS[PRESTADOR["ambiente"]]
