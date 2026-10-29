# Artefatos científicos das quatro adições — auditoria de 29/10/2026

O manifesto reproduzível está em `scripts/model_assets_v1_manifest.json`.
Ele guarda URL original, revisão, tamanho, formato e SHA256 de cada download,
além do hash de **cada arquivo extraído**. Pesos, fontes de referência e licenças
instalados ficam em subpastas de `models/`, ignoradas pelo Git. O manifesto
não altera o catálogo de distribuição: integridade do peso não comprova validação
clínica nem conclusão dos adaptadores.

## Preparo e conferência

```powershell
.venv\Scripts\python.exe scripts\model_assets_v1.py
.venv\Scripts\python.exe scripts\model_assets_v1.py --verify-only
.venv\Scripts\python.exe scripts\model_assets_v1.py --offline --cache models\_audit
```

O último comando reaproveita o cache desta auditoria; em outra máquina use o
primeiro. O preparador recusa HTML, hash/tamanho incorretos e ZIP com caminhos
inseguros ou links. Extrai somente os membros declarados. Um diretório existente
incompleto/corrompido causa erro; não é aceito como modelo pronto.

Testes do preparador:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_model_assets_v1.py -v
```

Neste executor, o diretório temporário padrão do Windows sofre restrição de
escrita. Quando necessário, antes dos testes: `$env:TEMP=(Resolve-Path
runtime/model_assets_v1_tmp).Path; $env:TMP=$env:TEMP`.

## Raidionics GBM pós-operatório de três sequências

Fonte primária: [release1.2.0](https://github.com/raidionics/Raidionics-models/releases/tag/1.2.0),
`Raidionics-MRI_GBM_Postop_FV_3p-ONNX_v12.zip`.

- ZIP:69.324.037 bytes; SHA256 `7004111ea42ffcdd75afc354e823ce17b52c419001bc8067ad55c2cc750672ff`.
- ONNX extraído:74.795.300 bytes; SHA256 `bf4b9fe0ceff04e39bb7cce1d2a6fec1df62f76c5eed11438174b3bd400953db`.
- Ordem do `pipeline.json`, etapa8: **T1-CE,T1-w,FLAIR**, todos no espaço T1-CE.
- Etapas1–7: cérebro auxiliar em cada sequência; registro de FLAIR→T1-CE e
  T1-w→T1-CE; aplicação explícita dessas transformações. Três arquivos presentes
  não substituem esse preparo.
- `pre_processing.ini`:1mm isotrópico, recorte pela máscara cerebral,
  `new_axial_size=128,128,144`, `normalization_method=zeromean`, clipping
  `0,99.995`, sem correção de bias, três entradas.
- Duas classes do ONNX:background e Tumor; limiares publicados0.6/0.4.
  Saída tumor residual realçante, sem classe de edema/necrose.
- Dependência:`MRI_Brain` existente. A instalação mantém o layout
  `fold0/model.onnx` esperado pelo RaidionicsSeg.
- Código e pesos:BSD-2-Clause; textos separados em `LICENSE.code.txt` e
  `LICENSE.weights.txt`, obtidos da fonte oficial fixada.

## Attention U-Net 3D de Motaz Alqaoud

[Peso oficial](https://huggingface.co/motazalqaoud/brain-tumor-segmentation-weights),
revisão HF `d36aa60aa5535fcc25fe935282586c8453ab255e`.
[Código](https://github.com/motazalqaoud/Brain-Tumor-Segmentation/tree/df041271344dcab6bd52a584bbbff5f4bf8103b1)
fixado em `df041271344dcab6bd52a584bbbff5f4bf8103b1`.

`best_model.pth`:94.617.685 bytes; SHA256
`7177bf156edbf4cbffdc140b9e940f09409f9233c8155c38e98869d185a91041`,
conferido contra o SHA256 LFS publicado pela API HF e contra os bytes locais.

Arquitetura exata de `src/model.py`:

```python
monai.networks.nets.AttentionUnet(
    spatial_dims=3, in_channels=4, out_channels=3,
    channels=(32,64,128,256,512), strides=(2,2,2,2), dropout=0.1)
```

Carregar com `torch.load(...,weights_only=True,map_location='cpu')` e
`model.load_state_dict(checkpoint['model_state_dict'],strict=True)`.
Não há inferência utilizável sem checkpoint; a função do autor que permite rede
aleatória não deve ser exposta pelo produto.

Entrada **FLAIR,T1,T1c,T2**, previamente corregistrada, NIfTI4D com canais no
último eixo. `src/dataset.py:inference_transforms` usa RAS, spacing1mm com
interpolação bilinear e normalização individual de voxels não zero por canal.
A inferência publicada usa `sliding_window_inference`, ROI128³, batch1,
overlap0.5; sigmoid e limiar0.5 independentes. Retorno efetivo **TC,WT,ET**:
`tumor_core,whole_tumor,enhancing_tumor`. Essa ordem difere da ordem inicial
proposta no catálogo. Preservar regiões sobrepostas; não aplicar argmax.

O autor devolve a grade RAS/1mm preparada. O adaptador precisa inverter esse
preparo para a referência original; essa etapa de produto não existe no script
publicado. A transformação de intensidade não faz registro intermodalidade.
Código MIT e declaração MIT dos pesos preservados separadamente. Checkpoint de
pesquisa/portfólio; métricas do cartão não são métricas do NeuroRT.

## SynthSeg PyTorch da distribuição DIPY1.12.0

[Implementação primária fixada](https://github.com/dipy/dipy/blob/407e9319cbfe3d05304682d317363ecd09a83fdc/dipy/nn/torch/synthseg.py)
e [fetcher](https://github.com/dipy/dipy/blob/407e9319cbfe3d05304682d317363ecd09a83fdc/dipy/data/fetcher.py).

Peso oficial:`https://ndownloader.figshare.com/files/60274412`,
`synthseg_model_weights.pth`,53.002.209 bytes; SHA256
`3023c046e3996796b1e87badeb337cc7edd2da4c79794a0214afc76b63c701fe`.
MD5 publicado por DIPY:`83d54a150410bdc1f04d70a84ff8f1ee`.

Rede `dipy.nn.torch.synthseg.Model(model_scale=24,n_levels=5,output_channels=33)`.
State dict direto; `weights_only=True`, strict=True. Não se trata da variante
TensorFlow robust/parcellation do SynthSeg original. A implementação DIPY
declara pesos e arquitetura Apache-2.0; licença original SynthSeg e licença
BSD-3-Clause do restante do DIPY foram mantidas em arquivos distintos.

Classe `SynthSeg(verbose=False,use_cuda=False)` chama download automaticamente
no construtor. Para inferência offline, o adaptador deve vincular localmente o
fetcher ao peso preparado, ou montar a instância localmente com os mesmos
atributos; jamais deixar essa consulta causar rede durante um exame.

`predict(T1,affine)` executa transformação1mm/crop192³, ordem3; percentis
0.5/99.5 para0..1; softmax33 canais; TTA por flip com troca dos labels laterais;
filtragem e correção topológica; `recover_img(order=0)` para a grade original.
Retorno é `(labels,label_dict,mask)`. O manifesto inclui os32 labels anatômicos
não zero com nomes e lateralidade, extraídos por AST do dicionário original.

Restrição observada por leitura de código: `__predict` usa `.detach().numpy()`
sem `.cpu()`. `use_cuda=True` falhará ao converter o tensor CUDA; manter CPU
até existir correção local testada. O código de referência aplica ainda uma
suavização com sigmas `(0,0.5,0.5,0.5,0)` sobre um tensor N,C,X,Y,Z; não mudar
silenciosamente esse comportamento ao alegar equivalência com a referência.
Comparação com TensorFlow original permanece uma validação científica separada.

## CerebrA e ANTs

[CerebrA oficial NIST](https://nist.mni.mcgill.ca/cerebra/) fornece o ZIP
`mni_icbm152_nlin_sym_09c_CerebrA_nifti.zip`:351.216 bytes; SHA256
`51ae4a9a2d004c3c0edea2e3ab0c15f71a2c88f04960aa2e599a3633816f445d`.
[DOI da distribuição](https://doi.gin.g-node.org/10.12751/g-node.be5e62/)
declara CC0-1.0 e template simétrico2009c.

Esse ZIP contém **somente labels e CSV**. O template T1 e a máscara do cérebro
devem vir da distribuição [MNI2009c simétrica](https://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009).
Não usar assimétrica2009c nem simétrica2009a. A licença MNI é própria e exige
preservação do aviso de copyright, portanto a licença do conjunto não pode
ser reduzida a CC0. ANTsPy usa Apache-2.0.

ZIP MNI oficial:57.583.823 bytes; SHA256
`ed981b4611ddd797a22f539035979723ecb1badebd06dcd85df149b5ef00890d`.
Template, máscara e atlas foram abertos e comparados: shapes e affines iguais,
T1 sem valores não finitos. O manifesto extrai apenas T1, máscara e `COPYING`
da distribuição MNI, preservando os avisos; não empacota as demais modalidades.

Atlas aberto com nibabel:193×229×193,1mm,RAS; affine com diagonal1 e origem
(-96,-132,-78)mm;103 valores incluindo background. `CerebrA_LabelDetails.csv`
tem51 linhas com IDs RH e LH separados:102 ROIs, inclusive rótulos distintos
nos dois lados para algumas estruturas medianas. Preservar os IDs originais.

Registro de implantação:fixed=T1 do usuário, moving=template, inicialização
rígida/afim e deformável; aplicar `fwdtransforms` aos labels com
`interpolator='genericLabel'`. Arquivar forward/inverse transforms e grade
de referência. Não chamar o registro de validado apenas porque convergiu.
Teste sintético de compatibilidade do runtime fica no smoke abaixo; parâmetros
de um registro anatômico de produção precisam de validação própria.

## Runtime privado e smoke

O `.venv` original é Python3.12.10 com ONNX; não possui torch,MONAI,DIPY,ANTs.
O runtime de auditoria é `runtime/model_assets_v1_env/Scripts/python.exe`,
criado dentro do projeto, sem mudança global. Versões selecionadas:
torch2.7.1+cpu,MONAI1.5.1,DIPY1.12.0,antspyx0.6.3,numpy1.26.4,
nibabel5.3.2,scipy1.14.1. O ambiente completo instalado é registrado por
`pip freeze` em `scripts/model_assets_v1_runtime.lock.txt`; ele não é um pacote
portátil de distribuição. Para recriar num Python3.12 Windows x64:

```powershell
.venv\Scripts\python.exe -m venv runtime/model_assets_v1_env
runtime\model_assets_v1_env\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r scripts/model_assets_v1_runtime.lock.txt
```

Esse lock registra versões instaladas; não fixa hashes de wheels. A instalação
de distribuição ainda precisa do empacotamento e teste no Windows alvo. Configure
também `MPLCONFIGDIR` para um diretório gravável do runtime para evitar cache de
fontes no perfil global, e `ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS` conforme o host.

```powershell
runtime\model_assets_v1_env\Scripts\python.exe scripts\smoke_model_assets_v1.py
```

O script verifica carregamento restrito/estrito dos dois checkpoints,
forward CPU com tensor sintético32³ e ANTs SyN em blobs sintéticos32³. O JSON
em `runtime/model_assets_v1_smoke.json` informa versão, forma e tempo.
Esse smoke não substitui inferência completa com restauração de geometria ou
comparação com a referência.

Resultado observado em Windows11 x64/Python3.12.10, CPU:Motaz196 tensores,
23.628.611 parâmetros, todos compatíveis, saída1×3×32³ finita em0,39s;
SynthSeg83 tensores,13.240.641 parâmetros, saída1×33×32³ finita em0,22s;
ANTs SyN e propagação `genericLabel` em0,85s, saída finita com labels0/1.
São tempos dos testes pequenos, sem valor como previsão de tempo de exame.
ONNX3p também passou `onnx.checker`; entradaN×128×128×144×3 e saída principal
`conv3d_36` N×128×128×144×2; outras saídas são deep supervision em resoluções
64×64×72,32×32×36 e16×16×18. Os resultados brutos estão em `runtime/`.

## QTIM condicionado

QTIM foi adiado. O Dockerfile oficial parte de `nvcr.io/nvidia/tensorflow:22.11-tf2-py3`
e o repositório usa TensorFlow2.10/NVIDIA DALI. O caminho documentado requer
container NVIDIA/Linux; não foi demonstrado runtime Windows local equivalente.
Não foram baixados folds e não existe alegação de disponibilidade neste preparo.
A fonte fixa permanece [QTIM Brain-Mets-Seg](https://github.com/QTIM-Lab/Brain-Mets-Seg).
