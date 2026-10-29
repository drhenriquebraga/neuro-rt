# NeuroRT

## Evolução para plugin — 29/10/2026

A implementação do plugin opcional do Local Suite começou. Consulte o
[estado real e ponto de retomada](docs/IMPLEMENTACAO_PLUGIN.md) e o
[roadmap aprovado](docs/superpowers/plans/2026-10-29-neuro-rt-roadmap.md).
Os contratos novos e a preparação da migração Nidus já estão em desenvolvimento;
instalador, integração final na home e motores novos seguem pelos próximos marcos.
As instruções abaixo descrevem o módulo v0.2 existente, ainda compatível.

Módulo independente de segmentação de SNC para incorporar depois ao Local
Suite. Construído em **C:\AI_PROJETOS\NEURO_RT**, sem alterar as fontes do
AUTO_CONTORNO. A página roda sozinha ou dentro de um iframe na mesma origem.

Leia [INTEGRACAO.md](docs/INTEGRACAO.md) para acoplar; o pedido pronto para a
próxima sessão está em [PEDIDO_LOCAL_SUITE.md](docs/PEDIDO_LOCAL_SUITE.md).

## O que esta versão entrega

- Interface em português, sem CDN, com seleção explícita de modelo e exame.
- Inferência em processo e runtime Python separados do host.
- Cinco modelos binários oficiais da release 1.2.0, mais cérebro auxiliar:

| Modelo | Entrada |
|---|---|
| MRI_GBM | T1 com contraste, pré-operatória |
| MRI_LGGlioma | FLAIR, pré-operatória |
| MRI_Meningioma | T1 com contraste, pré-operatória |
| MRI_Metastasis | T1 com contraste, pré-operatória |
| MRI_GBM_Postop_FV_1p | T1 com contraste, pós-operatória |

- Entrada de série DICOM MR por UID ou NIfTI escalar 3D; máscaras binárias na
  grade original, volumes em cm³ e manifesto versionado.
- Cortes navegáveis: axial principal, 3D ao lado, sagital e coronal menores.
  Botão Ampliar alterna qualquer plano com o principal, preservando o corte.
  Cortes, malhas e renderizador reutilizam os motores do Local Suite.
  A edição do contorno acontece no TPS após importar o RTSTRUCT.
- RTSTRUCT pelo **engine.build_rtstruct do Local Suite**, gravado na pasta
  original da série DICOM, com nome exclusivo. Cópia no job para download.
  Conferência de UNAPPROVED, procedência e referências da série.
- Demos públicas já executadas, disponíveis por modelo em cache nesta máquina.
  Ver [fontes e instalação](docs/INSTALACAO_E_CREDITOS.md).
- Download somente no preparo; inferência com arquivos locais. SHA256 de pesos
  e metadados conferidos. Avisos BSD incluídos na distribuição.

Toda saída é sugestão não aprovada. Não há aprovação, geração de CTV, registro
RM–TC, classificação diagnóstica ou execução automática de achados. O operador
confere a sequência; a modalidade MR sozinha não prova que houve contraste.
Modelos multissequência/multiclasse não fazem parte desta versão.

## Abrir nesta máquina

Execute **INICIAR.cmd** e abra http://127.0.0.1:8766/neuro/.
O runtime e os seis pesos já foram preparados nesta pasta.

O desenvolvimento também roda com:

```powershell
.venv\Scripts\python.exe -m neuro_rt.server
```

`neuro_rt.local.json` é configuração desta máquina e não viaja no pacote.
A cópia em `neuro_rt.example.json` mostra as opções. Sem config, o módulo usa
`python/python.exe` quando disponível, `models/` e `runtime/` dentro da raiz.

A conexão de desenvolvimento com o gravador está configurada para usar as
fontes de AUTO_CONTORNO e o Python do bundle existente **somente em subprocesso**.
Não significa instalação no host. A exportação exige entrada DICOM MR.

## Preparar em outra estação

O pacote offline já inclui Python portátil e pesos; basta extrair e iniciar.
Para montar a partir do código, `PREPARAR.cmd` requer Python com pip na máquina
de preparo e conexão à internet. Ele baixa o Python embeddable oficial e os
wheels dentro do projeto; não precisa de admin e não instala pacotes globais.
Na estação de uso, não há download em atendimento.

`auto` é o padrão; neste runtime resolve para CPU. O seletor global do Local
Suite será conectado na montagem, com auto, somente CPU e somente GPU.
Não há seletor duplicado nesta tela. CUDA exige runtime próprio onnxruntime-gpu e
drivers compatíveis; não foi validada nesta máquina. O pacote preparado é para
Windows x64. O Windows LTSB 14393 da clínica ainda precisa de teste no destino.

## Contrato e resultados

POST /neuro/api/jobs recebe:

```json
{
  "model": "MRI_GBM",
  "input_path": "C:/Exames/RM",
  "series_uid": "",
  "device": "auto",
  "explicit_request": true,
  "export_rtstruct": true
}
```

O header X-Neuro-Token vem de GET /neuro/api/status. O navegador mantém a mesma
origem. GET /neuro/api/jobs/{id} acompanha o job. Uma execução por serviço.

Resultados ficam em `runtime/jobs/<id>/`, com `manifest.json`, `masks/Tumor.nii.gz`
e, para DICOM conectado, `RS_NeuroRT.dcm` como cópia do arquivo publicado na
pasta original. A tela pede exportação automaticamente para DICOM; NIfTI gera
máscaras e visualizações. Entradas, cópias DICOM e logs privados
ficam nessa pasta; ela pode conter dados identificáveis e não entra em Git ou
pacotes. Não há envio a servidores nem faxina automática. O estado de polling
fica em memória; após reinício, os resultados permanecem no disco. Demos
listadas em `runtime/demos.json` são reabertas depois de reiniciar, sem inferência.

## Validação

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O teste FastAPI separado usa o ambiente de desenvolvimento do host com httpx.
O teste de exportação só roda quando o host está configurado. Todos os dados
de teste são sintéticos. Evidências e limites: [VALIDACAO.md](docs/VALIDACAO.md).

## Licenças e correções da discussão

Nossa camada é MIT. O motor e o repositório de pesos publicam BSD-2-Clause;
seus textos completos permanecem em `licenses/`. Redistribuir exige preservar
copyright, condições e disclaimer, inclusive nos materiais que acompanham os
binários. Listar a dependência sozinho não substitui esses avisos.

A release PyPI 1.5.2 exige `from raidionicsseg.fit import run_model`, apesar do
exemplo de README importar da raiz. A configuração usa [System] inputs_folder,
model_folder e output_folder. O preparo conserva os arquivos de metadados e
coloca o ONNX em fold0/, pois esse backend procura redes em subpastas.
O modelo tumoral pede máscara cerebral auxiliar; não é uma única chamada sem
pré-processamento. Pesos e metadados foram verificados no código real.

Fontes: [motor](https://github.com/dbouget/raidionics_seg_lib),
[release dos pesos](https://github.com/raidionics/Raidionics-models/releases/tag/1.2.0),
[licença dos pesos](https://github.com/raidionics/Raidionics-models/blob/main/LICENSE).
