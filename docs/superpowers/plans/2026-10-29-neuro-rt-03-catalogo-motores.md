# NEURO RT — Catálogo e motores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Execução autorizada em 29/10/2026. Consultar `../../IMPLEMENTACAO_PLUGIN.md` para estado e pendências.

**Goal:** integrar os modelos escolhidos sob contratos comuns, com artefatos,
pré-processamento, geometria, licenças e resultados verificáveis por versão.

**Architecture:** catálogo declarativo leve no host/plugin; adaptadores científicos
em workers isolados. Um registry associa IDs conhecidos a adaptadores permitidos.
Todos retornam `ModelResult`; o orquestrador, e não o motor, decide fila/exportação.

**Tech Stack:** ONNX/Raidionics; PyTorch/MONAI; SynthSeg; ANTs; nnU-Net do host;
QTIM/TensorFlow apenas se a compatibilidade Windows for demonstrada. Runtimes
fixados por lock, sem atualização global de dependências.

**Spec:** [desenho](../specs/2026-10-29-neuro-rt-plugin-local-suite-design.md).

## Global Constraints

- Restrições do [plano mestre](2026-10-29-neuro-rt-roadmap.md) valem para todos os adaptadores.
- Até cinco adições; Buti é reutilização, auxiliar cerebral é dependência existente.
- Cada peso define seu pipeline; não copiar normalização de um modelo para outro.
- Não treinar/fine-tunar em dados do serviço; não baixar peso não escolhido para completar catálogo.
- Código e pesos têm proveniência/licenças registradas separadamente.
- Preservar as classes/focos previstos, inclusive regiões aninhadas; não inventar classes.
- Performance externa, tempo e memória só são afirmados quando sustentados por evidência.

## Review Focus

- URL devolve HTML com status 200 em vez de peso: M01 detecta conteúdo/integridade incorretos.
- Quatro sequências na ordem errada: M04 compara canal a canal com o contrato do autor.
- Conversão de runtime muda inferência: M05/M07 exigem comparação com a referência.
- NIfTI de atlas entra no pacote: M06/R02 exige artefato permitido com origem/hash, sem liberar exames.
- Cache de Buti está no Python do host: M08 não testa disponibilidade no Python Raidionics.

## M01 — Catálogo declarativo, artefatos e política de distribuição

**Files:** evoluir `C:/AI_PROJETOS/NEURO_RT/neuro_rt/catalog.py` e
`C:/AI_PROJETOS/NEURO_RT/models.lock.json`; criar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/model_registry.py`,
`C:/AI_PROJETOS/NEURO_RT/catalog/models.json`,
`C:/AI_PROJETOS/NEURO_RT/docs/MODEL_CATALOG.md` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_model_catalog.py`;
adaptar `C:/AI_PROJETOS/NEURO_RT/scripts/prepare_models.py`.

**Interfaces:** `get_model(model_id) -> ModelSpec` permanece como consulta pública;
`get_adapter(model_id) -> AdapterFactory` usa registry explícito;
`verify_artifacts(model_spec, paths) -> ArtifactReport` valida o conjunto completo.
`ModelSpec` contém ID, rótulos/chaves de tradução, grupos, papéis/canais ordenados,
classe IDs, referência preferida, adapter ID, runtime ID, requisitos, licença,
fontes, perfil de preparo e estágio de disponibilização.

- [ ] Separar IDs atuais preservados de IDs propostos: `MRI_GBM_Postop_FV_3p`,
  `glioma_attention_unet3d`, `metastasis_qtim`, `anatomy_synthseg`,
  `anatomy_cerebra_ants` e `cranio_buti` para reutilização.
- [ ] Para cada arquivo, registrar URL original, revisão/tag imutável, nome,
  tamanho, SHA-256, formato, licença/aviso, origem do hash e dependências de inferência.
  A release própria fixa os hashes depois de obter/verificar artefatos reais.
- [ ] Distinguir estado do catálogo (`candidate`, `verified`, `distributed`) de
  instalação local (`missing`, `corrupt`, `ready`) e de elegibilidade do exame.
  A release só oferece para execução modelos distribuídos e localmente íntegros.
- [ ] Criar testes para artefato incompleto, licença não registrada, hash diferente,
  resposta HTML, classe não reconhecida, ID duplicado e download já íntegro.
- [ ] Preservar integralmente avisos exigidos e declarar licença dos pesos, não só
  do código. Registrar incertezas de procedência; não tratá-las como permissivas.
- [ ] Adotar carregamento de tensores restrito quando o formato permitir; não habilitar
  execução de código remoto por conveniência. Conteúdo baixado é dado, não instrução.
- [ ] Separar assets de atlas de imagens de trabalho: apenas arquivos explicitamente
  registrados como modelo/atlas público podem atravessar o empacotador.
- [ ] Verificar `test_model_catalog.py`; aceite: catálogo descreve exatamente o que
  o preparador consegue provar, sem nomes de modelos funcionais fictícios. Revisar/commitar.

## M02 — Adaptador Raidionics existente como corte vertical

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/base.py` e
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/raidionics.py`; adaptar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/worker.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_backend.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_raidionics_adapter.py`.

**Interfaces:** contrato de adapter `prepare(context) -> PreparedInputs`,
`predict(prepared, context) -> RawPrediction`,
`normalize_result(raw, context) -> ModelResult`, conforme D05.
`RawPrediction` é interno ao motor; o resto do produto só consome `ModelResult`.

- [ ] Preservar os cinco modelos binários existentes e o `MRI_Brain` auxiliar.
  Começar com um deles de ponta a ponta, sem alterar os pesos ou seus limiares.
- [ ] Reproduzir a importação/estrutura já corrigidas no projeto: backend e metadados
  reais, ONNX na pasta esperada, máscara cerebral quando o perfil a exige.
- [ ] Tirar o nome único `Tumor_NeuroRT` da lógica de múltiplos modelos; devolver
  classe `tumor` vinculada ao `model_id`, com nome final atribuído por D06.
- [ ] Confirmar equivalência com a execução v0.2 em entrada sintética/demonstração
  permitida e verificar que nenhum foco foi perdido pela camada nova.
- [ ] Verificar CPU, erro de peso/metadado e cancelamento; testar preferência de GPU
  somente em ambiente disponível, sem declarar suporte medido quando não existe.
- [ ] Rodar `test_backend.py` e `test_raidionics_adapter.py`, depois o corte D/U
  completo com gravador e visualizador. Aceite: mesma segmentação com novo fluxo,
  fila compartilhada e resultado versionado. Revisar/commitar.

## M03 — Raidionics GBM pós-operatório de três sequências

**Files:** estender `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/raidionics.py`,
`catalog/models.json` e `models.lock.json` dentro de `C:/AI_PROJETOS/NEURO_RT`;
criar `C:/AI_PROJETOS/NEURO_RT/tests/test_raidionics_multisequence.py`.

**Interfaces:** mesmo adapter de M02 com `ModelSpec` multicanal; não criar outro
pipeline de exportação. ID: `MRI_GBM_Postop_FV_3p`.

Fonte selecionada: [Raidionics-models](https://github.com/raidionics/Raidionics-models),
asset `Raidionics-MRI_GBM_Postop_FV_3p-ONNX_v12.zip`, release `1.2.0`.
Contexto: [estudo de pós-operatório](https://www.nature.com/articles/s41598-023-45456-x).

- [ ] Obter o asset e conferir seus metadados, classes e ordem real dos canais.
  Entradas previstas: T1c, T1 sem contraste e FLAIR do pós-operatório precoce.
- [ ] Documentar o que o modelo produz: tumor residual realçante, sem anunciar
  edema/necrose como saídas só porque existem três entradas.
- [ ] Reproduzir o preparo/registro exigidos pelo peso, referenciando o protocolo
  publicado. A existência de três arquivos não equivale ao preparo correto.
- [ ] Testar canal ausente, canal incerto presente, duplicata, ordem trocada e
  conjunto pré/pós incompatível; consumir a regra única de D02.
- [ ] Testar restauração na referência e mais de um componente na mesma classe.
- [ ] Executar `test_raidionics_multisequence.py` e um smoke real permitido.
  Aceite: entradas/saída correspondem ao artefato e não ao palpite do integrador.

## M04 — Attention U-Net 3D para glioma

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/attention_unet.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_attention_unet_adapter.py`; atualizar catálogo,
lock e conteúdo educacional em `C:/AI_PROJETOS/NEURO_RT/catalog`/`docs/MODEL_CATALOG.md`.

**Interfaces:** adapter comum; ID `glioma_attention_unet3d`; classes estáveis
`whole_tumor`, `tumor_core`, `enhancing_tumor`, associadas aos canais reais do peso.

Fonte: [pesos do autor](https://huggingface.co/motazalqaoud/brain-tumor-segmentation-weights).
O cartão publica MIT, modelo MONAI AttentionUnet 3D e checkpoint `best_model.pth`.
O artefato selecionado corresponde ao pipeline atual descrito pelo autor; não
usar releases antigas de classificação de tipos tumorais como se fossem esse peso.

- [ ] Fixar checkpoint, revisão, arquitetura exata e dependências verificadas.
  Conferir `model_state_dict` e os metadados sem executar código arbitrário do arquivo.
- [ ] Associar as quatro modalidades presentes: T1, T1c, T2 e FLAIR. A ordem
  visual da tabela não define a ordem dos canais; registrar a ordem do código do autor.
- [ ] Reproduzir alinhamento, preparação, normalização e inferência por janelas
  usados na distribuição do modelo. Não limitar o estudo a uma fatia para acelerar.
- [ ] Tratar WT/TC/ET como regiões sobrepostas/aninhadas, não como três classes
  mutuamente exclusivas por argmax quando o modelo usa saídas sigmoid independentes.
- [ ] Testar um volume multicanal de valores identificáveis para demonstrar ordem,
  saída aninhada conhecida, janela de borda e restauração da geometria.
- [ ] Documentar que é checkpoint experimental de pesquisa; métricas do autor não
  se tornam métricas do NEURO RT em exames de qualquer origem.
- [ ] Rodar `test_attention_unet_adapter.py` e smoke do peso real. Aceite: três
  regiões entregues fielmente, com tempo/memória medidos no ambiente usado.

## M05 — SynthSeg para estruturas anatômicas em RM

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/synthseg.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_synthseg_adapter.py`; atualizar catálogo/locks.

**Interfaces:** adapter comum; ID `anatomy_synthseg`; entrada inicial T1;
classes anatômicas vêm da tabela ligada ao peso, com lateralidade preservada.

Fontes: [SynthSeg original](https://github.com/BBillot/SynthSeg) e
[adaptação DIPY](https://docs.dipy.org/stable/_modules/dipy/nn/torch/synthseg.html).
A adaptação documenta arquitetura/pesos Apache-2.0 e download, mas precisa de
verificação técnica; não presumir equivalência de todas as variantes SynthSeg.

- [ ] Fixar uma variante e seus pesos, tabela de labels e runtime. Preferir uma
  implementação compatível com o ambiente escolhido; documentar qual realmente rodou.
- [ ] Conferir que o pré-processamento da implementação selecionada reproduz o
  contrato daquele peso, inclusive orientação, resampling e normalização.
- [ ] Verificar caminhos CPU/GPU; detectar diferenças entre tensores em GPU e
  conversão para NumPy, sem declarar suporte por mera presença de `use_cuda`.
- [ ] Mapear cada índice anatômico à ROI correta, distinguindo lados e excluindo
  apenas background. O número de estruturas vem do artefato efetivo.
- [ ] Testar retorno da grade de trabalho de 1 mm à série de referência, laterais
  assimétricas e classes desconectadas. Não suavizar/remover estruturas pequenas
  por analogia com modelos de órgãos grandes.
- [ ] Comparar a adaptação com referência conhecida quando aplicável e registrar
  diferenças numéricas/geométricas. Não alegar precisão em TC nesta integração T1.
- [ ] Rodar `test_synthseg_adapter.py` e smoke real permitido. Aceite: anatomia na
  referência e tabela de labels fiel, com seus limites explicados no “?”.

## M06 — CerebrA com registro deformável ANTs

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/cerebra_ants.py`,
`C:/AI_PROJETOS/NEURO_RT/tests/test_atlas_registration.py` e
`C:/AI_PROJETOS/NEURO_RT/catalog/atlas_assets.json`; atualizar preparo/empacotamento.

**Interfaces:** adapter comum; ID `anatomy_cerebra_ants`; artefatos incluem template,
atlas de rótulos, tabela anatômica, configuração de registro e textos de licença.
`RawPrediction` neste caso contém labels propagados e transformações, não logits.

Fontes: [CerebrA CC0](https://doi.gin.g-node.org/10.12751/g-node.be5e62/),
[ANTs](https://github.com/ANTsX/ANTs) e
[template MNI](https://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009).

- [ ] Conferir versão e compatibilidade espacial entre template e atlas. Não combinar
  variantes simétrica/assimétrica ou grids diferentes por semelhança de nome.
- [ ] Preparar ANTs no runtime Windows testado. Registrar versão, parâmetros e
  comando/API usados; não exigir configuração manual de Linux/Docker do usuário.
- [ ] Construir registro template→T1 com preparação, inicialização rígida/afim e
  etapa deformável apropriada; conservar direção das transformações e seus inversos.
- [ ] Propagar labels com interpolação adequada e mapear a tabela original às ROIs.
  Se a referência final for outra RM do conjunto, compor explicitamente a transformação.
- [ ] Testar identidade e transformação conhecida em atlas/fantoma sintético:
  conferir direção, round-trip, laterais e conjunto de labels. Testar também
  transformações não finitas/inválidas sem publicar resultado como íntegro.
- [ ] Expor no material educacional que propagação de atlas depende do registro;
  efeito de massa/cavidade podem prejudicar correspondência. Um registro numericamente
  executado não comprova correção anatômica nem preservação de função.
- [ ] Manter atlas públicos numa allowlist de assets com hash/licença. O pacote
  aceita esses NIfTI específicos e continua excluindo qualquer NIfTI de exames/jobs.
- [ ] Rodar `test_atlas_registration.py` e smoke real permitido. Aceite: registro
  reproduzível, labels na referência e evidências suficientes para inspecionar o alinhamento.

## M07 — QTIM Brain-Mets-Seg, condicionado à compatibilidade

**Files:** criar, somente se viável, `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/qtim_mets.py`
e `C:/AI_PROJETOS/NEURO_RT/tests/test_qtim_adapter.py`; manter decisão em
`C:/AI_PROJETOS/NEURO_RT/docs/MODEL_CATALOG.md`.

**Interfaces:** adapter comum; ID `metastasis_qtim`; T1c; resultado segmentado
conforme o pipeline publicado, sem introduzir classificação de resposta ou seguimento.

Fonte: [QTIM Brain-Mets-Seg](https://github.com/QTIM-Lab/Brain-Mets-Seg).
Os autores declaram Apache-2.0 para código e pesos, com ensemble de cinco folds.
Downloads e execução local ainda devem ser comprovados; links no Dockerfile
não são evidência de que os bytes baixados sejam checkpoints válidos.

- [ ] Primeiro provar download íntegro dos checkpoints/metadados e inventariar
  dependências TensorFlow/NVIDIA DALI. Não começar reescrevendo a rede às cegas.
- [ ] Separar dependências de treino das estritamente necessárias à inferência;
  avaliar caminho Windows oculto compatível com o host e sem Docker manual.
- [ ] Se houver adaptação/conversão, comparar entradas preparadas, probabilidades,
  binarização e ensemble com a implementação de referência, em dados permitidos.
  Definir tolerância numérica antes da comparação e documentar discrepâncias.
- [ ] Preservar preparo publicado: resolução, N4, extração cerebral, normalização
  e registros necessários. Não importar automaticamente o módulo longitudinal/RANO.
- [ ] Medir memória e CPU/GPU suportados, cancelamento e restauração da máscara.
- [ ] Se não houver caminho demonstrado, registrar motivo e excluir QTIM da release
  inicial, mantendo os quatro novos modelos restantes e o metastático já existente.
- [ ] Aceite: evidência de equivalência/funcionamento Windows ou decisão explícita
  de não distribuir. Um adapter mock não satisfaz essa entrega.

## M08 — Reutilização de Buti para TC

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/adapters/buti_host.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_buti_host_adapter.py`; adaptar catálogo.
Consumir `C:/AI_PROJETOS/CONTOURLAB/app/radai_cranio_engine.py` e
`C:/AI_PROJETOS/CONTOURLAB/app/radai_models.py`, sem duplicar esses motores.

**Interfaces:** ID `cranio_buti`, execução pelo host task `cranio_ct`, adapter
comum usando ponte de processo para o Python/paths efetivos do ContourLab.

- [ ] Resolver pesos pelo catálogo compartilhado e executar disponibilidade no
  Python do host; testar no runtime Raidionics não prova ausência de nnU-Net no host.
- [ ] Preservar preparo e dependências anatômicas do wrapper, incluindo recorte e
  critério de campo cerebral. Mostrar essas dependências no “?”.
- [ ] Preservar nesta entrega as cinco saídas atuais do wrapper. O peso bruto tem
  oito classes anatômicas, mas expandi-las alteraria a política acordada de reutilização.
- [ ] Testar reuso de peso já instalado, peso ausente, executor indisponível e
  referência CT; resultado final passa pelo mesmo agrupador D06.
- [ ] Documentar suporte do código a CT sem bloqueio por contraste, sem prometer
  que a base de treino/verificação local comprova desempenho específico sem contraste.
- [ ] Rodar `test_buti_host_adapter.py` com ponte simulada e smoke pelo motor real.
  Aceite: nenhum download duplicado e mesmas saídas do wrapper atual.

## Evidência mínima para cada modelo distribuído

Registrar versão do plugin/runtime, revisão/hash dos pesos, configuração de
pré-processamento, referência, conjunto de classes, dispositivo e fonte da imagem
permitida. Conservar resultado de smoke e inspeção espacial, uso aproximado de
memória/tempo na estação testada e falhas conhecidas. Esses números não são SLA.

Testes unitários de adapters podem usar saídas controladas para exercitar canais,
classes e geometria; a liberação exige também executar pesos reais. Demos de
automação continuam exemplos educacionais, sem inventar diagnóstico ou acurácia.
