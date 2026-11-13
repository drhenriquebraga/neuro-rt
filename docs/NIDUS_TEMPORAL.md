# NIDUS: angiografia temporal e preparo inicial

O botão **CINE de enchimento**, antes de Anatomia, abre o seletor padrão de séries.
Ele aceita fases temporais adquiridas e conferidas nos metadados DICOM; a ordem
dos arquivos, o nome TOF ou a expressão 3SLAB não estabelecem tempo.

O visualizador mantém câmera e janela iguais entre as fases. Oferece reprodução,
pausa, velocidade, seleção de fase e loop. Mostra os intervalos relativos à
primeira fase quando os metadados os informam. A velocidade do player não altera
o tempo adquirido nem representa a resolução temporal efetiva de técnicas com
view-sharing. Não há interpolação temporal nem geração de anatomia por IA.

Volumes 3D permitem mudar a incidência; projeções temporais 2D são reproduzidas
sem inventar rotação 3D. Uma mudança de incidência prepara novamente as projeções
de todas as fases. O primeiro preparo depende da CPU e do tamanho do exame.
Depois de prontas, as imagens decodificadas ficam em cache e o loop não pede
novas reconstruções ao servidor.

A referência estática, os MPR, as marcações e o consenso do NIDUS são preservados
e ficam fora do painel temporal. Voltar à referência restaura a estação. Este
CINE não exporta contornos nem transfere marcações entre fases.

Na angiografia estática, a roda gira em LAO/RAO; Shift + roda muda CRA/CAU.
Nos MPR, a roda continua percorrendo cortes. A abertura usa o popup animado do
host, com etapas reais: leitura do volume, projeção/MPR e preparo das incidências.
Os controles só são liberados depois da conclusão. Cancelar ou escolher outra
série invalida respostas atrasadas.

## Identificação e limites

- DICOM clássico: TemporalPositionIdentifier; ou protocolo explicitamente
  dinâmico com AcquisitionNumber e tempos de aquisição coerentes por volume.
- Enhanced MR: índices temporais e geometria por frame. Leitura indexada de
  pixels, sem carregar toda uma aquisição 4D como uma pilha espacial.
- Identidade, estudo, FrameOfReference e grade completos são conferidos.
  Sequências ambíguas, grades incompletas e fontes alteradas são recusadas.
- Até 64 fases. Preparação serial sob o mesmo bloqueio da projeção estática,
  com limite de memória, tempo, número de trabalhos e expiração de sessões.
- Mensagens e controles usam os 12 idiomas do host. Dados DICOM não são enviados
  a serviços externos; identificadores e caminhos não aparecem nas respostas
  públicas da API temporal.

As verificações de software usam DICOMs sintéticos e navegador automatizado.
Compatibilidade com os arquivos de um equipamento específico depende da
organização efetiva das séries e deve ser conferida com um exame local.
