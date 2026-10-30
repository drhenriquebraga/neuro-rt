# Installer-only Host Python Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Instalar o Nidus como plugin leve que reutiliza o Python e componentes da suíte, baixando somente o SETUP confirmado.

**Architecture:** Estender o formato transacional existente com modo host CODE-only. O host fornece seu interpretador, e o builder publica só SETUP versionado e LATEST. Não montar runtimes nem instalar pacotes/pesos para ferramentas em construção.

**Tech Stack:** Python stdlib 3.10+, FastAPI e bibliotecas já pertencentes ao Local Suite, PowerShell, JS existente.

**Spec:** `docs/superpowers/specs/2026-10-30-installer-only-host-python-design.md`.

## Global Constraints

- Host mínimo 8.11; `local-suite/plugins/1`; somente Nidus habilitado.
- Não baixar/copiar/reinstalar Python, venv, Torch/CUDA ou bibliotecas da base.
- Somente SETUP versionado + LATEST no GitHub; sem OFFLINE/PLUGIN/modelos/runtimes.
- Aceite, segurança de paths, fila, rollback, cleanup e reinício estrito preservados.
- Nenhuma alteração de animação/CSS. Não alterar main nem tags históricas.
- Retirada de assets pertence ao chat LOCAL SUITE I, sem concorrência.

## Review Focus

- Receita/estado tentando substituir o binding do Python da suíte: recusar.
- CODE-only escondendo executáveis, wheels, modelos ou um runtime: recusar antes da extração.
- Base incompleta ou ABI incompatível: diagnóstico antes da promoção, sem pip/rebaixamento.
- Nova versão com pendência antiga: preservar dados e não baixar/reusar um bundle como fallback remoto.
- Sucesso aparente com processo/versão antigos: manter aguardando a nova montagem.

### Task 1: Manifesto, paths e prontidão compartilhada

**Files:** `neuro_rt/plugin_manifest.py`, `neuro_rt/plugin_paths.py`, `neuro_rt/service.py`, `integration/radai_neuro.py`, testes correspondentes.

**Interfaces:** `PluginManifest.execution_mode`; `resolve_plugin_paths(host_root, state, *, host_python=None)`; host binding `host_info['python_executable']`; nenhum caminho vindo de pacote/estado.

- [ ] Testes RED para runtimes vazios em modehost, binding obrigatório, mesmo exe e runtime_dir=None.
- [ ] Implementar modehost fechado e Settings/adapter usando binding confiável.
- [ ] Verificar CODE-only ready com base completa; estado/receita não substituem exe; tools futuros indisponíveis.

### Task 2: Instalação transacional CODE-only

**Files:** `neuro_rt/install_state.py`, `tests/test_host_install_state.py`.

**Interfaces:** release schema legado com `execution_mode='host', runtime=None, runtimes=[], models=[]`; estado ativo/pendente carrega execution_mode.

- [ ] Testes RED para extração segura do CODE-only e rejeição de payloads científicos/execs no modo host.
- [ ] Implementar validação fechada, catálogo sem exigir artefatos de cards em construção e publicação/ativação do modo.
- [ ] Rodar cleanup/progresso/rollback/reparse legados e novos testes antes do freeze.

### Task 3: Cliente SETUP, builder e PowerShell

**Files:** `neuro_rt/plugin_update.py`, `integration/update_provider.py`, `module.json`, `scripts/build_web_setup.py`, `installer/*.ps1`, `scripts/build_host_bootstrap.py`, testes de cliente/SETUP.

**Interfaces:** seleção versionada do SETUP com digest exterior API; `UpdateCoordinator(..., host_python=...)`; ZIP CODE-only aceito por Task2.

- [ ] Testes RED: nunca escolher OFFLINE/PLUGIN; sem digest não preparar; pacote leve contém código/PS/licenças, nenhum binário/modelo/runtime.
- [ ] Publicar manifesto modehost e builder de somente dois ZIPs idênticos.
- [ ] Fazer PS/provedor usar Python da base e preservar aceite/fila/reabertura; imprimir progresso manual.
- [ ] Verificar zero chamadas de download científico/pip/ambiente nesta entrega.

### Task 4: Coordenação, prova e publicação

**Files:** documentação, recibos novos, bootstrap gerado; host alterado somente por LOCAL SUITE I.

- [ ] Fornecer contrato e bootstrap ao dono do host, receber binding real e prova de equivalência do embed.
- [ ] Rodar gates de Python 3.10/3.12, UI já existente e CI da branch.
- [ ] Prova real com SETUP leve e base completa: mesmo Python, CODE-only, consentimento/novoPID/token/mounted.
- [ ] Confirmar GitHub somente SETUP_v + LATEST e nenhum fallback remoto de bundle.
- [ ] Publicar coordenado com base8.11, conferir download anônimo e SHA, manter main preservada/PR revisável.
