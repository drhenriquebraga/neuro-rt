# NEURO RT 1.1.0 — fase de testes

Requer Local Suite8.12 ou posterior com o bootstrap desta entrega. A instalação
completa da suíte deve existir previamente; o plugin usa seu mesmo Python.

- Nidus permite ampliar axial, coronal ou sagital no visor principal e restaurar
  o layout. O consenso geométrico varia da união estrelada(0) à interseção de todas
  as incidências(100), com edição por plano, desfazer e exportação explícita de
  uma sugestão RTSTRUCT UNAPPROVED na referência original.
- Glioma, Metastasis, Meningioma e Anatomia ficam disponíveis em fase de testes,
  com aviso e aceite ao abrir cada card. O convite a colaborar com Dr.Henrique
  Braga não envia exames, logs ou feedbacks automaticamente.
- As chaves continuam por modelo. Falta de sequência obrigatória desativa o
  modelo; classificação ambígua avisa e permite associação manual. Nenhum modo
  AUTO/FAST foi acrescentado ao seletor de modelos.
- Instalação e atualização usam manutenção externa com progresso, encerramento
  protegido e reabertura da suíte. Configurações inclui atualização Neuro,
  nova consulta à release e seleção de uma pasta local para máquinas sem rede.
- START_HERE.cmd abre um assistente com dois botões: instalar/atualizar através
  da suíte existente e montar uma pasta offline para transportar. O destino de
  instalação de um pacote trazido é escolhido na interface da suíte.

O SETUP público contém somente código, termos, licenças e receitas verificadas.
Somente SETUP versionado e SETUP_LATEST são publicados. Pesos e complementos são
preparados na estação, com SHA256/origens fixados e cache reutilizável; o pacote
offline completo é montado localmente. Nenhum Python ou venv é baixado ou copiado,
e Torch/CUDA/NumPy/SimpleITK da suíte não são substituídos.

O catálogo mantém seis opções tumorais Raidionics, Attention U-Net3D,
SynthSeg/DIPY, CerebrA/ANTs e Buti existente no host. Os auxiliares exigidos pelos
motores são preparados junto, sem aparecer como outra escolha. SynthSeg recebeu
uma adaptação local auditada para DIPY1.11/Python3.10, preservando as funções
científicas da fonte fixada e suas licenças.

As dez opções foram executadas em fantomas sintéticos com pesos reais, rede
bloqueada e geometria conferida no Python3.10.11 da suíte. Resultados vazios foram
preservados. Essa prova verifica execução e geometria; não mede precisão
anatômica ou clínica. Os ensaios registrados são de CPU, sem validação GPU.
Consulte os recibos de modelos, Nidus, interface e instalação nesta pasta.

Todo RTSTRUCT continua UNAPPROVED. Revisão, junção de arquivos e aprovação são
atos do profissional no TPS. Não há CTV, margem automática ou fusão implícita RM–TC.
