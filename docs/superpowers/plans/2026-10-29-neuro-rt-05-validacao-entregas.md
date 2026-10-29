# NEURO RT — Validação, empacotamento e entregas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> Plano para futura execução; nenhuma publicação, instalação ou exclusão nesta entrega documental.

**Goal:** transformar os subsistemas implementados num pacote demonstravelmente
instalável, atualizável e rastreável, com evidência das funcionalidades prometidas.

**Architecture:** uma cadeia de verificação liga versão das fontes, catálogo efetivo,
locks dos runtimes/pesos, testes e artefatos de release. Pacote leve e offline
representam a mesma release funcional, diferindo na presença dos artefatos baixáveis.

**Tech Stack:** testes Python existentes/novos, PowerShell em instalação isolada,
browser para fluxos, empacotador por allowlist, Git/GitHub e hashes de artefatos.

**Spec:** [desenho](../specs/2026-10-29-neuro-rt-plugin-local-suite-design.md).

## Global Constraints

- Todas as restrições do [plano mestre](2026-10-29-neuro-rt-roadmap.md) se aplicam.
- Testes usam sintéticos/demos permitidas; não usar banco, shares ou imagens do serviço.
- Rodar um teste não significa que passou: guardar comando, resultado e ambiente.
- Nenhuma marca de pronto sem corte completo do usuário, do carregamento à reabertura.
- Pacote exclui dados de trabalho, segredos e configuração local; preserva licenças.
- Repositório privado é mantido; publicação pública ou exclusão do Nidus são atos posteriores.
- QTIM pode ser omitido conforme alinhamento; a release declara o catálogo que realmente contém.

## Review Focus

- Instalação do zero sem Python global: R03 usa máquina/ambiente realmente limpo.
- Update da suíte limpa arquivos do plugin: R03 comprova preservação das duas direções.
- Arquivo clínico perdido no pacote por extensão liberada: R02 aplica allowlist por origem.
- Licença ou peso diferente do testado na release: R02/R04 cruzam manifestos, hashes e evidências.
- Teste isolado passa, fluxo multiapp falha: R01/R03 testam fila/atualização/visores juntos.

## Estratégia de qualidade

### Camada 1 — Contratos e transformações

Testes pequenos verificam schema, elegibilidade, classes, composição de transformações,
nomeação de ROIs, estados e concorrência com executores controlados. Eles devem
falhar se o comportamento errado for reintroduzido, não apenas conferir presença
de uma palavra ou função no arquivo.

### Camada 2 — Adaptadores com pesos reais

Executar cada modelo distribuído, não apenas mocks. Conferir que arquivo carregado,
classes, dispositivo, preparo e referência correspondem ao manifesto. Uma inferência
em fantoma pode demonstrar execução, mas não demonstra segmentação tumoral correta;
usar demos públicas permitidas quando o propósito for inspecionar comportamento real.

### Camada 3 — Integração do host

Exercer a fila compartilhada, cancelamento, atualização, gravador real, acervo e
visualizadores. A suíte base deve continuar funcionando sem plugin e quando o
plugin falha. Testar o efeito do Neuro nos outros apps é parte da entrega.

### Camada 4 — Instalação e operação

Instalar, abrir, processar, atualizar, interromper e recuperar em diretório limpo,
com caminhos representativos. A máquina de desenvolvimento já contém dependências:
ela não prova que o pacote leva tudo o que precisa.

### Camada 5 — Revisão de produto e de procedência

Conferir nomenclatura, explicações, licenças, privacidade das evidências, requisitos
de hardware e descrição de limitações. Não rotular licença permissiva ou aprovação
de teste de software como aprovação de uso clínico.

## R01 — Matriz de integração completa

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/tests/test_neuro_integration.py`,
`C:/AI_PROJETOS/NEURO_RT/tests/test_cross_app_lifecycle.py` e
`C:/AI_PROJETOS/NEURO_RT/docs/VALIDACAO_PLUGIN.md`; atualizar
`C:/AI_PROJETOS/NEURO_RT/docs/VALIDACAO.md` com referência à nova fase.

**Interfaces:** cenário sintético reproduzível `IntegrationScenario` contém
fontes sintéticas, pedido v2, estado inicial de instalação/fila e expectativas
de resultados. Ele consome os contratos reais, não um segundo fluxo de teste.

- [ ] Montar cenários: uma série/um modelo; uma referência/vários modelos; dois
  conjuntos com duas referências; tumor mais anatomia; quatro séries incertas;
  entrada realmente ausente; retorno à home durante execução.
- [ ] Acrescentar concorrência ContourLab/Neuro/vigia, cancelamento, falha parcial,
  resultado vazio, falha de publicação, retry de exportação e reinício do host.
- [ ] Verificar cardinalidade e conteúdo do RTSTRUCT, recuperação dos manifestos,
  ausência de execução automática e coerência dos avisos no backend/frontend.
- [ ] Exercitar API com origem/token inválidos, tickets expirados e tentativa de
  path fora dos artefatos autorizados, sem imprimir dados sensíveis em erro.
- [ ] Rodar a suíte Neuro: `.venv/Scripts/python.exe -m unittest discover -s tests -v`
  em `C:/AI_PROJETOS/NEURO_RT`, além das baterias do host/componentes afetados.
  Não marcar como aprovado teste pulado por dependência ausente; registrar a pendência.
- [ ] Revisar o fluxo manual completo no navegador com dados permitidos e capturas
  desidentificadas. Aceite: usuário consegue chegar ao resultado/reabri-lo e a suíte
  continua funcional. Revisar/commitar.

## R02 — Artefatos reproduzíveis de release

**Files:** adaptar `C:/AI_PROJETOS/NEURO_RT/scripts/package_module.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_packaging.py`; criar
`C:/AI_PROJETOS/NEURO_RT/scripts/build_release.py` e
`C:/AI_PROJETOS/NEURO_RT/tests/test_release_manifest.py`;
atualizar `LICENSE`, `NOTICE`, `licenses/` e documentação de instalação no mesmo projeto.

**Interfaces:** `build_release(version, catalog, locks, output_dir) -> ReleaseArtifacts`
gera os mesmos metadados para os pacotes abaixo;
`verify_release(manifest, artifacts) -> ReleaseVerification` confere integridade,
licenças e inclusão permitida. Reaproveitar `source_files`/`package` existentes.

Artefatos planejados:

| Artefato | Conteúdo/papel |
|---|---|
| `NEURO_RT_SETUP_v<versao>.zip` | Instalador leve, manifestos e avisos; busca payloads autorizados |
| `NEURO_RT_SETUP_LATEST.zip` | Alias estável do setup da release publicada, não fonte de versão de pesos |
| `NEURO_RT_PLUGIN_v<versao>.zip` | Payload de código/UI do plugin, com manifesto e licenças |
| `NEURO_RT_OFFLINE_v<versao>.zip` | Mesmo produto com runtimes/pesos/atlas do catálogo distribuído |
| `release-manifest.json` e checksums | Versões, compatibilidade, nomes, tamanhos, hashes e catálogo efetivo |
| Notas de release e inventário de componentes | Funcionalidades, migração, evidências e limitações |

- [ ] Fixar tags/revisões de fontes, runtimes e modelos usados na validação; uma
  rebuild não deve procurar novas versões de terceiros silenciosamente.
- [ ] Construir por allowlist de arquivos, não zipar a pasta de trabalho inteira.
  Excluir `.venv`, `.git`, credenciais, configs locais, jobs, caches, logs privados e imagens.
- [ ] Incluir NIfTI apenas quando asset do atlas constar em M01/M06 com identidade,
  procedência e licença verificadas. Testar arquivo-isca de paciente em diretório
  de dados e com nome de atlas: o nome sozinho não o torna permitido.
- [ ] Incluir Python/pesos no offline sem adicioná-los ao Git. Catálogo offline deve
  ser íntegro; não anunciar instalação offline que ainda depende de baixar um motor.
- [ ] Testar checksum do payload, classes/versões declaradas, licença ausente e arquivo
  não permitido. Ao omitir QTIM, retirá-lo do catálogo distribuído e das promessas da release.
- [ ] Abrir/verificar os ZIPs produzidos; conferir inventário e comparar com o manifesto.
  Aceite: arquivos reproduzíveis quanto ao conteúdo declarado e totalmente rastreáveis;
  timestamps de ZIP não são, por si, identidade do modelo. Revisar/commitar.

## R03 — Instalação limpa, compatibilidade e recuperação

**Files:** criar `C:/AI_PROJETOS/NEURO_RT/tests/test_install_upgrade_scenarios.py` e
`C:/AI_PROJETOS/NEURO_RT/docs/MATRIZ_COMPATIBILIDADE.md`; estender os testes I02/I04.

**Interfaces:** roteiro de estação com `host_version`, `plugin_version`, Windows,
arquitetura, Python efetivo, dispositivo, drivers, artefato e resultado de cada fase.
Não usar informações privadas de exames como identificação da máquina.

- [ ] Testar base sem plugin, primeira instalação, reinstalação idempotente,
  upgrade do plugin, upgrade do host e retorno à versão anterior após falha.
- [ ] Usar caminhos com espaço/acento, outra unidade, falta de permissão no destino,
  falta de espaço, conexão interrompida e pacote offline com rede indisponível.
- [ ] Provar que tarefas/resultado/configurações sobrevivem às duas atualizações;
  o novo host reconhece o plugin já instalado sem obrigar novo download dos pesos íntegros.
- [ ] Testar falha antes da ativação, durante troca de versão e na reabertura. A
  instalação anterior íntegra permanece recuperável, sem apagar resultados.
- [ ] Verificar CPU e, quando disponível, GPU no equipamento real. Registrar
  explicitamente plataformas não exercitadas, inclusive Windows LTSB citado no projeto.
- [ ] Em máquina sem Python global, abrir a suíte/plugin e executar o corte básico;
  falha por dependência ambiental significa pacote incompleto, não instrução para
  o usuário instalar Python manualmente por fora do instalador.
- [ ] Aceite: matriz contém evidências e limites reais. Não declarar combinação
  suportada apenas porque outra versão do Windows funcionou. Revisar/commitar.

## R04 — Preparação e publicação controlada da release

**Files:** criar, na futura execução autorizada,
`C:/AI_PROJETOS/NEURO_RT/.github/workflows/verify.yml` e
`C:/AI_PROJETOS/NEURO_RT/.github/workflows/release.yml`, quando o repositório estiver
preparado; criar `C:/AI_PROJETOS/NEURO_RT/docs/RELEASE_PROCESS.md`.
Não executar publicação como efeito de editar esta documentação.

**Interfaces:** uma release associa tag, commit, manifesto, catálogo distribuído,
checksums e evidências R01–R03. Pipeline de verificação não usa dados privados;
etapa pesada de modelos é separada dos testes rápidos e reporta o que realmente rodou.

- [ ] Configurar verificação de fontes, contratos e empacotamento com artefatos
  sintéticos, sem exigir baixar todos os pesos a cada edição de texto.
- [ ] Reservar execução dos modelos reais/estação para alterações que afetam esses
  caminhos e para a candidata final de release; guardar evidências associadas à versão.
- [ ] Conferir dono/visibilidade do repositório. Na fase privada, provar distribuição
  por acesso autorizado ou pacote offline obtido por esse acesso. Nunca embutir
  PAT/token, nem incluir token em URL, log ou manifesto do instalador.
- [ ] Antes de prometer instalação via latest a usuários externos sem acesso,
  definir publicação autorizada dos assets ou fluxo de autenticação aprovado.
  Essa condição de distribuição não autoriza mudar a visibilidade do repositório.
- [ ] Preparar release candidata, validar downloads e update por manifesto fixo e,
  somente no fluxo autorizado de entrega, publicar a release estável/alias latest.
  Não apontar latest para build não testada só para exercitar um cliente real.
- [ ] Incluir notas objetivas: modelos efetivos, sequências, plataforma testada,
  migração, falhas conhecidas, instruções de atualização e recuperação.
- [ ] Aceite: instalação/atualização consome os mesmos bytes testados, e a comunicação
  da release corresponde à disponibilidade real. Seguir revisão/PR do projeto quando aplicável.

## R05 — Documentação de operação, handoff e encerramento da migração

**Files:** atualizar `C:/AI_PROJETOS/NEURO_RT/README.md`, `AGENTS.md`,
`docs/INTEGRACAO.md`, `docs/PEDIDO_LOCAL_SUITE.md`, `docs/ESCOPO.md` e
`docs/INSTALACAO_E_CREDITOS.md`; criar
`C:/AI_PROJETOS/NEURO_RT/docs/ENTREGA_PLUGIN.md` e
`C:/AI_PROJETOS/NEURO_RT/docs/OPERACAO_PLUGIN.md`.

**Interfaces:** handoff versionado com tarefas feitas, revisões, interfaces estáveis,
artefatos, testes e limitações. O documento não deve dizer que uma fase está pronta
quando faltam resultados reais da mesma fase.

- [ ] Explicar instalação, seleção, entradas ausentes/incertas, referência, resultados
  parciais, retry, atualização e reabertura com a linguagem do produto.
- [ ] Atualizar instruções antigas que descrevem apenas iframe/serviço independente
  ou proíbem a integração da fase nova. Preservar histórico, sem deixar orientação
  antiga parecer contrato vigente para os próximos agentes.
- [ ] Registrar componentes/licenças e o que foi mantido de Nidus. Conferir inventário
  de I05 com regressões U05, releases antigas e destino do histórico recuperável.
- [ ] Produzir relatório de entrega com versões, cenários passados/falhados/não
  executados, catálogo efetivo, caminhos dos artefatos e problemas abertos.
- [ ] Só depois dessa conferência tratar a exclusão do repositório Nidus, como
  etapa posterior já solicitada pelo usuário. Não apagar automaticamente no build,
  instalador, migração local ou primeira publicação do Neuro; antes de executar,
  conferir alvo exato, cópia/histórico recuperável e autorização vigente.
- [ ] Aceite: outro agente consegue reproduzir o estado e continuar sem buscar
  decisões na conversa inteira; usuário consegue instalar/operar pelo documento.

## Critério final de pronto

A entrega requer: instalação opcional funcionando; cinco cards; Nidus preservado;
fila comum; seleção com a regra de ambiguidade correta; catálogo distribuído
verificado; modelos executados com pesos reais; geometria/RTSTRUCT conferidos;
visualização consistente; atualização/recuperação testadas; licenças e documentação
completas; regressões da suíte base resolvidas.

Uma limitação aceita, como adiar QTIM, consta da entrega. Um defeito pendente no
gravador, na geometria, no isolamento da fila ou na preservação dos resultados
não vira limitação aceitável apenas por faltar tempo. Se houver bloqueio externo,
reportar exatamente a condição e a parte já demonstrada, sem declarar o plugin concluído.
