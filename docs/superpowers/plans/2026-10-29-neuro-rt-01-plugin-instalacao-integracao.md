# NEURO RT — Plugin, instalação e integração Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Execução autorizada em 29/10/2026. Consultar `../../IMPLEMENTACAO_PLUGIN.md` para estado e pendências.

**Goal:** instalar e atualizar NEURO RT separadamente, carregando-o como parte do host.

**Architecture:** o host conserva um conector leve e consulta uma instalação
versionada do plugin. Código, runtimes, modelos e dados possuem ciclos de vida
distintos. O instalador prepara uma versão completa antes de ativá-la; a troca
usa a coordenação de encerramento/reabertura já existente na suíte.

**Tech Stack:** Python/FastAPI do host, PowerShell, ZIP, manifestos JSON,
hashes SHA-256 e releases GitHub, sem novas bibliotecas globais no host.

**Spec:** [desenho](../specs/2026-10-29-neuro-rt-plugin-local-suite-design.md).

## Global Constraints

- Aplicam-se todas as restrições do [plano mestre](2026-10-29-neuro-rt-roadmap.md).
- Pasta exata instalada: `<LocalSuite>/Plugins/NEURO RT`; plugin ID: `neuro-rt`.
- Instalação inicial confirmada; updates no padrão do Local Suite; dados preservados.
- Mesmo processo web/porta do host, inferência em processos ocultos autorizados pela fila.
- Repositório inicialmente privado; não embutir credenciais nem tornar público por conveniência.
- Não excluir NIDUS_RT nesta fase nem usar o checkout como destino de instalador.

## Review Focus

- Dois cliques/abas concorrentes: I02 comprova uma transação, com status compartilhado.
- Disco cheio durante extração: I02 conserva a versão ativa e os dados locais.
- Host antigo: I01/I03 recusam carregamento incompatível com explicação, sem derrubar a suíte.
- Atualização com fila Neuro ativa: I04 espera ou cancela pelo fluxo explícito do host.
- Caminho com espaços, acentos ou outro disco: I01/I02 comprovam resolução relocável.

## Arquitetura em disco proposta

Dentro de `<LocalSuite>/Plugins/NEURO RT`:

| Local | Responsabilidade | Política |
|---|---|---|
| `installation.json` | Versão ativa/anterior/pendente, schemas e inventário da instalação | Escrita transacional; sem dados de exames |
| `versions/<versao>/module.json` | Manifesto da versão, catálogo e compatibilidade | Imutável depois de verificado |
| `versions/<versao>/neuro_rt`, `web`, `integration`, `app` | Código e UI; `app` contém os módulos Nidus migrados | Trocar por versão, não sobrescrever arquivo importado |
| `runtimes/<runtime_id>/<lock_digest>` | Python e bibliotecas específicas | Compartilhar entre versões apenas quando o lock for idêntico |
| `models/<model_id>/<revision>` | Pesos, metadados e licença daquela revisão | Verificar antes de reutilizar; nunca confundir ID com integridade |
| `data/jobs`, `data/index` | Resultados e estado persistente do plugin | Preservar; integrar o índice de séries ao acervo comum |
| `config` | Configuração local necessária, com paths relativos | Não incluir em release nem substituir por defaults |
| `staging/<transaction_id>` | Downloads e extração ainda não ativados | Limpeza limitada à transação e após verificar paths |

O layout é uma decisão técnica proposta, não uma exigência de mostrar pastas ao
usuário. A raiz estável satisfaz o destino pedido. Runtimes/modelos não ficam
dentro da versão de código para evitar download duplicado a cada correção de UI.
O acervo da suíte mantém seus dados na política atual; não mover todo o acervo
para o plugin. A migração dos jobs do protótipo não pode apagar sua origem.

`module.json` evolui o manifesto existente e passa a declarar o contrato
`local-suite/plugins/1`. `host_min_version` será a versão real da primeira release
do host com esse contrato; não inventar número de release antes de sua criação.

## I01 — Manifesto, caminhos e estados da instalação

**Files:** modificar `C:/AI_PROJETOS/NEURO_RT/module.json`; criar
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/plugin_manifest.py` e
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/plugin_paths.py`; adaptar `Settings` em
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/service.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_plugin_manifest.py` e `test_plugin_paths.py`.

**Interfaces:** `read_manifest(path) -> PluginManifest` valida schema, ID,
contrato e referências relativas; `resolve_plugin_paths(host_root,
installation_state) -> PluginPaths` resolve os locais da tabela;
`check_host_compatibility(manifest, host_info) -> CompatibilityResult` devolve
compatibilidade, requisito e motivo legível. Donos: I01; consumidores: I02–I04/D01.

- [ ] Registrar a baseline e contratos atuais antes de editar, incluindo a resolução
  de `Settings.root`, `models_dir`, `host_app`, `host_python` e `data_dir`.
- [ ] Criar testes de manifesto ausente/inválido, plugin com ID diferente, host
  incompatível, paths escapando da instalação e path válido com espaço/acento.
- [ ] Implementar os três contratos sem importar PyTorch, Raidionics ou ANTs.
- [ ] Definir estados públicos: `absent`, `checking`, `installing`,
  `installed_pending_restart`, `ready`, `updating`, `incompatible` e `failed`.
  Separar estado da instalação do estado de um modelo específico.
- [ ] Em instalação de produção, remover fallback silencioso para `sys.executable`
  se faltar o runtime previsto; o status deve apontar preparo incompleto. Conservar
  configuração explícita de desenvolvimento para testes locais.
- [ ] Verificar com o Python de desenvolvimento: `-m unittest discover -s tests
  -p test_plugin_manifest.py -v` e o equivalente para `test_plugin_paths.py`, no
  diretório `C:/AI_PROJETOS/NEURO_RT`. Aceite: casos válidos resolvem o mesmo layout;
  erros não criam pastas fora do destino. Revisar e commitar a unidade.

## I02 — Instalador PowerShell transacional

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/installer/INSTALL.ps1` e
`C:/AI_PROJETOS/NEURO_RT/neuro_rt/install_state.py`; adaptar
`C:/AI_PROJETOS/NEURO_RT/scripts/build_portable_runtime.py` e
`C:/AI_PROJETOS/NEURO_RT/scripts/prepare_models.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_plugin_install.py` e fixtures de pacote pequeno.

**Interfaces:** `begin_install(host_root, package, transaction_id) -> InstallReceipt`,
`read_install_status(plugin_root) -> InstallStatus` e
`activate_release(plugin_root, version) -> ActivationReceipt`, em `install_state.py`.
O PowerShell expõe `-SuiteRoot`, `-PackagePath` e `-TransactionId`; a resolução de
URL/release pertence ao conector autorizado. Relatórios de progresso são JSON
locais da transação, sem caminhos de exames. Consome I01 e artefatos de M01/R02.

- [ ] Criar testes de pacote truncado, hash inválido, duplicidade de transação,
  saída fora do destino via ZIP, falta de espaço e cancelamento no meio da cópia.
- [ ] Validar a raiz do host por seus marcadores reais; não confiar em diretório
  corrente do PowerShell nem usar `C:/AI_PROJETOS` como fallback.
- [ ] Adquirir trava de instalação por plugin e publicar status comum para as abas.
  Um segundo pedido acompanha a transação; não começa outro download.
- [ ] Calcular espaço para download, extração e coexistência com a versão anterior.
  Baixar artefatos para staging, validar tamanho/hash e extrair só caminhos contidos
  no destino; rejeitar entradas absolutas, traversal e links que escapem dele.
- [ ] Preparar runtimes e pesos fixados. Reutilizar somente arquivos que passaram na
  verificação. Não instalar pip global nem modificar o Python do host.
- [ ] Escrever recibos de versão/licenças e marcar `installed_pending_restart`.
  Instalação em disco e ativação no host são passos distintos.
- [ ] Ativar pelo fluxo coordenado de reabertura do host. Na primeira instalação,
  a confirmação inicial cobre a instalação e a reabertura descritas no diálogo;
  trabalho ativo continua sujeito ao padrão de espera/interrupção da suíte.
- [ ] Testar em diretório sintético isolado com `test_plugin_install.py`. Aceite:
  falhas deixam a versão anterior íntegra e a reinstalação é idempotente. Não usar
  instalador contra a instalação real do usuário para validar o teste. Revisar/commitar.

## I03 — Carregador leve no Local Suite

**Files:** criar `C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_plugins.py` e
`C:/AI_PROJETOS/NEURO_RT/integration/host_services.py`; modificar
`C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_panel.py`,
`C:/AI_PROJETOS/NEURO_RT/integration/radai_neuro.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_adapter.py`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_plugin_host.py`.

**Interfaces:** `discover_plugin(suite_root, plugin_id) -> PluginInstallation` e
`mount_plugin(app, installation, host_services) -> MountReceipt`, no novo módulo
do host. Evoluir a entrada existente para
`montar(app, module_root, host_services=None) -> Service` e preservar um caminho
explícito de desenvolvimento com serviços simulados, nunca uma segunda fila em produção.

`HostServices` fornece: `host_info`, `resolve_series_ticket`, `queue_bridge`,
`device_preference`, `register_result`, `export_rtstruct` e `viewer_routes`.
Os adaptadores desses nomes devem envolver as funções existentes; não recriar os
serviços. O contrato de `queue_bridge` é definido em D04.

- [ ] Testar plugin ausente, corrompido e incompatível: home e apps base abrem normalmente.
- [ ] Montar uma única versão em startup/reabertura controlada. A mesma chamada
  repetida não duplica rotas, handlers de shutdown, menu ou instância de Service.
- [ ] Carregar somente o plugin conhecido e autorizado, por manifestos da instalação.
  Não transformar esta tarefa em descoberta de código arbitrário em qualquer pasta.
- [ ] Injetar serviços do host, paths reais e preferência global; tirar do contrato
  de produção a dependência de paths locais fixos para AUTO_CONTORNO.
- [ ] Manter mesma origem, controles de acesso/tickets e proteção das ações mutantes.
  Não transportar caminhos de exames na URL nem liberar artefatos por path livre.
- [ ] Executar `test_adapter.py` e `test_plugin_host.py`. Aceite: um host, uma porta,
  uma montagem e zero dependências científicas importadas para abrir a home. Revisar/commitar.

## I04 — Atualização independente com o comportamento da suíte

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/installer/UPDATE.ps1`; modificar
`C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_atualizar.py`,
`C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_plugins.py`,
`C:/AI_PROJETOS/AUTO_CONTORNO/installer/INSTALL.ps1` e
`C:/AI_PROJETOS/AUTO_CONTORNO/packager/UPDATE.ps1`; criar
`C:/AI_PROJETOS/NEURO_RT/tests/test_plugin_update.py`.

**Interfaces:** `check_plugin_release(plugin_id, installed_version) -> ReleaseCheck`
e `request_plugin_update(plugin_id, action) -> UpdateStatus` no conector do host;
`action` segue os atos existentes de aguardar/interromper, sem inventar um segundo
diálogo. Consome I01–I03 e atividade persistida de D04/D07.

- [ ] Testar abrir a minipágina sem rede, com mesma versão, release incompatível e
  release válida; ausência de rede não desativa instalação íntegra.
- [ ] Consultar latest ao abrir, compartilhando requisições concorrentes. Fixar o
  asset/revisão escolhidos durante a transação, mesmo se latest mudar no meio.
- [ ] Incluir Neuro em `o_que_segura()` e na espera da fila. Interrupção usa o
  cancelamento da fila e seus filhos, não encerra todos os processos Python do sistema.
- [ ] Preparar e verificar a nova release, manter a anterior, coordenar reinício
  do host e ativar. Nunca substituir módulos Python importados enquanto o plugin trabalha.
- [ ] Testar atualização do host com plugin instalado e do plugin com host estável;
  ambos preservam `data`, configuração, pesos válidos, acervo e release anterior.
- [ ] Verificar recuperação após falha antes/depois da troca do ponteiro ativo.
  Uma tentativa incompleta não aparece como atualização bem-sucedida.
- [ ] Executar `test_plugin_update.py` e regressões existentes do atualizador host
  afetadas pelo diff. Aceite: comportamento da suíte preservado com conhecimento
  da nova atividade Neuro. Revisar/commitar.

## I05 — Migração do repositório e da propriedade dos componentes

**Files:** migrar de `C:/AI_PROJETOS/NIDUS_RT/app`, `tools`, `docs` e arquivos de
licença para locais correspondentes dentro de `C:/AI_PROJETOS/NEURO_RT`;
criar `C:/AI_PROJETOS/NEURO_RT/docs/MIGRACAO_NIDUS.md`; revisar
`C:/AI_PROJETOS/NEURO_RT/.gitignore`, `LICENSE`, `NOTICE` e `AGENTS.md`;
modificar `C:/AI_PROJETOS/AUTO_CONTORNO/tools/_componentes.py`,
`C:/AI_PROJETOS/AUTO_CONTORNO/build/componentes.lock.json` e
`C:/AI_PROJETOS/AUTO_CONTORNO/build/empacotar_instalador.py` quando o novo carregamento
estiver pronto, não antes. Prova funcional em U05.

**Interfaces:** inventário de migração com origem, commit/tag quando existente,
destino, hash e motivo de exclusões deliberadas; registro único do proprietário
dos módulos Nidus. O host não incorpora esses módulos no bundle base novo.

- [ ] Inventariar fontes/histórico e alterações locais sem ler imagens, resultados
  ou segredos. Conferir Git/remotes reais e a existência do novo repositório.
- [ ] Preservar cópia recuperável do histórico e importar as fontes mantendo
  atribuições/licenças. Não relabelar arquivos Apache como MIT indiscriminadamente.
- [ ] Preparar repositório NEURO próprio e privado somente na futura etapa autorizada.
  Não sobrescrever repositório existente nem publicar por inferência.
- [ ] Atualizar resolução de módulos por propriedade/manifesto; impedir duas cópias
  de `radai_nidus` e `radai_nidus_screen` na montagem.
- [ ] Registrar rastreabilidade e verificar que todos os arquivos funcionais da
  migração estão contemplados. Preservar origem até R05; não emitir exclusão remota.
- [ ] Aceite: inventário conferido, nenhuma perda de história recuperável/licenças,
  bundle base não carrega Nidus duplicado e U05 demonstra equivalência funcional.

## Entrega deste subsistema

Plugin descoberto, instalado, atualizado e recuperável, com separação clara entre
código/dados e repositório pronto para o restante do trabalho. Não declarar o
produto inteiro pronto antes de D/U/M/R: instalação sem resultados corretos é
apenas uma entrega intermediária.
