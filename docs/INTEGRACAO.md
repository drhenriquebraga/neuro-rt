# Integração NEURO RT / Local Suite

## Contrato em desenvolvimento 1.1.0 / Local Suite 8.12

O desenho `superpowers/specs/2026-10-30-neuro-beta-110.md` substitui o recorte
Nidus-only das seções históricas. Cinco cards ativos têm `[fase de testes]` e
entrada `/neuro/testing/{tool}` com diálogo explícito a cada abertura de card.
O termo comum passa à versão1.1; instalação e primeiro uso continuam separados.
Os aceites de testes usam cookies opacos por ferramenta, HttpOnly, SameSiteStrict,
válidos por até8h na instância atual. Não escrevem feedbacks nem identidade.

URLs diretas de ferramentas passam pelo mesmo controle; `/api/nidus/*` exige
primeiro uso e aceite Nidus. APIs selection/studies/retry/jobs também exigem
aceite coerente com os grupos dos modelos, além dos controles de origem/token e
do pedido explícito. Modelos anatômicos podem acompanhar uma ferramenta tumoral.

O modo host continua sem runtime privado e sem artefatos científicos dentro do
SETUP. O perfil1.1.0 declara os cinco tools e `resource_recipe` fixada em
`catalog/resource_recipe.json`. O estado instalado tem um descritor `resources`
de oito campos, vinculado ao SHA do recibo e da receita; `PluginPaths` resolve
`resources`, `extras_dir` e `resources_file`. Caminhos de modelos devem coincidir
com o catálogo; Buti host_managed reutiliza recursos da base. Extras são adicionados
após os caminhos Python da suíte. Estado/pacote nunca escolhem outro interpretador.

O bootstrap confiável fornece `inspect_local_source`, `prepare_external_plan` e
`run_external`. O host fornece raiz e Python como argumentos confiáveis e possui
fila, ack/nonce/PID, fechamento e reabertura. O SDK não reinicia o host. A fonte
local é autenticada pelo digest canônico do inventário CODE fixado no bootstrap,
e cada recurso pela receita fixada. Nunca executar scripts da pasta selecionada.
START HERE cria o bundle offline local para transporte; a suíte instalada seleciona
essa pasta em Configurações. GitHub continua com somente dois SETUPs leves.

Os gates desta fase ainda estão em execução; esta seção documenta o contrato de
desenvolvimento e não comprova publicação ou validação clínica.

## Contrato publicado anterior 1.0.2

O [desenho atual](superpowers/specs/2026-10-30-installer-only-host-python-design.md)
substitui o modo isolado descrito nas seções históricas abaixo. O SETUP público
instala somente CODE; `execution_mode=host`, `runtime=null`, `runtimes=[]` e
`models=[]`. O binding `host_info['python_executable']` vem de `sys.executable`
da suíte e é usado pelo adapter/Settings. Nidus não baixa Python, dependências
ou pesos na base completa. Os demais quatro cards continuam em construção.
Os paths de runtimes privados abaixo valem para compatibilidade local legada,
nunca como fallback do instalador remoto. O host mínimo atual é 8.11.

Este é o contrato do plugin 1.0, com o recorte de disponibilidade 1.0.1 descrito
abaixo. O protótipo iframe/API v1 está preservado em
LEGADO_V02_INTEGRACAO.md; ele não define a instalação integrada atual.

## Responsabilidades

**Disponibilidade 1.0.1:** somente Nidus RT está habilitado. Os outros quatro
cards usam o renderer comum com rota vazia, `aria-disabled=true`, `[em construção]`
e opacidade do host. `neuro_rt/tool_availability.py` é a fonte canônica;
`module.json.enabled_tools` permite inspeção sem importar motores. As URLs dessas
ferramentas devolvem 503, e POST selection/studies/jobs/retry devolvem 409 após
os controles de origem/token. Leituras históricas e cancelamento são preservados.
O servidor stdlib de desenvolvimento também recusa novas execuções.

## Aceite compartilhado com o host

`neuro_rt/plugin_consent.py` contém o documento PT-BR, versão 1.0 e impressão
SHA-256 do conteúdo canônico. O bootstrap confiável inclui a mesma fonte. Texto
alterado exige versão nova, hash novo e coordenação com o bootstrap da base;
nunca buscar um termo executável no payload para autorizar sua própria instalação.

O provider gerado fornece `consent_policy()`, `consent_status()` e
`accept_consent(payload)`. Este último registra somente a etapa `installation`.
O host deve expor no status do plugin:

```json
{"consent":{"policy":"objeto retornado por consent_policy()",
            "installation_accepted":false,"first_use_accepted":false}}
```

O objeto `policy` real inclui title/version/digest/clauses, não a string ilustrativa.
O consumidor UI confiável mostra o texto e envia `consent={accepted:true,version,
digest}` no POST install/update quando necessário. O host valida sua origem/token
e JSON, chama `provider.accept_consent(body['consent'])` e só então `install()` ou
`request_plugin_update(...)`. A guarda do provider recusa qualquer ação sem recibo
atual, antes de segurar a fila, cancelar trabalho ou iniciar download. Instalações
antigas sem recibo também exigem essa confirmação antes de atualizar.

Na primeira entrada, `/neuro/onboarding` usa o mesmo documento. GET/POST
`/neuro/api/consent` fornecem estado/token e registram `first_use`, com origem e
token próprios da instância. Sem esse recibo, `/neuro/`, `/neuro/nidus`,
`/nidus/projecao` redirecionam ao onboarding e `/api/nidus/*` responde 428. Um
registro não substitui o outro. A tela inicial não tem checkbox marcado por padrão.
Os arquivos separados `config/consent-installation.json` e
`config/consent-first_use.json` guardam versão/hash/etapa/instante UTC, sem paciente
ou operador. São locais à instalação, não um serviço de autenticação pessoal.

O aceite complementa os termos da suíte; mantém MIT da integração, Apache-2.0 do
Nidus/core e licenças por componente, e não constitui aprovação clínica.

O host é dono da aplicação FastAPI, origem, home, menu, idioma, tema, carregador
DICOM e bilhetes, preferência de dispositivo, fila, acervo, gravador DICOM-RT e
visores. O plugin é dono do catálogo Neuro, bindings, coordenação dos estudos,
adaptadores e dados privados. Bibliotecas científicas ficam nos workers.

A pequena entrada do host funciona com o plugin ausente. Ao instalar, NEURO RT
usa a mesma origem e os componentes visuais existentes. Não abre outro servidor.

## Layout instalado

```text
<LocalSuite>/Plugins/NEURO RT/
  installation.json
  versions/<version>/
    module.json
    release-manifest.json
    neuro_rt/
    integration/
    catalog/
    app/                       # tela Nidus e alias do core compartilhado
    web/
    licenses/
  runtimes/<id>/<lock_digest>/  # imutáveis, com Python e dependências próprias
  models/<id>/<revision>/       # pesos e textos originais verificados
  data/jobs/<study_id>/         # entradas, execução e logs privados
  data/studies/<study_id>/revisions/<n>/
  config/
  staging/
```

`PluginPaths` resolve essa árvore a partir da raiz real do host. O código de
produção não usa diretórios de desenvolvimento como fallback. Instalação em disco
e ativação são passos diferentes; uma versão em uso não é substituída por arquivos
novos. A versão anterior, modelos válidos e dados são preservados.

## Contrato do host

O manifesto 1.0.2 exige `local-suite/plugins/1` e Local Suite 8.11 ou posterior. O host
carrega a entrada conhecida e chama `montar(app, code_dir, host_services=...)` uma
vez. HostServices fornece:

- `resolve_series_ticket`: descritor autorizado e origem privada do bilhete do
  carregador existente; nunca interpreta um path vindo da API Neuro v2.
- `queue_bridge`: enqueue/await/report/finish/cancel na arbitragem única da estação.
- `device_preference`: a preferência global é congelada quando o item recebe a vez.
- `register_result`: publicação confirmada no acervo comum, sem substituir um arquivo
  válido por resultado de exportação incompleta.
- `export_rtstruct` e `viewer_routes`: capacidades do host; a execução usa seus
  motores em subprocessos, sem importar bibliotecas científicas na home.

Os callbacks de produção são composição interna, não opções técnicas a preencher
pelo usuário. Os descritores expostos à seleção contêm bilhetes e grupo opaco;
UIDs, paths, PatientID e logs não pertencem ao StudyView.

## API de estudos

A API integrada usa `/neuro/api/`. Mutações exigem conexão local, host/origem
permitidos e `X-Neuro-Token` obtido no status. Respostas sensíveis usam `no-store`.

- `GET status`: estado e token da instância.
- `POST selection`: `{tickets, category}`; retorna modelos, bindings sugeridos,
  elegibilidade, avisos e séries/grupos opacos.
- `POST studies`: `neuro-rt/request/2`, pedido explícito, estudos/referências,
  modelos e canais distintos por modelo.
- `GET studies`: trabalhos atuais e revisões publicadas no store.
- `GET studies/{id}?revision=N`: estado ou revisão específica.
- `POST studies/{id}/cancel`: cancelamento explícito.
- `POST studies/{id}/retry`: `{explicit_request:true}`; revisão completa posterior.
- `GET studies/{id}/artifacts/{opaque_id}`: somente artefato declarado, confinado e
  íntegro. O ID não é um nome de arquivo nem um caminho recebido livremente.

Os endpoints legados por path servem o protótipo de desenvolvimento. A montagem
integrada recusa sua submissão. Nenhuma seleção, abertura de página ou reabertura
de resultado inicia inferência por omissão.

## Execução e resultados

Cada item tem uma referência. Entradas devem pertencer ao mesmo sujeito, estudo e
modalidade. Classificação incerta não é ausência de volume. Preparação usa o leitor
do host; registros são explícitos em coordenadas físicas LPS. As máscaras voltam à
grade completa da referência e são verificadas antes da entrega.

A fila dá uma concessão por item; os modelos rodam sequencialmente. Na fase1.1.0,
os workers usam o mesmo Python da suíte completa, CODE explícito e flags -I/-B.
Somente extras ausentes e compatíveis são acrescentados ao final dos caminhos de
importação; bibliotecas da base mantêm prioridade. O processo científico é oculto
e, no Windows, recebe JobObject com handshake antes da entrada científica.
O cancelamento encerra e confirma os descendentes antes de liberar a vez.
Falhas independentes não descartam saídas válidas dos demais.

O store publica revisões completas, preserva anteriores e resolve artefatos por
IDs opacos. Retry só reutiliza entradas/máscaras íntegras e fingerprints iguais.
Reiniciar recupera resultados e marca trabalho interrompido; não o reinicia sozinho.

Um RTSTRUCT é gravado por referência/execução com ROIs por modelo/classe. O mesmo
`engine.build_rtstruct` da suíte grava e o leitor nativo `radai_rt.SessaoRT` confere
voxels, SOPs e planos. Uma ROI pequena não desaparece silenciosamente. Erro ou
omissão preserva máscaras e declara exportação falha/incompleta. A publicação usa
nome exclusivo e conserva os arquivos anteriores. Todas as estruturas são
`UNAPPROVED`; fusão/edição/aprovação pertencem ao TPS e ao operador.

## Nidus e Recon3D

A tela Nidus pertence ao plugin e é montada por `integration/nidus_bridge.py`.
O alias `radai_nidus` aponta para o core compartilhado `radai_projection` do
Recon3D. O helper de osso também pertence ao serviço compartilhado. Assim Recon3D
funciona sem instalar a tela Nidus, com uma implementação geométrica.

A entrada é `/neuro/nidus`; `/nidus/projecao` e APIs legadas continuam compatíveis.
Não montar a tela Nidus novamente no laço base do painel. O repositório antigo só
poderá ser removido em etapa posterior, após conferência da migração.

## Pacotes e compatibilidade

O manifesto transacional inventaria todos os arquivos, tamanhos, hashes e licenças.
Atlas NIfTI só entra pela allowlist de origem/hash; dados de trabalho nunca entram.
Buti é gerido pelo host e não é duplicado no payload do plugin. O Brain auxiliar
Raidionics e a prova de licença do atlas também entram na verificação de preflight.

O conector latest fixa a release/asset e confere SHA externo. Acesso privado é
explícito; nenhum token viaja no código. Sem rede, uma versão íntegra continua
utilizável. A atualização respeita a fila e a reabertura controlada do host. Consulte
`installer/PACKAGE_FORMAT.md` e `docs/IMPLEMENTACAO_PLUGIN.md` para estado e provas.

O contrato comum exige Python3.10 ou posterior e a fase1.1.0 requer Local Suite8.12.
O plugin não baixa outro Python, não cria venv e não sobrescreve ou rebaixa as
bibliotecas da suíte. Receitas fixam fontes, versões, tamanhos, SHA256 e licenças
dos extras e pesos. Um conflito com a base é apresentado antes da preparação.
O modo legado de runtimes privados pertence às revisões anteriores; sua presença
no contrato de compatibilidade não descreve a instalação1.1.0. GPU e outras
estações/Windows precisam de suas provas próprias antes de serem anunciadas como
compatíveis. Consulte `docs/FINAL_VALIDATION_v1.1.0.json` para os escopos testados.
