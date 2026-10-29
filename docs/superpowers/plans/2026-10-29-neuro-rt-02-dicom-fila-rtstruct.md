# NEURO RT — Dados, fila e RTSTRUCT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Documento de execução futura; nesta rodada, não escrever código funcional.

**Goal:** transformar escolhas de modelos/séries em resultados rastreáveis na
geometria correta, executados pela fila comum e publicados uma vez por referência.

**Architecture:** contratos versionados separam inventário DICOM, associação de
entradas, plano de execução, resultados dos motores e publicação. A fila do host
concede a vez; o plugin coordena etapas internas e mantém estado persistente.

**Tech Stack:** Python, leitor DICOM e gravador existentes, SimpleITK, manifestos
JSON, processos locais e adaptadores da fila/acervo do Local Suite.

**Spec:** [desenho](../specs/2026-10-29-neuro-rt-plugin-local-suite-design.md).

## Global Constraints

- Restrições do [plano mestre](2026-10-29-neuro-rt-roadmap.md) integram todas as tarefas.
- Uma referência por item; um arquivo por referência/execução; sem fusão entre máscaras.
- Modelos só executam quando escolhidos; ambiguidade de sequência não bloqueia.
- Nenhum conjunto cruza sujeitos ou inventa uma sequência ausente.
- Fila da estação é a única autoridade de execução pesada e cancelamento.
- Procedência, lateralidade e geometria têm de sobreviver ao pré-processamento.
- Nunca recriar o gravador RTSTRUCT ou ativar transferência RM–TC implícita.

## Review Focus

- DICOMs oblíquos, anisotrópicos ou em ordem de arquivo invertida: D03/D06 usam espaço físico.
- FLAIR com descrição incerta entre quatro volumes: D02 permite executar com aviso.
- Duplo clique e duas abas: D04 garante idempotência por request e uma posse global.
- ROI não vazia abaixo do limite aceito pelo gravador: D06 não anuncia saída completa.
- Reinício após máscaras prontas, antes de publicar: D07 recupera o estágio correto sem inferência silenciosa.

## D01 — Contratos de estudo e resultado v2

**Files:** modificar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/contracts.py`; criar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/study_types.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_study_contracts.py`; adaptar
`C:/AI_PROJETOS/NEURO_RT/tests/test_http.py` posteriormente ao novo endpoint.

**Interfaces:** `validate_study_request(payload, catalog, series_index) -> StudyRequest`
e `validate_model_result(result, model_spec) -> ModelResult`.
Tipos compartilhados moram em `study_types.py`; nomes/campos são os do plano mestre.
O catálogo é consumido sem importar o runtime científico.

- [ ] Testar pedido sem ato explícito, modelo fora do catálogo, referência desconhecida,
  binding de outro sujeito e dois itens repetindo a mesma referência no mesmo pedido.
- [ ] Definir `StudyRequest` v2 com ID idempotente e itens; cada item contém referência,
  `model_ids` e `bindings_by_model`. Cada binding preserva papel, série e avisos.
- [ ] Definir `ModelResult` com `model_id`, `status`, máscaras/class IDs, versões,
  transformações e erros/avisos estruturados; classes precisam corresponder ao manifesto
  do artefato. Não aceitar índice desconhecido silenciosamente.
- [ ] Definir `StudyManifest` v2 com versão do plugin, referência/UIDs, revisão,
  modelos solicitados, resultados, dispositivo efetivo e recibo de exportação.
- [ ] Conservar leitura dos resultados v1 por adaptador explícito `read_result_v1`;
  para API v1 legada, converter uma solicitação de modelo/série para um item v2.
  Nunca inferir modelo/UID a partir de nomes dos arquivos de resultados.
- [ ] Preservar a entrada NIfTI já usada pelo protótipo/ferramentas, quando aplicável,
  como caminho sem RTSTRUCT na ausência do DICOM original; não fabricar referências
  DICOM nem exigir nova interface de importação fora do escopo aprovado.
- [ ] Verificar com `test_study_contracts.py`: entradas inválidas dão erro específico;
  exemplo válido conserva a ordem dos canais de cada modelo. Revisar/commitar.

## D02 — Inventário, agrupamento e elegibilidade

**Files:** modificar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/imaging.py`; criar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/series_selection.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_series_selection.py`;
estender `C:/AI_PROJETOS/NEURO_RT/tests/synthetic_dicom.py` apenas com dados sintéticos.

**Interfaces:** `describe_series(series_ticket, host_services) -> SeriesDescriptor`,
`suggest_bindings(series_list, model_spec) -> list[InputBinding]` e
`evaluate_eligibility(model_spec, bindings, capabilities) -> Eligibility`.
Consome D01, `HostServices.resolve_series_ticket` de I03 e `ModelSpec` de M01.
U02 consome exatamente a mesma elegibilidade; não manter uma segunda regra no JS.

- [ ] Usar o seletor/leitor comum e seus tickets. Separar séries por UID e sujeito;
  a pasta não é unidade de identidade, e nomes de arquivos não definem sequência.
- [ ] Usar metadados disponíveis — descrição, protocolo e parâmetros de aquisição —
  como evidências para sugerir T1/T1c/T2/FLAIR. Registrar evidências e conflitos;
  o atributo MR sozinho não comprova contraste ou ponderação.
- [ ] Construir testes com quatro séries completas, três séries com canal ausente,
  quarta série incerta, duas candidatas T1c, duas datas e dois sujeitos.
- [ ] Em conjunto completo e incerto, `selectable` permanece verdadeiro, `warnings`
  explica a classificação e o mapeamento proposto é visível/editável. Não exigir
  correção/aceite adicional para executar só por causa da incerteza.
- [ ] Em canal realmente sem série atribuível, `selectable` é falso e `missing_roles`
  identifica o canal. Não preencher com zeros, clonar outra série nem sintetizar entrada.
- [ ] Distinguir ausência de entrada de peso/runtime indisponível: campos e mensagens
  diferentes; o “?” deve explicar o motivo real. Erro de geometria/arquivo ilegível
  não se converte em mera ambiguidade sem consequência técnica.
- [ ] Oferecer troca opcional de candidato em duplicatas, mantendo associação inicial
  determinística e verificável. Nunca misturar pré/pós-operatório por proximidade de nome.
- [ ] Verificar `test_series_selection.py`. Aceite: chave no cliente e decisão do
  servidor coincidem nos casos acima, especialmente ausência versus incerteza. Revisar/commitar.

## D03 — Referência, preparação e retorno das máscaras

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/geometry_pipeline.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_reference_geometry.py`; adaptar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/imaging.py` e `worker.py`.

**Interfaces:** `prepare_model_inputs(bindings, reference, model_spec, context)
-> PreparedInputs`; `restore_masks(model_result, prepared, reference) -> list[MaskArtifact]`;
`verify_reference_geometry(mask, reference) -> GeometryReport`.
`PreparedInputs` contém canais ordenados, grade de trabalho e cadeia de transformações.
`MaskArtifact` identifica classe, path privado, grade e origem por modelo.

- [ ] Construir fantomas assimétricos com marcos conhecidos, orientação oblíqua,
  espaçamentos distintos e objeto pequeno junto à borda. Eles devem denunciar flips.
- [ ] Carregar séries respeitando coordenadas físicas; identificar orientações LPS/RAS
  nas interfaces, sem tratar mudanças de convenção como simples inversão de array.
- [ ] Selecionar a referência única e construir o pipeline específico do motor.
  Registrar original → registro → reamostragem/recorte → entrada da rede e o retorno.
- [ ] Usar o pré-processamento publicado daquele peso. Não impor registro deformável
  a todos os motores só porque ANTs estará instalado. No atlas, a deformação atlas→exame
  pertence ao método; em motores tumorais, reproduzir suas exigências verificadas.
- [ ] Restaurar probabilidades/rótulos na sequência correta do pipeline. Para rótulos
  discretos, conservar o vocabulário de classes; não criar rótulos fracionários.
- [ ] Documentar o espaço de cada artefato. A referência final recebe todas as ROIs,
  mesmo quando um modelo anatômico usou T1 e o modelo tumoral usou T1c.
- [ ] Verificar origem, direção, espaçamento, extensão e alinhamento em coordenadas
  físicas. Teste não passa só porque arrays têm o mesmo shape; exigir erro de marco
  compatível com a interpolação definida, limitado a meio voxel da referência onde aplicável.
- [ ] Executar `test_reference_geometry.py`. Aceite: marcos/lateralidade preservados,
  máscara no espaço escolhido e nenhum RTSTRUCT gerado para auxiliares. Revisar/commitar.

## D04 — Fila única e contrato com o host

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/integration/queue_bridge.py`;
modificar `C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_queue.py`, `radai_queue_state.py`,
`radai_todo.py`, `radai_atualizar.py` e
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/service.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_shared_queue.py`.

**Interfaces:** `QueueBridge.enqueue_study(request_id, study_item) -> QueueTicket`,
`await_turn(ticket, cancel_signal) -> QueueLease`, `report(ticket, progress)`,
`finish(ticket, outcome)` e `cancel(ticket)`.
Registrar `neuro` como executor/origem manual na fila existente, preservando sua
prioridade manual relativa ao vigia/turno. A lista e arbitragem do host são únicas.

- [ ] Testar ContourLab rodando ao chegar Neuro, Neuro rodando ao chegar ContourLab,
  dois pedidos Neuro, vigia esperando e duas submissões com o mesmo `request_id`.
- [ ] Substituir o início imediato em `Service.submit()` por submissão à fila.
  Um coordenador pode observar a fila, mas nenhum worker inicia antes da concessão.
- [ ] Registrar um item por referência/conjunto, com etapas por modelo, preservando
  as ações comuns de fila. A vez é mantida durante as etapas pesadas daquele item.
- [ ] Garantir exclusão mútua e liberação da posse em sucesso, erro, cancelamento e
  encerramento inesperado. Não usar simples leitura de status seguida de start sem trava.
- [ ] Propagar cancelamento para os processos filhos pertencentes ao item; não matar
  processos por nome genérico. UI e atualizador observam o mesmo estado persistido.
- [ ] Testar o atualizador em espera/interrupção explícita. Novo trabalho não fura a
  barreira de fechamento da fila enquanto uma atualização prepara a troca.
- [ ] Executar `test_shared_queue.py` com workers simulados controláveis e regressões
  do host afetadas. Aceite: máximo de um processamento pesado ativo. Revisar/commitar.

## D05 — Orquestração dos modelos e conclusão parcial

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/orchestrator.py`;
modificar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/service.py` e `worker.py`;
criar `C:/AI_PROJETOS/NEURO_RT/tests/test_orchestration.py`.

**Interfaces:** `build_study_plan(study, catalog) -> ExecutionPlan` e
`run_study(plan, context, registry) -> StudyManifest`. O registry é de M01/M02;
adapters implementam `prepare(context)`, `predict(prepared, context)` e
`normalize_result(raw, context) -> ModelResult`. Cancelamento/progresso ficam no contexto.

- [ ] Testar modelo A concluído, B falhando, C vazio e D concluído: D ainda executa,
  saída agrega A/D, C é vazio e B mantém causa. Estado geral: parcial.
- [ ] Construir dependências de preparação por entradas, modelo/revisão, parâmetros
  e referência. Reutilizar cache só se todas essas identidades coincidirem.
- [ ] Executar modelos em sequência; liberar sessões/tensores e arquivos temporários
  de cada etapa de acordo com suas dependências. Não manter todos os modelos na GPU.
- [ ] Aplicar preferência global: CPU não usa CUDA; GPU estrita não cai silenciosamente
  para CPU; auto registra o dispositivo efetivamente usado e o motivo de fallback.
- [ ] Distinguir erro do motor, falta de recurso, cancelamento e resultado vazio.
  Registrar versão, limiar e pós-processamento publicados; não remover componentes
  pequenos nem selecionar apenas a maior lesão na integração.
- [ ] Em falha de preparação compartilhada, marcar somente os dependentes afetados;
  continuar caminhos independentes. Interrupção do usuário encerra o restante do item.
- [ ] Planejar retry com resultados anteriores válidos mais novas saídas: gerar uma
  revisão completa, sem executar novamente modelos já concluídos por obrigação.
- [ ] Executar `test_orchestration.py`. Aceite: estados/ROIs correspondem ao ocorrido,
  sem mensagem global de sucesso quando parte falhou. Revisar/commitar.

## D06 — Exportação única por referência

**Files:** modificar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/export.py`; criar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/roi_naming.py`;
estender `C:/AI_PROJETOS/NEURO_RT/tests/test_dicom_export.py` e criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_multi_model_export.py`.
Se necessário parametrizar destino, fazer mudança mínima no gravador existente
em `C:/AI_PROJETOS/CONTOURLAB/app/engine.py`, sem duplicar a construção de contornos.

**Interfaces:** `make_roi_identity(model_id, class_id, revision) -> RoiIdentity`;
`collect_reference_masks(manifest) -> RoiCollection`;
`export_reference(manifest, host_services) -> ExportReceipt`.
`RoiIdentity` contém ID estável, ROIName curto, descrição/procedência e cor.

- [ ] Testar dois modelos que chamam sua classe de Tumor: produzir duas ROIs com
  identidades diferentes no mesmo arquivo; não somar máscaras nem sobrescrever chave.
- [ ] Testar duas referências em um pedido: exatamente um arquivo por referência
  nesta execução; zero arquivos automáticos nas séries auxiliares.
- [ ] Preservar todas as classes publicadas, inclusive WT/TC/ET aninhadas; o usuário
  deve conseguir ligar/desligar as estruturas separadamente no visor e no TPS.
- [ ] Adaptar a lista permitida atualmente fixa em `Tumor_NeuroRT` para o catálogo
  verificado. Nomes curtos estáveis respeitam os limites DICOM; tradução não muda IDs.
- [ ] Chamar o gravador do host, conferir ROIs produzidas versus solicitadas e
  validar UIDs, UNAPPROVED e geometria antes de anunciar/publicar sucesso.
- [ ] Exercer o caso de ROI não vazia abaixo do mínimo do gravador atual: não
  aumentá-la artificialmente nem omiti-la em silêncio. Marcar exportação incompleta/
  falha explícita e conservar a máscara para inspeção. Nenhuma entrega completa é anunciada.
- [ ] Publicar com nome exclusivo na pasta de origem, sem substituir resultados
  anteriores; se origem não gravável, manter o artefato interno e informar que a
  publicação não concluiu. Não apresentar o cache como arquivo publicado na origem.
- [ ] Se todas as máscaras estiverem vazias, registrar resultado vazio sem RTSTRUCT.
  Se exportar falhar após inferir, permitir repetir exportação sem refazer a inferência.
- [ ] Executar `test_dicom_export.py` e `test_multi_model_export.py` com o gravador
  real e séries sintéticas. Aceite: conteúdo e referências corretos, não só existência
  do `.dcm`. Revisar/commitar.

## D07 — Persistência, reabertura e API segura

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/result_store.py`;
modificar `C:/AI_PROJETOS/NEURO_RT/neuro_rt/service.py`,
`C:/AI_PROJETOS/NEURO_RT/integration/radai_neuro.py` e
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/build_views.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_result_recovery.py`; adaptar `test_http.py`.

**Interfaces:** `save_manifest(manifest) -> revision`, `load_manifest(study_id,
revision=None) -> StudyManifest`, `list_results(reference_ticket=None)` e
`resolve_artifact(study_id, artifact_id) -> AuthorizedArtifact`, no `ResultStore`.
`register_result` do host recebe recibo/ticket e usa o acervo existente.
As respostas para UI usam `StudyView`, projeção autorizada do manifesto, não o
manifesto privado integral. Os endpoints de seleção/resultado definidos em U02/U04
pertencem a esta integração HTTP e consomem os mesmos contratos.

- [ ] Persistir transições de estágio e recibos atomicamente; índices podem ser
  reconstruídos a partir de manifestos válidos, sem inventar resultados por pasta.
- [ ] Reiniciar com itens concluídos, parciais e interrompidos: concluídos reabrem,
  interrompidos não aparecem como rodando nem reiniciam inferência silenciosamente.
- [ ] Expor API por IDs/tickets, mantendo mesma origem e proteção de ações mutantes;
  retirar dependência de paths em query para a UI integrada. Preservar adaptação
  explícita dos endpoints legados quando ainda consumidos por testes/ferramentas.
- [ ] Generalizar artefatos/visões via manifesto autorizado; não substituir a
  allowlist antiga por acesso irrestrito ao filesystem. Tentativas de traversal falham.
- [ ] Registrar séries/revisões no acervo comum; evitar duplicação de identidade
  e manter a versão anterior acessível quando houver retry bem-sucedido.
- [ ] Aplicar `no-store` a respostas sensíveis conforme host. Logs privados ficam
  locais; mensagens públicas de erro não expõem caminho/identidade do exame.
- [ ] Executar `test_result_recovery.py`, `test_http.py` e `test_service.py` afetados.
  Aceite: atualização/reinício preserva reabertura e referências; nenhum caminho
  arbitrário pode ser lido pela API. Revisar/commitar.

## Comando e evidência por tarefa

No diretório `C:/AI_PROJETOS/NEURO_RT`, usar o Python de desenvolvimento informado
no AGENTS: `.venv/Scripts/python.exe -m unittest discover -s tests -p <arquivo> -v`.
O nome de `<arquivo>` é o teste indicado na tarefa. Falha inicial deve exercer o
comportamento faltante; importar uma função inexistente não é sozinho evidência
de que o teste encontrará o defeito de geometria, fila ou exportação.

Depois das tarefas deste plano, rodar a suíte Neuro completa e as baterias do
host/componentes afetadas. Não repetir inferências pesadas sem alteração ou
falha que justifique. Guardar evidências sem dados privados no documento da entrega.
