# Construção e instalação da release 1.0.0

A release exige Local Suite 8.10 com Python do host >=3.10.
Os motores executam em dois runtimes privados, separados do host. O runtime
Raidionics existente usa CPython 3.10.11; o científico usa CPython embeddable
3.12.10 e o lock de scripts/scientific_adapters_runtime.lock.txt.

O construtor recebe explicitamente os diretórios de runtime e seus locks. Não
procura latest de terceiros, não chama pip e não usa o conteúdo inteiro do
checkout como payload. Os runtimes, pesos e pacotes produzidos continuam fora
do Git. A procedência do CPython e as versões completas das bibliotecas ficam
nos recibos dos runtimes e no inventário de cada release.

Exemplo de especificação local de entrada:

```json
{
  "raidionics-onnx": {
    "path": "D:/build/neuro/raidionics-portable",
    "lock": "D:/build/neuro/raidionics_runtime.lock.txt",
    "python": "python.exe",
    "license_paths": ["LICENSE.txt"]
  },
  "neuro-scientific-cpu": {
    "path": "D:/build/neuro/scientific-portable",
    "lock": "D:/build/neuro/scientific_adapters_runtime.lock.txt",
    "python": "python.exe",
    "license_paths": ["LICENSE.txt"]
  }
}
```

Execute pelo Python de construção:

```powershell
python scripts/build_plugin_release.py --version 1.0.0 --runtime-spec runtime-spec.json --output dist
```

O OFFLINE contém código, runtimes, pesos e atlas completos. O PLUGIN contém
código e o inventário inteiro; só é suficiente quando a instalação já possui
todos os componentes com os mesmos hashes, sem arquivos extras. O SETUP contém
o bootstrap confiável e pode preparar a release publicada por
installer/PREPARE_LATEST.ps1 ou um OFFLINE local por installer/INSTALL.ps1.
Nenhum dos scripts troca código Python que já esteja importado. A ativação e
o reinício são coordenados pela fila do Local Suite.

O construtor também gera release-manifest.json, SHA256SUMS.txt e o alias local
SETUP_LATEST. Gerar arquivos locais não publica uma release. Antes de publicar,
é necessário revisar os artefatos e adicionar os assets imutáveis e seus hashes
ao repositório autorizado. Enquanto o repositório GitHub estiver privado e sem
uma release acessível, a consulta pode retornar 404; isso não desativa o plugin
instalado nem significa que o download de produção esteja disponível.

O cliente consulta releases/latest pela API GitHub e seleciona o nome exato
NEURO_RT_OFFLINE_v<versão>.zip. Exige digest SHA256 do asset da API, fixa seu ID
e URL durante a transação e confere tamanho e hash após o download. GH_TOKEN é
opcional, lido somente do ambiente; não integra configuração, recibo ou pacote,
e não acompanha redirecionamento para outro domínio.

Para receber o bootstrap no host base, gere app/radai_neuro_install.py com
scripts/build_host_bootstrap.py. Ele embute somente fontes de instalação stdlib
e seus hashes; nunca importa código de um ZIP antes de verificá-lo.

Consulte installer/PACKAGE_FORMAT.md para o contrato dos componentes e a
matriz de evidências em docs/MATRIZ_COMPATIBILIDADE.md.
