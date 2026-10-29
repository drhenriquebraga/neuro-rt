# Conexão com o Local Suite

Esta fase não instala em AUTO_CONTORNO. Para integrar, leia este arquivo,
module.json e integration/radai_neuro.py; não é necessário reler os motores.

## Estrutura para a próxima montagem

Extraia o pacote offline em uma pasta própria, por exemplo:

```
<LocalSuite>/modules/neuro-rt/
  module.json
  neuro_rt/
  web/
  integration/
  python/       # runtime portátil CPU separado
  models/       # seis modelos, metadados, hashes e licenças
  licenses/
```

Não copie .venv, runtime de desenvolvimento, testes DICOM, imagens ou logs.
O ZIP offline inclui python/ e models/. O ZIP leve de fontes exige o preparo.

## Único hook de servidor

No ponto em que o FastAPI da suíte monta módulos, adicione a pasta integration
ao caminho ou carregue o adaptador pelo caminho conhecido:

```python
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

raiz = Path(__file__).resolve().parent / 'modules' / 'neuro-rt'
spec = spec_from_file_location('radai_neuro', raiz / 'integration' / 'radai_neuro.py')
adaptador = module_from_spec(spec)
spec.loader.exec_module(adaptador)
adaptador.montar(app, raiz)
```

O adaptador monta /neuro/api/... e os arquivos da página em /neuro/.
Inferência roda no Python portátil do módulo. Não importe raidionicsseg no
processo do watcher. Não é necessário subir outra porta nessa configuração.
O host precisa servir o iframe na mesma origem e permitir enquadramento dela.
O hook de shutdown encerra um subprocesso ainda ativo.

## Configuração relocável do gravador

Crie neuro_rt.local.json no módulo durante a montagem, com caminhos relativos:

```json
{
  "worker_python": "python/python.exe",
  "models_dir": "models",
  "data_dir": "runtime",
  "host_app": "../..",
  "host_python": "../../python/python.exe",
  "processing_preference": "auto"
}
```

Isso pressupõe engine.py e o Python do host na raiz do bundle. No checkout
de fontes, host_app aponta para AUTO_CONTORNO/app; no bundle já montado, aponta
para a raiz. O destino dos jobs pode ser ajustado à política local.

## Único hook de tela

Registre o item NeuroRT no catálogo/menu do host. O conteúdo é
integration/iframe.html, src=/neuro/. Este é o dado a acrescentar na porta;
não copie o HTML, JS ou worker para dentro de radai_panel/engine.
Achados ficam desabilitados por omissão; nenhum protocolo ou vigia aciona este
módulo sem o pedido explícito. RTSTRUCT próprio, fora de FULL/OAR.

Mensagens são objetos {module:'neuro-rt', version:1, type:'ready'|'status'|
'completed'|'failed', jobId?, status?}. O iframe envia somente à mesma origem.
O host deve verificar event.origin e event.source === iframe.contentWindow.

O host pode enviar type:'context', inputPath e seriesUid; isso preenche a tela,
sem executar nem marcar o aceite. Pode enviar type:'theme', theme:'dark'|'light'.
Não use '*', origem file:// ou localStorage para transportar o exame.

## Validação da conexão na próxima versão

1. Montar /neuro/ e conferir interface/API no mesmo iframe/origem.
2. Confirmar paths relativos após mover o bundle para outra pasta.
3. Rodar MRI_GBM com imagem sintética no worker próprio.
4. Exportar série DICOM MR sintética pelo Python do host; conferir UNAPPROVED,
   nomes com procedência, SOPInstanceUIDs e FrameOfReferenceUID originais.
5. Conferir ausência de tasks automáticas e de alterações em FULL/OAR.
6. Testar o runtime no Windows LTSB 14393 e, se houver plano de usar GPU,
   validar CUDA separadamente. O preparo atual e os testes foram em CPU.

Cada ROI precisa de pelo menos 10 voxels para o gravador atual aceitá-la; se
ele descartar uma máscara não vazia, o adaptador declara falha, sem anunciar
RTSTRUCT completo. Máscara vazia é resultado 'empty', sem RTSTRUCT.

## Pendência: configurações globais

Conectar o processamento ao seletor já existente da suíte: auto (padrão),
somente CPU e somente GPU. A API aceita `auto`, `cpu`, `cuda`; a montagem final
deve mapear os valores do host e atualizar a preferência quando mudar.
`auto` pode usar CPU se CUDA não inicializar. `cuda` é estrito e falha se a GPU
não estiver disponível. Nenhum seletor novo deve ser criado no módulo.

## Resultados e demos

RTSTRUCT é gravado na pasta de origem enviada em inputPath, depois de reconferir
FrameOfReferenceUID, SOPInstanceUIDs e geometria. Nome exclusivo
RS_NeuroRT_<identificador>.dcm; nunca sobrescrever o arquivo existente.
O cache de job conserva uma cópia para download. Sem acesso de escrita à origem,
a publicação falha e a interface não anuncia sucesso.

As prévias e STL são criadas pelo Python do host usando radai_png,
radai_recon3d, radai_viewer e radai_recon3d_screen. Nenhum motor novo é instalado
no host. A página recebe artefatos por /neuro/api/jobs/<id>/views/<arquivo>.
GET /neuro/api/demos/<model> reabre a demo executada, sem segmentar novamente.
Cache público não vem nos ZIPs por padrão; fontes/licenças estão na instalação.
