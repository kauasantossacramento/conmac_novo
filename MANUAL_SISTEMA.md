# Manual do Sistema — CONMAC (conmac_novo)

> Documento de referência para qualquer IA/desenvolvedor que for mexer neste
> projeto depois. Escrito em 2026-08-18 após a implementação do módulo de
> emissão de NFS-e via SAATRI Direto. Cobre a estrutura geral do sistema
> (todos os módulos, mesmo os que não foram tocados nesta sessão) e o
> detalhamento técnico completo do que foi construído.
>
> **Antes de confiar em qualquer nome de arquivo/linha citado aqui, confira
> se ainda existe** — o `views.py` principal tem ~13.500 linhas e é editado
> com frequência; números de linha ficam desatualizados rápido.

---

## 1. Visão geral

- **Empresa**: CONMAC - Serviços Contábeis, Treinamento e Desenvolvimento LTDA
  (CNPJ 17.449.551/0001-30), prestadora de serviços de assessoria/consultoria
  contábil para prefeituras e câmaras municipais da Bahia.
- **O que o sistema faz**: gestão interna completa da CONMAC — despesas de
  viagem/reembolso, fechamento contábil de clientes (SIGA/SIOPE/SIOPS/SICONFI/
  E-TCM), prestação de contas, RH/contracheques, e o módulo mais relevante pra
  este manual: **gestão de contratos e emissão de NFS-e** para os clientes
  (prefeituras/câmaras).
- **Stack**: Django 5.2.7, SQLite (`db.sqlite3`), deploy no **PythonAnywhere**.
- **App único**: tudo vive dentro do app Django `despesas` (nome genérico,
  mas cobre o sistema inteiro — não é só "despesas de viagem"). Projeto
  Django se chama `conmac` (`conmac/settings.py`, `conmac/urls.py`).
- **Integração externa principal**: **Omie** (ERP) — contratos, clientes e,
  até esta sessão, toda a emissão de NFS-e passavam por lá. Ver seção 4.
- **Repositório**: `git@github.com:kauasantossacramento/conmac_novo.git`,
  branch `main`.

### Como rodar localmente

```bash
git clone git@github.com:kauasantossacramento/conmac_novo.git
cd conmac_novo
python -m venv venv        # NÃO reaproveite a pasta venv/ do repo — ver seção 7
venv\Scripts\activate       # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Deploy (PythonAnywhere)

```bash
cd ~/conmac_novo
git pull origin main
workon <nome-do-virtualenv>       # ou: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
# depois: aba "Web" do painel PythonAnywhere → botão "Reload"
```

---

## 2. Estrutura de pastas

```
conmac_novo/
├── conmac/                  # projeto Django (settings, urls, wsgi)
│   ├── settings.py          # INSTALLED_APPS, OMIE_APP_KEY/SECRET, Firebase, etc.
│   └── context_processors.py
├── despesas/                 # ÚNICO APP — o sistema inteiro mora aqui
│   ├── models.py             # ~2.500 linhas, todos os models (ver seção 3)
│   ├── views.py               # ~13.500 linhas — MUITAS funções duplicadas
│   │                          # (definidas 2x; Python usa a ÚLTIMA definição
│   │                          # do arquivo — ver seção 6 "Armadilhas")
│   ├── views.py.bak          # backup antigo, NÃO é importado por ninguém,
│   │                          # pode ser ignorado/removido com segurança
│   ├── views_pc.py           # módulo de Prestação de Contas — arquivo
│   │                          # separado, importado dentro de views.py
│   │                          # (`from .views_pc import (...)`)
│   ├── views_saatri.py       # NOVO (esta sessão) — emissão SAATRI Direto,
│   │                          # mesmo padrão do views_pc.py
│   ├── saatri/                # NOVO (esta sessão) — pacote com o cliente
│   │                          # SOAP do Web Service da prefeitura (ver seção 5)
│   ├── forms.py
│   ├── urls.py                 # todas as rotas do app (namespace nenhum,
│   │                          # tudo direto — ver `include` em conmac/urls.py)
│   ├── admin.py
│   ├── signals.py
│   ├── auth_backends.py      # login por CPF ou username
│   ├── omie_service.py       # cliente da API Omie (contratos, clientes, NFS-e)
│   ├── contracheque_ocr_service.py
│   ├── utils.py / utils_push.py
│   ├── services/              # helpers de fechamento contábil, UI
│   ├── templates/             # ver subpastas por módulo (seção 3)
│   ├── migrations/
│   └── management/commands/
├── db.sqlite3                # banco de PRODUÇÃO real (usado também local)
│                              # ⚠️ desde 2026-08-18 NÃO está mais no git
│                              #    (estava rastreado por engano — ver seção 6)
├── venv/                     # ⚠️ pasta de virtualenv LINUX commitada no
│                              #    git por engano — não funciona no Windows,
│                              #    ver seção 6
├── requirements.txt
└── manage.py
```

---

## 3. Módulos do sistema (mesmo dentro do único app `despesas`)

O `views.py` é organizado em blocos sequenciais, muitas vezes com comentários
tipo `#MÓDULO DE X` ou `# ─────` como separador. Nem sempre estão em ordem —
o arquivo cresceu por colagem de trechos ao longo do tempo (por isso as
funções duplicadas, ver seção 6). Módulos identificados:

| Módulo | Prefixo de URL | Models principais | Views/arquivo | Templates |
|---|---|---|---|---|
| **Autenticação** | `/login/`, `/logout/` | `UsuarioPerfil` | `views.py` (topo) | `auth/` |
| **Despesas de viagem / reembolso** | `/despesas/`, `/viagens/`, `/admin-despesas/`, `/admin-reembolso/`, `/centros/` | `Despesa`, `CentroDeCusto`, `AssociacaoCentroCusto`, `LoteReembolso`, `ChecklistItem` | `views.py` | `despesas/`, `centros/`, `viagens/` |
| **Notificações Push** | `/api/push/`, `/push/`, `sw.js`, `firebase-messaging-sw.js` | `FCMToken`, `NotificacaoConfig`, `NotificacaoPush` | `views.py`, `utils_push.py`, `apps.py` (init Firebase) | — |
| **Fechamento Contábil** (clientes, etapas SIGA/SIOPE/SIOPS/SICONFI/E-TCM) | `/fechamento/`, `/etapa/`, `/painel/`, `/salvar-config-nivel/` | `Cliente`, `AssociacaoUsuarioCliente`, `Etapa`, `EtapaRegistro`, `EtapaHistorico`, `CompetenciaLiberada`, `ConfiguracaoNivel`, `FilaAutomatica`, `SolicitacaoReabertura` | `views.py`, `services/fechamento.py` | `fechamento/` |
| **SIOPS (questionários de prefeituras)** | `/siops/<slug>/` | `Prefeitura`, `QuestionarioSIOPS` | `views.py` | `siops/` |
| **Eventos (RSVP)** | `/conmacfest2025/` | `Rsvp` | `views.py` | `eventos/` |
| **Receitas / Contratos / NFS-e** ⭐ | `/receitas/` | `Contrato`, `NotaFiscal`, `NotaFiscalPDF`, `RecebimentoNota`, `ServicoExtra`, `ContratoEmail`, `DocumentoPadrao`, `DocumentoModelo`, `DocumentoModeloGerado`, `EnvioMensal`, `EmailMunicipio`, `PrevisaoPagamento`, `PrevisaoPagamentoLog`, **+ `RpsSaatri`, `LogSaatri`, `SaatriNumeracao` (novos)** | `views.py` (maior parte), `omie_service.py`, **`views_saatri.py` + `saatri/` (novos)** | `receitas_dashboard.html`, `notas_competencia.html`, `relatorio_receitas.html`, `modal_editar_lote.html`, `documentos_contrato.html`, `gestao_documentos.html`, `adicionar_email_municipio.html` |
| **Ferramentas / OCR de PDF** | `/ferramentas/pdf-ocr/`, `/confronto-balanco/` | — | `views.py` | `compress_pdf.html`, `conciliacao.html` |
| **Monitor de Boletos / TCM** | `/monitor-boletos/`, `/tcm/` | `CartaoCorporativo`, `TransacaoCartao` | `views.py` | `boletos/` |
| **Prestação de Contas (PC)** | `/prestacao-contas/` | `PrestacaoContas`, `PCItem`, `PCAnexo`, `PCHistorico`, `PCItemAnotacao`, `PCPrazo`, `PCRetorno`, `EtapaPC` (choices) | **`views_pc.py`** (arquivo separado) | `pc/` |
| **Despesas Gerais** (diferente do módulo de reembolso de viagem) | `/despesas-gerais/` | `DespesaGeral` | `views.py` | — |
| **Raio-X / Relatórios administrativos** | `/raio-x/`, `/relatorio/` | — | `views.py` | `relatorios/` |
| **Configuração Financeira / Vínculos** | — (usado por outros módulos) | `ConfiguracaoFinanceira`, `VinculoCentroCustoContrato`, `VinculoFuncionarioCentro` | `views.py` | — |
| **RH / Contracheques** | `/rh/`, `/meus-contracheques/` | `LoteContracheque`, `Contracheque` | `views.py` | `rh_dashboard.html`, `colaborador_contracheques.html` |

⭐ = módulo onde toda a construção desta sessão aconteceu.

---

## 4. Módulo Receitas/NFS-e — como funciona (Omie x SAATRI Direto)

### 4.1 Conceitos

- **`Contrato`**: sincronizado da Omie (`OmieService.sincronizar_dados`),
  representa um contrato de prestação de serviço com um cliente (prefeitura/
  câmara). Campos-chave: `omie_cod_ctr`, `omie_num_ctr`, `cliente_id_omie`,
  `cliente_nome`, `valor_mensal`, `municipio`, `tipo_entidade`.
- **`NotaFiscal`**: uma NFS-e já emitida. Tem o campo **`origem`** (novo):
  `'omie'` (fluxo padrão, todo o histórico até 2026-08-18) ou `'saatri'`
  (emissão direta, novo). A tela `notas_competencia.html` e o envio de
  dossiê por e-mail (`enviar_lote_dashboard`) **tratam os dois iguais** —
  não fazem nenhuma distinção por origem, então uma vez que a nota está
  salva em `NotaFiscal` ela se comporta identicamente não importa como foi
  emitida.
- **Painel principal**: `/receitas/` (`receitas_dashboard.html`) — lista
  contratos, permite seleção múltipla, e a partir daí: editar em lote, faturar
  em lote (Omie ou SAATRI), gerar/enviar documentos por e-mail.
- **Tela de controle de recebimento**: `/receitas/notas/`
  (`notas_competencia.html`) — lista as `NotaFiscal` emitidas por competência,
  com KPIs (emitido/recebido/a receber) e confirmação de pagamento
  (`RecebimentoNota`). **Não depende de origem**, confirmado em código.

### 4.2 Fluxo ORIGINAL — emissão via Omie

1. `editar_lote_modal` → `OmieService.alterar_contrato_lote()`: busca o
   contrato na Omie, ajusta item de serviço / NBS / alíquota / competência /
   descrição (inclui bloco fixo de texto bancário + cláusula de não
   incidência), manda de volta (`AlterarContrato`).
2. `faturar_lote_view` (`POST /receitas/contratos/faturar-lote/`) →
   `OmieService.faturar_contrato()` → chama `FaturarContrato` na Omie, que
   internamente fala com a prefeitura (opaco pra nós).
3. `sincronizar_nfse` / `sincronizar_nfse_ajax` (`GET /receitas/notas/
   sincronizar/`, `POST /receitas/sincronizar-nfse/`) →
   `OmieService.sincronizar_nfse()` → puxa as notas já emitidas na Omie pro
   model local `NotaFiscal` (`omie_nfse_id` como chave).
4. `enviar_lote_dashboard` → manda o dossiê (docs padrão + `NotaFiscal`
   correspondente, como PDF) por e-mail. Se o PDF ainda não foi baixado,
   busca via `OmieService.obter_link_pdf_nfse(omie_nfse_id)`.

### 4.3 Fluxo NOVO — SAATRI Direto (bypassa a Omie)

Emite a NFS-e **direto no Web Service ABRASF da prefeitura de Oliveira dos
Brejinhos/BA** (SAATRI/ADM Sistemas), sem passar pelo conector da Omie. Ainda
assim **usa a Omie como fonte de dados** (valor/descrição do contrato,
CNPJ/endereço do cliente) — só não usa a Omie pra *emitir*.

1. Usuário seleciona contratos em `/receitas/`, abre o modal de
   faturamento/edição em lote, e escolhe **"Emitir via: Omie | SAATRI
   Direto"** (rádio novo no `modal_editar_lote.html`, dentro do painel de
   confirmação).
2. Se escolher SAATRI: `chamarFaturarLote()` (JS) posta pra
   `/receitas/contratos/faturar-lote-saatri/` em vez de `/faturar-lote/`.
3. `faturar_lote_saatri_view` (`despesas/views_saatri.py`), por contrato:
   - `OmieService.consultar_contrato_completo()` → pega valor, descrição e
     NBS **atuais** do contrato na Omie (respeitando o que `alterar_contrato_
     lote` já tiver ajustado).
   - `OmieService.consultar_cliente_completo()` (**novo método**) → busca o
     cadastro fiscal completo do tomador direto na Omie (CNPJ/CPF, endereço,
     `cidade_ibge`, telefone, e-mail) — não existe cadastro de tomador local,
     é sempre ao vivo.
   - Monta um `RpsSaatri` (numera via `SaatriNumeracao`, contador
     dedicado — nunca reusa `omie_cod_ctr`/OS da Omie) e chama
     `saatri.client.gerar_nfse()`.
   - Trata 3 resultados possíveis (ver seção 5.3): nota pronta na hora,
     "aceita, sai depois" (Ambiente Nacional), ou erro.
4. Se ficou pendente ("aceita, sai depois"): `sincronizar_saatri_pendentes()`
   (função pura em `views_saatri.py`) resolve depois — **está plugada direto
   dentro de `sincronizar_nfse` e `sincronizar_nfse_ajax`**, ou seja, o
   mesmo botão "Sincronizar NFS-e" que já existia pra Omie também resolve
   os RPS SAATRI pendentes. Não existe botão separado (só uma view standalone
   `sincronizar_saatri_pendentes_view` pra debug/uso manual direto).
5. Ao resolver (imediato ou via sync), `_salvar_nota_saatri()` cria/atualiza
   a `NotaFiscal` (`origem='saatri'`) **e baixa o PDF (DANFSe) automaticamente**
   via `saatri.client.baixar_pdf_nfse()`, salvando em `NotaFiscalPDF` — o
   mesmo model que o fluxo Omie usa.
6. `enviar_lote_dashboard` tem um **fallback específico** pra origem SAATRI:
   se por algum motivo o PDF não tiver sido baixado no passo 5, ele detecta
   `nota_fiscal.origem == 'saatri'` e baixa via `saatri.client.baixar_pdf_
   nfse()` em vez de tentar o caminho da Omie (que falharia, pois
   `omie_nfse_id` é `None` pra essas notas).

---

## 5. Detalhamento técnico do módulo `saatri/`

### 5.1 Origem — herdado do projeto `nfse_project`

Todo o cliente SOAP foi **portado de um projeto irmão** (`nfse_project`,
sistema Django dedicado só a isso) onde foi **testado e validado em produção
de verdade** contra o Web Service SAATRI de Oliveira dos Brejinhos/BA em
2026-08-18 (emissão real: NFS-e nº 3254, RPS 3255/série 9000). Todos os bugs
abaixo já foram descobertos e corrigidos lá antes de portar pra cá:

| Bug | Causa | Correção aplicada |
|---|---|---|
| HTTP 500 genérico em toda chamada | `SOAPAction` sem o segmento `/Infse/` (WCF responde `ActionNotSupported`) | `client.py` usa `http://nfse.abrasf.org.br/Infse/<Metodo>` |
| Parser retornava vazio mesmo com sucesso | Resposta sem CDATA vem com entidades XML escapadas (`&lt;`) | `xml_parser.extrair_xml_negocio` faz `unescape()` no fallback sem-CDATA |
| Erro `E160` (Complemento/Telefone) | Tags enviadas vazias violam `minLength=1` do XSD | `xml_builder` só inclui `<Complemento>`/`<Telefone>` se preenchidos |
| Erro `E333` (Sociedade de Profissionais não pode ter retenção) | `<ResponsavelRetencao>` enviado mesmo com `IssRetido=Não` | só inclui a tag quando `IssRetido == "1"` |
| Mensagem de sucesso tratada como erro | Código `"0"` (Ambiente Nacional: "DPS aceita, sai em ~5min pela SEFIN") é informativo, não erro | `parse_resposta_generica` separa `erros` (código ≠ "0") de `info` (código "0") |
| Série reservada | Prefeitura rejeitou série `75688` (reservada pro site do SAATRI) com `[25] Erro na gravação — série reservada` | usar série **`9000`**, dedicada à integração via Web Service |
| Regime de tributação divergente | `E327` — regime cadastrado na prefeitura é diferente do enviado | confirmado com o cliente: **`3` = "Sociedade de Profissionais"** (não é Simples Nacional nesse regime, apesar de `OptanteSimplesNacional=1` no XML — dado real confirmado, não mexer sem reconfirmar) |
| Item de serviço "errado" | Item enviado como `01.01.01` (3 níveis) não bate com a Lista de Serviços nacional da LC 116/2003 (2 níveis, `NN.NN`) | **Não é bug** — esta prefeitura usa uma tabela de tributação municipal/nacional própria de 3 níveis (`cTribNac`), confirmado analisando uma NFS-e real já emitida (item `171901` = `17.19.01`) |

### 5.2 Arquivos

- **`despesas/saatri/config.py`** — dados **fixos** do prestador (CONMAC):
  CNPJ, IM, endereço, credenciais WS (`ws_usuario`/`ws_senha`, texto puro —
  mesmo padrão do `OMIE_APP_KEY`/`OMIE_APP_SECRET` já commitado em
  `settings.py`), regime tributário, série RPS, ambiente (`producao`).
  **Item/NBS padrão** (`ITEM_LISTA_SERVICO_PADRAO = "17.19.01"`,
  `CODIGO_NBS_PADRAO = "113022100"`) — os mesmos valores que já estavam
  hardcoded em `omie_service.alterar_contrato_lote` (`PADRAO_COD_SERV_MUNIC`
  etc.), então são consistentes com o que a CONMAC já usa hoje.
- **`despesas/saatri/xml_builder.py`** — monta o envelope SOAP e o XML
  ABRASF (`GerarNfseEnvio`, `ConsultarNfseRpsEnvio`). Recebe **dicts simples**
  (`rps`, `tomador`), não instâncias de model — o RPS aqui é passageiro
  (nasce e morre dentro da view), o estado persistente fica no model
  `RpsSaatri`.
- **`despesas/saatri/xml_parser.py`** — parseia a resposta SOAP (lxml).
  Depende do pacote `lxml` (**adicionado ao `requirements.txt` nesta
  sessão** — não existia antes).
- **`despesas/saatri/client.py`** — `gerar_nfse()`, `consultar_nfse_por_
  rps()`, `baixar_pdf_nfse()`. Toda chamada grava um `LogSaatri` (auditoria —
  XML enviado/recebido, status HTTP, duração).
- **`despesas/views_saatri.py`** — views + lógica de negócio (busca dados na
  Omie, monta RPS, chama o client, salva `NotaFiscal`). Importado dentro de
  `views.py` do mesmo jeito que `views_pc.py`.

### 5.3 Os 3 resultados possíveis de uma emissão

```python
resultado = saatri_client.gerar_nfse(rps_dict, tomador)
# resultado = {"notas": [...], "info": [...], "erros": [...], "log": <LogSaatri>}
```

1. **`resultado["notas"]` não vazio** → nota pronta na hora (formato ABRASF
   clássico, `ListaNfse`/`CompNfse`). Salva direto.
2. **`resultado["info"]` não vazio** (código `"0"`) → "Ambiente Nacional"
   (Reforma Tributária): a DPS foi aceita e compartilhada com a SEFIN, a
   NFS-e "de verdade" sai ~5 min depois. `RpsSaatri.status = 'enviado'`,
   precisa de sync depois (ver 4.3 passo 4). **Este foi o comportamento
   observado no teste real em produção — é bem provável que seja o caminho
   mais comum hoje**, não a exceção.
3. **`resultado["erros"]` não vazio** → erro de negócio de verdade.
   `RpsSaatri.status = 'erro'`, guarda `mensagem_erro` (código + mensagem +
   `correção`, quando o WS manda uma sugestão).

### 5.4 Modelos novos

- **`RpsSaatri`** — uma tentativa de emissão (equivalente ao `Rps` do
  `nfse_project`). `unique_together = ('numero', 'serie', 'tipo')`. Se uma
  tentativa falha, ela **fica com `status='erro'` e o número não é reusado
  automaticamente** por uma nova tentativa — isso foi decisão consciente
  (evita duplicar RPS no lado da prefeitura). Não existe hoje uma tela de
  "reenviar RPS que falhou" no `conmac_novo` (existe no `nfse_project`, não
  foi portado pra cá ainda — considerar se for pedido).
- **`SaatriNumeracao`** — singleton (`SaatriNumeracao.obter()`), contador de
  RPS pra série 9000. Começa em **3260** (folga de segurança acima do RPS
  3255 já usado no teste real do `nfse_project`).
- **`LogSaatri`** — auditoria de toda chamada SOAP (equivalente ao
  `LogWebService` do `nfse_project`). Não tem tela própria no `conmac_novo`
  ainda (no `nfse_project` tem `/logs/<id>/`) — considerar portar se for
  útil pra debug.
- **`NotaFiscal`** ganhou: `origem`, `codigo_verificacao`, `xml_completo`.
  `omie_nfse_id` virou `null=True, blank=True` (antes era obrigatório).

### 5.5 O que NÃO foi feito / pontos em aberto

- **Sem tela de "reenviar RPS com erro"** pro fluxo SAATRI Direto (existe só
  no `nfse_project`). Se um RPS falhar, hoje só dá pra ver o erro — não tem
  botão de correção/reenvio.
- **Sem tela de logs SAATRI** (`LogSaatri` existe mas não tem view/template).
- **Sem teste de emissão real** feito no `conmac_novo` propriamente (o
  pipeline foi validado com **dry-run** — gerou o XML completo com dados
  reais de um contrato real (Ibirataia) mas não chegou a enviar). O teste
  real de ponta a ponta foi feito só no `nfse_project`, com dados de teste
  próprios (não um cliente real da CONMAC).
- **Item de serviço e NBS**: hoje usa os valores padrão de
  `saatri_config` OU o que estiver salvo no contrato na Omie
  (`codNBS` do item). **Não há seletor/edição desses campos no formulário
  de emissão SAATRI** — se algum contrato precisar de item/NBS diferente do
  padrão, precisa ajustar via Omie antes (mesma limitação que já existia:
  `alterar_contrato_lote` também assume os `PADRAO_*`).

---

## 6. Armadilhas conhecidas do código (não é bug que eu introduzi — já existia)

1. **Funções duplicadas em `views.py`** — várias views são definidas **duas
   vezes** no arquivo (ex.: `editar_lote_modal`, `faturar_lote_view`,
   `notas_competencia`, `ConfiguracaoNivel` em `models.py` também). Python só
   usa a **última definição** — a primeira é código morto, mas ainda ocupa
   espaço e pode confundir buscas. Ao procurar uma função, **sempre confira
   se há mais de uma definição** (`grep -n "^def nome_da_funcao"`) e edite a
   que está mais embaixo no arquivo (a que realmente roda).
2. **`views.py.bak`** — backup antigo solto na raiz do app, não é importado
   por nada. Pode ser removido com segurança, mas não mexi nele.
3. **`venv/` estava commitada no git** (Linux, ~8.400 arquivos — foi a causa
   de o clone inicial deste repo ter sido lento/instável nesta sessão).
   Está no `.gitignore`, mas como já foi commitada antes da regra existir,
   o `.gitignore` sozinho **não** remove ela do histórico. Não é utilizável
   no Windows (sem `Scripts/`, só `bin/`). Se for limpar, usar `git rm -r
   --cached venv/` num commit dedicado (não fiz isso ainda — só tratei o
   `db.sqlite3`, que era o risco mais grave).
4. **`db.sqlite3` estava commitado** — corrigido em 2026-08-18
   (`git rm --cached db.sqlite3`, já está no `.gitignore`). **Isso é
   crítico**: se alguém commitar o banco de novo no futuro, um `git pull`
   no PythonAnywhere pode tentar sobrescrever o banco de produção real.
   Nunca versionar `db.sqlite3` de novo.
5. **Console Windows com problema de encoding** — `apps.py` usa `print()`
   com emoji (`❌`) no log de erro do Firebase; isso quebra
   (`UnicodeEncodeError`) quando roda num terminal com codepage cp1252
   (comum no Windows). Não afeta produção (Linux/PythonAnywhere), só polui
   o console ao rodar localmente no Windows.
6. **Credenciais em texto puro no código-fonte**: `OMIE_APP_KEY`/
   `OMIE_APP_SECRET` em `conmac/settings.py`, e agora `ws_usuario`/
   `ws_senha` do SAATRI em `despesas/saatri/config.py`. Decisão explícita do
   cliente (CONMAC) — não é acidente, mas vale saber que está lá caso o
   repositório algum dia deixe de ser privado.
7. **`requirements.txt` estava incompleto**: faltava `lxml` (usado pelo
   parser SAATRI) — adicionado nesta sessão. Se algo novo for importado no
   futuro, sempre conferir se está no `requirements.txt` antes de dar como
   pronto — o ambiente do PythonAnywhere só tem o que está listado lá.

---

## 7. Referências externas relevantes

- **Projeto irmão `nfse_project`** — sistema Django separado, dedicado só à
  integração SAATRI, onde todo o cliente SOAP foi originalmente construído e
  testado em produção real. Útil consultar se precisar entender uma decisão
  técnica em mais profundidade (tem histórico de debug mais detalhado — logs
  de todas as tentativas reais, XMLs de exemplo em `Exemplos XML/`, o XSD
  oficial ABRASF 2.03 em `nfse v2 03.xsd`).
- **Portal SAATRI da prefeitura**: `https://oliveiradosbrejinhos.saatri.com.br`
  — WSDL em `/servicos/nfse.svc?wsdl`, PDF público da nota em
  `/Relatorio/VisualizarNotaFiscal?numero=<N>&codigoVerificacao=<C>`.
- **Tabela oficial de correlação NBS × LC 116/2003** (Receita Federal, Anexo
  VIII da Reforma Tributária) — usada como referência pra validar formatos,
  baixável em `gov.br/nfse` → biblioteca → documentação técnica → RTC.
  (Não foi portada pro `conmac_novo` como seletor — só usada pra validação
  manual durante o desenvolvimento.)
