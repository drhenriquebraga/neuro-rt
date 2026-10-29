# NEURO RT 1.0.0

Primeiro plugin opcional do Local Suite, com Nidus RT, Glioma RT, Metastasis RT,
Meningioma RT e Anatomia RT na mesma navegação e fila. Requer a base compatível
8.10 e os helpers comuns Recon3D fornecidos na integração privada.

Inclui seleção manual de modelos, associação de sequências, referência explícita,
alinhamento físico, resultados por revisão e visores MPR/3D do host. A exportação
entrega um RTSTRUCT por referência/execução, com ROIs independentes por modelo e
classe, procedência e status UNAPPROVED.

Quatro adições ao catálogo: Raidionics GBM pós-operatório 3p, Attention U-Net 3D,
SynthSeg/DIPY e CerebrA/ANTs. Os cinco Raidionics anteriores permanecem; Buti usa
os pesos do host. QTIM não integra a distribuição. Pesos e bibliotecas mantêm suas
próprias licenças, documentadas no inventário.

Os runtimes distribuídos nesta entrega são CPU. Testes usam fantomas e verificam
execução/contratos/geometria, sem demonstrar precisão clínica. GPU, Windows LTSB e
outra estação física não foram validados. Consulte a matriz de evidências e as
instruções de instalação para os limites e artefatos desta versão.

Um ZIP SOURCE contém fontes. A instalação completa requer OFFLINE com runtimes e
pesos ou SETUP apontando para uma release acessível. Um rascunho sem esses assets
não oferece instalação por latest. O repositório Nidus original permanece intacto.
