# Validação do host após integração do aceite — 30/10/2026

O responsável pelo host informou ter aplicado a proposta do conector e o
bootstrap 1.0.1, preservando SOURCES/provider e formatando o JavaScript em várias
linhas. Esta rodada **não alterou arquivos de AUTO_CONTORNO** e não reaplicou o
patch. O SHA atual pode diferir do arquivo proposto por causa do trabalho do dono
do host; os testes abaixo consultaram a integração atual.

## Identidade dos arquivos verificados

| Arquivo no host | SHA-256 |
|---|---|
| `C:\AI_PROJETOS\AUTO_CONTORNO\app\radai_plugins.py` | `9bb5a6bd85a6366d98e2bce1a5b59d835aca6d407d436f677030031c525ab07c` |
| `C:\AI_PROJETOS\AUTO_CONTORNO\app\radai_neuro_install.py` — durante a primeira rodada | `e96b86fba9959fb035218ffe2744039989dc12b6dd60f32a0ba894d3ecee3339` |
| `C:\AI_PROJETOS\AUTO_CONTORNO\app\radai_neuro_install.py` — estado final, antes/depois da repetição | `3065f7da443a50e7e084703f6c9b8daaeb58905b7fb7e5a6cac2182bcbb516f9` |

O conector permaneceu igual. O bootstrap mudou na primeira janela por trabalho
concorrente no host. As duas baterias foram repetidas e aprovadas; os hashes
finais permaneceram iguais antes/depois da repetição. O baseline anterior documentado no
README continua sendo a referência histórica do patch original. Não reaplique
esse patch sobre o arquivo atualizado sem nova revisão do dono.

## Ajuste dos testes

Somente `C:\AI_PROJETOS\NEURO_RT\tests\test_plugin_host.py` foi adaptado:
os pedidos sintéticos de instalação destinados a ter sucesso agora enviam
`confirm: true` e `consent: {accepted: true, version, digest}`, usando a versão e
a impressão fornecidas pelo GET de status do bootstrap atual. As recusas por
token/origem e por confirmação diferente de `true` foram preservadas. Nenhum
requisito foi desabilitado nem substituído por um provider falso nessa bateria.

## Resultados

- `test_plugin_host.py`: **16 testes aprovados**, 7,066 s na repetição final. Cobriu montagem única,
  integridade, compatibilidade, espera pela fila, responsividade, encerramento,
  delegação da instalação com aceite, segurança do POST, home e navegação. O
  navegador também aprovou o fluxo sintético de instalação, progresso, reinício,
  indisponibilidade temporária, token de nova sessão e redirecionamento.
- `test_consent_update_ui.py`: **1 teste de navegador aprovado**, 6,818 s na repetição final. Cobriu
  ausência do contrato na base, aceite inicialmente desmarcado, preservação entre
  consultas, descarte após mudança do termo, payload exato, confirmação separada
  para interrupção, reaproveitamento do recibo e recusa de política inválida.

Comandos executados a partir de `C:\AI_PROJETOS\NEURO_RT`:

```powershell
& C:\AI_PROJETOS\AUTO_CONTORNO\.venv\Scripts\python.exe -m unittest discover -s tests -p test_plugin_host.py -v
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_consent_update_ui.py -v
```

As execuções de TestClient/Chrome foram autorizadas fora da restrição de execução
local do ambiente. Usaram metadados e adaptadores sintéticos em pastas temporárias
do NEURO RT, consultas de release simuladas e respostas de navegador interceptadas.
Não instalaram plugin real na base, não baixaram pesos, não executaram inferência
e não produziram commit ou publicação. Nenhuma falha real de código foi encontrada
nessas duas baterias.
