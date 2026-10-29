# NEURO RT — Interface integrada e Nidus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Planejamento apenas. Não gerar novo frontend ou modificar telas nesta rodada.

**Goal:** tornar o Neuro uma extensão visual e funcional do Local Suite, com
seleção compreensível de modelos e resultados anatômicos na referência escolhida.

**Architecture:** páginas hospedadas no servidor da suíte e compostas com seus
componentes compartilhados. Catálogo, elegibilidade e status vêm do backend único;
o frontend apresenta escolhas e resultados, sem decidir regras científicas.

**Tech Stack:** HTML/CSS/JavaScript existentes, menu, seletor de séries, fila,
popups e motores de Reconstruções 3D/MPR do host; sem novo framework ou CDN.

**Spec:** [desenho](../specs/2026-10-29-neuro-rt-plugin-local-suite-design.md).

## Global Constraints

- Aplicam-se as restrições do [plano mestre](2026-10-29-neuro-rt-roadmap.md).
- A referência de design é o Local Suite instalado e Reconstruções 3D, não um novo tema.
- Chaves inicialmente desligadas; não oferecer AUTO, FAST ou selecionar modelos por omissão.
- Nome/chave desativados em ausência real; “?” permanece ativo, legível e acessível.
- Ambiguidade gera aviso informativo e permite execução; não introduzir modal obrigatório.
- Anatomia nos cards tumorais usa os mesmos IDs/arquivos do card Anatomia RT.
- Nidus mantém seus recursos; migração não acrescenta exportação da interseção.

## Review Focus

- “?” dentro de linha desativada: U03 comprova abertura por mouse e teclado.
- Troca rápida entre duas séries: U04 não mostra resposta atrasada da série anterior.
- Seleção anatômica com muitas ROIs: U04 mantém busca e visibilidade utilizáveis.
- Dois caminhos de entrada para o mesmo modelo: U02 não duplica seleção/pesos/estado.
- Instalador falha: U01 mostra recuperação, sem transformar card em link quebrado.

## Direção de layout e design

### Home e minipágina

A home conserva posição, dimensões, ritmo e interação do card inferior esquerdo,
trocando sua identidade para NEURO RT. A minipágina usa o mesmo cabeçalho/menu e
uma grade de cinco cards. Não acrescentar um sexto card para cada motor; os motores
ficam nas tabelas das ferramentas, não na navegação principal.

Entradas propostas: `/neuro/`, `/neuro/nidus`, `/neuro/glioma`,
`/neuro/metastasis`, `/neuro/meningioma` e `/neuro/anatomia`.
Os paths são decisões técnicas para o host integrado. Links internos antigos
do Nidus que ainda são usados devem continuar resolvendo durante a migração.

### Tela de trabalho

O carregamento usa o popup comum. Depois de carregar, a pessoa vê a lista de
séries/conjuntos, referência atual e tabela de modelos do card escolhido. A
tabela preserva densidade, tipografia, alinhamento, tooltips e controles do host.
O grupo de anatomia é uma seção da mesma tabela, com seleção independente.

Ao iniciar, progresso/fila aparecem pelo componente comum. Ao terminar, a área
principal apresenta o resultado no padrão Recon 3D, com seletor da série
segmentada e lista de estruturas. Voltar à seleção mantém o contexto do estudo.

### Visualizadores

Preservar o arranjo aprovado: axial como plano principal, 3D ao lado e sagital/
coronal auxiliares; aproveitar os componentes compartilhados e seu comportamento
de ampliar/trocar plano. Se o componente compartilhado atual difere em detalhes,
adaptar o invólucro do Neuro, não reescrever o renderizador para obter esse arranjo.

Visores compartilham série, posição espacial, cores e estado de estruturas.
Ao escolher outra série, atualizar imagem, contornos, malhas, referência e rótulos
como uma unidade. Um controle de opacidade não altera a máscara exportada.

### Linguagem visual

Reutilizar tokens/classes de tipografia, espaçamento, cores, bordas, sombras,
foco, loading e animação existentes. Usar CSS do Neuro apenas onde o componente
comum não cobre o layout, sempre sob escopo do plugin. Respeitar temas/idiomas,
zoom e preferências de movimento do sistema conforme o host. Evitar animação
contínua custosa durante inferência; progresso não deve concorrer com o worker.

## U01 — Home, entrada do plugin e cinco cards

**Files:** modificar `C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_porta.py`,
`C:/AI_PROJETOS/AUTO_CONTORNO/app/porta/porta.js` e os registros de menu/tradução
que eles efetivamente consomem; criar
`C:/AI_PROJETOS/NEURO_RT/integration/radai_neuro_screen.py`;
adaptar `C:/AI_PROJETOS/NEURO_RT/web/index.html`, `app.js` e `style.css`.

**Interfaces:** `pagina_neuro(host_services, plugin_status) -> HTML` e
`pagina_estudo(category, host_services) -> HTML`, na tela integrada.
`category` é `glioma`, `metastasis`, `meningioma` ou `anatomia`; Nidus tem seu
próprio renderer existente. Estado de instalação vem de I01/I02.

- [ ] Registrar referências visuais da home, popup de carregamento, tabela e
  Recon 3D existentes usando dados sintéticos; nenhuma captura de exame privado.
- [ ] Substituir o card conservando posição e interação. A ação consulta o plugin:
  ausente oferece instalar; instalado abre a minipágina; falha explica e permite tentar.
- [ ] Mostrar download/preparo/ativação com estágios reais. Percentual de bytes não
  significa percentual de toda instalação; não congelar em 100% durante a etapa seguinte.
- [ ] Criar cinco cards no padrão da suíte, usando navegação comum e retorno à home.
  Não duplicar logos, seletor de dispositivo, linguagem ou configurações.
- [ ] Integrar reinstalação/reabertura controlada ao fluxo de I02/I04, sem deixar
  uma tela em branco esperando um backend que mudou de versão.
- [ ] Verificar visualmente ausência/instalação/falha/pronto, temas e largura alvo.
  Testar ações contra backend de teste; não escrever testes de contagem de classes CSS.
- [ ] Aceite: fluxo completo da home até cada ferramenta, inclusive plugin ausente.
  Revisar/commitar com evidência visual sem PHI.

## U02 — Seleção de séries, conjuntos e modelos

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/web/model-selection.js` e
`C:/AI_PROJETOS/NEURO_RT/web/model-selection.css`; adaptar `web/app.js` e a tela
integrada dentro de `C:/AI_PROJETOS/NEURO_RT`; consumir seletor e fila do host.
Criar `C:/AI_PROJETOS/NEURO_RT/tests/test_selection_api.py` para o contrato servidor.

**Interfaces:** `renderModelSelection(container, selectionState)` e
`collectStudyRequest(selectionState) -> StudyRequest v2` no módulo JS proposto.
`selectionState` contém séries/tickets, referência, ModelSpecs públicos, bindings,
elegibilidade e chaves escolhidas. Backend expõe elegibilidade por
`POST /neuro/api/selection`; submissão continua em `POST /neuro/api/jobs` com schema v2.

- [ ] Exibir séries/conjuntos identificáveis pelo padrão de rótulos da suíte;
  detalhes locais não vão a query strings ou logs públicos.
- [ ] Para cada linha, mostrar chave, nome, exigências resumidas, estado e “?”.
  Sem coluna de implementação inútil para quem está escolhendo o modelo.
- [ ] Usar `Eligibility` de D02: disponível permite escolher; ausente desativa
  nome/chave; incerto fica selecionável com aviso. Aplicar opacidade ao nome/chave,
  não ao popup, e manter leitura suficiente para a pessoa entender o que falta.
- [ ] Mostrar papéis de entrada propostos e referência, com correção opcional e
  escolha entre duplicatas; não criar uma confirmação impeditiva para incerteza.
- [ ] Anatomia aparece nos três cards tumorais com as mesmas entradas de catálogo;
  estado da seleção usa IDs, e não strings traduzidas de nomes de modelos.
- [ ] Habilitar iniciar quando existir ao menos um modelo escolhido com entradas
  concretas e requisitos técnicos satisfeitos. Abrir página não inicia inferência.
- [ ] Congelar o pedido submetido; edições posteriores da tela não alteram o job
  em andamento. Outro pedido recebe outro ID e entra na fila comum.
- [ ] Testar o contrato com `test_selection_api.py` e, no navegador, carregar quatro
  séries incertas, remover uma, escolher modelos e verificar payload/estado efetivos.
  Aceite: comportamento visual e servidor coerentes. Revisar/commitar.

## U03 — Popup educacional por modelo

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/web/model-help.js` e conteúdo estruturado
em `C:/AI_PROJETOS/NEURO_RT/catalog/model_help.json`; adaptar
`C:/AI_PROJETOS/NEURO_RT/web/bibliografia.html` e mapeamento de traduções do plugin.

**Interfaces:** `openModelHelp(anchor, modelId, eligibility)` consome o catálogo e
conteúdo versionados; só interpola dados locais necessários ao motivo de disponibilidade.
Não carregar texto arbitrário da internet para dentro do popup a cada abertura.

- [ ] Definir conteúdo curto inicial: o que segmenta, quais séries precisa e por
  que está disponível/indisponível/incerto neste exame.
- [ ] Organizar explicação complementar: método, preparação, classes entregues,
  equipamento suportado, limitações, referência/publicação, versão e licença.
- [ ] Distinguir U-Net de propagação de atlas; explicar nomes WT/TC/ET e que
  metástase/glióma são o objetivo do modelo, não diagnóstico emitido pelo aplicativo.
- [ ] Mostrar pesos/runtime ausentes como problemas de instalação, não como falta
  de sequência. Não misturar licenciamento com validação científica.
- [ ] Garantir abertura com clique e teclado, fechamento por Escape/clique externo,
  posicionamento dentro da janela e retorno de foco. “?” não fica dentro de um
  controle desativado que capture seus eventos.
- [ ] Revisar conteúdo contra M01–M08; citar apenas evidências reais e informar
  quando desempenho/tempo não foram medidos no ambiente do plugin.
- [ ] Aceite: ajuda útil em todos os estados, legível em tema claro/escuro, sem
  exigir inferência ou download para explicar o modelo. Revisar/commitar.

## U04 — Progresso, resultados e visores integrados

**Files:** adaptar `C:/AI_PROJETOS/NEURO_RT/web/app.js`, `viewer.js`,
`mesh-view.js` e `C:/AI_PROJETOS/NEURO_RT/neuro_rt/build_views.py` apenas como
pontes; criar `C:/AI_PROJETOS/NEURO_RT/web/result-selection.js`;
consumir `C:/AI_PROJETOS/RECON_3D/app/radai_recon3d_screen.py` e seus motores,
sem copiar o renderizador. Estender `C:/AI_PROJETOS/NEURO_RT/tests/test_views.py`
e `test_view_centers.py`.

**Interfaces:** `showStudyResult(studyView, referenceTicket)` abre o resultado;
`selectResultSeries(studyId, revision)` troca o item ativo.
O estado recuperável vem de `GET /neuro/api/jobs/{study_id}` e índice
`GET /neuro/api/results`, implementados em D07; caminhos de imagem permanecem autorizados.

- [ ] Usar o componente comum da fila e suas ações, exibindo preparo, modelo atual,
  retorno à referência, exportação e visualização sem inventar progresso contínuo.
- [ ] Mostrar concluído/parcial/vazio/falha com diferença explícita e retry aplicável.
  Não traduzir máscara vazia como ausência confirmada de tumor.
- [ ] Abrir o resultado na referência selecionada; seletor lista séries segmentadas
  e suas revisões disponíveis, não cada sequência auxiliar como se fosse novo resultado.
- [ ] Usar lista de estruturas do Recon: busca, visibilidade individual, ações sobre
  as filtradas e opacidade. Preservar cores/lateralidade de cada ROI nos MPRs e 3D.
- [ ] Cancelar/ignorar respostas antigas durante troca rápida de série, liberar
  recursos WebGL que saem de uso e preservar estado de navegação de forma coerente.
- [ ] Abrir grandes conjuntos anatômicos com os padrões de visibilidade do host,
  evitando travar o navegador ou pré-carregar todas as malhas sem necessidade.
- [ ] Verificar sincronização entre cortes, contornos e malhas com fantomas e série
  oblíqua; usar `test_views.py`/`test_view_centers.py` para geometria e navegador para UX.
- [ ] Aceite: troca de série nunca mistura contornos de outra referência; reload e
  retorno à minipágina reabrem resultados do acervo sem refazer inferência. Revisar/commitar.

## U05 — Migração funcional completa do Nidus

**Files:** modificar os arquivos já transferidos por I05:
`C:/AI_PROJETOS/NEURO_RT/app/radai_nidus.py`,
`C:/AI_PROJETOS/NEURO_RT/app/radai_nidus_screen.py` e
`C:/AI_PROJETOS/NEURO_RT/tools/test_nidus.py`;
adaptar somente imports, montagem e navegação necessários. Fontes anteriores em
`C:/AI_PROJETOS/NIDUS_RT` servem de baseline; não repetir a migração Git de I05.

**Interfaces:** manter os módulos/imports funcionais Nidus e uma única chamada
de montagem. Entrada `/neuro/nidus` delega à tela existente; aliases `/nidus/...`
podem permanecer compatíveis enquanto seus consumidores forem migrados, sem duas
instâncias do serviço ou dois conjuntos de estado.

- [ ] Rodar baseline sintética do Nidus antes da mudança e inventariar fluxos:
  escolha de série, caixa, projeção, ângulos, desenho, interseção, MPR e visualização 3D.
- [ ] Conferir o inventário de fontes, testes e documentação transferidos por I05;
  não aproveitar a mudança de repositório para redesenhar geometria ou remover recursos.
- [ ] Substituir caminhos dependentes da pasta antiga pela resolução do plugin/host.
  Preservar SimpleITK, reader, motor de projeção e renderizador compartilhados.
- [ ] Preservar remoção de osso a partir da segmentação existente e o pedido explícito
  de preparação pela fila. Não inserir detecção vascular nova nem exportação da interseção.
- [ ] Ajustar menu/cabeçalho/retorno para o contexto NEURO RT, mantendo os controles
  de incidência e convenções angulares já existentes.
- [ ] Executar `tools/test_nidus.py` pelo resolvedor de componentes atualizado e
  repetir o fluxo no navegador com fantoma. Conferir que instalação sem plugin
  não tenta importar Nidus removido do bundle base.
- [ ] Aceite: equivalência funcional demonstrada, uma montagem, dependências resolvidas
  e navegação integrada. Entregar evidência a R05; nenhuma exclusão remota nesta tarefa.

## Padrão de aceite visual

Verificar telas vazias e carregadas, erro, falta de sequência, classificação
incerta, muitos modelos/ROIs, janela reduzida, zoom aumentado, teclado, tema e
idioma suportados pelo host. Capturas e roteiros usam dados sintéticos ou demos
permitidas. O aceite visual é comparação com a suíte existente e teste das ações,
não um redesign abstrato nem uma imagem estática sem funcionalidade.
