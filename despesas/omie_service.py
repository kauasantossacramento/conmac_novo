import requests
import json
import re
import calendar
from django.conf import settings
from time import sleep
from datetime import datetime

# ── Endpoints ──────────────────────────────────────────────
URL_CONTRATO = "https://app.omie.com.br/api/v1/servicos/contrato/"
URL_CLIENTE  = "https://app.omie.com.br/api/v1/geral/clientes/"
URL_NFSE     = "https://app.omie.com.br/api/v1/servicos/nfse/"
URL_OSDOCS = "https://app.omie.com.br/api/v1/servicos/osdocs/"
URL_CONTRATO_FAT = "https://app.omie.com.br/api/v1/servicos/contratofat/"


def atualizar_competencia_em_descricao(desc_atual, mes_upper, ano):
    """
    Reescreve "MÊS DE <mes> DE <ano>" na descrição do serviço e reposiciona
    o bloco fixo (Mão de obra/Insumos + dados bancários/cláusula fiscal)
    logo após esse trecho.

    Função PURA (sem chamada de rede) — extraída de
    OmieService.alterar_contrato_lote para poder ser reaproveitada quando o
    usuário edita a competência SEM sincronizar com a Omie (atualiza só o
    cache local do Contrato). Mantém exatamente o mesmo comportamento de
    antes; qualquer ajuste no texto deve valer para os dois caminhos.
    """
    if not desc_atual:
        return desc_atual

    # Aceita com ou sem "DE" antes do mês (corrige erro de digitação em campo).
    # Sempre grava o formato correto: "MÊS DE <mes> DE <ano>".
    padrao = re.compile(
        r"(M[EÊ]S\s+)(?:DE\s+)?([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]+)(\s+DE\s+)(\d{4})",
        re.IGNORECASE | re.UNICODE,
    )
    nova_desc = padrao.sub(
        lambda m: m.group(1).strip() + " DE " + mes_upper + " DE " + str(ano),
        desc_atual,
    )

    BLOCO_BANCARIO = (
        '\n\nBANCO DO BRASIL\n'
        'AG:3025-2\n'
        'CONTA:46061-3\n'
        'CHAVE PIX: contato@conmac.com.br\n\n'
        'Não incidência na fonte do IRPJ, da Contribuição Social sobre o Lucro Líquido (CSLL), '
        'da Seguridade Social (INSS), da Contribuição para o Financiamento da Seguridade Social (COFINS), '
        'e da Contribuição para o PIS/PASEP, a que se refere o art. 64 da Lei nº 9.430, de 27 de dezembro '
        'de 1996, que é regularmente inscrita no Regime Especial Unificado de Arrecadação de Tributos e '
        'Contribuições devidos pelas Microempresas e Empresas de Pequeno Porte - Simples Nacional, de que '
        'trata o art. 12 da Lei Complementar 123, de 14 de dezembro de 2006.'
    )

    # Sempre reposiciona "Mão de obra/Insumos" logo após o ano da competência
    nova_desc = nova_desc.replace('\r\n', '\n').replace('\r', '\n')
    nova_desc = re.sub(r'\n?Mão de obra:[^\n]*', '', nova_desc)
    nova_desc = re.sub(r'\n?Insumos:[^\n]*',     '', nova_desc)
    # Remove bloco bancário/fiscal anterior para reinserir atualizado
    nova_desc = re.sub(r'\n*BANCO DO BRASIL[\s\S]*$', '', nova_desc)
    nova_desc = re.sub(r'\n{3,}', '\n\n', nova_desc).strip()

    match_ano = re.search(
        r'M[EÊ]S\s+DE\s+[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ]+\s+DE\s+\d{4}\.?',
        nova_desc, re.IGNORECASE | re.UNICODE,
    )

    if match_ano:
        pos    = match_ano.end()
        antes  = nova_desc[:pos].rstrip()
        depois = nova_desc[pos:].lstrip()
        nova_desc = antes + '\n\nMão de obra: 60%\nInsumos: 40%' + BLOCO_BANCARIO
        if depois:
            nova_desc += '\n' + depois
    else:
        nova_desc = nova_desc.rstrip() + '\n\nMão de obra: 60%\nInsumos: 40%' + BLOCO_BANCARIO

    return nova_desc


class OmieService:

    def __init__(self):
        self.app_key    = settings.OMIE_APP_KEY
        self.app_secret = settings.OMIE_APP_SECRET
        self.headers    = {'Content-Type': 'application/json'}

    # ── Requisição base ─────────────────────────────────────
    def _request(self, url, call, params, _retry=True):
        payload = {
            "call":       call,
            "app_key":    self.app_key,
            "app_secret": self.app_secret,
            "param":      [params]
        }
        try:
            # timeout=30 evita que o requests.post trave indefinidamente,
            # o que causava "Erro de conexão" no browser antes de qualquer resposta.
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            if response.status_code != 200:
                try:
                    err   = response.json()
                    fault = err.get('faultstring') or err.get('cDescStatus') or str(err)
                except Exception:
                    err   = None
                    fault = response.text[:300]

                # ── Retry automático para consumo redundante (REDUNDANT) ──────────
                if _retry and err and 'REDUNDANT' in str(err.get('faultstring', '')):
                    print(f"⏳ [{call}] Omie detectou redundância — aguardando 65s para retry...")
                    sleep(65)
                    return self._request(url, call, params, _retry=False)
                # ─────────────────────────────────────────────────────────────────

                print(f"⚠️ HTTP {response.status_code} [{call}]: {fault}")
                return err or {"faultstring": f"Erro HTTP {response.status_code}", "raw": response.text}
            return response.json()
        except requests.exceptions.Timeout:
            print(f"❌ Timeout [{call}]: servidor não respondeu em 30s")
            return {"faultstring": f"Timeout na chamada {call} — tente novamente."}
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro de Conexão: {e}")
            return None

    # ── Clientes ────────────────────────────────────────────
    def consultar_cliente(self, codigo_cliente_omie):
        params = {"codigo_cliente_omie": codigo_cliente_omie}
        dados  = self._request(URL_CLIENTE, "ConsultarCliente", params)
        if dados and "nome_fantasia" in dados:
            return dados.get("nome_fantasia") or dados.get("razao_social")
        return "-"

    def consultar_cliente_completo(self, codigo_cliente_omie):
        """
        Busca o cadastro completo do cliente na Omie e devolve já no
        formato esperado pelo despesas.saatri.xml_builder ("tomador"):
        cpf_cnpj, is_cpf, razao_social, endereco, numero, bairro,
        codigo_municipio (IBGE), uf, cep, telefone, email, etc.

        Usado pelo fluxo de emissão SAATRI Direto — a Omie já guarda o
        cadastro fiscal completo do cliente (endereço, CNPJ/CPF, IM),
        então buscamos ao vivo em vez de manter um cadastro duplicado.
        """
        params = {"codigo_cliente_omie": codigo_cliente_omie}
        dados  = self._request(URL_CLIENTE, "ConsultarCliente", params)
        if not dados or dados.get("faultstring") or "cnpj_cpf" not in dados:
            return None

        cpf_cnpj = re.sub(r"\D", "", dados.get("cnpj_cpf", ""))
        is_cpf   = (dados.get("pessoa_fisica") == "S") or len(cpf_cnpj) == 11

        ddd      = (dados.get("telefone1_ddd") or "").strip()
        numero_t = (dados.get("telefone1_numero") or "").strip()
        telefone = re.sub(r"\D", "", f"{ddd}{numero_t}") if (ddd or numero_t) else ""

        numero_end = (dados.get("endereco_numero") or "").strip() or "S/N"

        return {
            "cpf_cnpj":       cpf_cnpj,
            "is_cpf":         is_cpf,
            "razao_social":   dados.get("razao_social") or dados.get("nome_fantasia") or "",
            "logradouro":     dados.get("endereco", ""),
            "numero":         numero_end,
            "complemento":    dados.get("complemento", "") or "",
            "bairro":         dados.get("bairro", ""),
            "codigo_municipio": (dados.get("cidade_ibge") or "").strip(),
            "uf":             dados.get("estado", ""),
            "codigo_pais":    "1058",
            "cep":            re.sub(r"\D", "", dados.get("cep", "")),
            "telefone":       telefone,
            "email":          dados.get("email", "") or "",
            "inscricao_municipal": dados.get("inscricao_municipal", "") or "",
        }

    # ── Contratos ────────────────────────────────────────────
    def listar_contratos_api(self, pagina=1):
        params = {
            "pagina": pagina,
            "registros_por_pagina": 50,
            "apenas_importado_api": "N",
            "cExibirProdutos": "N",
            "cExibirInfoCadastro": "S"
        }
        return self._request(URL_CONTRATO, "ListarContratos", params)

    def consultar_contrato_completo(self, cod_contrato_omie):
        params = {"contratoChave": {"nCodCtr": int(cod_contrato_omie)}}
        return self._request(URL_CONTRATO, "ConsultarContrato", params)

    # ── NFS-e ───────────────────────────────────────────────
    def listar_nfse(self, pagina=1, registros=50, filtros=None):
        params = {
            "nPagina":       pagina,
            "nRegPorPagina": registros,
        }
        if filtros:
            params.update(filtros)
        return self._request(URL_NFSE, "ListarNFSEs", params)

    # ── Sincronização de NFS-e ──────────────────────────────
    def sincronizar_nfse(self, mes=None, ano=None):
        from .models import Contrato, NotaFiscal

        filtros = {}
        if mes and ano:
            ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
            filtros['dEmiInicial'] = f"01/{int(mes):02d}/{int(ano)}"
            filtros['dEmiFinal']   = f"{ultimo_dia}/{int(mes):02d}/{int(ano)}"

        pagina          = 1
        criadas         = 0
        atualizadas     = 0
        _cache_clientes = {}

        print(f"--- Sync NFS-e | filtro: {filtros or 'todas'} ---")

        while True:
            res = self.listar_nfse(pagina=pagina, filtros=filtros)

            if not res:
                print("  Sem resposta da API.")
                break

            if res.get('faultstring'):
                print(f"  Erro API: {res['faultstring']}")
                break

            total_pags  = res.get('nTotPaginas', res.get('total_de_paginas', 1))
            total_regs  = res.get('nTotRegistros', res.get('total_de_registros', '?'))
            lista       = res.get('nfseEncontradas', [])
            chaves_resp = list(res.keys())
            print(f"  Página {pagina}/{total_pags} | registros_total={total_regs} | itens_retornados={len(lista)} | chaves={chaves_resp}")

            if not lista:
                import json as _json
                print(f"  Resposta completa (primeiros 500 chars): {str(res)[:500]}")
                break

            for item in lista:
                if lista.index(item) == 0:
                    print(f"  Estrutura primeiro item — chaves: {list(item.keys())}")
                    cab_diag = item.get('Cabecalho', item.get('cabecalho', {}))
                    os_diag  = item.get('OrdemServico', item.get('ordemServico', {}))
                    print(f"  Cabecalho chaves: {list(cab_diag.keys())}")
                    print(f"  OrdemServico chaves: {list(os_diag.keys())}")
                    print(f"  nCodNF={cab_diag.get('nCodNF')} nNumeroNFSe={cab_diag.get('nNumeroNFSe')} nCodigoContrato={os_diag.get('nCodigoContrato')}")

                cab      = item.get('Cabecalho',    {})
                os_dados = item.get('OrdemServico', {})
                valores  = item.get('Valores',      {})
                emissao  = item.get('Emissao',      {})

                nfse_id = cab.get('nCodNF')
                if not nfse_id:
                    continue

                data_str   = emissao.get('cDataEmissao', '') or cab.get('cDataEmissao', '')
                data_emiss = None
                comp_mes   = mes
                comp_ano   = ano
                if data_str:
                    try:
                        data_emiss = datetime.strptime(data_str, "%d/%m/%Y").date()
                        comp_mes   = data_emiss.month
                        comp_ano   = data_emiss.year
                    except ValueError:
                        pass

                if not comp_mes or not comp_ano:
                    continue

                cod_ctr  = os_dados.get('nCodigoContrato')
                contrato = None
                if cod_ctr:
                    contrato = Contrato.objects.filter(omie_cod_ctr=cod_ctr).first()
                    if not contrato:
                        print(f"  [AVISO] nCodigoContrato={cod_ctr} não encontrado no banco.")

                if not contrato:
                    cli_id_ctr = cab.get('nCodigoCliente')
                    if cli_id_ctr:
                        contrato = (
                            Contrato.objects
                            .filter(cliente_id_omie=cli_id_ctr)
                            .exclude(status_omie__in=['99', 'Cancelado', 'Inativo', 'Suspenso'])
                            .order_by('-id')
                            .first()
                        )
                        if contrato:
                            print(f"  [NUM_NOTA] Contrato resolvido via cliente_id_omie={cli_id_ctr} → {contrato.omie_num_ctr}")
                        else:
                            contrato = (
                                Contrato.objects
                                .filter(cliente_id_omie=cli_id_ctr)
                                .order_by('-id')
                                .first()
                            )
                            if contrato:
                                print(f"  [NUM_NOTA] Contrato resolvido (inativo) via cliente_id_omie={cli_id_ctr} → {contrato.omie_num_ctr}")
                            else:
                                print(f"  [AVISO] Nenhum contrato encontrado para cliente_id_omie={cli_id_ctr} — nota ficará sem contrato.")

                sit    = cab.get('cStatusNFSe', 'N')
                status_nuvem = 'cancelada' if sit == 'C' else 'emitida'

                # VERIFICA O STATUS LOCAL PARA PRESERVÁ-LO CASO ESTEJA EXCLUÍDA/CANCELADA
                nota_local = NotaFiscal.objects.filter(omie_nfse_id=nfse_id).first()

                # Ajuste os nomes 'cancelada' ou 'excluida' para os status exatos usados no seu sistema
                if nota_local and nota_local.status in ['cancelada', 'excluida']:
                    status_final = nota_local.status
                else:
                    status_final = status_nuvem

                cli_id   = cab.get('nCodigoCliente')
                cli_nome = ''
                if cli_id:
                    if cli_id not in _cache_clientes:
                        c_local = Contrato.objects.filter(cliente_id_omie=cli_id).first()
                        if c_local and c_local.cliente_nome:
                            _cache_clientes[cli_id] = c_local.cliente_nome
                        else:
                            _cache_clientes[cli_id] = self.consultar_cliente(cli_id)
                            sleep(1.5)
                    cli_nome = _cache_clientes[cli_id]

                defaults = {
                    'contrato':        contrato,
                    'numero_nfse':     str(cab.get('nNumeroNFSe', '')),
                    'omie_os_id':      os_dados.get('nCodigoOS'),
                    'cliente_nome':    cli_nome,
                    'valor_bruto':     valores.get('nValorTotalServicos', 0),
                    'valor_iss':       valores.get('nValorISS',           0),
                    'valor_liquido':   valores.get('nValorLiquido',       0),
                    'competencia_mes': int(comp_mes),
                    'competencia_ano': int(comp_ano),
                    'data_emissao':    data_emiss,
                    'status':          status_final,
                }

                obj, created = NotaFiscal.objects.update_or_create(
                    omie_nfse_id=nfse_id,
                    defaults=defaults,
                )
                if created:
                    criadas += 1
                else:
                    atualizadas += 1

                sleep(0.05)

            if pagina >= total_pags:
                break
            pagina += 1

        print(f"--- Sync NFS-e End | criadas={criadas} atualizadas={atualizadas} ---")
        return criadas, atualizadas

    def obter_link_pdf_nfse(self, omie_nfse_id):
        res = self._request(URL_OSDOCS, "ObterNFSe", {"nIdNf": int(omie_nfse_id)})
        if res and not res.get("faultstring"):
            return res.get("cPdfNFSe") or res.get("cUrlNFSe") or None
        return None

    # ── Limpeza de auditoria ────────────────────────────────
    def _limpar_dados_auditoria(self, dados):
        if isinstance(dados, dict):
            campos_proibidos = [
                'dInc', 'hInc', 'uInc',
                'dAlt', 'hAlt', 'uAlt',
                'cImpAPI', 'dImpAPI', 'hImpAPI',
                'infoCadastro',
                'nValLiq', 'nValServ',
                'nTotImpostos', 'nTotRetencoes',
                'cCodStatus', 'cDescStatus',
                'cNumContrato',
            ]
            for campo in campos_proibidos:
                dados.pop(campo, None)
            for k in [k for k, v in list(dados.items()) if v is None]:
                del dados[k]
            for value in dados.values():
                if isinstance(value, (dict, list)):
                    self._limpar_dados_auditoria(value)
        elif isinstance(dados, list):
            for item in dados:
                self._limpar_dados_auditoria(item)
        return dados

    # ── alterar_contrato_lote ───────────────────────────────

    def alterar_contrato_lote(self, cod_contrato_omie, novo_valor=None, novo_nbs=None, nova_competencia=None):
        print(f"--- ALTERANDO CONTRATO {cod_contrato_omie} ---")
        dados_response = self.consultar_contrato_completo(cod_contrato_omie)
        if not dados_response or 'contratoCadastro' not in dados_response:
            return False, f"Erro busca: {dados_response}"

        sleep(1.5)

        contrato  = dados_response['contratoCadastro']
        contrato  = self._limpar_dados_auditoria(contrato)
        cabecalho = contrato.get('cabecalho', {})
        itens     = contrato.get('itensContrato', [])

        cabecalho['nCodCtr'] = int(cod_contrato_omie)
        alterado = False

        PADRAO_COD_SERV_MUNIC = "171901"
        PADRAO_COD_LC116      = "17.19"
        PADRAO_NBS            = "113022100"
        PADRAO_ALIQ_ISS       = 2.00

        for item in itens:
            if 'itemCabecalho' in item:
                cab_item = item['itemCabecalho']
                if not cab_item.get('natOperacao'):
                    cab_item['natOperacao'] = '01'
                    print(f"  ⚠️ natOperacao ausente no item — definido como '01' (padrão)")
                else:
                    print(f"  ✅ natOperacao preservado: '{cab_item['natOperacao']}'")

                cab_item['codServMunic'] = PADRAO_COD_SERV_MUNIC
                cab_item['codLC116']     = PADRAO_COD_LC116
                cab_item['codNBS']       = str(novo_nbs).strip() if novo_nbs else PADRAO_NBS

                impostos_atuais = item.get('itemImpostos', {})
                impostos_atuais['aliqISS'] = PADRAO_ALIQ_ISS
                item['itemImpostos'] = impostos_atuais

                alterado = True

                if novo_valor:
                    try:
                        val_str     = str(novo_valor).replace('.','').replace(',','.') if ',' in str(novo_valor) else str(novo_valor)
                        valor_float = float(val_str)
                        cab_item['valorTotal'] = valor_float
                        cab_item['valorUnit']  = valor_float
                    except Exception:
                        pass

        if novo_valor:
            try:
                val_str     = str(novo_valor).replace('.','').replace(',','.') if ',' in str(novo_valor) else str(novo_valor)
                valor_float = float(val_str)
                cabecalho['nValTotMes'] = valor_float
                alterado = True
            except Exception:
                pass

        if nova_competencia and nova_competencia.get('mes') and nova_competencia.get('ano'):
            mes = nova_competencia['mes'].upper()
            ano = str(nova_competencia['ano'])

            for item in itens:
                descr_obj  = item.get('itemDescrServ', {})
                desc_atual = descr_obj.get('descrCompleta', '')
                if not desc_atual:
                    continue

                nova_desc = atualizar_competencia_em_descricao(desc_atual, mes, ano)

                if nova_desc != desc_atual:
                    trecho_antes  = re.search(r'.{0,20}M[EÊ]S.{0,50}', desc_atual, re.IGNORECASE)
                    trecho_depois = re.search(r'.{0,20}M[EÊ]S.{0,50}', nova_desc,  re.IGNORECASE)
                    print(f"  ✅ Competência substituída:")
                    print(f"     antes : '{trecho_antes.group()  if trecho_antes  else desc_atual[-60:]}'")
                    print(f"     depois: '{trecho_depois.group() if trecho_depois else nova_desc[-60:]}'")
                    descr_obj['descrCompleta'] = nova_desc
                    alterado = True
                else:
                    trecho = re.search(r'.{0,30}M[EÊ]S.{0,60}', desc_atual, re.IGNORECASE)
                    print(f"  ℹ️ Competência já atualizada. Trecho MÊS: '{trecho.group() if trecho else 'NÃO ENCONTRADO'}'")

        if not alterado:
            return True, "Sem alterações."

        if 'despesasReembolsaveis' in contrato:
            dr = contrato['despesasReembolsaveis']
            if isinstance(dr, dict) and not dr.get('despesaReembolsavel'):
                del contrato['despesasReembolsaveis']

        for k in ['departamentos', 'infAdic', 'observacoes', 'emailCliente']:
            if k in contrato and not contrato[k]:
                del contrato[k]

        resultado = self._request(URL_CONTRATO, "AlterarContrato", contrato)
        if resultado:
            if "nCodCtr" in resultado or str(resultado.get("cCodStatus")) == "0":
                sleep(3.0)  # ← dá tempo ao Omie limpar o flag de redundância
                print("--- SUCESSO ---")
                return True, "Sucesso", dados_response
            msg = resultado.get('faultstring') or resultado.get('cDescStatus') or str(resultado)
            print(f"ERRO API: {msg}")
            return False, msg
        return False, "Erro desconhecido"


    # ── faturar_contrato ────────────────────────────────────
    def faturar_contrato(self, cod_contrato_omie):
        params = {"nCodCtr": int(cod_contrato_omie)}
        res    = self._request(URL_CONTRATO_FAT, "FaturarContrato", params)

        if not res:
            return False, "Sem resposta da API"

        if res.get("faultstring"):
            return False, res["faultstring"]

        cod_status = str(res.get("cCodStatus", ""))
        if cod_status == "0" or res.get("nCodOS"):
            print(
                f"  ✅ Contrato {cod_contrato_omie} faturado — "
                f"OS={res.get('nCodOS')} | status={res.get('cDescStatus')}"
            )
            return True, res

        msg = res.get("cDescStatus") or str(res)
        print(f"  ⚠️ Faturamento status inesperado [{cod_status}]: {msg}")
        return False, msg

    # ── sincronizar_dados ────────────────────────────────────
    def sincronizar_dados(self):
        from .models import Contrato

        pagina          = 1
        _cache_clientes = {}
        print("--- Sync Contratos Start ---")

        while True:
            res = self.listar_contratos_api(pagina)

            if not res or res.get("bloqueado"):
                break

            lista = res.get('contratoCadastro', [])
            if not lista:
                break

            for item in lista:
                cab    = item.get('cabecalho', {})
                cli_id = cab.get('nCodCli')

                if cli_id not in _cache_clientes:
                    local = Contrato.objects.filter(cliente_id_omie=cli_id).first()
                    if local and local.cliente_nome:
                        _cache_clientes[cli_id] = local.cliente_nome
                    else:
                        sleep(1.0)
                        _cache_clientes[cli_id] = self.consultar_cliente(cli_id)

                nome_cli = _cache_clientes[cli_id]

                d_ini = (
                    datetime.strptime(cab['dVigInicial'], "%d/%m/%Y").date()
                    if cab.get('dVigInicial') else None
                )
                d_fim = (
                    datetime.strptime(cab['dVigFinal'], "%d/%m/%Y").date()
                    if cab.get('dVigFinal') else None
                )

                Contrato.objects.update_or_create(
                    omie_cod_ctr=cab.get('nCodCtr'),
                    defaults={
                        'omie_num_ctr':         cab.get('cNumCtr'),
                        'cliente_id_omie':       cli_id,
                        'cliente_nome':          nome_cli,
                        'valor_mensal':          cab.get('nValTotMes', 0),
                        'data_vigencia_inicial': d_ini,
                        'data_vigencia_final':   d_fim,
                        'status_omie':           cab.get('cCodSit'),
                    },
                )

                sleep(0.3)

            total_pags = res.get('total_de_paginas', 1)
            print(f"  Página {pagina}/{total_pags} | itens={len(lista)}")

            if pagina >= total_pags:
                break

            pagina += 1
            sleep(1.5)

        print("--- Sync Contratos End ---")