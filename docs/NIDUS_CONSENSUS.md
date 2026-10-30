# Nidus: sugestão geométrica por incidências

Implementação autorizada para a versão beta 1.1.0. Este documento substitui a
restrição histórica do Nidus que vedava exportar sua construção geométrica.
A nova entrega é uma sugestão manual para estudo e revisão, sempre não aprovada.

## Comportamento da tela

Depois de registrar incidências e receber sua retroprojeção, os botões Ampliar
levam axial, coronal ou sagital ao visor principal. O mesmo elemento de imagem,
cursor de corte e sobreposição é movido; Layout original o recoloca em sua
posição. A projeção, seu zoom e o estado da cena 3D continuam disponíveis.

A temperatura usa uma escala geométrica de 0 a 100: 0 é a união literal das
retroprojeções dentro da referência; 100 é a interseção de todas. A linha verde
representa a sugestão. A cor de cada incidência e a interseção original continuam
visíveis para comparação. Interseção vazia é um resultado permitido, indicado na
tela; uma máscara vazia não produz RTSTRUCT.

Editar sugestão prepara uma cópia completa pela fila compartilhada. Adicionar e
Remover aplicam um polígono fechado somente ao corte escolhido. Desfazer restaura
o plano anterior; no máximo 60 traços e 16 MiB de planos compactados ficam na
memória de desfazer. A temperatura fica bloqueada durante a edição. Voltar à
temperatura deixa de apresentar a cópia editada; preparar novamente cria outra
sugestão, sem sobrescrever seus arquivos privados anteriores.

Exportar usa a sugestão mostrada ou a cópia editada, conforme o modo da tela. O
arquivo contém uma única ROI geométrica, na série DICOM original, com aprovação
UNAPPROVED. Não há CTV, fusão de séries, margem automática ou interpretação de
probabilidade. A revisão e qualquer junção posterior pertencem ao usuário no TPS.

## Definição matemática e limites

Cada silhueta rasterizada recebe um campo de distância assinado no plano do
detector, em milímetros: positivo dentro e negativo fora. Silhuetas totalmente
vazias ou cheias recebem sentinelas finitas com o sinal correspondente. A mesma
extrusão, transformação física e amostragem SimpleITK por vizinho mais próximo
da retroprojeção existente leva esses valores à grade nativa.

Em cada voxel, sejam d[0] <= ... <= d[n-1] os valores ordenados. Para temperatura
T, calcula-se r=(1-T/100)*(n-1), interpola-se linearmente entre os dois valores
adjacentes a r, e inclui-se o voxel quando o resultado é maior ou igual a zero.
Assim, T=0 usa o máximo (união), T=100 o mínimo (interseção), e n=1 permanece
invariável. Aumentar T nunca acrescenta voxels. O campo interpolado é contínuo por
partes em T; a máscara binária muda em passos e pode desaparecer. A distância é
projetada, não uma distância euclidiana tridimensional nem evidência clínica.

Usar interpolação bilinear na distância, mantendo retroprojeções binárias por
vizinho mais próximo, quebraria os extremos. A implementação mantém a mesma
convenção de centros e bordas do núcleo existente, testada bit a bit.

O núcleo conserva size, origin, spacing e direction originais. A orientação SPL
do visor é somente permutação/inversão de índices; não retifica obliquidade.
Prévia e edição desfazem essa transformação para escrever em ZYX nativo.

## Memória, fila e persistência

O núcleo guarda no máximo 12 campos 2D float32 de até 1024x1024 (~48 MiB).
A ordenação ocorre em blocos limitados de voxels, sem empilhar 12 volumes 3D.
A máscara final é compactada por bits (512³: ~16 MiB). A prévia calcula apenas o
plano solicitado. O volume de imagem e os tubos já existentes na tela também
consomem memória e não estão incluídos nesses valores.

Preparar, editar, desfazer e exportar adquirem uma lease da fila da suíte. O
cancelamento é verificado entre blocos e antes de publicar o arquivo de metadados.
Persistência e publicação em memória acontecem antes de liberar a lease. Uma
falha de gravação conserva o candidato anterior. O gravador RTSTRUCT síncrono
não é interrompido no meio da chamada; o cancelamento seguinte impede publicar
o arquivo para download.

Cada candidato usa uma pasta privada em data/nidus/<id>. Sua máscara e
candidate.json são publicados por substituição atômica, conservando a máscara
atual e a anterior; revisões antigas e órfãs são recolhidas após o commit.
Desfazer não depende de cópias completas por traço em disco. Sugestões distintas
e exportações permanecem privadas para revisão; não existe limpeza global de
estudos adicionada por este recurso. Os polígonos de incidência são dados do
estudo e são mantidos somente nessa área privada e no estado da aba.

## Referência e exportação

A abertura da série captura uma assinatura privada dos SOPs, Series, Study,
FrameOfReference e identidade DICOM. Antes de exportar, a série resolvida pelo
bilhete do servidor deve continuar com a mesma assinatura e geometria física.
O cliente nunca fornece um caminho de origem ou destino.

O gravador engine.build_rtstruct da suíte recebe a máscara nativa, sem suavizar,
decimar, descontar ou fundir. A ROI NidusGeo_ai contém descrição de construção
manual, temperatura, revisão, edição, algoritmo, quantidade de incidências e
SHA-256 dos polígonos/ângulos. O sufixo _ai é a convenção de nomes do gravador;
esta operação não executa modelo ou inferência. O arquivo só é oferecido depois
de verificar UNAPPROVED, SOPs e FrameOfReference e de reler o contorno com o
leitor da suíte, exigindo igualdade voxel a voxel. A referência é conferida de
novo antes de publicar o artefato. Os DICOMs de entrada não são modificados.

## Contratos internos

O núcleo compartilhado RECON_3D expõe `radai_projection.consenso(...)`, com
`ProjectionConsensus.packed(T)`, `mask(T)` e `plane(T,eixo,indice)`. O módulo novo
`radai_projection_consensus.py` precisa acompanhar `radai_projection.py` no
componente RECON distribuído pelo host. As importações científicas são tardias.

As rotas novas usam a sessão de incidências já registrada:

| Rota | Dados JSON exatos |
| --- | --- |
| POST /api/nidus/consenso | s, temperatura |
| POST /api/nidus/consenso/editar | s, eixo, indice, pontos, operacao |
| POST /api/nidus/consenso/desfazer | s |
| POST /api/nidus/consenso/exportar | s, temperatura, editado |
| GET /api/nidus/consenso/download | query s, id opaco do artefato |

Mutação exige origem local, token Neuro atual e os gates de primeiro uso/beta
do host. Índice do plano é inteiro na orientação do visor; os pontos normalizados
estão entre 0 e 1 e a operação é add/remove. Campos extras são recusados. O
estado de sessão expira com as regras existentes; os arquivos privados salvos
não reabrem automaticamente uma sessão após reiniciar a suíte nesta versão.

## Verificação reproduzível

`test_nidus_consensus_core.py` cobre extremos exatos, monotonicidade, incidência
única, vazios, geometria anisotrópica/oblíqua, prévia e limite de blocos.
`test_nidus_geometry.py` cobre edição/desfazer em planos nativos, persistência
limitada e exportação por gravador real usando somente DICOM sintético.
`test_nidus_consensus_api.py` cobre origem/token, campos fechados, fila, falha
de persistência e cancelamento. `browser_nidus_consensus.cjs` exercita a página
completa em Chrome com respostas sintéticas, sem rede externa ou dados clínicos.
