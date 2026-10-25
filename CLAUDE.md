# Nidus RT · Radioterapia.AI Local Suite

A mesma lesão em duas incidências, e onde as duas se cruzam — a lógica da angiografia biplanar.

Componente da **Local Suite**. Os outros apps e a Suite (o comum, o
empacotador, o instalador e a integração) são pastas irmãs em
`C:\AI_PROJETOS`; a Suite é a pasta que tem `tools/_componentes.py` (hoje,
`AUTO_CONTORNO`). Na estação tudo vira um programa só — um processo, uma
porta, um `app\` — montado pela Suite a partir das pastas que têm o
`componente.json`.

## Com quem você está falando

Médico radio-oncologista e especialista em qualidade, trabalha com
Eclipse/ARIA. Responda sempre em português do Brasil, tom de colega de
engenharia, conciso, sem didatismo.

## O que é deste projeto

O `componente.json` lista os arquivos e as baterias. Trocar de pasta não muda
nome de módulo: `import radai_x` é igual em todos os projetos, e quem acha a
pasta é o integrador da Suite.

## A fronteira com os outros projetos

- **O que outro projeto usa de você é contrato.** Antes de mudar nome,
  assinatura ou comportamento disso, mande mensagem ao agente daquele projeto
  (e ao da Suite) e espere a resposta. A lista viva sai de
  `<python da Suite> <Suite>\tools\_componentes.py --contratos`, medida no
  código: se esta frase e o comando divergirem, o comando está certo.
- **O que você usa dos outros, você não edita**: peça ao dono.
- **Frase nova de tela**: o dicionário dos doze idiomas mora na Suite
  (`radai_phrases`, a chave é a frase em português). Mande a frase ao agente
  da Suite.
- **O registro na suíte** (cor, trilha, trilho, porta, cartões, montagem da
  tela, frases) é da Suite: a tela é sua, o lugar dela na suíte não.

## Regras clínicas que valem aqui

1. **Nada é aprovado automaticamente.** Toda saída é sugestão não aprovada,
   e revisão e aprovação são ato médico humano.
2. **PHI nunca entra no contexto.** Não leia, não copie e não imprima
   conteúdo de DICOM de paciente; teste com os fantomas sintéticos das
   baterias. O banco pseudonimizado `C:\AI_EXAMES_ANONIMOS` não afrouxa esta
   regra.
3. **Não commite DICOM.** Se um `.dcm` aparecer no repositório, avise e pare.
4. **Não somos autores dos modelos nem dos métodos de terceiros.** No texto
   que o usuário lê: «o TotalSegmentator desenha», nunca «nosso algoritmo».
5. Se um pedido aumentar risco clínico, diga com todas as letras e proponha
   o caminho seguro.

## O que não pode ser desfeito sem perceber

- **A interseção não vira número**, e a máscara do tubo nunca vai ao disco.
- É construção geométrica a partir do desenho do usuário: **não é volume de
  tratamento** (a linha da tela diz).
- As projeções podem mostrar o rosto: imagem de série real não sai da
  máquina.
- A projeção usa o núcleo 3D do Recon3D (`radai_recon3d`): contrato.
- **E o Recon3D usa o osso daqui** (onda 5 da v8.7): o Vascular das
  Reconstruções tira o osso pelo `radai_nidus_screen.osso_da_segmentacao`
  (contrato novo, que o `--contratos` mede) e pelo método `tirar_osso` da
  série que o `radai_nidus.abrir` devolve (método, que o `--contratos` não
  vê). Mudar a assinatura, o que eles devolvem ou a guarda que nunca deixa
  vaso entrar no osso é avisar o agente do RECON_3D antes.
- **Série que a transposição para LPS não aceita é recusada na abertura**
  (`radai_nidus.SerieRecusada`: imagem colorida, volume que não é 3D, poucos
  cortes), com o motivo, e não é relida a cada pedido: era a causa do
  «ValueError: axes don't match array». **Cada ação vira um estado salvo** no
  armazenamento da aba (`sessionStorage`), sob a chave que o abrir devolve
  (`radai_nidus_screen.chave_da_serie`: a impressão SHA-256 do UID, sem
  caminho e sem UID), e não sob o bilhete, que muda a cada processo: reabrir
  a série na mesma aba, até depois de o servidor reiniciar, traz a marcação
  de volta. `/api/nidus/estado` só devolve o último erro da série, que a
  tela mostra. Erro de projeção volta ao último estado bom e avisa; a
  segunda falha seguida trava a série, grava os parâmetros bons e oferece
  «Tentar de novo», que a reabre (o Guardar volta com ela). Erro da
  retroprojeção guarda a incidência como não cruzada, com «Cruzar de novo»;
  as linhas que falham são refeitas uma vez por ato, e a segunda falha
  avisa. As rotas de imagem respondem 422 ou 500 com o motivo, e não 404
  calado.
- **Só o lápis** (saíram «cliques» e «circular a área»): soltar o clique
  fecha a área do último ponto ao primeiro. LAO/RAO e CRA/CAU em barra de
  arrastar, e a lista das guardadas diz RAO e CAU no ângulo negativo.
- **A projeção que vale é a de resolução máxima** (`radai_nidus.LADO_ALTA`,
  1024): desde a v8.7, durante qualquer arraste de ângulo (as barras, o
  mapa, o 3D) a tela mostra uma prévia a 256, com selo e estado âmbar, e o
  **lápis fica travado até a projeção cheia chegar** — nidus não se desenha
  em resolução baixa. Cada projeção a 1024
  reamostra uma grade de ~0,75 GiB, então `/api/nidus/projecao` roda **uma
  por vez** (uma trava no servidor), e a pedida que envelheceu na espera não
  roda: a tela manda o número do pedido e a aba (`n`, `t`), e a mais velha
  responde 409. **Toda série abre nos padrões** (invertida, MIP, todo o
  volume, janela angio, LAO 0 / CRA 0, osso fora, planos no meio); só o
  estado salvo dela os muda.
- **O osso sai da projeção pela segmentação que o ContourLab gravou**: o
  FULL ou o OAR, o mapa de rótulos do Estudo 3D e, sem eles, o OAR_Fast
  (`radai_nidus_screen.ORDEM_DO_OSSO`), por
  `radai_viewseg.mascaras_da_serie` (o contrato C6), uma chamada por pasta da
  série, com `radai_nidus_screen.e_osso` como filtro. Série sem segmentação:
  a tela oferece «Segmentar primeiro (AUTO)» pela fila única (C1), e nunca
  adivinha o osso pela densidade. Série com entrega (OAR ou OAR_Fast) sem
  osso que sirva, ou que a fila deu como pronta sem osso: o botão diz
  «Segmentar em AUTO (substitui a entrega)», pede confirmação e manda o
  pedido com `substituir` (sem ele o lote pula a série com marcador de
  pronta). Desde a 2e a fila guarda o campo na carga e no `fila.json`, e o
  lote refaz a série, substituindo a entrega pela regra do «Rodar agora»; a
  bateria virou a pendência (`PENDENTE_SUBSTITUIR_NA_FILA = False`). O acompanhamento lê o campo `rodando` de
  `/api/fila/estado`: com a fila parada, diz que o cartão espera o
  «Iniciar»; sem o campo, não inventa a situação. «A fila não responde» só
  depois de falhas seguidas; o acompanhamento para em 4 h, e aí diz que o
  cartão continua na fila.
- **A série se escolhe pela tabela do acervo da Suite** (C2, filtrada para TC
  e RM) ou pela aba «Aponte uma pasta», que desde a v8.7 é a varredura da
  casca (abaixo); a tela não varre o `ROOT` sozinha ao abrir.
  Desde a v8.6 as duas abas moram no popup da casca
  (`radai_ui.popup_de_serie`, as abas à esquerda), e o cartão «Carregar
  série» da tela de trabalho o reabre e diz a série aberta.
  As duas abrem por `POST /api/nidus/abrir` com a origem: a do acervo passa
  por `radai_tabela_acervo.resolver` (só o que está no acervo), a da pasta
  pelo bilhete. O `GET /api/nidus/forma` ficou para as baterias da Suite, e
  chama a mesma função.
  Desde a v8.7 o leiaute é o do estudo validado: a série na cabeça pelo
  `radai_ui.cartao_de_serie`, as barras LAO/RAO e CRA/CAU coladas à
  projeção, o 3D da caixa e a sala num segmentado da casca, e o MPR numa
  faixa embaixo do 3D, com a legenda — sem rolar em 1280×800, 1366×768,
  1920×1080 e 1280×720. O brilho de processamento da casca acende na
  projeção e nos MPR; a barra da fila aparece recolhida, com contador.

**O que a v8.7 mudou** (o Nidus no padrão do angioview: o estudo de design
navegável, validado por um segundo agente, e então o código, sem copiar
código nem arte do angioview; o registro no `docs/ENTREGA-V87-25OUT2026.md`
da Suite, as decisões na seção «v8.7» de `docs/DECISOES-V85.md`):

- **A convenção do arco em C numa função só**
  (`radai_nidus.matriz_da_incidencia`, as linhas r, v, u, ortonormal e sem
  espelho), usada pela projeção, pelo tubo e pelos eixos
  (`radai_nidus.eixos_da_incidencia`), e o JS igual a ela
  (`radai_nidus.JS_CONVENCAO`, conferido em 50 ângulos): positivo é LAO e
  CRA; LAO põe o detector à esquerda; Towne é CRA 30 e Caldwell CAU 15;
  Perfil D é RAO 90 e Perfil E LAO 90 (`radai_nidus.INCIDENCIAS`). A
  convenção de antes trocava o sinal de dez das trinta marcas do fantoma.
  **A chave da aba passou a `radai_nidus_v2_<impressão do UID>`**, para um
  desenho salvo na convenção velha não voltar com a matriz nova.
- **As barras e o mapa**: Page Up/Down giram 10°, o campo aceita vírgula, a
  leitura grande diz «RAO 30° · CRA 20°», cada botão de incidência mostra o
  ângulo, e o mapa de incidências aceita clique e arraste, com encaixe a
  7 px (Shift tira o encaixe) e as setas.
- **«Acompanhar a caixa»**: a pegada da caixa sai dos oito cantos levados ao
  LPS pela matriz da série (`radai_nidus.pegada_da_caixa`); fora da pegada a
  projeção fica velada, e a pegada aparece tracejada quando não acompanha.
- **O 3D da caixa**, em WebGL pelo visor das Reconstruções
  (`radai_recon3d_gl`, contrato com o RECON_3D): vista do detector, vista
  livre com as placas, «Ver através» e o recorte no espaço da série. As
  malhas saem do servidor só para a caixa (`radai_nidus.malha_da_caixa`,
  por `POST /api/nidus/malhas` e `GET /api/nidus/malha` com bilhete): o vaso
  por limiar (relativo na RM) menos o osso dilatado, em passo de no máximo
  1 mm e sem suavizar; o osso, só o da segmentação do ContourLab; a pele só
  na TC; teto somando 80 mil triângulos (`radai_nidus.TETOS_DA_MALHA`,
  recusa com o motivo, `radai_nidus.MalhaRecusada`). O STL leva UNAPPROVED
  no cabeçalho e fica só na memória do processo (até
  `radai_nidus_screen.TETO_MALHAS_MB`), e sai com a série e com a
  ociosidade: **nada se exporta, e a interseção nunca vai ao 3D**. Sem a
  segmentação, nenhum osso é tirado pela densidade, e o canto do 3D diz
  que o osso não foi separado. O 3D mostra o rosto.
- **A sala** é desenhada no código (arco, detector, tubo, carro, coluna,
  mesa, paciente e o feixe em prisma), com os detectores fantasmas das
  incidências guardadas e o aviso «ilustrativa» no canto: projeção
  paralela, sem colisão nem distância fonte–detector. **O arco do Tripo
  (c-arc.glb) não entrou**: pelos Termos do Tripo, o que se gera no plano
  grátis é do Tripo, e só o plano pago dá o direito de distribuir; o plano
  em que ele foi gerado não está registrado (`docs/PENDENTES-V88.md` da
  Suite).
- **«Guardar incidência» apagado diz por quê** (`uiPorQue`), e o âmbar ficou
  só para a caixa e o traço (saiu da paleta das guardadas).
- **O osso num STUDY com nome próprio** sai pelo nome padrão da descrição da
  ROI (o `radai_viewseg.mascaras_da_serie` do ContourLab decide por ele).
- **O «Aponte uma pasta» é a varredura da casca** (C-VARRER): o
  `uiVarrerLista` com o uso «series» do `radai_varrer` da Suite, as
  modalidades da tela e o mínimo de cortes (`radai_nidus_screen.MIN_CORTES`),
  o filtro de data, a estrela da favorita e o «Parar a leitura» da casca; os
  itens vão pelo bilhete (o mapa `ND.porB`), e não pelo índice da lista; o
  campo vazio treme e pede a pasta. Saiu a rota POST /api/nidus/series.

## Como trabalhar

- **Regra do autor (12/10/2026):** sem as skills do superpowers e do
  impeccable, e sem rodar a bateria inteira como ritual. Rode só a bateria
  que a mudança toca.
- **Uma bateria:** `python tools\test_<nome>.py` com o Python do `.venv` da
  Suite (o `_python.txt` daqui aponta para ele; `--ligar`, na Suite, põe as
  pastas de todos os projetos no caminho desse Python). **As deste projeto:**
  `verify.cmd`.
- **Código sem comentário narrativo**: só `# GUARDA: <motivo técnico curto>`,
  sem data, nome, citação ou referência a documento. O porquê de cada trecho,
  como estava antes da limpeza, está em `docs/aprendizado/`.
- **Guiado por log**, honesto sobre incerteza, e afirmação sobre o que o
  programa faz se mede contra o programa.
- **GitHub** (`radioterapia-ai/nidus-rt`, público desde 20/10/2026, com o
  relato privado de vulnerabilidade ligado): nada sobe daqui. A
  publicação é montada pela Suite, por manifesto, e o envio é ato do autor; a
  pasta não tem remote.
