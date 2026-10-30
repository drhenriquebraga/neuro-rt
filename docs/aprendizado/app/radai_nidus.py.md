# app/radai_nidus.py

Comentários e docstrings do código como estava antes da limpeza, na ordem do arquivo. «fica no código» marca o que a limpeza manteve (`GUARDA:`, licença, codificação).

## linha 2 · (módulo) (docstring)

~~~text
radai_nidus.py — projeção vascular: a geometria da angiografia biplanar.

═══ O QUE ELE FAZ ═══

Carrega uma angiotomografia, projeta em ângulo arbitrário (MIP, como a mesa de
angiografia enquadra), o médico circula uma área na projeção, e a área vira um
**tubo** — o conjunto de voxels cujo raio passa por dentro dela. Dois tubos de
angulações diferentes se cruzam, e a interseção é a estimativa clássica.

**Reproduz a lógica geométrica da angiografia biplanar**, que é como a
definição de nidus foi feita historicamente em radiocirurgia.

═══ NADA É APRENDIDO, NADA É DETECTADO ═══

É geometria aplicada ao desenho do próprio médico. A máquina não varre o
volume, não procura, não pontua e não classifica: ela projeta o que o médico
circulou. É a única peça deste aplicativo que não encosta na regra 6 por
construção, e não por trava.

═══════════════════════════════════════════════════════════════════════════
A FRONTEIRA, E ELA ESTÁ AQUI PORQUE PRECISA ESTAR ANTES DA PRIMEIRA LINHA
═══════════════════════════════════════════════════════════════════════════

**A interseção de dois tubos retroprojetados é, na prática, uma estimativa de
volume de alvo para radiocirurgia.**

Isso não cai na regra de detecção — o médico desenhou, a máquina não achou
nada. Mas cai na mesma regra do módulo torácico: **nenhum volume de alvo
derivado.** Então:

  * o tubo e a interseção **existem na tela**, como construção de visualização
    e de ensino;
  * **não exportam.** Nem como RTSTRUCT, nem como malha, nem como imagem;
  * **não têm leitura de volume.** Ver `SEM_VOLUME` abaixo — é a trava menos
    óbvia e a mais importante.

═══ POR QUE NÃO HÁ `volume_cm3` NESTE MÓDULO ═══

No instante em que a tela souber calcular a interseção, alguém vai querer
saber quantos centímetros cúbicos ela tem — e **um volume em cm³ ao lado de
uma forma é um volume de alvo com passos a mais**. A construção geométrica
vira número, o número vira registro, e o registro vira a coisa que se compara
com o plano.

A função que contaria os voxels não existe aqui. Não é omissão: é a trava.

═══ E ANGIOTOMOGRAFIA NÃO É ANGIOGRAFIA ═══

A DSA mostra dinâmica de fluxo — aferentes, tempo de enchimento, drenagem. Uma
angioTC estática não mostra nenhuma dessas coisas: **a veia de drenagem e a
artéria nutridora têm o mesmo brilho**, e é por isso que a definição de nidus
por uma difere da definição pela outra. A tela diz isso, e o cartão se chama
*projeção vascular* — "arteriografia virtual" sugere substituição.
~~~

## linha 58 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 A TRAVA, DECLARADA COMO DADO
 ═══════════════════════════════════════════════════════════════════════════

 `check_project` pergunta se ela ainda está aqui e se o módulo continua
 sem função de volume. Guarda que só existe em prosa é uma lembrança.
~~~

## linha 77 · (módulo)

~~~text
 ═══ E A RM COM GADOLÍNIO (27/09/2026, v8.3) ═══

 Desde a v8.3 o seletor lista RM também (`radai_nidus_screen.MODALIDADES`),
 e a frase de cima fala só de angioTC. O limite vale igual — a T1 pós-
 gadolínio é uma imagem estática, e artéria e veia realçam as duas — e há um
 a mais: o sinal da RM não é HU, então as janelas são relativas à própria
 série (`JANELAS_RELATIVAS`). Frase SEPARADA, e não a de cima reescrita: a de
 cima é chave do dicionário nos doze idiomas, e reescrevê-la a deixaria em
 português em onze até a trilha de tradução passar.
~~~

## linha 93 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 AS INCIDÊNCIAS
 ═══════════════════════════════════════════════════════════════════════════

 Par de ângulos, como a mesa de angiografia: o primeiro é a rotação em torno
 do eixo craniocaudal (LAO positivo, RAO negativo) e o segundo é a angulação
 cranial (positiva) ou caudal (negativa).

 São as incidências de rotina em neuro; entrada livre continua existindo. Elas
 estão aqui e não na tela porque a tela é uma leitura desta tabela — dois
 lugares divergem.
~~~

## linha 115 · (módulo)

~~~text
 Janelas para vaso contrastado, em (centro, largura). A de angio é estreita e
 alta de propósito: o contraste intravascular fica bem acima do parênquima, e
 a janela de mediastino o achata contra o osso.
~~~

## linha 125 · (módulo)

~~~text
 ═══ E A RM NÃO TEM HU (26/09/2026, v8.3) ═══

 As quatro janelas acima são em unidade Hounsfield, e a tela aplicava as
 mesmas quatro a qualquer série. Medido nas três RM de crânio pós-gadolínio
 do banco pseudonimizado: o sinal vai de 0 a 1.178, a 6.957 e a 14.188 —
 três escalas para o mesmo tipo de exame, porque o valor do pixel da RM não
 é grandeza física. Com a janela «angio» (−50 a 650) a projeção de duas
 delas saía um borrão branco, e a da terceira saía um quadrado branco
 inteiro (ver `projetar`, o preenchimento de fora num `uint16`).

 Série sem HU recebe janela RELATIVA: o par de percentis do próprio volume
 (`estatistica`). Os pares foram escolhidos OLHANDO a projeção das três RM
 — são nossos, e não de fonte publicada. «osso» não existe na RM: quem pede
 essa janela numa série sem HU recebe a «ampla».

 O PISO DA «angio» É O p90, e não a mediana. Numa RM de crânio metade do
 volume é ar, então a mediana é ruído de fundo; o MIP de cada raio que
 atravessa o encéfalo já sai ACIMA dela, e o parênquima ocupava a janela
 inteira. O p90 é o nível do parênquima realçado, e é ele que tem de ficar
 escuro para o vaso aparecer — medido nas três RM (ver o relatório da v8.3).
~~~

## linha 156 · estatistica (docstring)

~~~text
Os percentis que as janelas relativas usam, numa amostra do volume.

    AMOSTRA, e não o volume inteiro: um percentil sobre 155 milhões de voxels
    ordena o volume inteiro, e a janela não muda na terceira casa por isso.
    Um voxel a cada 2 × 3 × 3 é o que se lê.
~~~

## linha 170 · tem_hu (docstring)

~~~text
A série está em unidade Hounsfield?

    A MODALIDADE DECIDE quando ela é conhecida: só a TC tem HU. Sem ela — o
    fantoma, ou um chamador antigo —, decide o mínimo do volume: uma TC tem
    ar, e ar é −1.000; uma RM começa em zero. É a regra que vale para o
    fantoma da bateria e para os chamadores que não sabem a modalidade.
~~~

## linha 183 · escala_de (docstring)

~~~text
A escala de intensidade da série: `{"hu", "min", "max", "percentis"}`.

    `min` e `max` são do volume INTEIRO (`MinimumMaximumImageFilter`, 0,1 s
    numa RM de 44 milhões de voxels): é deles que sai o preenchimento de
    fora da projeção, e um mínimo amostrado poderia ficar ACIMA de um voxel
    real e vencer o MIP. Os percentis só existem para série sem HU.
~~~

## linha 201 · janela_de (docstring)

~~~text
`(centro, largura)` da janela pedida — em HU, ou relativa à série.

    `escala` é o que `escala_de` devolveu. Sem ela, ou com `hu` verdadeiro,
    vale a tabela de HU; série sem HU recebe o par de percentis de
    `JANELAS_RELATIVAS` — «osso» vira «ampla», porque na RM não há osso
    brilhante para enquadrar.
~~~

## linha 218 · (módulo)

~~~text
 Lado da projeção. 512 é a resolução de trabalho; a tela usa 256 para girar e
 sobe para 512 na incidência escolhida — medido: 0,14 s contra 0,94 s.
~~~

## linha 222 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 ALTA RESOLUÇÃO: A MAV É FINA, E O DETECTOR ERA MAIS GROSSO QUE A CTA
 ═══════════════════════════════════════════════════════════════════════════

     «quero o Nidus com alta resolução dos vasos porque a MAV é muito fina»
     — Dr. Henrique, 02/09/2026

 O detector é um cubo de lado³ com passo = diagonal/lado. Numa angio de
 crânio de 202 × 202 × 160 mm a diagonal é 327 mm, então:

     lado    passo     contraste do vaso de 0,6 mm    tempo    memória
     256     1,28 mm         +1052                    0,09 s     67 MB
     512     0,64 mm         +1052                    0,52 s    537 MB
     768     0,43 mm         +1121                    3,57 s    1,8 GB
     1024    0,32 mm         +1259                    7,77 s    4,3 GB

 A CTA de origem tem 0,45 mm. Em 512 o detector é MAIS GROSSO que ela — a
 projeção jogava fora resolução que o exame trouxe.

 > **O ganho é real e o cubo é o problema.** 4,3 GB para uma projeção, numa
 > estação que também segmenta, é o caminho para o `MemoryError` que este
 > projeto já viu em campo.

 ═══ E O CUBO NÃO PRECISA SER CUBO ═══

 O que decide a nitidez do vaso é o passo NO PLANO do detector. A terceira
 dimensão é a profundidade do raio, e ela só precisa de amostras suficientes
 para não pular o vaso — o MIP tira o máximo ao longo dela e joga o resto
 fora. Amostrar a profundidade tão fino quanto o plano é pagar memória por
 um eixo que é reduzido a um número.

 Com o plano em 1024 e a profundidade em 512, a memória cai à metade e o
 passo no plano continua o mesmo. Ver `FUNDO_MAXIMO`.
~~~

## linha 257 · (módulo)

~~~text
 Teto de amostras ao longo do raio. MEDIDO no mesmo fantoma, variando só a
 profundidade e mantendo o plano em 1024:

     plano x fundo    passo    tempo    memória    vaso de 0,6 mm
     1024 x 1024      0,32 mm  7,77 s   4,3 GB        +1259
     1024 x  512      0,32 mm  2,4 s    2,1 GB        +1154
     1024 x  384      0,32 mm  1,47 s   1,6 GB        +1154

 De 512 para 384 o contraste não muda e a memória cai um terço. É o eixo que
 o MIP reduz a um número — o que ele precisa é não PULAR o vaso, e com
 interpolação linear um vaso entre duas amostras aparece nas duas, mais
 fraco, em vez de sumir.

 > **Contra o cubo de 1024: mesma imagem, 2,7× menos memória e 5× mais
 > rápido.** O cubo pagava resolução num eixo que ninguém olha.
~~~

## linha 274 · (módulo)

~~~text
 O passo que a origem oferece. Pedir resolução abaixo disto é interpolar
 ruído com cara de vaso — e num módulo cuja fronteira é «isto não vira
 número», inventar detalhe é o pior tipo de erro.
~~~

## linha 278 · lado_para_o_exame (docstring)

~~~text
O maior `lado` que ainda diz algo, dado o espaçamento da série.

    Passar disto não acrescenta informação: o detector ficaria mais fino que
    a CTA, e o que aparece a mais é o interpolador, não o paciente.
~~~

## linha 298 · _euler (docstring)

~~~text
A transformada da incidência, centrada no volume.

    O CENTRO É O DO VOLUME, e não a origem: rotacionar em torno da origem
    joga a anatomia para fora do campo, e a pessoa vê uma tela preta e conclui
    que a incidência não existe.
~~~

## linha 313 · eixos_da_incidencia (docstring)

~~~text
Para onde cada eixo do paciente aponta na projeção desta incidência.

    `{"L": (x, y, prof), "P": ..., "S": ...}`, unitários: `x` cresce para a
    direita da tela, `y` para baixo, e `prof` para longe de quem olha.
~~~

## linha 324 · eixos_da_incidencia (fica no código)

~~~text
 GUARDA: mesma rotação de `_euler`; coluna = x, profundidade = y, linha = -z (crânio em cima).
~~~

## linha 331 · caixa_de_texto (docstring)

~~~text
`(s0, s1, p0, p1, l0, l1)` em fração da vista S-P-L, ou `None` (sem caixa).

    Vem da tela como `"s0,s1,p0,p1,l0,l1"`. Cada valor é preso a [0, 1] e cada
    par é posto em ordem; a caixa que cobre tudo, ou que não tem volume, é
    `None`.
~~~

## linha 352 · _medidas_da_grade (docstring)

~~~text
`(diag, passo, passo_fundo, fundo)` da grade — sem alocar a grade.

    Separada de `_grade` porque a rota da forma da tela precisa só do passo
    de cada resolução, e `_grade` aloca a imagem de referência (a tela pedia
    `fundo=1` para não alocar 1,6 GB em 1024). Número se pede a quem só faz
    conta.
~~~

## linha 368 · _grade (docstring)

~~~text
A grade do detector. Devolve `(ref, diag, passo, passo_fundo)`.

    O LADO É A DIAGONAL, e não a maior aresta: girado 45°, um volume alongado
    passa da caixa que o continha alinhado, e os cantos da anatomia seriam
    cortados na incidência oblíqua — que é justamente a que interessa.

    E ELA NÃO É CUBO. `fundo` é o número de amostras ao longo do RAIO, e o
    MIP reduz esse eixo a um número — amostrá-lo tão fino quanto o plano é
    pagar memória por um eixo que vai ser jogado fora. Ver `FUNDO_MAXIMO`.

    O EIXO DA PROFUNDIDADE É O `y` DO SimpleITK, que vira o eixo 1 do array —
    o mesmo que `projetar` reduz. Trocar a ordem aqui daria uma reformatação
    em vez da incidência, e ela pareceria uma imagem plausível.
~~~

## linha 392 · projetar (docstring)

~~~text
A projeção na incidência dada. Devolve `(array 2D, info)`.

    `modo`     `mip` (máximo) ou `minip` (mínimo)
    `laje_mm`  espessura da laje; `None` projeta o volume inteiro
    `escala`   o que `escala_de` devolveu; sem ela, é medida aqui
    `amostra`  a imagem de onde os raios leem (o recorte da caixa); a grade
               e o centro continuam saindo de `img`

    ═══ REAMOSTRAR E DEPOIS PROJETAR ═══

    O ângulo arbitrário sai de reamostrar o volume para a grade do detector e
    tirar o extremo ao longo de um eixo. A alternativa seria escrever um
    traçador de raio — mais código, mesmo resultado, e sem o interpolador
    validado do ITK por baixo.

    ═══ A LINHA 0 É A CRANIAL (26/09/2026, v8.3) ═══

    A grade do detector cresce para cima em `z`, e a linha 0 do array é a de
    MENOR `z` — a mais caudal. A tela desenha a linha 0 no topo, então toda
    projeção saía DE CABEÇA PARA BAIXO: medido na TC de pescoço do banco
    pseudonimizado, o tórax em cima e o crânio embaixo, e o mesmo nas três
    RM. Angiografia se lê com o crânio em cima.

    O plano é invertido AQUI, e `tubo` inverte o polígono do mesmo jeito —
    é a mesma grade, e inverter só na tela poria o desenho num lugar e o
    tubo no outro, espelhados em torno do meio.
~~~

## linha 428 · projetar

~~~text
 ═══ O PREENCHIMENTO É O EXTREMO DA PRÓPRIA SÉRIE (v8.3) ═══

 Era −1024 no MIP e 3071 no MinIP, os dois em HU — e o `Resample`
 devolve o TIPO DA ENTRADA. Numa RM `uint16`, −1024 não existe: ele
 voltava como 64.512, todo raio que passa fora do volume vencia o MIP, e
 a projeção saía um quadrado branco inteiro (medido: a RM de 256 px do
 banco pseudonimizado). O mínimo da série cabe no tipo dela por
 definição, e nunca vence o MIP; o máximo nunca vence o MinIP.
~~~

## linha 439 · projetar

~~~text
 VISTA, e não cópia: o volume reamostrado tem lado × fundo × lado
 voxels (400 MB numa TC de 32 bits em 512) e vai ser reduzido a um
 plano na linha seguinte. `r` vive até o fim da função.
~~~

## linha 444 · projetar

~~~text
 O EIXO 1 é a profundidade do detector — a direção do raio depois da
 rotação. Projetar noutro eixo daria uma reformatação, e não a incidência.
~~~

## linha 447 · projetar

~~~text
 A LAJE E MEDIDA NO EIXO DA PROFUNDIDADE, e ele tem passo proprio
 desde que a grade deixou de ser cubo. Usar o passo do PLANO aqui
 daria uma laje com a espessura errada por um fator -- e ela
 pareceria uma laje, so que de outra espessura.
~~~

## linha 456 · projetar

~~~text
 A cranial em cima: ver o docstring.
~~~

## linha 463 · projetar

~~~text
 O QUE SAIU, e nao so o que foi pedido: o passo no plano
 e o que decide a nitidez do vaso, e a tela mostra.
~~~

## linha 472 · tubo (docstring)

~~~text
A retroprojeção do que o médico circulou. Devolve máscara booleana.

    `poligono` é uma lista de `(coluna, linha)` na projeção de `lado`×`lado`.

    ═══ O CAMINHO CURTO, E POR QUE ELE É O CERTO ═══

    A força bruta seria rotacionar as coordenadas físicas de todo voxel e
    testar a pertinência — medido: 11 s num volume de 84 milhões de voxels.

    O caminho curto faz o inverso: monta a máscara do polígono **no
    referencial do detector**, extrudada ao longo do raio, e a traz de volta
    com uma reamostragem única. É a MESMA operação da projeção, que custa
    menos de um segundo — e usa o mesmo interpolador, então o tubo cai
    exatamente onde a projeção o mostrou.

    VIZINHO MAIS PRÓXIMO na volta: o tubo é uma máscara, e interpolar máscara
    produz meia pertinência, que não quer dizer nada.

    ═══ E O POLÍGONO ESTÁ NA PROJEÇÃO QUE A TELA MOSTRA (v8.3) ═══

    Linha 0 é a CRANIAL, como em `projetar`. A grade do detector cresce para
    cima, então a máscara 2D é invertida antes de voltar para o volume —
    inverter só a projeção espelharia o tubo em torno do meio da incidência.

    ═══ E O RAIO NÃO PRECISA DE AMOSTRAS (v8.3) ═══

    O tubo é o MESMO plano em toda profundidade, e o vizinho mais próximo
    não interpola entre amostras. Extrudá-lo em `fundo` camadas montava um
    volume de lado × 384 × lado (100 MB em 512) para responder a mesma
    pergunta que DUAS camadas respondem. As duas ficam a um `diag` de
    distância, centradas no volume: todo ponto do paciente está a menos de
    meia diagonal do centro, e o ITK aceita meio voxel além da borda — então
    nenhum voxel cai fora. `fundo` fica na assinatura por compatibilidade e
    não muda nada.
~~~

## linha 514 · tubo

~~~text
 a máscara 2D do polígono, na grade do detector — com a cranial em
 cima, como a projeção, e invertida para a grade (ver o docstring)
~~~

## linha 517 · tubo

~~~text
 Duas camadas no raio, e nao `fundo`: ver o docstring.
~~~

## linha 524 · tubo

~~~text
 de volta para a grade do VOLUME — é onde o tubo precisa estar para ser
 desenhado nos três planos
~~~

## linha 527 · tubo

~~~text
 `view`, e não `astype`: o vizinho mais próximo só devolve 0 e 1, e o
 `uint8` com 0/1 é byte a byte um booleano. A cópia custava o tubo
 inteiro de novo (155 MB numa TC de pescoço de 591 cortes).
~~~

## linha 534 · _mascara_poligono (docstring)

~~~text
Máscara do polígono, por regra do número de voltas. Sem dependência.

    O `cv2` faria isto, e o `skimage` também. Nenhum dos dois entra: são 25
    linhas, e o rasterizador do `rt_utils` já mostrou o que custa depender de
    `cv::fillPoly` para uma forma degenerada.

    ═══ SÓ DENTRO DA CAIXA DO POLÍGONO (v8.3) ═══

    Cada aresta varria a grade `lado × lado` inteira: 0,46 s para 24
    vértices em 512 (medido numa RM de crânio), quase tudo sobre pixels que
    nenhum polígono alcança. Fora da caixa o teste de cruzamento é falso por
    construção, então varrer só a caixa dá a MESMA máscara — a bateria
    compara as duas.
~~~

## linha 555 · _mascara_poligono

~~~text
 A caixa dos CENTROS de pixel que o polígono pode conter: o centro de
 (l, c) é (c + 0,5, l + 0,5).
~~~

## linha 573 · _mascara_poligono

~~~text
 cruza a horizontal deste pixel?
~~~

## linha 582 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 OS TRÊS PLANOS: A SÉRIE NA ORIENTAÇÃO DO PACIENTE (26/09/2026, v8.3)
 ═══════════════════════════════════════════════════════════════════════════

 A tela cortava o ARRAY da série — `v[i]`, `v[:, i, :]`, `v[:, :, i]` — e
 chamava o primeiro de axial. Isso só é verdade numa série adquirida em
 axial. As três RM de crânio pós-gadolínio do banco pseudonimizado são
 SAGITAIS (orientação PIR): o quadro «axial» mostrava um sagital, o
 «coronal» um axial deitado e achatado pela metade, e o «sagital» um coronal.
 E mesmo na TC axial o coronal e o sagital saíam de cabeça para baixo,
 porque a linha 0 do array é o corte mais caudal.

 O conserto é uma VISTA do array na ordem do paciente — (S, P, L), a mesma
 convenção do LPS —, feita com `transpose` e inversão de eixo: nada é
 copiado nem reamostrado. `DICOMOrient` faria o mesmo copiando o volume, e
 levou 1,8 s numa RM de 44 milhões de voxels. Série oblíqua (a RM P12 do
 banco está a 17°) vai para a orientação MAIS PRÓXIMA, que é o que um
 visualizador de TPS mostra.
~~~

## linha 601 · eixos_lps (docstring)

~~~text
`(perm, inverter, mm_zyx)`: como levar o array da série à ordem S-P-L.

    `perm[a]` é o eixo do array que vira o eixo `a` da vista (0 = crânio-
    caudal, 1 = antero-posterior, 2 = direita-esquerda); `inverter[a]` diz se
    ele corre ao contrário. `mm_zyx` é o espaçamento na ordem da vista.

    A escolha é a permutação de maior alinhamento com os eixos do paciente —
    as seis, e não um `argmax` por coluna: numa série a 45° dois eixos do
    índice empatariam no mesmo eixo do paciente, e o `argmax` devolveria uma
    «permutação» com um eixo repetido.
~~~

## linha 614 · eixos_lps

~~~text
 coluna n da matriz = direção física do índice n (0 = i, 1 = j, 2 = k)
~~~

## linha 618 · eixos_lps

~~~text
 p[f] = índice (i, j, k) que corre ao longo do eixo físico f (x, y, z)
~~~

## linha 624 · eixos_lps

~~~text
 vista: 0 = z, 1 = y, 2 = x
 eixo físico: z=2, y=1, x=0
 índice sitk (i=0, j=1, k=2)
 eixo do array numpy (k, j, i)
~~~

## linha 634 · para_lps (docstring)

~~~text
A VISTA do array `a` (na grade da série) na ordem S-P-L. Sem cópia.
~~~

## linha 644 · corte (docstring)

~~~text
O corte `indice` no plano `eixo`, NA ORIENTAÇÃO DA TELA.

    `v` está na ordem S-P-L (`para_lps`): o eixo 0 cresce para o crânio, o 1
    para trás e o 2 para a esquerda do paciente.

      eixo 0  axial    anterior em cima, direita do paciente à esquerda
      eixo 1  coronal  crânio em cima, direita do paciente à esquerda
      eixo 2  sagital  crânio em cima, anterior à esquerda

    É a convenção radiológica. A inversão do crânio mora AQUI, e as linhas
    do tubo passam por esta mesma função — duas contas de orientação, uma
    para a imagem e outra para a linha, divergiriam, e a linha fina cairia
    espelhada sobre a anatomia. Aceita também o tubo em bits (`Compacto`).
~~~

## linha 669 · mm_do_corte (docstring)

~~~text
`(mm por linha, mm por coluna)` do corte `eixo` da vista S-P-L.
~~~

## linha 674 · (módulo)

~~~text
 ═══ PIXEL QUADRADO NA TELA ═══

 O palco mostra o corte num quadro quadrado com `object-fit: contain`, que
 preserva a proporção em PIXELS. Numa RM com 0,5 mm no plano e 1 mm entre
 cortes, o corte ortogonal ao da aquisição saía achatado pela metade — e a
 linha fina, desenhada na mesma grade, achatada junto. Anatomia deformada
 não parece defeito de tela: parece a anatomia.

 O corte é ampliado por vizinho mais próximo até o pixel ter o mesmo
 tamanho em milímetros nos dois sentidos, e as linhas são multiplicadas
 pelos MESMOS fatores (`grade_da_tela` é a fonte dos dois). O teto evita
 que uma TC de 5 mm vire uma imagem de milhares de linhas.

 (28/09/2026) AS TRÊS MUDARAM DE CASA, e não de conta: `TETO_DA_TELA`,
 `grade_da_tela` e `para_a_tela` moram em `radai_recon3d`, ao lado de
 `para_png`, porque as Reconstruções 3D passaram a precisar da MESMA
 regra — o coronal e o sagital delas saíam achatados desde a v8.2. Os
 nomes continuam aqui (esta tela e `tools/test_nidus.py` os usam), e
 `tools/test_recon3d.py` confere que são os mesmos objetos: uma cópia
 divergiria, e o mesmo corte sairia com duas proporções em duas telas.
 noqa: E402,F401
~~~

## linha 699 · escalar (docstring)

~~~text
Os segmentos de `contorno_do_tubo` na grade de `para_a_tela`.
~~~

## linha 705 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 O TUBO GUARDADO EM BITS (26/09/2026, v8.3)
 ═══════════════════════════════════════════════════════════════════════════

 A tela guarda os tubos de cada incidência para desenhar as linhas a cada
 corte rolado. Um booleano por voxel é um BYTE por voxel: 155 MB por tubo
 numa TC de pescoço de 591 cortes, e o teto é de doze incidências — 1,9 GB
 por sessão, dentro do mesmo processo que segmenta à noite. (O comentário da
 tela dizia «16,8 MB a 256»; isso era o `lado³`, e o tubo tem o tamanho do
 VOLUME, não da projeção.)

 `np.packbits` guarda oito voxels por byte: 19 MB no mesmo tubo. O corte
 desembrulha só o plano pedido, e a interseção é um `&` sobre os bytes —
 exata, porque o E de bits empacotados é o empacotamento do E.
~~~

## linha 720 · Compacto (docstring)

~~~text
Um tubo (máscara booleana na ordem S-P-L) guardado em bits.
~~~

## linha 729 · Compacto.fatia (docstring)

~~~text
O plano `indice` do eixo `eixo`, na ordem do array (sem inverter).
~~~

## linha 746 · compactar (docstring)

~~~text
O tubo em bits. Aceita vista (a de `para_lps`): ela é copiada uma vez.
~~~

## linha 753 · intersecao (docstring)

~~~text
Onde TODOS os tubos se cruzam. Um, dois, ou vinte.

    ═══ POR QUE N, E NÃO DOIS ═══

    Cada incidência de gantry vê o ninho por um ângulo, e o polígono que
    o médico circula ali vira um tubo — tudo o que poderia estar naquela
    direção. Com **duas** incidências a interseção é uma caixa larga;
    com **seis** ela fecha em torno do que todas viram.

    É essa a pergunta da simulação: *onde a arteriografia enxerga o
    ninho?* — e a resposta melhora com cada incidência acrescentada.

    Aceita uma lista ou os tubos soltos. Sem nenhum, devolve `None`:
    interseção de conjunto vazio é o espaço inteiro, e devolver o
    espaço inteiro aqui seria dizer «o ninho está em toda parte».

    **NÃO devolve volume.** Ver `SEM_VOLUME`: um número em cm³ ao lado
    de uma forma é um volume de alvo com passos a mais. E quanto mais
    incidências, mais a interseção parece uma estrutura — o que torna
    esta regra mais necessária, e não menos.
~~~

## linha 780 · intersecao

~~~text
 EM BITS, O E É SOBRE OS BYTES — e o resultado continua em bits. Os
 bits de enchimento do último byte são zero nos dois, e continuam zero.
~~~

## linha 794 · contorno_do_tubo (docstring)

~~~text
As LINHAS FINAS do tubo num corte. Devolve segmentos, não região.

    ═══ POR QUE LINHA, E NUNCA REGIÃO PREENCHIDA ═══

    Região fechada e preenchida num corte axial tem uma leitura só neste
    ofício: é um contorno. Alguém tira print, e o print circula.

    A aparência é o que vaza. O tubo é uma construção de visualização, e ele
    tem de **parecer** uma construção.

    Devolve pares `((c0, l0), (c1, l1))` das arestas de fronteira, em índice
    de coluna e linha do corte pedido — NA ORIENTAÇÃO DA TELA: o plano sai
    de `corte`, a mesma função que a rota da imagem usa (v8.3). A máscara é
    a vista S-P-L do tubo (`para_lps`), densa ou em bits (`Compacto`).
~~~

## linha 815 · contorno_do_tubo

~~~text
 as arestas onde a pertinência muda — que é a fronteira, e nada além
~~~

## linha 829 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 A SÉRIE ABERTA, NUM OBJETO SÓ (26/09/2026, v8.3)
 ═══════════════════════════════════════════════════════════════════════════

 O que a tela precisa de uma série — a imagem, a vista S-P-L, a escala de
 intensidade e o passo de cada resolução — sai daqui, uma vez. As rotas liam
 a série do DISCO a cada pedido: cada corte rolado relia o volume inteiro
 (12,4 s na TC de pescoço de 591 cortes, 1,7 a 3,0 s nas RM), e três planos
 mais a projeção eram quatro leituras por gesto.
~~~

## linha 839 · Serie (docstring)

~~~text
A série aberta. `img` é a do disco; `v` é a vista S-P-L do array.
~~~

## linha 846 · Serie.__init__

~~~text
 VISTA do buffer da `img`: vale enquanto `self.img` viver, e ela
 vive junto com este objeto.
~~~

## linha 855 · Serie.img_na_caixa (docstring)

~~~text
Só os voxels da caixa, no lugar físico deles (`RegionOfInterest`).

        Vai para `projetar(..., amostra=)`: a grade do detector continua
        saindo da série inteira, e o raio que passa fora do recorte recebe o
        extremo que nunca vence o modo. Guarda UMA caixa; `modo` não muda o
        recorte.
~~~

## linha 873 · Serie.img_na_caixa (fica no código)

~~~text
 GUARDA: eixo da vista -> eixo do array (`perm`) -> dimensão do sitk (2 - eixo do array).
~~~

## linha 890 · Serie.passos (docstring)

~~~text
O passo no plano da projeção, em mm, para cada `lado`.
~~~

## linha 895 · Serie.tubo (docstring)

~~~text
O tubo desta incidência, na vista S-P-L e em bits.
~~~

## linha 902 · abrir (docstring)

~~~text
A `Serie` de uma imagem lida (`engine.load_sitk`).
~~~
