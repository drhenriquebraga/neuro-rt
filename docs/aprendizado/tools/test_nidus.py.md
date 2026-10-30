# tools/test_nidus.py

Comentários e docstrings do código como estava antes da limpeza, na ordem do arquivo. «fica no código» marca o que a limpeza manteve (`GUARDA:`, licença, codificação).

## linha 2 · (módulo) (docstring)

~~~text
test_nidus.py — a projeção vascular, e a fronteira que ela não cruza.

═══ DUAS COISAS SÃO TESTADAS, E A SEGUNDA É A QUE IMPORTA ═══

**A geometria fecha.** Um alvo em ponto conhecido do paciente, circulado em
duas incidências, tem de cair dentro dos dois tubos e dentro da interseção. Se
não cair, a peça não estima nada — e estimaria errado com aparência de certo.

**E a fronteira não se cruza.** A interseção de dois tubos retroprojetados é,
na prática, uma estimativa de volume de alvo para radiocirurgia. Ela existe na
tela como construção de visualização; ela **não exporta e não vira número**.

> No instante em que a tela souber calcular a interseção, alguém vai querer
> saber quantos centímetros cúbicos ela tem — e um volume em cm³ ao lado de
> uma forma é um volume de alvo com passos a mais.

Fantomas geométricos. Nenhum dado de paciente.

Uso:  python tools/test_nidus.py [-v]
~~~

## linha 45 · (módulo)

~~~text
 ═══ ACERVO PRÓPRIO — a bateria não escreve no registro do operador ═══

 `radai_dicom.converter` chama `radai_corpus.registrar` no fim, e esta bateria
 converte fantomas várias vezes. Sem isolar, cada `verify.cmd` acrescenta
 essas linhas ao corpus da estação.

 **Medido em 26/08/2026:** o `corpus_recusa.jsonl` de
 `C:\RADIOTERAPIA_AI\TC_TESTE` tinha **100 entradas, todas de fantoma** —
 3 a 9 cortes, espaçamento 3,0 mm. O corpus é o censo do que a estação
 recebe, e ele estava 100% preenchido por teste.

 > **Registro que mente é pior que registro vazio:** sem ele você procura;
 > com ele você confia.

 Mesma família do `test_shutdown` de 23/08 (fantoma escrevendo o
 `radai_status.json` do operador) e do atalho no Desktop real de 20/08:
 **verificação com efeito na máquina de quem a roda não é verificação.**
~~~

## linha 64 · (módulo)

~~~text
 noqa: E402
~~~

## linha 91 · sem_prosa (docstring)

~~~text
O código, sem comentário e sem DOCSTRING — mas COM os gabaritos.

    A CHECAGEM É POR CÓDIGO, e não por prosa. O texto PODE — e deve — explicar
    por que não há canvas e por que não há volume; uma guarda que proíbe o
    texto que a justifica é uma guarda que se apaga sozinha.

    ═══ E O GABARITO DA PÁGINA NÃO É PROSA ═══

    A primeira versão tirava TODA string de aspas triplas. `PAGINA`, `CSS` e
    `JS` também são de aspas triplas — e sumiam junto. A checagem "a tela
    desenha em SVG" passou a reprovar porque o `<svg>` tinha sido apagado
    antes de se procurar por ele.

    > Recorte que remove mais do que devia acusa o CERTO — e o "conserto"
    > seria estragar o código.

    Por isso a docstring é removida pelo `ast`, que sabe quais literais são
    docstring de módulo, classe ou função — e quais são atribuição.
~~~

## linha 133 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 a cabeça fantoma
 ═══════════════════════════════════════════════════════════════════════════
~~~

## linha 137 · cabeca (docstring)

~~~text
Crânio com um novelo denso em ponto CONHECIDO do paciente.
~~~

## linha 165 · onde (docstring)

~~~text
Onde o alvo cai na projeção — para circular ali.

    `t.TransformPoint`, e NÃO a matriz à mão: o `Resample` usa
    `t.GetInverse()` para ir da grade de saída para a de entrada, logo `t`
    leva o ponto do paciente para o detector. Refazer a conta é onde se troca
    `R` por `R^T`, e o sintoma seria o tubo cair ao lado do alvo **só nas
    oblíquas** — a AP acerta porque a rotação é a identidade.
~~~

## linha 176 · onde

~~~text
 A GRADE DEIXOU DE SER CUBO em 02/09/2026: o plano do detector e a
 profundidade do raio passaram a ter passos proprios, e `_grade`
 devolve os dois. O eixo que o MIP reduz nao precisa da resolucao do
 eixo que a pessoa OLHA -- ver `FUNDO_MAXIMO`.
~~~

## linha 184 · onde

~~~text
 ═══ NA PROJEÇÃO QUE A TELA MOSTRA, com a cranial em cima (v8.3) ═══

 `gx`, `gz` são índices contínuos da GRADE (o centro do pixel `g` fica
 em `g`). O polígono mora na projeção mostrada, onde o centro do pixel
 `r` fica em `r + 0,5` e a linha 0 é a cranial — a grade invertida. Esta
 conta devolvia `gz` cru, e passou a errar o alvo no dia em que a
 projeção deixou de sair de cabeça para baixo: é assim que a bateria
 sabe que a inversão da projeção e a do tubo andam juntas.
~~~

## linha 197 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
~~~

## linha 199 · teste_a_geometria_fecha (docstring)

~~~text
O alvo tem de cair nos dois tubos, e na interseção.

    Se não cair, a peça não estima nada — e estimaria errado com aparência de
    certo, que é a pior forma de errar neste ofício.
~~~

## linha 229 · teste_a_geometria_fecha

~~~text
 E ELA ESTREITA. Uma intersecao do tamanho do tubo nao estimou nada.
~~~

## linha 235 · teste_a_geometria_fecha

~~~text
 ═══ A INCIDENCIA IMPORTA ═══
 Dois tubos do MESMO angulo nao cruzam nada -- eles sao o mesmo tubo. Se a
 intersecao deles fosse menor, a geometria estaria errada.
~~~

## linha 242 · teste_a_geometria_fecha

~~~text
 POLIGONO DEGENERADO NAO LEVANTA, e devolve tubo vazio: dois cliques nao
 fecham area, e a tela pode chamar antes de a pessoa terminar.
~~~

## linha 252 · teste_a_projecao_e_o_extremo_do_raio (docstring)

~~~text
MIP é o máximo ao longo do raio, e MinIP o mínimo.

    Parece óbvio e não é: a alternativa natural — a fatia do meio — devolve
    imagem plausível e não é projeção. Um vaso que passe fora do plano central
    sumiria, e ninguém saberia que sumiu.
~~~

## linha 265 · teste_a_projecao_e_o_extremo_do_raio

~~~text
 SO DENTRO DO VOLUME, e a razao e do desenho: o MIP preenche a borda com
 -1024 e o MinIP com 3071, de proposito -- assim o preenchimento NUNCA
 vence a projecao. Fora do volume, portanto, o MinIP e maior, e comparar
 ali mediria o preenchimento, e nao a projecao.
~~~

## linha 276 · teste_a_projecao_e_o_extremo_do_raio

~~~text
 O ALVO E DENSO: ele tem de aparecer no MIP.
~~~

## linha 286 · teste_a_projecao_e_o_extremo_do_raio

~~~text
 A LAJE RECORTA. Sem laje o volume inteiro entra; com laje fina o
 extremo cai, porque menos tecido entra na conta.
~~~

## linha 292 · teste_a_projecao_e_o_extremo_do_raio

~~~text
 ═══ A GRADE E A DIAGONAL, e nao a maior aresta ═══
 Girado 45 graus, um volume alongado passa da caixa que o continha
 alinhado -- e os cantos seriam cortados justamente na obliqua, que e a
 incidencia que interessa.
~~~

## linha 306 · teste_as_linhas_sao_finas (docstring)

~~~text
Segmentos de fronteira, e nunca região preenchida.

    Região fechada e preenchida num corte axial tem uma leitura só neste
    ofício: é um contorno. Alguém tira print, e o print circula. **A aparência
    é o que vaza.**
~~~

## linha 324 · teste_as_linhas_sao_finas

~~~text
 SAO MUITO MENOS QUE A AREA. Se o numero de segmentos se aproximasse da
 area, o "contorno" seria a regiao inteira desenhada aresta a aresta.
~~~

## linha 330 · teste_as_linhas_sao_finas

~~~text
 CORTE SEM TUBO DEVOLVE LISTA VAZIA, e nao levanta: a pessoa rola ate o
 topo da cabeca, e a tela nao pode parar ali.
~~~

## linha 343 · teste_a_fronteira_nao_se_cruza (docstring)

~~~text
**Nenhum volume de alvo derivado.** É a regra do módulo torácico.

    A interseção de dois tubos retroprojetados é, na prática, uma estimativa
    de volume de alvo para radiocirurgia. Ela existe na tela como construção
    de visualização; ela não exporta e **não vira número**.
~~~

## linha 352 · teste_a_fronteira_nao_se_cruza

~~~text
 ═══ NAO HA FUNCAO DE VOLUME, E ISSO E A TRAVA ═══

 A funcao que contaria os voxels nao existe. Nao e omissao: e a guarda.
~~~

## linha 360 · teste_a_fronteira_nao_se_cruza

~~~text
 O QUE NAO PODE EXISTIR E O CALCULO, e nao a palavra. `SEM_VOLUME`
 contem "cm³" e TEM de conter: e a declaracao da guarda. Proibir a
 palavra proibiria o aviso que a guarda existe para dar.
~~~

## linha 369 · teste_a_fronteira_nao_se_cruza

~~~text
 E A TELA TAMBEM NAO. A trava tem de olhar a TELA, e nao so a lib: o
 numero que alguem acrescenta por conveniencia entra pelo arquivo da
 tela, que e onde a pessoa pede. Foi assim com a Reconstrucao 3D.
 NA TELA, A PALAVRA `volume` E LEGITIMA -- "nao e um volume de
 tratamento" e justamente a frase da fronteira. O que nao pode existir e
 a EXIBICAO de um numero: cm3 e as formas de exportar.
~~~

## linha 381 · teste_a_fronteira_nao_se_cruza

~~~text
 E A FRASE DA FRONTEIRA ESTA LA, que e o outro lado da mesma checagem.
~~~

## linha 386 · teste_a_fronteira_nao_se_cruza

~~~text
 ═══ E O DESENHO E SVG, E NAO CANVAS ═══
~~~

## linha 391 · teste_a_fronteira_nao_se_cruza

~~~text
 ═══ A FRONTEIRA ESTA NA TELA, e nao so no codigo ═══
~~~

## linha 403 · teste_a_fronteira_nao_se_cruza

~~~text
 E A RM (v8.3): o seletor lista RM, e a limitação de angioTC sozinha
 deixaria a RM sem a dela — o sinal não é HU, e a janela é relativa.
~~~

## linha 411 · teste_a_fronteira_nao_se_cruza

~~~text
 ═══ E O NOME E `projecao vascular` ═══
 "Arteriografia virtual" sugere substituicao, e ela nao substitui.
~~~

## linha 424 · teste_nao_detecta_nada (docstring)

~~~text
Regra 6: o médico desenha, a máquina projeta.

    Esta é a única peça do aplicativo que não encosta na regra por
    **construção**, e não por trava — mas a checagem existe porque construção
    é uma propriedade que alguém pode remover sem perceber.
~~~

## linha 438 · teste_nao_detecta_nada

~~~text
 O CAMINHO NAO VIAJA NA URL. `<img src>` e GET, e GET entra no historico
 do navegador e no log de acesso.
~~~

## linha 449 · teste_a_suite_conhece_o_modulo (docstring)

~~~text
Cinco lugares, e é isso que faz a casca sair certa.

    Faltar um deles não quebra: produz um link para o vazio, um cabeçalho sem
    trilha, ou um cartão que leva para a home. Foi exatamente o que aconteceu
    ao ligar este módulo — `linha_da_home` tinha um mapa de rotas fixo dentro
    da função, e o quarto módulo caía em `/`.
~~~

## linha 474 · teste_a_suite_conhece_o_modulo

~~~text
 ═══ A COR EXISTE NOS DOIS TEMAS ═══
 Ficha so no escuro fica com o valor do escuro no claro, e a linha some
 sobre branco -- sem nada quebrar.
~~~

## linha 488 · teste_a_suite_conhece_o_modulo

~~~text
 ═══ A LINHA DA HOME LEVA PARA O MODULO, e nao para a home ═══
~~~

## linha 492 · teste_a_suite_conhece_o_modulo

~~~text
 E MODULO SEM ROTA NAO VIRA CARTAO: um cartao que leva para a home e
 pior que cartao nenhum -- promete um modulo e devolve a pessoa ao
 comeco.
~~~

## linha 500 · teste_acumular_incidencias (docstring)

~~~text
A intersecao APERTA a cada incidencia, e continua contendo o ninho.

    ═══ A PERGUNTA DA SIMULACAO ═══

    Cada incidencia de gantry ve o ninho por um angulo, e o poligono que o
    medico circula ali vira um TUBO -- tudo o que poderia estar naquela
    direcao. Com duas incidencias a intersecao e uma caixa larga; a cada
    angulo novo ela aperta.

    Isto mede exatamente isso: um volume com uma esfera conhecida, a
    projecao dela circulada em seis angulos, e a contagem de voxels que
    sobram. **Se o numero nao cair com N, a acumulacao nao esta fazendo
    nada** -- e o teto de duas que existia ate 30/08/2026 e' justamente o
    caso em que ela nao fazia.

    ═══ A GRADE TEM DE SER A MESMA ═══

    `projetar(lado=A)` e `tubo(lado=B)` com A != B poem o poligono numa
    grade e o tubo noutra: a intersecao sai compacta, e no lugar errado. A
    primeira volta desta prova mediu o centroide em (76,48,82) numa esfera
    centrada em (48,48,48) -- e o defeito era do teste.

    > Fantoma que mistura grades acusa a geometria certa, e o conserto
    > obvio e' estragar a geometria.
~~~

## linha 541 · teste_acumular_incidencias.circulo (docstring)

~~~text
Circula onde a esfera cai NA PROJECAO -- nao adivinha.
~~~

## linha 567 · teste_acumular_incidencias

~~~text
 \u2550\u2550\u2550 O PONTO \u2550\u2550\u2550 ela so aperta, e nunca cresce.
~~~

## linha 576 · teste_acumular_incidencias

~~~text
 E ELA CONTINUA CONTENDO O NINHO. Apertar demais e' tao errado quanto
 nao apertar: a intersecao que exclui o alvo nao mostra nada.
~~~

## linha 591 · teste_acumular_incidencias

~~~text
 \u2550\u2550\u2550 E CONTINUA SENDO LINHA \u2550\u2550\u2550
~~~

## linha 598 · teste_acumular_incidencias

~~~text
 UMA POR INCIDENCIA. Com N tubos o desenho tem N camadas mais a soma.
~~~

## linha 606 · teste_acumular_incidencias

~~~text
 \u2550\u2550\u2550 A FRONTEIRA \u2550\u2550\u2550 quanto mais convincente, mais necessaria.
~~~

## linha 614 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 A TELA EXECUTADA, E NÃO LIDA
 ═══════════════════════════════════════════════════════════════════════════

 **Esta bateria passava com a tela morta dentro.** 103 checagens verdes, e:

   * `ndPintarGuardadas`, chamada no `DOMContentLoaded`, levantava
     `TypeError` sobre o `[null,null]` que sobrou da versão de duas
     incidências — e como ela é chamada UMA LINHA ANTES de `ndListar('')`, a
     lista de séries **nunca era pedida**. A tela abria com «carregando…»
     para sempre;
   * `ndGuardar` levantava `ReferenceError: qual is not defined` antes de
     chamar `ndCalcular()` — a incidência entrava na lista e a retroprojeção
     **não disparava**.

 Os dois estão medidos: o palco abaixo os reproduz, e o conserto os apaga.

 > **Checagem que lê o fonte como texto mede que o código existe; ela não
 > mede que ele roda.** Os dois defeitos eram do segundo tipo, e nenhuma
 > das 103 chegava perto — a que procurasse a palavra `qual` no arquivo
 > provaria apenas que uma palavra sumiu.

 O palco é um DOM de mentira: `getElementById` cria o elemento que lhe
 pedirem, `fetch` guarda a URL e responde o que a rota real responderia, e os
 botões de cada barra vêm do gabarito **real** da página — é assim que a
 checagem cruza o HTML com o JavaScript em vez de acreditar nos dois
 separadamente.

 Ele não é um navegador e não tenta ser. O que ele prova é que o caminho do
 operador — abrir, girar, desenhar, guardar — atravessa o JavaScript sem
 levantar, e que a retroprojeção é PEDIDA.
~~~

## linha 646 · (módulo)

~~~text
 Nomes que o navegador oferece e o JavaScript pode ler sem declarar.
~~~

## linha 657 · _declarados_por_var (docstring)

~~~text
Todo nome de um `var`, inclusive os depois da vírgula.

    `re.findall(r"var\s+(\w+)")` pega só o PRIMEIRO de
    `var fica=[], pilha=[[0,n]]` — e os outros saíram acusados de soltos,
    onze de uma vez. **A checagem estava errada, e o código certo**, que é o
    caso em que o «conserto» óbvio é estragar o código.

    O caminhar até o `;` respeita profundidade: o `;` de `for(var i=0;i<n;i++)`
    fecha o `var`, e a vírgula dentro de `[[0, n]]` não abre declarador.
~~~

## linha 683 · _declarados_por_var

~~~text
 declarador terminado no fim da linha, sem `;` e sem vírgula
~~~

## linha 701 · identificadores_soltos (docstring)

~~~text
Nomes que o JavaScript LÊ e que não foram declarados em lugar nenhum.

    ═══ POR QUE ESTA NÃO É UMA BUSCA PELA PALAVRA `qual` ═══

    Procurar `qual` no arquivo provaria que uma palavra sumiu. O defeito não
    era a palavra: era um nome lido sem declaração — e o próximo virá com
    outro nome, do mesmo jeito (resíduo de refatoração, um `i` que mudou de
    laço, um parâmetro renomeado na assinatura e não no corpo).

    Ela roda em QUALQUER runtime, sem node, e é por isso que existe ao lado do
    palco: o palco prova mais e depende de um interpretador que a estação de
    campo não tem. Guarda que só roda na máquina do desenvolvedor é guarda que
    a estação não tem.
~~~

## linha 717 · identificadores_soltos

~~~text
 As strings saem ANTES da busca: `'qual'` dentro de um texto de tela é
 texto, e acusá-lo mandaria procurar defeito numa frase.
~~~

## linha 727 · identificadores_soltos

~~~text
 `(\.\s*)?` exclui o acesso a propriedade (`ND.lado` não declara `lado`)
 e `(\s*:)?` exclui a chave de objeto literal (`{modo:'mip'}`).
~~~

## linha 739 · (módulo) (web)

~~~text
// ═══ O PALCO FALSO ═══  (montado por tools/test_nidus.py)
~~~

## linha 742 · (módulo) (web)

~~~text
// ═══ `className` E `classList` SAO A MESMA COISA ═══
//
// No navegador o `classList` e uma DOMTokenList VIVA: `classList.toggle`
// muda o `className`, e atribuir `className` refaz a lista. O palco tinha os
// dois separados, e o preco foi imediato -- `ndResolucao` escreve
// `className` e `ndFerramenta` usa `classList.toggle`, entao a checagem
// «so o corrente esta aceso» via DOIS botoes acesos e acusava a tela.
//
// > Palco que nao imita o navegador acusa o certo, e o «conserto» obvio seria
// > estragar a tela. E a mesma familia do recorte que apagava o `<svg>` antes
// > de procurar por ele.
~~~

## linha 775 · (módulo) (web)

~~~text
// O palco tem 400 x 400 e a origem em zero: assim a conta do desenho fica
// legivel no roteiro -- um pixel de tela vale `lado/400` unidades da projecao.
~~~

## linha 782 · (módulo) (web)

~~~text
// OS BOTOES VEM DO GABARITO REAL DA PAGINA. Inventa-los aqui faria a checagem
// medir o palco: `data-r` trocado no HTML passaria, e a tela marcaria o botao
// errado como ativo.
~~~

## linha 805 · (módulo) (web)

~~~text
// AS RESPOSTAS SAO AS DAS ROTAS REAIS, no formato que elas devolvem. Uma
// resposta inventada testaria o palco.
~~~

## linha 837 · (módulo)

~~~text
 O roteiro roda depois da tela, no MESMO escopo — é por isso que os três
 pedaços viram um arquivo só em vez de três módulos.
~~~

## linha 873 · _node (docstring)

~~~text
O caminho do node, ou `None`. Ausência ANUNCIA, e não passa calada.
~~~

## linha 879 · _botoes_da_pagina (docstring)

~~~text
Os botões de cada barra, tirados do gabarito REAL da página.
~~~

## linha 894 · _encenar (docstring)

~~~text
Roda a tela de verdade no palco falso e devolve o que ela fez.

    `ajuste` recebe o JavaScript e devolve outro — é como a ISCA desfaz o
    conserto sem tocar no arquivo: a bateria não pode editar o código que
    está medindo.
~~~

## linha 922 · teste_o_javascript_nao_le_nome_solto (docstring)

~~~text
Nenhum nome é lido sem ter sido declarado. Roda em qualquer runtime.
~~~

## linha 928 · teste_o_javascript_nao_le_nome_solto

~~~text
 ═══ O TESTE DO TESTE ═══ sem isto, uma checagem que nunca dispara passa
 por guarda. A isca é o defeito REAL de 14/09, reinjetado.
~~~

## linha 936 · teste_a_tela_acorda_e_pede_as_series (docstring)

~~~text
O `DOMContentLoaded` atravessa, e a lista de séries é PEDIDA.

    Era aqui que a tela morria: `ndPintarGuardadas` levantava no `[null,null]`
    e `ndListar('')`, a linha seguinte, nunca rodava. A tela abria com
    «carregando…» e ficava assim — sem erro visível, porque o `TypeError`
    morre no console do navegador, que ninguém abre.
~~~

## linha 963 · teste_a_tela_acorda_e_pede_as_series

~~~text
 ═══ O TESTE DO TESTE: os dois nulos de volta ═══
 Com eles, `ndPintarGuardadas` levanta e `ndListar` — a linha seguinte —
 nunca roda. É a prova de que esta checagem mede a CARGA, e não a
 presença da chamada.
~~~

## linha 980 · teste_guardar_dispara_a_retroprojecao (docstring)

~~~text
«vou salvando» — e cada guardar tem de RETROPROJETAR.

    O defeito: `ndMsg('incidência '+(qual?'B':'A')+' guardada')` levantava
    `ReferenceError` na linha ANTERIOR a `ndCalcular()`. A incidência entrava
    na lista, a lista pintava, e a retroprojeção não acontecia — só voltava a
    acontecer ao REMOVER uma incidência, que é o outro caminho para
    `ndCalcular`.
~~~

## linha 1014 · teste_guardar_dispara_a_retroprojecao

~~~text
 A MENSAGEM SAI DA LISTA, e nao de uma variavel que a lista nao tem.
~~~

## linha 1018 · teste_guardar_dispara_a_retroprojecao

~~~text
 ═══ E GUARDAR DUAS VEZES NAO ACRESCENTA A MESMA DUAS VEZES ═══
 O desenho passa para a lista quando se guarda; mante-lo na tela faria o
 clique seguinte gravar a mesma incidencia de novo, com o mesmo angulo.
~~~

## linha 1035 · teste_guardar_dispara_a_retroprojecao

~~~text
 ═══ O TESTE DO TESTE: O DEFEITO DE VOLTA ═══

 A isca mora AQUI, e não num script que alguém rodou uma vez: guarda que
 só foi provada no dia em que nasceu é guarda que ninguém sabe se ainda
 pega. Ela devolve o `qual` ao lugar exato de onde ele saiu, e exige que
 a retroprojeção PARE de acontecer.
~~~

## linha 1061 · teste_o_lapis_traca_e_afina (docstring)

~~~text
«desenhar com um lápis» — arrasto, e o traço não vira mil vértices.

    ═══ POR QUE AFINAR NÃO É ENFEITE ═══

    `radai_nidus._mascara_poligono` varre a grade `lado × lado` UMA VEZ POR
    ARESTA. Medido nesta máquina, num polígono regular:

        lado  512 ·  24 vértices  0,20 s   ·  400 vértices  1,47 s
        lado 1024 ·  24 vértices  0,41 s   ·  400 vértices  8,13 s
                                            ·  900 vértices 16,57 s

    E é **por incidência**: cinco traços à mão livre em alta resolução
    passariam de um minuto dentro de `/api/nidus/tubos`, com a tela dizendo
    «retroprojetando…» e nada mais. O traço do mouse produz um ponto por
    evento — dezenas por segundo.
~~~

## linha 1081 · teste_o_lapis_traca_e_afina

~~~text
 UM TRACO DE MAO: 240 amostras com tremor, que e o que um arrasto de
 quatro segundos a 60 Hz produz.
~~~

## linha 1110 · teste_o_lapis_traca_e_afina

~~~text
 O TETO E DE CUSTO, e ele tem de valer para qualquer traco.
~~~

## linha 1116 · teste_o_lapis_traca_e_afina

~~~text
 ═══ E A FORMA SOBREVIVE AO AFINAMENTO ═══

 Afinar que muda a area retroprojetaria outro tubo. A prova nao e uma
 opiniao sobre o numero de vertices: e a MESMA mascara do motor,
 rasterizada nos dois poligonos.
~~~

## linha 1135 · teste_os_dois_modos_convivem (docstring)

~~~text
Os dois desenhos, e o corrente visível na tela.

    O desenho por cliques não foi pedido para sair, e estrutura vascular fina
    precisa dele: um vértice por clique é o desenho de precisão que um arrasto
    não faz. O lápis é o que foi pedido. Os dois ficam, e a tela diz qual está
    valendo — senão o arrasto não desenha nada e a pessoa conclui que a tela
    quebrou.
~~~

## linha 1151 · teste_os_dois_modos_convivem (web)

~~~text
// 1. por CLIQUES, que e o modo de fabrica
~~~

## linha 1156 · teste_os_dois_modos_convivem (web)

~~~text
// o arrasto NAO desenha no modo de cliques
~~~

## linha 1160 · teste_os_dois_modos_convivem (web)

~~~text
// 2. o LAPIS
~~~

## linha 1168 · teste_os_dois_modos_convivem (web)

~~~text
// e o clique nao acrescenta vertice no modo lapis
~~~

## linha 1187 · teste_os_dois_modos_convivem

~~~text
 ═══ O MODO CORRENTE ESTA NA TELA ═══ um botao aceso, e so um.
~~~

## linha 1195 · teste_a_grade_do_desenho_acompanha_a_resolucao (docstring)

~~~text
O `viewBox` do desenho é `ND.lado`, e não um 256 fixo.

    O desenho é convertido para unidades da projeção (`ND.lado`), e o `<svg>`
    nascia com `viewBox="0 0 256 256"`. Em «normal» (512) o vértice desenhado
    no meio do palco vira 256 num viewBox de 256 — o desenho aparece no CANTO,
    com o dobro do tamanho, e metade dele fora do quadro.

    > **O tubo sairia certo e o desenho apareceria errado**, que é a forma
    > que faz duvidar da retroprojeção em vez do quadro.

    E o `ND.lado` de fábrica tem de ser o do botão aceso: eram 256 no
    JavaScript e 512 no HTML, então a tela dizia «normal» e projetava
    «rápida».
~~~

## linha 1239 · teste_as_incidencias_se_somam_nos_tres_planos (docstring)

~~~text
«visualizar como eles se comportam no MPR» — juntas, e com cor própria.

    As linhas dos três planos saem da MESMA sessão, então elas aparecem
    juntas por construção — desde que a sessão exista. Ela não existia: quem
    a pedia era `ndCalcular`, e `ndGuardar` levantava antes de chamá-la.
~~~

## linha 1279 · teste_as_incidencias_se_somam_nos_tres_planos

~~~text
 E A LISTA AO LADO DIZ QUAL E QUAL, com a cor de cada uma.
~~~

## linha 1290 · teste_serie_nova_nao_herda_a_sessao (docstring)

~~~text
Trocar de série apaga a sessão — senão o MPR desenha o tubo da outra.

    `ndEscolher` zerava `guardadas`, `pontos` e `forma`, e deixava
    `ND.sessao`. A sessão vive no servidor e é de OUTRA série: `ndPintarPlanos`
    pedia as linhas dela e as desenhava sobre os cortes da série nova.

    > Linha fina sobre a anatomia errada não parece defeito — parece achado.
~~~

## linha 1329 · teste_o_passo_do_detector_aparece (docstring)

~~~text
O `<span id="nd_passo">` era escrito no HTML e nunca preenchido.

    ═══ POR QUE PREENCHER, E NÃO REMOVER ═══

    A barra oferece três resoluções, e a diferença entre elas **é** o passo do
    detector — 1,28 mm, 0,64 mm, 0,32 mm. Sem o número, «alta» é uma promessa
    sem unidade, e o caso que importa fica invisível: pedir mais detalhe do
    que a série tem devolve interpolação com cara de vaso, que num módulo cujo
    limite é «isto não vira número» é o pior tipo de erro.

    O número vem do SERVIDOR, e não de uma conta na tela: quem sabe a diagonal
    do volume é `radai_nidus._grade`, e uma segunda conta aqui divergiria dela
    no dia em que a grade mudar — foi o que já aconteceu quando ela deixou de
    ser cubo.
~~~

## linha 1369 · teste_o_passo_do_detector_aparece

~~~text
 E O EXCESSO E DITO. A serie do palco oferece ate 768; 1024 e interpolacao.
~~~

## linha 1378 · teste_a_tela_diz_a_escala_da_rm (docstring)

~~~text
Numa RM, a tela diz que a janela é relativa — e diz a modalidade.

    A rota da forma devolve `hu` desde a v8.3, e o comentário dela dizia que
    «a tela diz qual»; a tela não lia o campo. Os botões de janela da RM têm
    os nomes dos da TC e significam outra coisa (percentis do próprio sinal).
    E a lista passou a trazer TC e RM: sem a modalidade na opção, uma pasta
    com as duas mostra duas descrições parecidas.

    A resposta é trocada no roteiro, e não no palco: o palco responde como
    a TC, que é o caso em que a nota NÃO pode aparecer.
~~~

## linha 1426 · (módulo)

~~~text
 AS CHECAGENS DA TELA, NUMA TUPLA SO. Elas entram nas DUAS listas do `main`,
 e uma lista escrita a mao duas vezes e a que esquece a checagem nova.
~~~

## linha 1441 · _rotas_montadas (docstring)

~~~text
As funções que `montar` registra, sem subir servidor nenhum.

    O decorador do FastAPI só precisa devolver a função — é isso que permite
    chamar a rota como função e medir o que ela DEVOLVE.
~~~

## linha 1470 · teste_a_rota_da_forma_calcula_o_passo (docstring)

~~~text
E o número tem de sair da LIB, não de uma conta na tela.

    ═══ POR QUE ESTA CHECAGEM EXISTE ═══

    A primeira versão media só o palco, que responde um `passos` de mentira —
    e a isca «a rota parou de mandar o passo» **passou**: o `<span>` continuava
    preenchido porque quem o preenchia era o palco.

    > **Checagem que dubla a fonte do número prova o desenho, e não o
    > número.** É a mesma família da checagem que procurava a frase «sugestão
    > não aprovada» e a achava na tabela de tradução.

    A rota é chamada como função, com a leitura do disco dublada: o que roda é
    o código real, sobre um fantoma geométrico.
~~~

## linha 1500 · teste_a_rota_da_forma_calcula_o_passo

~~~text
 O UID VAI JUNTO desde a v8.3 (`_serie` chama `load_sitk(pasta,
 uid)`): a dublagem aceita os dois, e a leitura continua dublada.
~~~

## linha 1512 · teste_a_rota_da_forma_calcula_o_passo

~~~text
 ═══ O NUMERO E A DIAGONAL DIVIDIDA PELO LADO ═══
 Conferido contra a geometria da imagem, e nao contra um numero copiado:
 numero copiado envelhece com o fantoma.
~~~

## linha 1525 · teste_a_rota_da_forma_calcula_o_passo

~~~text
 E O LADO UTIL E UM DOS OFERECIDOS: a tela compara `ND.lado` com ele.
~~~

## linha 1530 · (módulo)

~~~text
 ═══════════════════════════════════════════════════════════════════════════
 v8.3 — O QUE A PRIMEIRA SÉRIE DE VERDADE DERRUBOU (26–27/09/2026)
 ═══════════════════════════════════════════════════════════════════════════

 O módulo foi aberto pela primeira vez sobre séries do banco pseudonimizado
 — três RM de crânio pós-gadolínio e uma TC de pescoço com contraste — e
 nenhuma das checagens acima pegou o que apareceu: a projeção de cabeça para
 baixo, a RM como um quadrado branco, os três planos trocados numa aquisição
 sagital, a série relida do disco a cada corte rolado. Todo fantoma daqui
 para cima é TC axial em `float32` — a única forma de série que o módulo
 nunca teve problema para abrir. As checagens abaixo põem a forma que
 faltava: a série sagital, a série em `uint16` sem HU, o pixel anisotrópico.
~~~

## linha 1543 · marcada (docstring)

~~~text
TC axial com UM marcador num canto conhecido do paciente.

    O marcador fica CRANIAL (z alto), ANTERIOR (y baixo) e à ESQUERDA do
    paciente (x alto) — em LPS, x cresce para a esquerda e y para trás. Um
    canto só, e não um ponto no meio: cada eixo da tela tem de pô-lo num
    lado sabido, e um marcador central passaria em qualquer inversão.
~~~

## linha 1562 · como_sagital (docstring)

~~~text
A MESMA anatomia, adquirida em sagital — como as RM do banco.

    Direção de linha para trás (+y), de coluna para baixo (−z), e os cortes
    para a direita do paciente (−x): é a orientação de uma T1 3D sagital, e
    uma rotação própria. A grade de amostras é a MESMA da axial, só
    percorrida noutra ordem — então o vizinho mais próximo é exato, e a vista
    na ordem do paciente tem de devolver o array axial byte a byte.
~~~

## linha 1585 · _onde_no_corte (docstring)

~~~text
`(linha, coluna)` do centro do marcador num corte 2D.
~~~

## linha 1594 · teste_os_tres_planos_saem_na_orientacao_do_paciente (docstring)

~~~text
O quadro «axial» é axial, e o crânio fica em cima — em qualquer série.

    A tela cortava o ARRAY (`v[i]`, `v[:, i, :]`, `v[:, :, i]`) e chamava o
    primeiro de axial. Nas três RM de crânio do banco, que são SAGITAIS, o
    «axial» mostrava um sagital; e mesmo na TC axial o coronal e o sagital
    saíam de cabeça para baixo, porque a linha 0 do array é o corte caudal.
~~~

## linha 1621 · teste_os_tres_planos_saem_na_orientacao_do_paciente

~~~text
 ═══ A CONVENÇÃO DA TELA, eixo a eixo ═══
 O marcador é cranial, anterior e à esquerda do paciente. Radiológico:
 a esquerda do paciente fica à DIREITA da imagem; o crânio em cima; no
 axial, a frente em cima; no sagital, a frente à esquerda.
~~~

## linha 1634 · teste_os_tres_planos_saem_na_orientacao_do_paciente

~~~text
 o corte que passa pelo marcador, na coordenada da vista
~~~

## linha 1643 · teste_os_tres_planos_saem_na_orientacao_do_paciente

~~~text
 ═══ OBLÍQUA: a orientação mais próxima, e nunca um eixo repetido ═══
 A RM P12 do banco está a 17°. E a 45° dois índices empatam no mesmo
 eixo do paciente: um `argmax` por coluna devolveria um eixo repetido,
 e o `transpose` levantaria na cara do operador.
~~~

## linha 1658 · teste_a_projecao_sai_com_o_cranio_em_cima (docstring)

~~~text
Angiografia se lê com o crânio em cima — e o tubo anda junto.

    A grade do detector cresce para cima em `z`, e a linha 0 do array era a
    mais caudal: medido na TC de pescoço do banco, o tórax em cima e o crânio
    embaixo. O conserto inverte a projeção E o polígono do tubo; inverter só
    um espelharia o tubo em torno do meio da incidência — e a checagem de
    geometria (`onde`) é a que pega esse lado.
~~~

## linha 1675 · teste_a_projecao_sai_com_o_cranio_em_cima

~~~text
 E NA AP O LADO DO PACIENTE É O RADIOLÓGICO: a esquerda dele à direita.
~~~

## linha 1684 · rm_uint16 (docstring)

~~~text
Uma «RM» em `uint16`: fundo 0, encéfalo 300, um vaso a 1.100.

    Sem HU e sem valor negativo — é assim que as RM do banco chegam, com o
    sinal de 0 a 1.178, a 6.957 e a 14.188.
~~~

## linha 1704 · teste_a_rm_nao_vira_um_quadrado_branco (docstring)

~~~text
O preenchimento de fora da projeção cabe no tipo da série.

    Era −1024 no MIP, em HU — e o `Resample` devolve o tipo da ENTRADA. Numa
    RM `uint16` o −1024 voltava como 64.512, todo raio fora do volume vencia
    o MIP, e a projeção saía um quadrado branco. E a janela: a RM não tem HU,
    e as quatro janelas em HU enquadravam um borrão.
~~~

## linha 1734 · teste_a_rm_nao_vira_um_quadrado_branco

~~~text
 ═══ A JANELA É RELATIVA AO SINAL DA PRÓPRIA SÉRIE ═══
~~~

## linha 1746 · teste_a_rm_nao_vira_um_quadrado_branco

~~~text
 E NA TC NADA MUDOU: a tabela em HU continua valendo.
~~~

## linha 1753 · _mascara_de_referencia (docstring)

~~~text
O rasterizador de ANTES da v8.3 — a grade inteira, aresta a aresta.

    Copiado para a bateria de propósito: o conserto só varre a caixa do
    polígono, e a pergunta é se a máscara é a MESMA. Comparar contra a
    própria função nova não provaria nada.
~~~

## linha 1782 · teste_a_mascara_do_poligono_e_a_mesma_na_caixa (docstring)

~~~text
Varrer só a caixa do polígono dá a MESMA máscara que a grade inteira.

    Cada aresta varria `lado × lado`: 0,46 s para 24 vértices em 512, quase
    tudo sobre pixels que nenhum polígono alcança. A borda da caixa é onde
    um erro de um pixel mora — por isso os casos com vértice exatamente no
    meio do pixel, fora da grade e côncavos.
~~~

## linha 1818 · _tubo_de_referencia (docstring)

~~~text
O tubo de antes: o plano extrudado em `fundo` camadas no raio.

    Com a inversão do plano da v8.3 — a pergunta aqui é só se DUAS camadas
    respondem o mesmo que `fundo` camadas, e não a da orientação.
~~~

## linha 1840 · teste_o_tubo_de_duas_camadas_e_o_de_antes (docstring)

~~~text
Duas camadas no raio respondem o que `fundo` camadas respondiam.

    O tubo é o mesmo plano em toda profundidade, e o vizinho mais próximo não
    interpola entre amostras. A pergunta que resta é a da COBERTURA: nenhum
    voxel do paciente pode cair fora das duas camadas — e é na oblíqua que a
    diagonal aperta.
~~~

## linha 1862 · teste_o_tubo_em_bits_e_o_mesmo_tubo (docstring)

~~~text
`Compacto` é o tubo byte a byte: fatia, interseção e linhas.

    Um booleano por voxel é um BYTE: 155 MB por tubo na TC de pescoço de 591
    cortes, e o teto é de doze. Em bits são 19 MB. A largura que NÃO é
    múltiplo de 8 é o caso da borda — o último byte leva enchimento.
~~~

## linha 1893 · teste_o_pixel_da_tela_e_quadrado (docstring)

~~~text
O corte sai com pixel quadrado em mm, e as linhas na MESMA grade.

    O palco mostra o corte num quadro com `object-fit: contain`, que preserva
    a proporção em PIXELS. Numa RM de 0,5 mm no plano e 1 mm entre cortes, o
    corte ortogonal saía achatado pela metade — e a linha fina junto.
~~~

## linha 1931 · _Pedido (docstring)

~~~text
O `Request` do FastAPI, só com o `json()` que as rotas leem.
~~~

## linha 1941 · teste_as_rotas_leem_a_serie_uma_vez (docstring)

~~~text
Rolar um corte não relê a série — e o UID vai junto na leitura.

    Cada rota chamava `engine.load_sitk(pasta)`: medido no banco, 12,4 s por
    leitura na TC de pescoço de 591 cortes e 1,7 a 3,0 s nas RM. A tela pede
    a projeção e três cortes ao mesmo tempo. E sem o UID, a pasta com duas
    séries abria sempre a primeira.

    A rota é chamada como função, com a leitura DUBLADA e CONTADA: o que roda
    é o código real, sobre um fantoma sagital anisotrópico.
~~~

## linha 1982 · teste_as_rotas_leem_a_serie_uma_vez

~~~text
 AS LINHAS NA GRADE DA IMAGEM: o `viewBox` do SVG e o PNG do corte
 têm de ser a mesma grade — senão a linha fina cai deslocada sobre
 a anatomia, e deslocada o bastante para parecer achado.
~~~

## linha 2004 · teste_as_rotas_leem_a_serie_uma_vez

~~~text
 OUTRA SÉRIE É OUTRA LEITURA — e a anterior sai antes.
~~~

## linha 2014 · teste_a_rm_entra_no_seletor (docstring)

~~~text
O seletor pede CT E MR ao `varrer`.

    A chamada não dizia `modalidades`, e o padrão do `varrer` é só CT: as RM
    de crânio pós-gadolínio — o exame que o autor pediu para projetar — nem
    apareciam na lista.
~~~

## linha 2049 · main

~~~text
 noqa: F401
 noqa: F401
~~~

## linha 2054 · main

~~~text
 ESTA LISTA E' O RUNTIME SEM numpy/SimpleITK: so as checagens
 de fonte. `teste_acumular_incidencias` MEDE geometria e nao
 cabe aqui -- por engano ele entrou nesta e nao na de baixo,
 e passou a nao rodar em lugar nenhum: a lista de baixo e' a
 que executa nesta maquina.
 AS DA TELA ENTRAM AQUI TAMBEM: o palco nao usa numpy nem SimpleITK.
 Deixa-las so na lista de baixo faria a tela deixar de ser exercida
 justamente no runtime de campo, que e onde ela roda.
~~~

## linha 2077 · main

~~~text
 Esta NAO entra em `TELA`: ela monta a rota de verdade sobre um
 fantoma, e fantoma precisa de SimpleITK.
~~~

## linha 2080 · main

~~~text
 v8.3: o que a primeira serie de verdade derrubou.
~~~
