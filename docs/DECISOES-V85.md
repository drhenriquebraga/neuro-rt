# Nidus RT — decisões da v8.5 (14/10/2026)

As decisões do autor para este app, compiladas do brainstorm de 14/10. O
registro mestre é `C:\AI_PROJETOS\AUTO_CONTORNO\docs\BRAINSTORM-V85.md`.
Nada aqui tem identificação de paciente. «Rn Qm» é a rodada e a pergunta.

## O erro «ValueError: axes don't match array»

O autor o viu várias vezes: ao fechar a caixa de recorte, e depois de só
circular com o lápis. Medido: a única transposição do app fica na conversão
para LPS, chamada ao abrir a série e ao pedir os tubos. Ela quebra quando o
volume não chega com três dimensões. A sequência exata que o produz na tela
ainda não foi reproduzida: reproduzir com fantoma antes de consertar.

Valha a causa que valer, o conserto é o mesmo (R1 Q27, e o retorno de campo):
- **cada ação vira um estado salvo**: os desenhos de cada incidência, com os
  parâmetros (ângulos, recorte, janela);
- **perto do erro, a ação é bloqueada**; se o erro vier mesmo assim, a tela
  volta sozinha ao último estado bom, avisa, e nada do que foi desenhado se
  perde;
- o progresso pode ser salvo mesmo depois de um erro.

## Osso fora da projeção (R1 Q26)

- Usar a segmentação que o ContourLab já gravou para a série (o FULL ou o
  mapa de rótulos) para omitir o crânio e os ossos, e deixar só os vasos
  contrastados. O foco são os **pequenos vasos com contraste**.
- Série sem segmentação: a tela oferece «segmentar primeiro (AUTO)», pela
  fila única da estação, e não adivinha o osso pela densidade.

## Ferramentas

- **Só o lápis.** Saem «cliques» e «circular a área». Hoje o lápis só
  funciona com «circular a área» ligado ao mesmo tempo: é a causa de ele «não
  habilitar».
- Pontilhado mais fino e pontos mais próximos; soltar o clique fecha a área,
  do último ponto ao primeiro.
- **LAO/RAO e CRA/CAU em barra de arrastar**, e não só no campo digitado. A
  lista das guardadas passa a dizer RAO e CAU quando o ângulo é negativo.

## Padrões de abertura

- Inverter cores, todo o volume e MIP ligados de partida.
- **Resolução sempre a máxima**, e a opção de resolução sai: «não dá para ver
  nidus em qualquer resolução que não for alta».

## Desenho da tela

O bloco de ferramentas sobe para cima do visor principal; à direita do visor,
os três MPR empilhados, com a mesma altura do visor. Tudo numa tela só, sem
rolar.

## Da Suite

- O acervo vem pela tabela comum da Suite (R1 Q24), e não pelo seletor.
- O brilho de processamento da casca, por pelo menos 2 s, na projeção e nos
  MPR.
- O pedido de refazer em AUTO, substituindo a entrega, chega ao lote desde a
  onda 2e: a fila da Suite guarda o `substituir` (só o `true` literal,
  depois da confirmação na tela), e a pendência da bateria virou `False`.
- No tema claro, o rótulo e os botões sobre a projeção usam as fichas da
  imagem, escuras nos dois temas.
