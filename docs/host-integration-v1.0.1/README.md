# Proposta de integração do aceite — Local Suite / NEURO RT 1.0.1

Esta entrega contém uma proposta para o dono do host revisar e aplicar. **Nenhum
arquivo de AUTO_CONTORNO foi alterado por esta tarefa.** Não foi criado endpoint
novo, instalado plugin na base, executada inferência nem feita publicação.

## Arquivos e identidade da fonte

| Item | Local | SHA-256 |
|---|---|---|
| Fonte do host consultada | `C:\AI_PROJETOS\AUTO_CONTORNO\app\radai_plugins.py` | `878618e0c406a15799cb299d7429c96526892270f97d5b7e537b18a7dc44eaad` |
| Arquivo proposto completo | `C:\AI_PROJETOS\NEURO_RT\dist\handoff-1.0.1\radai_plugins.py` | `98f883226d76c9c26930dbea35c055f529623a2e743da2004780709de1198a41` |
| Patch | `C:\AI_PROJETOS\NEURO_RT\docs\host-integration-v1.0.1\radai_plugins.patch` | `800272c127015acdc2059cf94bcf20423039e15da06bde341fcef56cee391297` |

O SHA da fonte foi conferido antes e depois da geração e novamente depois dos
testes; permaneceu igual. A aplicação do patch em uma cópia sintética produziu
bytes idênticos ao arquivo proposto. Os metadados completos estão em
`C:\AI_PROJETOS\NEURO_RT\dist\handoff-1.0.1\radai_plugins-proposal.json`.
Os arquivos em `dist` e `.research` são artefatos locais e não integram o Git.

## Alterações propostas

- `public_status()`, usado pelo GET existente `/api/plugins/neuro-rt`, consulta
  `provider.consent_status()` uma vez e acrescenta `consent` com
  `policy: provider.consent_policy()`, `installation_accepted` e
  `first_use_accepted`. Os dois indicadores são booleanos; nenhum dado de exame
  ou identidade do operador é acrescentado ao status.
- O helper interno assíncrono `accept_installation_terms(payload)` consulta o
  recibo atual. Se ele estiver ausente, ou houver `consent` no pedido, exige um
  objeto e chama `provider.accept_consent(payload['consent'])` antes da ação.
  O provider confere aceite explícito, versão e digest do documento. Recusa gera
  HTTP 400 sem iniciar instalação, fila ou cancelamento.
- O POST existente `/api/plugins/neuro-rt/install` passa a aceitar somente
  `{confirm: true}` ou `{confirm: true, consent: {...}}`. Conserva as verificações
  de acesso local, Origin, token e tamanho do corpo. Após validar a confirmação,
  registra o aceite quando necessário e só então executa o callback de instalação
  já existente, cujo padrão é `provider.install`.
- O POST existente `/api/plugins/neuro-rt/update` passa a aceitar somente
  `{action: ...}` ou `{action: ..., consent: {...}}`. Valida primeiro a ação
  `comecar`, `esperar` ou `interromper`, conserva as verificações de segurança e
  tamanho e registra o aceite antes de `provider.request_plugin_update`.
- As chamadas de provider nos POSTs continuam em `run_in_threadpool`; navegação,
  descoberta, montagem, fila e instalação assíncrona existentes são preservadas.
  O aceite de instalação não registra primeiro uso nem aprova resultados.

Requer o bootstrap confiável **1.0.1**, com `consent_policy()`, `consent_status()`
e `accept_consent(payload)`. O `INSTALL_UI_SCRIPT` dessa versão envia o objeto
`consent` somente quando o recibo atual estiver ausente. O primeiro uso continua
no endpoint do plugin `/neuro/api/consent`; esta proposta não cria outra rota.

## Conferência e aplicação pelo dono do host

O host está sendo trabalhado por outro agente. **Confira novamente o baseline
imediatamente antes de aplicar.** Se o SHA divergir, não substitua o arquivo
completo nem force o patch: o dono deve reconciliar estas mudanças com a fonte
atual e repetir a revisão.

```powershell
$hostFile = 'C:\AI_PROJETOS\AUTO_CONTORNO\app\radai_plugins.py'
$expected = '878618e0c406a15799cb299d7429c96526892270f97d5b7e537b18a7dc44eaad'
$actual = (Get-FileHash -LiteralPath $hostFile -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'Baseline mudou; reconciliar o patch antes de aplicar.' }

git -C C:\AI_PROJETOS\AUTO_CONTORNO apply --check C:\AI_PROJETOS\NEURO_RT\docs\host-integration-v1.0.1\radai_plugins.patch
```

Somente depois de a conferência terminar com sucesso, o dono do host pode aplicar:

```powershell
git -C C:\AI_PROJETOS\AUTO_CONTORNO apply C:\AI_PROJETOS\NEURO_RT\docs\host-integration-v1.0.1\radai_plugins.patch
```

Este README não indica que o patch já foi aplicado ou que a base foi empacotada.

## Evidências e reprodução sintética

Foram executados **quatro testes de API, todos aprovados**, no harness local
`C:\AI_PROJETOS\NEURO_RT\.research\test_host_consent_proposal.py`:

1. `test_status_exposes_policy_and_only_acceptance_booleans`: política e indicadores
   no GET; sem acrescentar campos de paciente ou operador.
2. `test_install_requires_acknowledgement_and_reuses_current_receipt`: recusa sem
   aceite, ordem `accept` antes de `install`, reutilização do recibo e primeiro
   uso ainda não aceito.
3. `test_invalid_security_confirmation_action_and_terms_do_not_record_or_start`:
   Origin e token inválidos, confirmação falsa, digest incorreto, ação inválida,
   termo ausente ou desmarcado, campos extras e corpo acima do limite não
   registram aceite nem iniciam ação.
4. `test_all_three_update_actions_record_before_queue_action`: as três ações de
   atualização registram o aceite antes de chamar o provider da fila.

Reprodução no workspace compartilhado, enquanto esses artefatos locais existirem:

```powershell
Set-Location C:\AI_PROJETOS\NEURO_RT
& C:\AI_PROJETOS\AUTO_CONTORNO\.venv\Scripts\python.exe .research\test_host_consent_proposal.py
```

O harness importa o **arquivo proposto em `dist`**, monta uma aplicação FastAPI
sintética e usa provider falso. Não importa o conector ativo, não instala plugin
real e não altera a base. Usa o Python e as dependências HTTP já disponíveis no
host. No ambiente restrito, a execução do TestClient precisou de autorização de
execução local; a execução autorizada aprovou os quatro testes.

A aplicação do patch foi verificada separadamente pelo harness local
`C:\AI_PROJETOS\NEURO_RT\.research\check_host_consent_patch.py`: ele executou
`git apply --check` e `git apply` apenas em uma cópia temporária dentro do projeto
NEURO RT e comparou o resultado com o SHA da proposta. Nenhum desses comandos foi
executado sobre o checkout real de AUTO_CONTORNO nesta tarefa.
