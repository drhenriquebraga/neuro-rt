# Evidências técnicas da integração NEURO RT 1.0.0

## Revisão dirigida 1.0.1 — 30/10/2026

- 107 testes selecionados de contratos, paths, pacote, instalador, atualização,
  recibos, disponibilidade e provider: OK, com dois skips de symlink por privilégio
  Windows. Junctions foram efetivamente exercitadas.
- Sete testes HTTP locais: três de acesso/aceite, dois de adapter/montagem tardia
  (incluindo tentativa no intervalo de publicação) e dois de servidor stdlib.
  Nenhuma chamada a motor foi permitida nos cenários bloqueados.
- Chrome/Playwright: quatro fluxos dirigidos passaram — cards/foco/opacidade,
  primeiro uso, aceite do instalador com renovação de hash e atualização comum.
  Cobertura dos controles nos 12 idiomas preservada; documento do termo em PT-BR.
- Revisão independente: sem achados bloqueantes conhecidos após corrigir quatro
  achados. Relatório de trabalho em
  `.superpowers/sdd/neuro-plugin/2026-10-30-nidus-consent-review.md`.
- Auditoria pré-publicação: histórico/refs Git e snapshot publicável examinados,
  sem credenciais ou PHI identificados; nenhum peso/ambiente/imagem versionado.
- Build final com os componentes comprimidos já inventariados, verificação de
  cada SHA descomprimido, inventário/licenças e comparação CODE com a fonte atual.
  A publicação e os downloads são registrados no handoff 30/10.

Essas provas são técnicas e sintéticas. Não houve nova inferência científica,
instalação em estação clínica ou teste em TPS nesta revisão. Os pesos existentes
continuam no OFFLINE, mas as quatro ferramentas científicas não ficam habilitadas.

Registro da construção de 29/10/2026. Dados exclusivamente sintéticos, sem leitura
de exames privados, acesso ao TPS ou mudança de instalação de uso. As provas
demonstram execução e contratos; não medem precisão de segmentação em pacientes.

## Ambientes e separação

- API integrada: ambiente de desenvolvimento do Local Suite, Python 3.14.6,
  FastAPI/httpx. Os contratos comuns também têm alvo mínimo Python 3.10.
- Leitor/escritor/visores do host: Python embeddable 3.10.11 do bundle existente.
- Raidionics: runtime privado Python 3.10.11/ONNX, separado do host.
- Novos motores científicos: runtime privado embeddable 3.12.10,
  Torch 2.7.1+cpu, MONAI 1.5.1, DIPY 1.12.0 e ANTs 0.6.3, conforme locks.
- Windows AMD64 10.0.26200.0 nesta estação. GPU, LTSB, outra unidade física e
  máquina inteiramente nova sem Python global não foram demonstrados.

## Provas concluídas por fronteira

| Fronteira | Evidência observada |
|---|---|
| Instalação transacional | 20 testes do instalador; paths versionados, staging, rollback, hashes e contenção; cinco testes adicionais de resolução de modelos |
| Home e montagem | 15 provas HTTP do host, incluindo ausência, corrupção, incompatibilidade, montagem única, rede lenta, verificação em segundo plano e encerramento sem montagem tardia |
| Arbitragem compartilhada | 12 testes da ponte e 180 verificações existentes do host; cancelamento conserva posse até confirmação de término |
| Árvore de subprocessos | Duas provas Windows com filho/neto e processo órfão; handshake antes de importar o worker e JobObject privado |
| Geometria | Referência física LPS, registro explícito, NaN/inversas/composições inválidas recusadas; 12 regressões geométricas e seis de preparação após a correção Unicode |
| Resultados | Revisões imutáveis, artefatos por IDs opacos, reabertura sem inferência, retentativa completa, cache por identidade e recuperação sem paths públicos |
| RTSTRUCT | Nove provas incluindo referência TC explícita e fluxo HTTP; corrupções de foco/plano/SOP recusadas antes de publicar; cores conferidas sem alterar o restante do dataset/file_meta |
| Interface | Chrome/WebGL reais: chaves desligadas, incerteza permitida, ausência real bloqueada, ajuda acessível, canais distintos, referência, histórico, seleção de série, visibilidade/opacidade, 390 px e 12 idiomas/RTL |
| Nidus/Recon | Nidus 519/519, Recon 443/443, regressão Recon 181/181, componentes 84/84, migração 6/6 no host API; core e funções compartilhadas comparados por AST |
| Atualização da base | Dois ensaios PowerShell reais em bases sintéticas; preservação de Plugins, pesos, configuração, dados e versão anterior |

Os números acima pertencem a baterias distintas e não devem ser somados como
casos únicos. Revisões independentes aprovaram contratos, I02, motores/geometria,
execução/exportação, interface/Nidus e a correção Unicode. O gate do atualizador,
o snapshot final do pacote e a revisão geral são registrados ao fechar a entrega.

A bateria ampla da continuação executou **346 testes em 276,648 s**: 321 passaram,
24 foram pulados conforme o ambiente e um revelou regressão na CLI dos visores.
O import Unicode relativo estava antes do bootstrap para execução por arquivo.
Foi movido para depois do bootstrap, com import absoluto; os dois testes de
`test_study_views.py` passaram em 12,502 s e a CLI `--help` passou no Python do
host. A revisão independente confirmou que somente esse import mudou. Não há
falha funcional pendente desse lote; os skips continuam registrados, não aprovados.

O gate I04/R02 encerrou os dois achados sobre inclusão de imagens e interrupção
de turno agendado. Passaram nove testes do builder, dois do provider real/gerado,
dois da UI e 16 do host, incluindo Chrome na primeira instalação e na atualização.
A tela ausente usa JS confiável da própria base, antes de existir payload montado;
acompanha download/preparo/reinício, indisponibilidade transitória e nova sessão
até a montagem. Nenhum JavaScript baixado é executado antes da conferência.

## Pesos reais

Cada motor novo executou uma inferência completa em CPU com seus pesos reais:

| Motor | Tempo no fantoma | Saída verificada |
|---|---|---|
| Raidionics GBM pós-operatório 3p | 49,89 s | Uma classe, restauração à referência |
| Attention U-Net 3D | 70,56 s | TC, WT e ET independentes e sobrepostos |
| SynthSeg/DIPY | 403,18 s | 32 classes anatômicas |
| CerebrA/ANTs | 64,81 s | 102 labels, template original e propagação deformável |
| Buti existente no host | 68,823 s | Oito labels originais, reaproveitando runtime/pesos |

Dezenove testes do ambiente científico e 12 específicos do Buti passaram.
Esses tempos não são previsão para exames. QTIM permanece adiado e não integra
o catálogo distribuído. Os smokes não compararam resultados clínicos externos
nem demonstram equivalência com outro backend SynthSeg.

## Corte completo com componentes realmente instalados

O pacote candidato completo foi instalado, ativado e descoberto como pronto em
uma pasta isolada com espaço/acento. O primeiro teste de processamento descobriu
dois defeitos antes de executar a rede: NiftiImageIO não abria destino absoluto
Unicode no Windows e a inversa composta SimpleITK expunha um wrapper recursivo.
Ambos foram corrigidos e revisados sem alterar os parâmetros científicos.

Para evitar misturar revisões de código, foi aplicado um snapshot coerente de
49 arquivos Python das fontes finais sobre a instalação sintética. Quinze
arquivos diferiam do candidato original; o ledger preservou hashes antes/depois.
Pesos, runtimes, catálogo e configuração instalada permaneceram canônicos. O
candidato antigo não passa a ser considerado corrigido: o pacote final precisa
conter esse snapshot e passar novamente pela verificação integral do inventário.

Uma única inferência pesada desse corte foi executada com Motaz CPU: **70,64 s**
do pedido à conclusão, quatro séries MR sintéticas (64 DICOM), três registros
reais, associação explícita FLAIR/T1/T1c/T2 e resolução estrita dos pesos
instalados, sem fallback de desenvolvimento. Concluiu preparo, execução,
restauração, exportação e visualização.

As máscaras finais TC (38 voxels) e WT (57) tinham shape/affine da referência,
conferidas independentemente com nibabel. A classe ET tinha dois voxels na grade
de trabalho de 1 mm e nenhum na grade original anisotrópica após nearest-neighbor;
não foi publicado ROI vazio. Não se alterou limiar nem se aplicou filtro para
obter o resultado. A geometria de referência e a grade de trabalho são diferentes;
contagens brutas de voxels entre elas não são comparação de volume.

O gravador nativo publicou um RTSTRUCT UNAPPROVED, duas ROIs, zero omitidas,
frame/série/SOPs da T1c autorizados e nome exclusivo. Foram construídos MPRs,
malhas e manifesto; a fila isolada terminou `completed`. A concorrência com a
fila do produto é provada pela bateria própria, não por esse harness isolado.

## Unicode e isolamento científico

NIfTI `.nii`/`.nii.gz` oblíquo e anisotrópico: voxels, origem, espaçamento e direção
idênticos após round-trip nos runtimes 3.10 e 3.12. O helper nativo opera somente
na thread principal do subprocesso privado, habilitado depois do handshake, e
restaura cwd em `finally`. Não muda o diretório da API.

A inversão de composição inverte os membros na ordem matemática inversa; evita
o defeito nativo sem substituir deformáveis por afins. Pontos físicos não nulos
e save/load/inverse foram comparados, preservando finitude de todos os membros.
Um probe ANTs SyN 24³ em pasta com acento produziu e releu affine, warp e inverse
warp e propagou labels binários. Não comprova Unicode em todo I/O interno do
nnU-Net/Buti ou de bibliotecas de terceiros não exercitadas nessa condição.

## Encerramento da revisão geral

O código `67961ff` encerrou uma única onda de correções, seguida de uma única
revisão independente escopada: seis achados **ADDRESSED**, nenhum P1/P2 novo,
18/18 arquivos conferidos por SHA-256. Foram corrigidos:

- Falha de confirmação de término agora é fatal para as próximas etapas; conserva
  árvore/concessão e bloqueia novos launches, repetição e retomada até confirmação.
  Falhas científicas comuns continuam isoladas quando o encerramento foi confirmado.
- Retry acompanha a tentativa ativa sem abrir acidentalmente uma revisão antiga;
  histórico, cache de modelos concluídos e cancelamento continuam disponíveis.
- Classes não vazias que zeram ao retornar à referência geram aviso estruturado
  por modelo/classe, com contagens e projeção pública segura, inclusive no histórico.
- MPRs têm plano principal e ampliação por controle/teclado/duplo clique, mantendo
  corte, cores, visibilidade e opacidade ao voltar; o renderizador permanece o do host.
- A ajuda informa método, requisitos, CPU-only, preparo e limitações específicas
  dos modelos nos 12 idiomas; fontes, licenças e número de motores permanecem iguais.
- Raidionics legado usa a fronteira Unicode privada até o backend, incluindo seu
  leitor interno e paths ASCII relativos no subprocesso privado, com cwd restaurado.

A evidência dirigida teve grupos sobrepostos de 50 testes (48 pass e dois skips
de MONAI/ANTs ausentes na `.venv`), 37 pass, dez pass com Chrome/JobObject/ONNX e
seis regressões finais depois da última mudança do serviço. Não são totais
somáveis de casos únicos. O adaptador completo com redes ONNX minúsculas de
Brain/tumor passou em pasta Unicode nos ambientes 3.12 e 3.10 distribuído
(Raidionics 1.5.2, SimpleITK 2.4.1, ONNX Runtime 1.20.1). Não se repetiram as
inferências treinadas nem a instalação de vários gigabytes por mudanças de
interface/proveniência. Pesos, licenças, revisões e parâmetros científicos
permaneceram iguais; o catálogo ganhou somente ajuda.

**Limite operacional explícito:** se um encerramento não foi confirmado e o
serviço recupera o registro sem o owner em memória, esse registro continua
bloqueando novos processamentos Neuro. Não existe desbloqueio automático por
tempo, status ou simples reinício; a liberação exige confirmação efetiva pelo
owner. Esse caso precisa de inspeção operacional. A revisão aceitou a escolha
segura sem apresentá-la como recuperação automática completa.

O ZIP anterior de SHA `8605b82bcd897d263c171c99e5ab8b2194c98b31491064416e0e74132a870d27`
é pré-correção. Os recibos finais precisam corresponder ao CODE pós-revisão.

## Verificação automática e rastreabilidade

O conjunto rápido de CI foi executado localmente com Python 3.12.10 `-I -S`:
**94 testes, OK, dois skips de symlink por privilégio Windows**, em 23,275 s,
sem site-packages. São os contratos/pacotes sintéticos selecionados em
`verify.yml`; os dois arquivos de workflow também passaram por parse YAML.
Uma tentativa pelo embeddable 3.10 não serviu como reprodução do runner regular:
seu `_pth` ignora o cwd nos subprocessos dos testes de importação. Não se
contabiliza aquela tentativa como aprovação de CI 3.10.

O pipeline remoto do commit `0dfc86c2fb18d878ea5f7003f687058d6de0e1a6` concluiu
com sucesso no Windows regular, tanto em Python 3.10 como em 3.12:
[execução de CI](https://github.com/drhenriquebraga/neuro-rt/actions/runs/40952839980).
Isso verifica aquele commit, anterior à onda final de correções da revisão geral;
o novo commit precisa de sua própria conferência. O workflow de release é manual
e cria apenas rascunho privado com fontes. A publicação de
OFFLINE/SETUP/latest é etapa controlada, descrita em `RELEASE_PROCESS.md`.

Consulte também `MATRIZ_COMPATIBILIDADE.md`, `RELEASE_BUILD.md`, o inventário final
de release, `DECISOES_IMPLEMENTACAO.md` e os patches privados em
`integration/host_updates`. O repositório Nidus original não foi excluído.
