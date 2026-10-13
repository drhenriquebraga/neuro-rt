# app/radai_nidus_screen.py

Comentários e docstrings do código como estava antes da limpeza, na ordem do arquivo. «fica no código» marca o que a limpeza manteve (`GUARDA:`, licença, codificação).

## linha 2 · (módulo) (docstring)

~~~text
radai_nidus_screen.py — a tela da projeção vascular.

═══ LADO A LADO, E É ISSO QUE A PEÇA ENSINA ═══

(Superado no leiaute: hoje a projeção fica em cima, com os comandos ao
lado, e o MPR embaixo. O porquê abaixo é o da tela anterior.)

À esquerda a **projeção** — a angio, na incidência escolhida. À direita a
**TC**, nos três planos, com as **linhas finas** do que foi retroprojetado.

A pergunta que ninguém consegue responder com uma ferramenta gratuita é *como
o mesmo nidus muda de forma entre duas incidências* — e ela só se responde com
as duas coisas na tela ao mesmo tempo. Uma acima da outra transformaria a
comparação em memória.

═══ O DESENHO É SVG, E NÃO CANVAS ═══

Três razões, e a terceira é a que decide:

  1. linha fina em SVG é fina de verdade em qualquer zoom;
  2. o desenho fica acessível — cada vértice é um elemento, e o teclado
     alcança;
  3. **`<canvas>` sobre imagem médica é a coisa que a regra 6 proíbe fazer.**
     Aqui o desenho é do médico e não da máquina, mas a distinção depende de
     quem lê o código. Com SVG não há o que distinguir.

═══ O QUE ESTA TELA NÃO FAZ ═══

Não detecta, não segmenta, não exporta — e **não imprime volume**. Ver
`radai_nidus.SEM_VOLUME`: um número em cm³ ao lado de uma forma é um volume de
alvo com passos a mais.
~~~

## linha 41 · (módulo)

~~~text
 ═══ OS LADOS OFERECIDOS, NUM LUGAR SÓ ═══

 A lista estava escrita três vezes — na rota da projeção, na dos tubos e nos
 botões da barra —, e o teto de cada rota é o que impede `lado=8192` de
 alocar a estação inteira. Três cópias de um teto é o teto que sobe numa e
 fica para trás nas outras.

 `LADO_ALTA` vem da lib porque ela é o maior valor MEDIDO (1,47 s, 1,6 GB);
 repetir o número aqui o desligaria da medida.
~~~

## linha 52 · (módulo)

~~~text
 ═══ AS MODALIDADES QUE O SELETOR LISTA (26/09/2026, v8.3) ═══

 Era só a TC — o padrão do `radai_batch.varrer` —, e o módulo foi pedido
 para RM de crânio pós-gadolínio também: a malformação se desenha em
 qualquer série com o vaso contrastado. A escala de intensidade de cada uma
 é decidida pela modalidade (`radai_nidus.escala_de`).
~~~

## linha 125 · (módulo) (web)

~~~text
/* ═══ LADO A LADO ═══
A projecao e a TC na mesma altura. Uma acima da outra transformaria a
comparacao em memoria -- e a comparacao E o produto desta tela.
(Superado: o leiaute de hoje e a projecao com os comandos ao lado, e o
MPR embaixo, em `.nd-trabalho` e `.nd-mpr`.) */
~~~

## linha 148 · (módulo) (web)

~~~text
/* FUNDO PRETO FIXO, e nao a ficha do painel: imagem medica em cinza sobre
painel claro muda de contraste aparente, e o operador compararia duas
incidencias pela cor do tema. */
~~~

## linha 161 · (módulo) (web)

~~~text
/* AS LINHAS SAO FINAS, E NUNCA REGIAO PREENCHIDA.
Regiao fechada e preenchida num corte axial tem uma leitura so neste
oficio: e um contorno. Alguem tira print, e o print circula. */
/* ═══ SEIS CORES, UMA POR INCIDÊNCIA ═══
Eram duas -- `a` e `b` --, que é o que se escreve quando são duas.
O ciclo de seis fecha porque acima disso a cor deixa de identificar:
quem olha não distingue a sétima da primeira, e a lista ao lado passa
a ser o único jeito de saber qual é qual -- que é o que ela faz.

`non-scaling-stroke` em todas: linha fina tem de ser fina em qualquer
zoom, e é por isso que o desenho é SVG e não canvas. */
~~~

## linha 180 · (módulo) (web)

~~~text
/* A SOMA É MAIS GROSSA E VEM POR CIMA. Ela é a resposta da simulação:
onde TODAS as incidências se encontram. Continua sendo LINHA -- região
preenchida num corte axial tem uma leitura só neste ofício. */
~~~

## linha 186 · (módulo) (web)

~~~text
/* a lista acumulada, ao lado */
~~~

## linha 226 · (módulo) (web)

~~~text
/* ═══ AS DUAS INCIDENCIAS GUARDADAS ═══ */
~~~

## linha 237 · (módulo) (web)

~~~text
/* A FRONTEIRA, VISIVEL. Nao e letra miuda: e o que separa uma construcao de
visualizacao de um volume de tratamento. */
~~~

## linha 248 · (módulo) (web)

~~~text
// ═══ `guardadas` NASCE VAZIA, E ISSO MATAVA A TELA ═══
//
// Era `[null,null]` — os dois lugares fixos da versão de duas incidências.
// Desde que guardar passou a ACRESCENTAR, os dois nulos continuaram lá, e
// `ndPintarGuardadas` (chamada no `DOMContentLoaded`) via `length === 2`,
// entrava no laço e lia `g.lao` de um `null`.
//
// > O `TypeError` matava o resto do `DOMContentLoaded`, e a linha seguinte
// > era `ndListar('')`. **A tela abria com «carregando…» para sempre**, sem
// > erro na tela — o console do navegador é o único lugar onde ele aparece,
// > e ninguém o abre.
//
// É a mesma família do `/lote` de 26/08/2026, onde um `TypeError` num bloco
// que tinha saído da tela matava a última linha do `<script>`.
//
// ═══ E `lado` NASCE 512, que é o botão aceso no HTML ═══
//
// Eram 256 aqui e `class="nd-bt on"` no botão de 512. A tela dizia «normal»
// e pedia «rápida» — e o `nd_passo` que ela agora mostra diria o passo de
// uma resolução que não é a que está valendo.
~~~

## linha 277 · (módulo) (web)

~~~text
// ═══ O AFINAMENTO DO TRAÇO, E POR QUE ELE NÃO É ENFEITE ═══
//
// `radai_nidus._mascara_poligono` varre a grade `lado × lado` UMA VEZ POR
// ARESTA. Medido nesta máquina, num polígono regular:
//
//     lado  512 ·  24 vértices 0,20 s ·  400 vértices  1,47 s
//     lado 1024 ·  24 vértices 0,41 s ·  400 vértices  8,13 s
//                                     ·  900 vértices 16,57 s
//
// E é POR INCIDÊNCIA. O arrasto do mouse produz um ponto por evento —
// dezenas por segundo —, então cinco traços à mão livre em alta resolução
// passariam de um minuto dentro de `/api/nidus/tubos`, com a tela dizendo
// «retroprojetando…» e mais nada.
//
// `ND_EPS` está em UNIDADES DA PROJEÇÃO, que são pixels do detector: meio
// pixel é abaixo do que o rasterizador consegue representar, porque ele
// amostra o centro de cada pixel. O teto é o que fecha a conta de custo para
// o traço longo, e ele vale mesmo quando o tremor da mão sobrevive ao `eps`.
~~~

## linha 300 · (módulo) (web)

~~~text
// ═══ A MENSAGEM PASSA PELO TRADUTOR (27/09/2026, v8.3) ═══
//
// Visto na prova da v8.3, com o navegador em inglês: a tela inteira trocou de
// idioma e a linha de estado — a que diz o que fazer em seguida — ficou em
// português. Há DUAS causas, e só a segunda é desta função: quase nenhuma
// destas frases tem chave ainda (a lista foi para a trilha de tradução); e
// `textContent` deixava no elemento a marca `data-radai-t` do tradutor, então
// nem a frase que tivesse chave seria alcançada depois da primeira troca.
// `uiTexto` (`radai_ui`) escreve e tira a marca. Sem ele (o palco da
// bateria), o texto vai como antes.
~~~

## linha 314 · (módulo) (web)

~~~text
// ═══ A LISTA VEM DA MESMA FUNCAO QUE AS OUTRAS TELAS USAM ═══
//
// Uma segunda implementacao de "quais series existem" divergiria da primeira,
// e as telas passariam a discordar sobre o que ha no disco.
~~~

## linha 329 · (módulo) (web)

~~~text
// SO O QUE IDENTIFICA A SERIE. Nunca o caminho, que carrega nome de
// paciente com frequencia -- a imagem viaja por bilhete opaco.
// A MODALIDADE NA FRENTE (v8.3): a lista passou a trazer TC e RM, e numa
// pasta com as duas a descrição sozinha não diz qual é qual.
// (27/09/2026, v8.3) O DESCRITOR E UM MOLDE, `%s · %s cortes · %s mm`,
// e nao uma soma: «cortes» ficava em portugues nos onze idiomas (medido
// na tela renderizada). O tradutor casa o molde no texto da `<option>` e
// devolve os valores como vieram. O mesmo molde das Reconstrucoes 3D.
~~~

## linha 352 · (módulo) (web)

~~~text
// LISTA, e nao dois lugares. Ver `ndGuardar`.
//
// E A SESSAO ZERA JUNTO. Ela nao zerava: a sessao vive no servidor e e de
// OUTRA serie, entao `ndPintarPlanos` pedia as linhas dela e as desenhava
// sobre os cortes da serie recem-aberta.
//
// > Linha fina sobre a anatomia errada nao parece defeito -- parece achado.
~~~

## linha 363 · (módulo) (web, fica no código)

~~~text
// GUARDA: a imagem da série anterior sai já; sob o carregamento ela pareceria a nova.
~~~

## linha 367 · (módulo) (web)

~~~text
// As linhas da serie anterior saem AGORA, e nao quando a nova responder:
// entre o clique e a resposta ha segundos em que os cortes ja sao os novos.
~~~

## linha 371 · (módulo) (web)

~~~text
// ═══ A MENSAGEM SO VEM DEPOIS DA RESPOSTA ═══
//
// Isto jogava fora `d.erro` (`ND.forma = d.forma || null`, `.catch`
// vazio) e escrevia «série aberta» NA LINHA SEGUINTE, antes mesmo de a
// resposta chegar. Com gantry inclinado o motor recusa a leitura, as
// rotas de imagem devolvem 404 vazio de propósito (para não vazar
// caminho de paciente numa tag <img>), o `onerror` tira o `src`, e a
// tela ficava com os quadros vazios AFIRMANDO que a série abriu.
//
// > Silêncio já seria ruim. Afirmar o contrário é pior: manda a pessoa
// > procurar defeito na tela, e não na série.
//
// O único lugar onde o motivo existe é esta rota, então é dela que a
// mensagem sai.
~~~

## linha 398 · (módulo) (web)

~~~text
// O PASSO DO DETECTOR VEM DAQUI, e nao de uma conta na tela: quem sabe a
// diagonal do volume e `radai_nidus._grade`. Ver `ndPasso`.
~~~

## linha 423 · (módulo) (web, fica no código)

~~~text
// GUARDA: o carregamento espera 250 ms para não piscar a cada grau girado.
~~~

## linha 435 · (módulo) (web)

~~~text
// ═══ A PROJECAO ═══
~~~

## linha 453 · (módulo) (web, fica no código)

~~~text
// GUARDA: os eixos vêm de `radai_nidus.eixos_da_incidencia`, a mesma rotação da projeção.
~~~

## linha 484 · (módulo) (web, fica no código)

~~~text
// GUARDA: o desenho e a imagem estão no MESMO contêiner escalado; `ndPonto` lê o retângulo já escalado.
~~~

## linha 546 · (módulo) (web, fica no código)

~~~text
// GUARDA: `ND.caixa` = [s0,s1,p0,p1,l0,l1] em fração da vista S-P-L, a ordem de `radai_nidus.caixa_de_texto`.
~~~

## linha 635 · (módulo) (web)

~~~text
// A RESOLUCAO E DA PROJECAO, e o desenho acompanha: `ND.lado` tambem
// converte o clique do mouse em coluna/linha da projecao (ver `ndClique`), e
// e o mesmo numero que vai para a retroprojecao do tubo. Trocar um sem o
// outro poria o desenho num lugar e o tubo noutro.
~~~

## linha 647 · (módulo) (web)

~~~text
// O DESENHO EM CURSO PERDE O SENTIDO: os vertices estao em coordenadas da
// grade ANTIGA -- `ndClique` converte o pixel do mouse dividindo por
// `ND.lado`. Retroprojetar um poligono dessa grade na grade nova daria um
// tubo deslocado, plausivel e errado.
~~~

## linha 663 · (módulo) (web)

~~~text
// A MARCA DO DESENHO SE PERDE AO GIRAR, e tem de se perder: o poligono e
// coordenada do DETECTOR daquela incidencia. Mante-lo na tela depois de
// girar mostraria o desenho no lugar errado, que e pior que nao mostrar.
~~~

## linha 673 · (módulo) (web)

~~~text
// ═══ O DESENHO: SVG, e nao canvas ═══
//
// `<canvas>` sobre imagem medica e a coisa que a regra 6 proibe fazer. Aqui o
// desenho e do medico e nao da maquina -- mas a distincao depende de quem le o
// codigo. Com SVG nao ha o que distinguir.
//
// ═══ A GRADE DO DESENHO E `ND.lado` ═══
//
// `ndPonto` converte o pixel do mouse em unidade da PROJECAO, dividindo pelo
// tamanho do palco e multiplicando por `ND.lado`. O `<svg>` nascia com
// `viewBox="0 0 256 256"` fixo: em «normal» (512) um vertice no meio do palco
// vira 256 num quadro de 256, e o desenho aparece no CANTO, com o dobro do
// tamanho e metade fora do quadro.
//
// > **O tubo sairia certo e o desenho apareceria errado** -- que e a forma
// > que faz duvidar da retroprojecao em vez do quadro.
~~~

## linha 694 · (módulo) (web)

~~~text
// ═══ DUAS FERRAMENTAS, E UM POLIGONO SO ═══
//
// «desenhar com um lápis» — Dr. Henrique, 14/09/2026. O lapis entrou; o
// desenho por cliques FICOU, e ele nao e redundante: um vertice por clique e
// o desenho de precisao que o arrasto nao faz, e vaso de MAV e fino.
//
// As duas alimentam `ND.pontos`, que e o mesmo poligono que vai para a
// retroprojecao. Duas listas divergiriam, e a divergencia apareceria como
// tubo no lugar errado.
~~~

## linha 730 · (módulo) (web)

~~~text
// A CONVERSAO E UMA SO, e os dois modos passam por ela: o clique e o arrasto
// desenhando em grades diferentes poriam metade do poligono noutro lugar.
~~~

## linha 743 · (módulo) (web)

~~~text
// ═══ O LAPIS ═══
~~~

## linha 746 · (módulo) (web)

~~~text
// SEM A SELECAO DE TEXTO: arrastar sobre a imagem seleciona o que estiver
// por baixo, e o traco sai com meia tela azul em volta.
~~~

## linha 756 · (módulo) (web)

~~~text
// O FILTRO DE CAPTURA: abaixo de meio pixel do detector o ponto novo nao
// acrescenta forma nenhuma -- ele so acrescenta uma aresta ao rasterizador.
~~~

## linha 777 · (módulo) (web)

~~~text
// ═══ AFINAR: Ramer–Douglas–Peucker, com teto ═══
//
// Ele guarda o vertice cuja distancia a corda passa de `eps`, e joga fora o
// resto -- a forma fica, o tremor sai. A pilha explicita, e nao recursao: um
// traco longo com tremor da profundidade proporcional ao numero de pontos.
~~~

## linha 807 · (módulo) (web)

~~~text
// O TETO E DE CUSTO, e `eps` sozinho nao o garante: mao tremida sobrevive a
// meio pixel, e um traco longo continua chegando com centenas de vertices.
// Por isso o `eps` cresce ate caber -- e nunca o contrario, porque o afinado
// com `eps` pequeno e o que preserva a forma.
~~~

## linha 820 · (módulo) (web)

~~~text
// O DUPLO CLIQUE FECHA E GUARDA, como sempre fez. A trava dos tres pontos
// mora em `ndGuardar`: duas travas divergem, e a que fica para tras e a que
// ninguem rele.
~~~

## linha 828 · (módulo) (web)

~~~text
// O RAIO ACOMPANHA A GRADE: `r="2"` era meio palco em 256 e um ponto
// invisivel em 1024.
~~~

## linha 834 · (módulo) (web)

~~~text
// ABERTO ENQUANTO SE DESENHA, e fechado quando se termina. No lapis quem
// diz «ainda estou desenhando» e o arrasto, e nao o modo: o traco solto ja
// e uma area, e mostra-lo aberto faria duvidar de que ele fechou.
~~~

## linha 842 · (módulo) (web)

~~~text
// ═══ O PASSO DO DETECTOR, NA TELA ═══
//
// O `<span id="nd_passo">` existia no HTML e o JavaScript nunca o preenchia:
// ele mostrava um travessao para sempre. Preencher, e nao remover, porque a
// barra oferece tres resolucoes e a diferenca entre elas E o passo do
// detector -- sem o numero, «alta» e uma promessa sem unidade.
//
// E porque o caso que importa ficava invisivel: pedir mais detalhe do que a
// serie tem devolve INTERPOLACAO com cara de vaso, e num modulo cujo limite
// e «isto nao vira numero» inventar detalhe e o pior tipo de erro. Quem
// responde qual e o maior lado util e `radai_nidus.lado_para_o_exame`.
~~~

## linha 857 · (módulo) (web)

~~~text
// «da projeção», e não «do detector», que é como o resto do módulo chama
// esta grade: `teste_nao_detecta_nada` recusa a raiz `detect` no que a tela
// DIZ, e ela não sabe separar o painel de raios-X do verbo. A guarda é
// grossa de propósito e fica como está — trocar uma palavra da tela custa
// menos que ensinar exceção a uma guarda da regra 6. Em comentário, que a
// guarda não lê, o nome certo continua sendo detector.
//
// ═══ UM MOLDE INTEIRO, E POR `uiTexto` (27/09/2026, v8.3) ═══
//
// Era o numero somado a frase, e mais um pedaco somado a ela: nenhuma das
// duas formas e chave, e o `span.sub` (bloco do tradutor) ficava em
// portugues nos onze idiomas -- medido na tela renderizada. E era escrito
// por `textContent`: o `span` traduzido uma vez ficava marcado, e a troca
// de resolucao escrevia portugues por cima da marca. Agora cada forma e uma
// frase inteira com `%s` (o molde de `radai_languages`) e sai por `uiTexto`.
~~~

## linha 879 · (módulo) (web)

~~~text
// ═══ A ESCALA DA SÉRIE, NA TELA (27/09/2026, v8.3) ═══
//
// A rota da forma já devolvia `hu` desde a v8.3, com o comentário dizendo
// que «a tela diz qual» — e a tela não lia o campo. Numa RM os botões de
// janela têm os mesmos nomes da TC e significam outra coisa (percentis do
// próprio sinal, `radai_nidus.JANELAS_RELATIVAS`), e «angio» sem aviso seria
// lido como a janela em HU. Sem `hu` na resposta (servidor antigo), vale HU,
// que é o que ele fazia.
~~~

## linha 895 · (módulo) (web)

~~~text
// ═══ AS DUAS INCIDENCIAS ═══
//
// Dois tubos de angulacoes diferentes se cruzam, e a intersecao e a
// estimativa classica. Uma so nao estima nada -- e a tela nao deixa pedir a
// intersecao antes de haver duas.
// ═══ CADA GUARDAR ACRESCENTA ═══
//
// Eram dois lugares fixos, A e B, e o terceiro clique sobrescrevia o
// B. A simulacao melhora com cada angulo: com duas incidencias a
// intersecao e uma caixa larga, com seis ela fecha em torno do que
// todas viram.
//
// O teto vem do servidor (`d.teto`) e a lista o mostra -- teto que
// trunca em silencio faz a intersecao mudar sem motivo aparente.
// ═══ E A MENSAGEM SAI DA LISTA ═══
//
// Ela era `'incidência '+(qual?'B':'A')+' guardada'` — `qual` era a variável
// que dizia se o lugar A ou o B estava ocupado, e ela morreu junto com os
// dois lugares fixos. **Nenhum `var qual` sobrou em lugar nenhum do
// arquivo**, então cada clique em guardar levantava `ReferenceError` — na
// linha ANTERIOR ao `ndCalcular()`.
//
// > A incidência entrava na lista, a lista pintava, e **a retroprojeção não
// > acontecia**. Ela só voltava a acontecer ao REMOVER uma incidência, que é
// > o outro caminho para `ndCalcular` — o que faz o defeito parecer o
// > contrário do que é.
//
// A contagem agora vem de onde a verdade mora: o tamanho da lista. `qual`
// tinha de ser mantida em dia por fora dela, e foi assim que ela ficou para
// trás quando os dois lugares viraram N.
~~~

## linha 930 · (módulo) (web)

~~~text
// GUARDAR FECHA O DESENHO, e num lugar so: a tela tem duas entradas para
// ca -- o duplo clique e o botao Guardar --, e sair do modo em cada uma
// deixaria a que ficasse para tras com o palco em modo de desenho.
~~~

## linha 938 · (módulo) (web)

~~~text
// O DESENHO PASSA PARA A LISTA. Mante-lo na tela faria o clique seguinte em
// Guardar acrescentar a MESMA incidencia de novo, com o mesmo angulo -- e a
// lista mostraria duas linhas identicas, que e indistinguivel de defeito.
~~~

## linha 954 · (módulo) (web)

~~~text
// TIRAR UMA. Guardar a incidencia errada acontece -- gantry no angulo
// errado, contorno pela metade -- e sem isto a saida seria limpar tudo
// e remarcar as outras cinco.
~~~

## linha 964 · (módulo) (web)

~~~text
// ═══ A LISTA ACUMULADA, AO LADO ═══
//
// Uma linha por incidencia, com o angulo de gantry -- que e por ele
// que a pessoa reconhece a linha fina no MPR -- e um x para tirar.
// A cor do chip e a mesma da linha daquela incidencia.
~~~

## linha 998 · (módulo) (web)

~~~text
// ═══ O CALCULO ═══
~~~

## linha 1010 · (módulo) (web)

~~~text
// O TEXTO CONTA, e diz o que falta. «Uma incidência» sozinha nao
// cruza nada, e a tela precisa dizer isso sem parecer erro.
~~~

## linha 1025 · (módulo) (web)

~~~text
// ═══ OS TRES PLANOS, COM AS LINHAS FINAS ═══
~~~

## linha 1050 · (módulo) (web)

~~~text
// UMA COR POR INCIDENCIA, e a intersecao por cima. A ordem importa:
// o servidor manda a soma por ultimo, e SVG desenha na ordem.
~~~

## linha 1063 · (módulo) (web)

~~~text
// ═══ os controles ═══
~~~

## linha 1112 · (módulo) (web)

~~~text
// O LAPIS. `mouseleave` fecha junto com `mouseup` porque soltar o botao
// fora do palco nao chega como `mouseup` aqui -- e o traco ficaria eterno,
// capturando o movimento do mouse pela tela inteira.
~~~

## linha 1180 · _incidencias (docstring)

~~~text
Os botões de incidência, a partir da tabela do módulo.

    A TABELA É A FONTE. Escrevê-los à mão aqui seria a segunda cópia — e a
    segunda cópia é a que envelhece, porque quem acrescenta uma incidência
    mexe na primeira.
~~~

## linha 1396 · _series_da_demo (docstring)

~~~text
As séries da demo instalada para o Nidus RT, no formato da lista.
~~~

## linha 1416 · _telas_do_mpr (docstring)

~~~text
`{eixo: [linhas, colunas]}` de cada corte como a tela o recebe.
~~~

## linha 1428 · _modalidade (docstring)

~~~text
A modalidade da série, lida de UM arquivo dela. `""` se não achar.

    Só a tag `Modality` (e o UID, para achar o arquivo certo numa pasta com
    duas séries): o cabeçalho de paciente nunca é lido aqui. Ela decide a
    escala de intensidade — HU na TC, relativa ao sinal na RM
    (`radai_nidus.escala_de`).
~~~

## linha 1459 · (módulo)

~~~text
 ═══ A SÉRIE ABERTA FICA NA MEMÓRIA (26/09/2026, v8.3) ═══

 Cada rota lia a série do disco: `/api/nidus/corte`, chamada a cada corte
 rolado em cada um dos três planos, relia o volume inteiro. Medido no banco
 pseudonimizado: 12,4 s por leitura na TC de pescoço de 591 cortes, 1,7 a
 3,0 s nas RM de crânio. Rolar um corte custava uma leitura de série.

 Uma série por vez, como nas Reconstruções 3D: a anterior sai ANTES de a
 nova ser lida, senão as duas ficariam na memória no instante da troca. E
 ela é SOLTA depois de `SOLTAR_APOS_S` sem uso — este processo é o mesmo que
 segmenta à noite, e uma TC de 591 cortes em 32 bits são 620 MB parados.
~~~

## linha 1480 · montar

~~~text
 ═══ AS SESSOES DE TUBO VIVEM NA MEMORIA ═══

 Um tubo e uma mascara booleana do tamanho do volume -- dezenas de MB. Ela
 nao vai para o navegador (seria a imagem inteira por rede) e NAO VAI PARA
 O DISCO: mascara gravada e mascara que alguem carrega noutro programa, e
 a fronteira desta tela e justamente nao produzir volume que se leve.

 Morre com o processo, como o bilhete. E e o certo: a construcao e da
 sessao, e nao um artefato.
~~~

## linha 1492 · montar

~~~text
 ═══ E O CONTADOR, QUE É O QUE TORNA A CHAVE ÚNICA ═══

 A chave era `"%s|%d" % (bilhete, len(_ORDEM))` — o TAMANHO da fila, que
 satura em `TETO_SESSOES`. Simulado em 13/09/2026: cliques 1 a 5 bem;
 6, 7 e 8 vivem mas o dicionário DRENA (4 → 3 → 2 → 1), despejando
 sessões legítimas de OUTRAS séries antes da hora; e no clique 9 a fila
 tem quatro cópias de `<bilhete>|4`, o `while` faz `pop` da entrada
 RECÉM-GRAVADA, e daí em diante `/api/nidus/linhas` responde «sessão
 expirada — refaça a marcação» PARA SEMPRE, até reiniciar o programa.

 > **A mensagem manda o operador repetir exatamente o que não vai
 > funcionar** — o pior tipo de diagnóstico, porque encerra a procura no
 > lugar errado. É a mesma família do UNINSTALL de 04/09/2026, que
 > mandava rodar de dentro da pasta instalada estando dentro dela.

 E com `TETO_INCIDENCIAS = 12`, o fluxo PREVISTO é justamente acumular
 muitas incidências, uma retroprojeção por vez. O defeito morava no
 caminho normal de uso.

 Contador monotônico: ele só cresce, então duas chaves nunca coincidem,
 e o despejo volta a ser o mais antigo de verdade. `itertools.count` em
 vez de `os.urandom` porque a chave aparece no log e num id de tela —
 número que cresce se lê; hex de 12 dígitos, não.
~~~

## linha 1516 · montar

~~~text
 ═══ O TETO DE INCIDÊNCIAS É DE CUSTO, e está dito ═══

 Ele aparece na resposta (`teto`) e a tela o mostra — teto que
 trunca em silêncio faz a interseção mudar sem motivo aparente, e
 a pessoa conclui que a marcação estava errada.

 ESTE COMENTÁRIO DIZIA que cada tubo era um volume `lado³` — 16,8 MB a
 256 — e que doze cabiam em 200 MB. Nunca foi: o tubo volta para a
 grade da SÉRIE, e tem o tamanho dela, qualquer que seja o `lado`.
 Medido na v8.3: 155 MB por tubo na TC de pescoço de 591 cortes, 44 a
 48 MB nas RM de 512 px — doze tubos da TC eram 1,9 GB. Desde a v8.3 o
 tubo é guardado em bits (`radai_nidus.Compacto`): 19 MB na mesma TC, e
 os doze cabem em 230 MB.
~~~

## linha 1531 · montar

~~~text
 ═══ A SÉRIE ABERTA, e a trava que a lê uma vez só ═══

 A tela pede a projeção e os três cortes AO MESMO TEMPO, e as rotas `def`
 rodam em threads. Sem a trava, quatro pedidos da série recém-escolhida
 fariam quatro leituras — que é o que o cache existe para evitar.
~~~

## linha 1539 · montar

~~~text
 ═══ O TUBO DE CADA INCIDÊNCIA É CALCULADO UMA VEZ ═══

 A tela manda a lista INTEIRA a cada Guardar, e a rota retroprojetava
 todas de novo: a sexta incidência custava seis tubos (1,3 a 2,9 s cada,
 medido nas RM e na TC do banco). A chave é a incidência inteira — série,
 resolução, ângulos e vértices —, então uma incidência mexida é outra
 chave, e nunca um tubo velho.
~~~

## linha 1561 · montar._armar

~~~text
 Chamada com `_TRAVA` na mão.
~~~

## linha 1570 · montar._serie (docstring)

~~~text
A `radai_nidus.Serie` do bilhete, lida uma vez. `None` sem pasta.

        ═══ E O UID VAI JUNTO (v8.3) ═══

        `_pasta` jogava o UID fora e chamava `engine.load_sitk(pasta)` — que,
        sem UID, devolve a PRIMEIRA série que o GDCM agrupa na pasta. Numa
        pasta com duas (o `.zip` do portal extraído), as duas opções do
        seletor abririam o mesmo volume, sem erro nenhum.
~~~

## linha 1588 · montar._serie

~~~text
 A ANTERIOR SAI ANTES DE A NOVA SER LIDA.
~~~

## linha 1606 · montar._series (docstring)

~~~text
As séries da pasta. A imagem viaja por BILHETE — ver `radai_thumbnail`.

        Aqui a lista NÃO é a de séries contornadas: uma angiotomografia não
        precisa ter passado pelo Auto-Contorno para ser projetada. Quem
        responde é o `radai_batch.varrer`, que é o mesmo que o Rodar agora usa.

        ═══ E A RM ENTRA (26/09/2026, v8.3) ═══

        A chamada não dizia `modalidades`, e o padrão do `varrer` é só CT: as
        RM de crânio pós-gadolínio — o exame que o autor pediu para projetar —
        nem apareciam no seletor. A fusão (`radai_elastic_screen`) já pedia
        as duas.
~~~

## linha 1630 · montar._series

~~~text
 fora do laco de eventos: ver `radai_web`
~~~

## linha 1653 · montar._forma

~~~text
 Rota `def`: o Starlette ja a roda fora do laco. Ver `radai_web`.
~~~

## linha 1658 · montar._forma

~~~text
 ═══ O PASSO DO DETECTOR SAI DA LIB, E NÃO DE UMA CONTA NA TELA ═══

 Quem sabe a diagonal do volume é `_grade` — e ela já mudou uma
 vez (deixou de ser cubo em 02/09/2026). Uma segunda conta na
 tela teria ficado para trás nesse dia, mostrando um número
 plausível e errado. Desde a v8.3 a conta é
 `radai_nidus._medidas_da_grade(`, a mesma que `_grade(` usa, e
 que não aloca a imagem de referência.
~~~

## linha 1669 · montar._forma

~~~text
 O MAIOR LADO QUE AINDA DIZ ALGO. Acima dele o detector
 fica mais fino que a CTA, e o que aparece a mais é o
 interpolador — a tela diz isso com todas as letras.
~~~

## linha 1673 · montar._forma

~~~text
 A ESCALA: HU na TC, relativa ao sinal na RM. A tela diz
 qual, porque «angio» numa RM não é a janela da TC.
~~~

## linha 1696 · montar._projecao (docstring)

~~~text
O PNG da projeção. Sem cache: o ângulo muda a cada arrasto.
~~~

## linha 1700 · montar._projecao

~~~text
 Rota `def`: o Starlette ja a roda fora do laco. Ver `radai_web`.
~~~

## linha 1704 · montar._projecao

~~~text
 ═══ O LADO VEM DA TELA, E ELE TEM TETO ═══

 A URL e editavel, e `lado=8192` alocaria 8192 x 8192 x 384
 floats -- 1 TB. Nao e ataque: e alguem experimentando, e o
 resultado seria a estacao inteira parada.

 O teto e `LADO_ALTA`, que e o maior valor MEDIDO (1,47 s, 1,6
 GB). Valor fora da lista cai no padrao em vez de ser recusado:
 a tela e quem escolhe, e um 400 aqui deixaria a projecao em
 branco sem dizer por que.
~~~

## linha 1730 · montar._projecao

~~~text
 SEM STACK TRACE NA IMAGEM: um traceback numa tag <img> vira um
 icone quebrado com o caminho do paciente no atributo.
~~~

## linha 1737 · montar._corte (docstring)

~~~text
Um corte da série, no plano pedido — o lado direito da tela.

        O plano é o do PACIENTE, e não o do array (v8.3): ver
        `radai_nidus.corte`. E o pixel sai quadrado em milímetros
        (`radai_nidus.para_a_tela`) — a mesma grade em que `/api/nidus/linhas`
        põe as linhas.
~~~

## linha 1763 · montar._tubo_da_incidencia (docstring)

~~~text
O tubo (em bits, na vista S-P-L) de UMA incidência, do cache.
~~~

## linha 1783 · montar._tubos (docstring)

~~~text
Retroprojeta as incidências guardadas. Devolve só o identificador.

        A MÁSCARA NÃO VAI PARA O NAVEGADOR. Ela tem o tamanho do volume;
        mandá-la seria trafegar a imagem inteira por rede a cada corte rolado.
        O que viaja são os SEGMENTOS de linha do corte que está na tela.
~~~

## linha 1794 · montar._tubos

~~~text
 fora do laco de eventos: ver `radai_web`
~~~

## linha 1797 · montar._tubos

~~~text
 O BILHETE É A CHAVE DA SÉRIE no cache de tubos: ele é o HMAC de
 pasta + UID, único por série, e não depende de ler `_ABERTA`
 fora da trava.
~~~

## linha 1801 · montar._tubos

~~~text
 MESMO TETO da rota da projecao: o tubo e retroprojetado na
 MESMA grade, e um `lado` diferente poria o desenho numa
 grade e o tubo noutra.
~~~

## linha 1807 · montar._tubos

~~~text
 ═══ SEM TETO DE DUAS ═══

 Era `[:2]`. Cada incidência acrescentada aperta a
 interseção: com duas ela é uma caixa larga, com seis ela
 fecha em torno do que todas viram — e é essa a pergunta
 da simulação.

 O TETO CONTINUA EXISTINDO, e é de custo: ver
 `TETO_INCIDENCIAS`.
~~~

## linha 1827 · montar._tubos

~~~text
 `next(_PROXIMA)` e nao `len(_ORDEM)`: o tamanho da fila satura
 no teto e a chave passa a se repetir. Ver o comentario de
 `_PROXIMA`, la em cima, com a simulacao clique a clique.
~~~

## linha 1831 · montar._tubos

~~~text
 A SESSÃO LEVA A GEOMETRIA DA VISTA: `/api/nidus/linhas` precisa
 dela para pôr as linhas na grade do corte, e a série pode ter
 sido solta da memória quando o operador voltar a rolar.
~~~

## linha 1841 · montar._tubos

~~~text
 O QUE VOLTA É A LISTA, e não só a contagem: a tela mostra
 cada incidência acumulada ao lado, com o ângulo dela, e
 sem isso ela teria de guardar o que mandou — duas
 verdades sobre a mesma coisa, e onde elas divergem.
~~~

## linha 1855 · montar._linhas (docstring)

~~~text
As LINHAS FINAS de um corte. Segmentos, nunca região.

        Região fechada e preenchida num corte axial tem uma leitura só neste
        ofício: é um contorno. A aparência é o que vaza.

        E NÃO DEVOLVE VOLUME. Ver `radai_nidus.SEM_VOLUME`.

        As linhas vêm na grade da imagem do corte (`radai_nidus.escalar` com
        os fatores de `radai_nidus.grade_da_tela`), e `altura`/`largura` são
        as da imagem: o `viewBox` do SVG e o PNG têm de ser a mesma grade.
~~~

## linha 1877 · montar._linhas

~~~text
 ═══ UMA CAMADA POR INCIDÊNCIA, NUMERADA ═══

 Eram `"a"` e `"b"`, que é o que se escreve quando são duas.
 Com N, a camada precisa dizer QUAL incidência é — e o
 ângulo vem junto, porque é por ele que a pessoa reconhece
 a linha na tela e na lista ao lado.
~~~

## linha 1891 · montar._linhas

~~~text
 E A SOMA POR ÚLTIMO, para desenhar por cima das outras.
 Ela é o que a simulação enxerga como ninho: onde TODAS as
 incidências se cruzam.
~~~

# O que a `entrega-v83` tinha e o código de hoje não tem

Linhas de comentário e de docstring da `entrega-v83` que não aparecem em comentário nenhum deste arquivo hoje (a comparação é por linha, com o espaço normalizado).

## linha 66 na entrega-v83 · (módulo) (web)

~~~text
comparacao em memoria -- e a comparacao E o produto desta tela. */
~~~

## linha 879 na entrega-v83 · (módulo) (web)

~~~text
<!-- ══ A ANGIO ══ -->
~~~

## linha 981 na entrega-v83 · (módulo) (web)

~~~text
<!-- ══ A TC, COM AS LINHAS FINAS ══ -->
~~~

# Comentários HTML de várias linhas (tirados na segunda passada)

Blocos `<!-- … -->` de várias linhas inteiras dentro das strings das telas. A primeira passada só tirava o `<!-- … -->` de uma linha; estes ficaram no código até a segunda, e a linha é a do arquivo depois da primeira limpeza.

## linha 887 · (módulo) (web)

~~~text
<!-- O RÓTULO DIZIA «angiotomografia», e a lista abaixo dele traz TC e RM
desde a v8.3 (`MODALIDADES`), cada série com a modalidade na frente.
Rótulo que nomeia uma só das duas manda procurar a RM em outra tela. -->
~~~

## linha 912 · (módulo) (web)

~~~text
<!-- ══ A ANGIO ══ -->
~~~

## linha 919 · (módulo) (web)

~~~text
<!-- O `viewBox` NASCE COM O `lado` DE FABRICA e e trocado por
`ndGradeDoDesenho` a cada resolucao: o desenho esta em unidades da
projecao, e um quadro fixo poria o vertice no lugar errado. -->
~~~

## linha 974 · (módulo) (web)

~~~text
<!-- ══ RESOLUCAO ══
«quero o Nidus com alta resolução dos vasos porque a MAV é muito
fina» — Dr. Henrique, 02/09/2026.

A projeção é reamostrada para uma grade de detector, e em 512 o passo
fica MAIS GROSSO que a própria CTA — a projeção jogava fora resolução
que o exame trouxe. Medido num fantoma com vasos de 2,4 a 0,6 mm:

512   0,64 mm   0,45 s   537 MB   vaso de 0,6 mm: +1052
1024  0,32 mm   1,47 s   1,6 GB   vaso de 0,6 mm: +1154

ALTA NÃO É O PADRÃO. Girar a incidência em 1024 seria 1,5 s por passo
de ângulo — a exploração ficaria intragável. 256 para girar, 512 para
olhar, 1024 para o momento em que ela decide onde desenhar. -->
~~~

## linha 1008 · (módulo) (web)

~~~text
<!-- ══ AS DUAS FERRAMENTAS ══
«desenhar com um lápis» — Dr. Henrique, 14/09/2026.

O lápis entrou e o desenho por cliques FICOU: um vértice por clique é
o desenho de precisão que o arrasto não faz, e vaso de MAV é fino.
Tirar o que já funcionava não foi pedido.

O modo corrente fica ACESO, e a dica troca com ele — sem isso, quem
arrasta no modo de cliques não desenha nada e conclui que a tela
quebrou. -->
~~~

## linha 1043 · (módulo) (web)

~~~text
<!-- ══ A TC, COM AS LINHAS FINAS ══ -->
~~~

## linha 1072 · (módulo) (web)

~~~text
<!-- A FRONTEIRA, VISIVEL. Nao e letra miuda: e o que separa uma construcao de
visualizacao de um volume de tratamento.
(Desde a tela de funcao ela mora no «?» da cabeca, em `_cabeca`.) -->
~~~
