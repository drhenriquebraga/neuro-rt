# Pacote offline NeuroRT: release-package/1

O instalador recebe **somente ZIP local autorizado**, com SHA-256 obtido externamente
ao ZIP. `begin_install(host_root, {'path': caminho_zip, 'sha256': hash_externo},
transaction_id)` não baixa URLs, não resolve latest, não executa payload e não chama
pip. SHA-256 comprova identidade com a origem autorizada, não autenticação sozinho.

O ZIP contém `release-manifest.json` UTF-8 na raiz e payload com três prefixos:

```text
code/module.json
code/neuro_rt/...
code/catalog/models.json
code/licenses/...
runtimes/<runtime_id>/<lock_digest>/python.exe
runtimes/<runtime_id>/<lock_digest>/...
models/<model_id>/<revision>/model.onnx
models/<model_id>/<revision>/...
```

O manifesto tem os campos obrigatórios a seguir. O exemplo omite os hashes reais;
o empacotador deve calcular `size` e SHA-256 de **cada** arquivo:

```json
{
  "schema": "neuro-rt/release-package/1",
  "plugin_id": "neuro-rt",
  "version": "1.0.0",
  "runtime": {"id": "raidionics-onnx", "lock_digest": "<64 hex minúsculos>", "python": "python.exe"},
  "runtimes": [{"id": "raidionics-onnx", "lock_digest": "<64 hex minúsculos>", "python": "python.exe", "license_paths": ["LICENSE.txt"]}],
  "models": [{"id": "MRI_GBM", "revision": "1.2.0", "license_paths": ["LICENSE.txt"]}],
  "code_license_paths": ["licenses/NEURO_RT_MIT.txt"],
  "files": [
    {"path": "code/module.json", "size": 100, "sha256": "<64 hex minúsculos>"}
  ]
}
```

`runtime` identifica o runtime principal consumido por `PluginPaths`. Deve ser
idêntico nos campos `id`, `lock_digest` e `python` a uma entrada de `runtimes`.
`lock_digest` identifica o lock de bibliotecas fornecido pelo preparador; o
inventário fixa todos os bytes do runtime produzido. Os IDs de runtime também
devem satisfazer o contrato de `module.json` (`[A-Za-z0-9][A-Za-z0-9_-]*`).
`python` é relativo à pasta daquele runtime. O conjunto de IDs e os caminhos
Python devem coincidir com `module.json.runtimes`.

`models` contém a revisão exata de todos os modelos `distributed` ou `verified`
do catálogo distribuído no código, inclusive auxiliares. Os arquivos de
`catalog.models[].artifacts` devem aparecer com os mesmos hashes e tamanhos
(quando declarados) em `models/<id>/<revision>/...`. Cada modelo distribuído
precisa do seu `runtime_id` completo na release. Modelos `candidate` podem
permanecer no catálogo sem pesos. As listas `license_paths` são caminhos
relativos ao respectivo componente, sempre incluídos em `files`. Licenças de
código são relativas a `code/`.

Todos os caminhos usam `/`, são relativos, sem `.`, `..`, drive, ADS, nomes
reservados Windows, ponto/espaço final ou aliases de caixa. ZIP com links,
junctions/reparse points, entradas especiais, caminhos duplicados, payload não
inventariado, arquivos acima de 16 GiB, extração acima de 64 GiB, mais de 100 mil
arquivos ou razão de compressão acima de 1000 é recusado. O manifesto é limitado
a 16 MiB. A release integral medida tem 35.990 registros e aproximadamente
9,06 MB de JSON compacto; o limite anterior de 8 MiB impedia esse inventário
legítimo. Permanecem os limites de arquivos, descompressão e SHA256 integral.
O prefixo `code/` aceita `module.json`, `neuro_rt`, `web`, `integration`,
`app`, `catalog`, `licenses`, `LICENSE`, `NOTICE`, `requirements.txt` e
`models.lock.json`. Não se distribuem `data/`, `config/`, ambientes de
desenvolvimento nem recibos gerados pela instalação.

Todos os arquivos de código devem estar no ZIP. Componentes runtime/modelo podem
ser omitidos integral ou parcialmente **apenas se** a pasta instalada já existe
e seu inventário inteiro é idêntico, sem arquivos extras. Sem esse componente
íntegro, a instalação falha; não existe download implícito nem estado pronto
para pacote leve incompleto. Uma pasta de componente existente mas corrompida
é preservada e recusada: reparação exige fluxo explícito posterior. Uma versão
de código já publicada é imutável; corrigir bytes exige outra versão.

O código é promovido para `versions/<version>`, runtimes e modelos para seus
prefixos na raiz do plugin. Em `versions/<version>` são gerados:

- `release-manifest.json`: o manifesto completo acima, com prefixos originais.
- `install-receipt.json`: campos de `InstallReceipt`, `package_sha256` e
  `licenses` (inventário de avisos do código, runtimes e modelos).

O host verifica os registros com prefixo `code/` removendo esse prefixo para
resolver arquivos em `versions/<version>`. O instalador verifica todos os
componentes novamente antes de ativar. Não existe outro `inventory.json`.

`installation.json` contém `schema=neuro-rt/installation/1`, `state`,
`active_version`, `previous_version`, `pending_version`, `runtime`,
`pending_runtime`, `transaction_id` e `package_sha256`. Durante instalação, a
versão ativa e seu runtime anteriores permanecem. Só o commit final publica
`installed_pending_restart` e `pending_version`; `activate_release` é invocado
na reabertura coordenada, antes de montar o serviço. Ele verifica novamente
código, runtimes, modelos e catálogo, troca o apontador atomicamente, conserva
`previous_version` e limpa a pendência. Chamá-lo com uma versão anterior íntegra
efetua rollback. `restart_required=False` no recibo de ativação significa que
a inicialização coordenada pode continuar; não autoriza troca de módulos já
importados em atendimento.

`install-status.json` e `transactions/<id>/status.json` publicam os campos
`transaction_id`, `state`, `stage`, `downloaded_bytes`, `total_bytes`, `reason`.
Não contêm caminhos de exames nem texto bruto de exceções. Falha de atualização
aparece nesse status, mas não altera `installation.json` da versão anterior.

Uma trava de kernel exclusiva cobre instalação e ativação. Um segundo pedido
recebe `InstallReceipt(following=True)` e acompanha `read_install_status`.
Repetir uma transação concluída retorna o recibo original após reverificar a
release; o ID não pode ser usado para outro SHA-256. Transações interrompidas
podem repetir o mesmo pacote; staging parcial é descartado somente na pasta
daquela transação. Componentes promovidos antes de morte abrupta são
reverificados/reutilizados na recuperação.

```powershell
& .\installer\INSTALL.ps1 -SuiteRoot 'D:\Local Suite' -PackagePath 'D:\Pacotes\neuro.zip' -PackageSha256 '<hash externo>' -TransactionId 'neuro-1.0.0'
```

O script usa `SuiteRoot/python/python.exe` ou o Python do checkout de
desenvolvimento em `.venv/Scripts/python.exe`. `-BootstrapPython` permite um
Python 3.10+ autorizado explicitamente. O bootstrap distribuído junto ao script
é código confiável do instalador e deve incluir `neuro_rt/__init__.py`,
`install_state.py`, `plugin_manifest.py`, `model_registry.py` e `model_paths.py`. O comando usa
`-I -B` e importa o bootstrap por caminho absoluto; não usa código do ZIP nem
depende do diretório atual.

O destino deve conter os marcadores reais de bundle plano `radai_panel.py`,
`radai_ui.py`, `entrega.txt` ou de fontes `app/radai_panel.py`,
`app/radai_ui.py`, `tools/_componentes.py`. O Python é validado na entrada
PowerShell; a API Python também permite hosts sintéticos somente com os
marcadores para testes isolados. O espaço livre precisa comportar cópia local
do ZIP, extração coexistindo com versões anteriores e margem de 16 MiB.
O instalador não encerra nem reinicia o host: essa coordenação é I03/I04.

Os consumidores usam `model_paths.resolve_model_folder(models_dir, model_id,
revision, allow_legacy=False)`, selecionando a revisão exata publicada. A API não
procura latest nem escolhe outra pasta por disponibilidade. O layout flat v1 é
permitido somente quando uma entrada de desenvolvimento habilita explicitamente
`allow_legacy=True`. `preflight_model_folders` aplica a resolução a tumor e Brain
auxiliar usando as revisões fixadas no catálogo legado (`RELEASE=1.2.0`), e
`shared_model_status` usa a mesma validação. O worker mantém a API v1 de
desenvolvimento; a entrada de produção passa `allow_legacy_models=False` ou
`--installed-models` na CLI.
