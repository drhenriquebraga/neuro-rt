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

## v8.6 — o retorno de campo de 19/10/2026

Os pedidos na letra do autor e as decisões do coordenador estão no
`docs/RETORNO-CAMPO-19OUT2026.md` da Suite; o registro medido, no
`docs/ENTREGA-V86-19OUT2026.md` de lá. Nada aqui tem identificação de
paciente.

- **O popup que os outros copiaram**: as abas passam a ficar à esquerda
  (eram centralizadas), e a tela de trabalho ganha o cartão «Carregar
  série», que reabre o popup e diz a série aberta.

## v8.7 — o retorno de campo de 21 a 24/10/2026

Os pedidos do autor e as 34 decisões do grilling de 24/10 (aprovadas
inteiras: «Estou de acordo com todas as suas sugestões. Todas aprovadas.»)
estão no `docs/RETORNO-CAMPO-21-24OUT2026.md` da Suite; a equipe e os
contratos, no `docs/EQUIPE-V87.md` de lá; o registro medido, no
`docs/ENTREGA-V87-25OUT2026.md`; o que ficou com o autor, no
`docs/PENDENTES-V88.md`. Nada aqui tem identificação de paciente.

- **O Nidus no padrão do angioview** (decisão 29, sem copiar código nem arte
  dele): um estudo de design navegável, validado por um segundo agente, e
  então o código — a convenção do arco em C numa função só (LAO põe o
  detector à esquerda, Towne CRA 30, Caldwell CAU 15), a projeção que
  acompanha a caixa, a prévia a 256 durante o arraste com o lápis travado
  até a projeção cheia (troca a decisão de v8.5 «resolução sempre a
  máxima»: a projeção que vale continua a de 1024), o mapa de incidências,
  o 3D da caixa (vista do detector, «Ver através»), a sala e as barras e os
  presets que já existiam, integrados. O desenho da tela da v8.5 (os três
  MPR à direita) deu lugar ao do estudo (o MPR numa faixa embaixo do 3D).
- **O arco em C é desenhado no código**: o c-arc.glb do Tripo não entrou
  (a premissa aprovada: retirar a textura ou, se a malha não pudesse ser
  usada, um arco próprio). Pelos Termos do Tripo, o que se gera no plano
  grátis é do Tripo, e só o plano pago dá o direito de distribuir; sem
  registro escrito do plano, o arco é o procedural. A licença fica com o
  autor.
- **A chave da aba passou a `radai_nidus_v2_`**, para um desenho salvo na
  convenção velha não voltar com a matriz nova.
- **O osso num STUDY com nome próprio** sai pelo nome padrão da descrição.
