# NEURO RT — primeiro plugin do Local Suite

Data: 29/10/2026.
Estado: desenho aceito pelo usuário em 29/10/2026. O pedido seguinte autoriza
somente escrever o roadmap detalhado; codificação ainda não autorizada nesta etapa.
Revisão independente do desenho concluída em 29/10/2026: nenhuma pergunta
impeditiva para planejar a implementação. Isso não representa teste de código,
dos pesos ou validação dos resultados de segmentação.

## 1. Intenção

Distribuir NEURO RT separadamente para manter o instalador inicial do Local
Suite leve. Depois de instalado, o plugin é parte da mesma aplicação: mesma
origem e porta, navegação, configurações, fila, seleção de séries, visualizadores
e atualização. O usuário não administra um segundo programa.

A finalidade é ensino e pesquisa: estudar a anatomia, a preservação ou deformação
dos órgãos em risco e a posição das lesões na série de referência. A presença de
contornos não equivale a comprovar preservação funcional ou invasão tumoral.

Este desenho consolida as decisões da conversa de 29/10 e evolui o NEURO RT
v0.2 existente. Preserva as decisões de 11/10 que não foram substituídas:
visualização sem editor de contorno, saída completa dos modelos, sem selecionar
apenas o maior foco, e ajuste/fusão final no TPS do usuário. Múltiplos focos de
uma mesma classe continuam numa ROI. As novas classes de modelos multiclasse
ganham ROIs distintas, respeitando inclusive classes aninhadas como WT/TC/ET.

## 2. Abordagens consideradas e escolha

1. **Integrar tudo ao bundle inicial:** aproveita a montagem atual, mas aumenta
   o download de todos os usuários. Não atende à razão declarada para o plugin.
2. **Aplicativo separado, com serviço, interface e fila próprios:** aproveitaria
   o modo independente atual do NEURO RT, mas não atende à integração pedida.
3. **Distribuição opcional com integração nativa ao host:** escolhida pelo usuário.
   NEURO RT tem fontes, instalador e releases próprios, e a suíte carrega seus
   recursos quando instalado. Os processos Python de inferência podem ser
   isolados para compatibilidade, mas obedecem à fila e às preferências do host.

Escolha técnica proposta pelo responsável pela implementação: usar os pontos de
extensão do host para rotas, catálogo, fila e páginas, sem abrir uma segunda
porta nem duplicar o visualizador, o leitor DICOM ou o gravador RTSTRUCT. O iframe
do protótipo anterior não é uma exigência deste desenho. A interface final deve
usar os componentes e comportamentos da suíte.

## 3. Home e navegação

- O card inferior esquerdo NIDUS RT da home passa a NEURO RT.
- No primeiro acesso, se ausente, a suíte confirma o download e a instalação.
- A instalação cria `<LocalSuite>/Plugins/NEURO RT`, relativa à instalação em
  execução, e não a um caminho fixo de desenvolvimento.
- A minipágina NEURO RT contém cinco cards confirmados: Nidus RT, Glioma RT,
  Metastasis RT, Meningioma RT e Anatomia RT.
- Glioma, Metastasis e Meningioma apresentam também o grupo opcional
  **Estruturas anatômicas**, com o mesmo catálogo usado por Anatomia RT.
- Carregamento, seleção de pasta/séries, popups, progresso, animações, tabelas,
  idioma e tema seguem os componentes compartilhados da suíte.

## 4. NIDUS RT e repositórios

Migrar integralmente fontes, ferramentas, testes, documentação, créditos e
histórico recuperável do NIDUS RT para o repositório próprio do NEURO RT,
preservando suas licenças. Manter funções de projeção, desenho, interseção,
remoção de osso e visualização. Evitar versões duplicadas dos módulos/rotas.

A migração não acrescenta exportação da interseção geométrica, cálculo de volume
ou modelo vascular ao Nidus. A referência a RTSTRUCT deste desenho diz respeito
às segmentações dos modelos, não altera silenciosamente o contrato do Nidus.

O Nidus continua usando os serviços comuns. Seu pedido explícito de preparação
da anatomia para remover osso pode reutilizar o executor atual do ContourLab;
isso não cria um seletor AUTO/FAST na seleção de modelos do NEURO RT.

O usuário informa que o repositório NIDUS ainda é privado. Sua exclusão fica
para uma etapa posterior à migração e verificação, conforme pedido: migrar tudo
primeiro, depois apagar. Nenhuma exclusão está autorizada nesta fase de desenho
ou deve acontecer como efeito de copiar os arquivos. O nome/disponibilidade e a
visibilidade do novo repositório devem ser verificados antes de criá-lo; por
padrão, criar privado, sem publicar código como efeito da migração.

## 5. Catálogo

### Modelos existentes

Manter os cinco modelos tumorais Raidionics já preparados: MRI_GBM,
MRI_LGGlioma, MRI_Meningioma, MRI_Metastasis e MRI_GBM_Postop_FV_1p, e seu modelo
auxiliar cerebral. Pesos e metadados existentes são referenciados por versão
e hash. Modelos auxiliares de pré-processamento não são opções tumorais
independentes da tabela.

### Até cinco adições selecionadas

| Adição | Arquitetura/resultado | Entradas | Licença declarada |
|---|---|---|---|
| Raidionics MRI_GBM_Postop_FV_3p | AGU-Net, tumor residual no pós-operatório precoce | T1 sem contraste, T1 com contraste e FLAIR pós-operatórios | BSD-2-Clause no repositório dos modelos; asset ONNX da release 1.2.0 |
| Attention U-Net 3D — Motaz Alqaoud | Regiões WT, TC e ET de glioma | T1 sem contraste, T1 com contraste, T2 e FLAIR | MIT no cartão dos pesos |
| Brain-Mets-Seg — QTIM | Ensemble de U-Nets 3D, metástases | T1 com contraste | Apache-2.0 explicitamente para código e pesos |
| SynthSeg | U-Net, estruturas cerebrais | Uma RM estrutural; entrada inicial proposta: T1 | Apache-2.0; adaptação PyTorch/DIPY documenta pesos e download |
| CerebrA + ANTs | Propagação de atlas por registro deformável | T1 volumétrico como entrada inicial proposta | CerebrA CC0, ANTs Apache-2.0 e avisos próprios do template MNI |

A seleção é para integração; os novos pipelines ainda não foram executados ou
validados localmente. Conferir arquivos efetivos, versões, licenças aplicáveis,
procedência, download, integridade e instruções de inferência antes de incluí-los
no pacote distribuído. A licença declarada por um publicador não é comprovação
de validação clínica ou da cadeia completa de direitos de terceiros.

QTIM apresenta maior risco de compatibilidade: sua distribuição publicada usa
Linux/Docker/NVIDIA DALI. Está aprovado lançar com as outras quatro adições se
não houver uma implementação verificável no Windows suportado pela suíte.
Não exigir que o usuário configure Docker manualmente. A versão lançada deve
declarar o catálogo efetivamente funcional, sem apresentar candidato como pronto.
Não adicionar outros modelos para completar o número cinco sem novo alinhamento.

**Incluído no alinhamento aceito:** expor em Anatomia RT o Buti para
TC já existente na suíte, reutilizando executor e pesos do ContourLab, sem contar
como modelo novo e sem download duplicado. Na primeira integração, preservar a
conversão e as saídas atuais do wrapper; não ampliar silenciosamente sua política
de entrega. O código atual permite TC sem exigir contraste, mas a documentação
local não comprova desempenho específico em TC sem contraste. Não apresentar tal
desempenho como validado. Não habilitar SynthSeg/CerebrA para TC só por analogia.

## 6. Carregar séries e selecionar modelos

Usar o seletor da suíte para localizar os DICOMs na pasta carregada, identificar
séries e apresentar séries/conjuntos do mesmo sujeito e momento de aquisição.
O usuário escolhe as chaves dos modelos que deseja executar; elas começam
desligadas. **Não existem AUTO ou FAST na seleção de segmentação.** Isso não
remove a preferência global de dispositivo auto/CPU/GPU da suíte.

Para modelos multissequência:

- Cada entrada obrigatória precisa corresponder a uma série realmente presente.
- Quando falta uma entrada, nome e chave ficam discretamente apagados e
  desativados. Não substituir uma entrada ausente por uma série duplicada,
  sintetizada ou por outro paciente.
- **Ambiguidade na identificação não bloqueia a execução.** Exibir aviso e a
  associação proposta; permitir escolher/corrigir as séries de entrada, mas não
  exigir resolução da incerteza para habilitar ou iniciar. A série selecionada
  pode continuar marcada como classificação incerta, com essa condição registrada.
- Distinguir no código uma entrada realmente ausente de uma entrada presente
  cuja classificação é incerta; não transformar incerteza em ausência.
- Séries duplicadas têm uma associação proposta visível e podem ser trocadas;
  o mapeamento efetivo fica registrado no resultado.
- Não reunir automaticamente exames de pacientes diferentes nem momentos
  pré/pós-operatórios incompatíveis. Isso é integridade do conjunto, não bloqueio
  por ambiguidade de nome ou classificação de sequência.

O **“?” permanece ativo inclusive nas linhas desativadas**. O popup flutuante
explica finalidade, classes/estruturas de saída, sequências obrigatórias,
entradas reconhecidas/ausentes/incertas, preparação e processamento, requisitos
de equipamento, explicação educacional breve, limitações, fontes, versão e licença.
Usar abertura por clique e suporte a foco/teclado conforme o padrão da suíte.
Não inventar tempo de processamento ou precisão antes de medi-los/verificá-los.

## 7. Série de referência e geometria

Um conjunto multissequência tem **uma única série de referência** apresentada
antes de iniciar, sugerida conforme o modelo: usualmente T1 com contraste para
tumores e T1 para anatomia. O usuário pode selecionar outra série adequada do
conjunto. A seleção de referência não dispensa as entradas exigidas pelo modelo.

Os demais volumes são entradas do processamento. Usar o pré-processamento,
registro e normalização apropriados a cada modelo, conservando as transformações
para devolver as máscaras à geometria da referência. Não presumir alinhamento
porque as séries estão na mesma pasta ou possuem dimensões iguais. Rótulos
devem ser transportados sem criar classes novas por interpolação.

Todos os modelos pedidos para a mesma referência entregam resultados nessa
série. Não gerar automaticamente um RTSTRUCT para cada sequência auxiliar.
Séries de referência diferentes produzem arquivos separados. O usuário faz
fusões, junções e ajustes no TPS. Não incluir transferência RM–TC implícita.

## 8. Fila, processamento e falhas

Integrar à fila compartilhada da estação, com um processamento pesado por vez,
respeitando a arbitragem do host. O plugin não mantém uma fila concorrente.
Processos Python ficam ocultos, com progresso e erros na interface da suíte.
Respeitar a preferência global de dispositivo: CPU estrita, GPU estrita ou auto,
conforme o resolvedor do host, sem novo seletor no plugin.

Proposta de apresentação a cargo da implementação: um item por série de
referência/conjunto, com etapas por modelo e exportação final; não exigir que o
usuário monte tarefas técnicas de pré-processamento.

Se um modelo falhar, continuar os demais e marcar conclusão parcial. Conservar
as saídas válidas; permitir repetir somente os modelos com falha. Falha do
pré-processamento compartilhado afeta apenas os modelos que dependem dele.
Máscara vazia é um resultado sem estruturas, não evidência de ausência de doença
nem falha técnica por si só. Quando não há nenhuma ROI exportável, não produzir
um RTSTRUCT vazio nem anunciar que um arquivo completo foi gerado.

Sair da minipágina enquanto o host continua aberto não cancela o trabalho;
o estado permanece acessível pela fila. Persistir resultados/índices para poder
reabrir após reinício, usando o acervo e os mecanismos da suíte. Não reiniciar
inferências interrompidas sem o comportamento explícito previsto pela fila.

## 9. RTSTRUCT e visualização

**Um arquivo RTSTRUCT por série de referência em cada execução**, reunindo as
ROIs dos modelos que concluíram para aquela referência. Isso é agregação de
ROIs no arquivo, não fusão geométrica entre máscaras de modelos diferentes.
Manter identificadores exclusivos por modelo/classe, preservando procedência
e o padrão de nomes da suíte. Respeitar o limite de nomes DICOM por meio de
nomes curtos estáveis e descrições completas; nunca colidir chaves de ROIs.

Usar o gravador existente do host. Preservar UNAPPROVED, referências DICOM,
FrameOfReferenceUID, SOPInstanceUIDs e geometria da série. Gravar na pasta
original conforme o comportamento do NEURO RT existente; nova execução não
sobrescreve arquivos anteriores. Um retry pode produzir uma revisão completa
do resultado da execução, preservando a anterior e identificando a revisão.
Falhas parciais e modelos ausentes ficam visíveis no manifesto e na tela.

Reutilizar o design e o motor de Reconstruções 3D: 3D, axial/sagital/coronal,
sincronização entre visores e **seletor da série segmentada**. Reutilizar a lista
de estruturas com busca, chaves de visibilidade e opacidade. Os nomes e créditos
permitem distinguir modelos no arquivo único sem criar um segundo comparador.
Preservar o comportamento de ampliar/trocar o plano principal quando aplicável
ao componente compartilhado. Edição de contornos continua no TPS.

## 10. Instalação e atualização

O bundle inicial do Local Suite contém apenas a integração necessária para
descobrir, instalar e carregar o plugin. O plugin tem instalador PowerShell e
artefatos próprios de release no GitHub; o instalador prepara dependências,
runtime e pesos do catálogo distribuído dentro da instalação selecionada.
Reutilizar pesos existentes quando compatíveis e verificados.

Ao abrir a minipágina, consultar a release latest do NEURO RT. **A experiência
de atualização segue o padrão atual do Local Suite**, inclusive as escolhas já
existentes de aguardar a fila ou interromper explicitamente. Não introduzir
uma política paralela de atualização silenciosa durante processamento ativo.
Registrar os trabalhos Neuro na arbitragem de uso do host para que a atualização
da suíte também os reconheça. Sem rede, uma instalação íntegra permanece usável.

Escolhas técnicas a cargo da implementação:

- Manifesto de plugin com versão, host mínimo/compatibilidade, catálogo e
  artefatos/pesos fixados por versão e integridade; latest descobre a release
  publicada por nós, não troca pesos por versões arbitrárias de terceiros.
- Downloads e extração em preparação, conferência antes da ativação, proteção
  contra extração fora do destino e substituição controlada com recuperação da
  versão anterior em caso de falha.
- Preservar configuração local, pesos válidos, resultados e acervo nas atualizações
  tanto do plugin quanto do host. Não remover Plugins ao atualizar o bundle base.
- Instalação cancelada ou incompleta não equivale a plugin instalado; retentativa
  recupera ou refaz os artefatos afetados sem corromper a instalação anterior.
- A aparência integrada não exige compartilhar todas as bibliotecas Python:
  manter isoladas as dependências incompatíveis, sob a mesma fila e configurações.
- Incorporar licenças e avisos completos de código, pesos e atlas nos artefatos.

## 11. Escopo, restrições e escolhas delegadas

Não acrescentar editor, margem/CTV, diagnóstico automático, classificação de
resposta, acompanhamento longitudinal, novo modelo vascular ou mudança funcional
do Nidus como parte implícita desta integração. Não ultrapassar cinco modelos
novos. Essas extensões exigiriam desenho próprio.

O responsável pela implementação decide organização interna, adaptadores,
nomes técnicos, estratégias de cache, mecanismo de carregamento, detalhes de
retomada e empacotamento, desde que respeite este contrato e o padrão do host.
Registrar decisões técnicas que alterem compatibilidade, tamanho ou comportamento
perceptível. A infraestrutura pode servir futuros plugins, sem construir agora
uma loja genérica ou redesenhar a suíte.

Fontes e testes podem entrar no Git; pesos, Python, imagens, resultados, caches,
configuração local e dados de pacientes não. Usar testes sintéticos e, quando
necessário, demos públicas desidentificadas com procedência/licença. Não ler nem
imprimir dados clínicos privados para planejar ou desenvolver.

As instruções locais da fase antiga que proibiam modificar o host descreviam
o desenvolvimento isolado do protótipo. O novo pedido prevê integração do host;
após aprovação deste desenho, as mudanças necessárias nessa integração fazem
parte do escopo, respeitando as permissões do ambiente. Não iniciar codificação
antes da aprovação final solicitada pelo próprio usuário.

## 12. Critérios de conclusão

1. Home e cinco cards corretos, com o plugin ausente/instalando/instalado/falha
   representados de forma verificável.
2. Instalação limpa em caminho real e relocável, sem segunda aplicação aparente;
   base da suíte funciona sem o plugin e continua funcionando após instalá-lo.
3. Nidus mantém seus fluxos e dependências sem rotas duplicadas.
4. Seleção manual; ausência efetiva desativa, ambiguidade avisa e permite rodar;
   popup permanece acessível nos três estados.
5. Casos sintéticos de múltiplas séries, referência, alinhamento e retorno de
   máscaras à geometria original; nenhum cruzamento de sujeitos.
6. Exclusão mútua com ContourLab, progresso, cancelamento, falha parcial,
   reabertura dos resultados e atualização respeitando os trabalhos ativos.
7. Um RTSTRUCT por referência/execução com ROIs distintas por modelo/classe,
   procedência e referências corretas, preservando arquivos anteriores.
8. Visualização consistente entre MPR/3D e troca de série, com geometria e
   lateralidade verificadas; pesos reais testados antes de serem anunciados
   como funcionais. Testes sintéticos não equivalem a validação clínica.
9. Download verificável dos modelos distribuídos, licenças preservadas e caminho
   de atualização/recuperação testado sem apagar dados locais.
10. Migração do repositório conferida antes de qualquer exclusão futura do Nidus.

## 13. Evidências e referências de implementação

Locais: `README.md`, `docs/INTEGRACAO.md`, `docs/ESCOPO.md`, `module.json`,
`models.lock.json`, `neuro_rt/catalog.py`, `neuro_rt/service.py`,
`neuro_rt/worker.py`, `neuro_rt/export.py` e `scripts/package_module.py`.

Host: `AUTO_CONTORNO/app/radai_queue.py`, `radai_queue_state.py`,
`radai_atualizar.py`, `radai_panel.py`, `build/empacotar_instalador.py`,
`installer/INSTALL.ps1` e `packager/UPDATE.ps1`.

Componentes: `NIDUS_RT/app/radai_nidus_screen.py`,
`RECON_3D/app/radai_recon3d_screen.py`,
`CONTOURLAB/app/radai_cranio_engine.py` e `CONTOURLAB/app/radai_models.py`.

Fontes externas já consultadas na seleção:

- https://github.com/raidionics/Raidionics-models e release `1.2.0`.
- https://www.nature.com/articles/s41598-023-45456-x
- https://huggingface.co/motazalqaoud/brain-tumor-segmentation-weights
- https://github.com/QTIM-Lab/Brain-Mets-Seg
- https://github.com/BBillot/SynthSeg
- https://docs.dipy.org/stable/_modules/dipy/nn/torch/synthseg.html
- https://doi.gin.g-node.org/10.12751/g-node.be5e62/
- https://github.com/ANTsX/ANTs/blob/main/COPYING.txt
- https://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009

## 14. Aprovação

As decisões atribuídas ao usuário estão descritas nas seções anteriores.
O alinhamento final aceito inclui expor Buti já existente no card Anatomia RT,
usar inicialmente T1 para as duas novas opções anatômicas, criar o novo
repositório privado até haver instrução para publicação e conservar versões
anteriores dos resultados e uma revisão completa após retry parcial.

O usuário aceitou o alinhamento e pediu primeiro um roadmap detalhado, sem código.
O plano está em `../plans/2026-10-29-neuro-rt-roadmap.md`, acompanhado dos planos
por subsistema. Sua redação não autoriza implementação nesta etapa. A exclusão
do repositório NIDUS continua uma etapa posterior e separada.
