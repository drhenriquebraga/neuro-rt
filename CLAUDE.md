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
- **A resolução é sempre a máxima** (`radai_nidus.LADO_ALTA`, 1024), e a
  opção saiu: nidus não se vê em resolução baixa. Cada projeção a 1024
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
  pronta; a fila ainda descarta o campo, e a bateria guarda a pendência em
  `PENDENTE_SUBSTITUIR_NA_FILA`). O acompanhamento lê o campo `rodando` de
  `/api/fila/estado`: com a fila parada, diz que o cartão espera o
  «Iniciar»; sem o campo, não inventa a situação. «A fila não responde» só
  depois de falhas seguidas; o acompanhamento para em 4 h, e aí diz que o
  cartão continua na fila.
- **A série se escolhe pela tabela do acervo da Suite** (C2, filtrada para TC
  e RM) ou pela aba «Aponte uma pasta», com a busca da Suite
  (`radai_dicom.buscar_series`); a tela não varre o `ROOT` sozinha ao abrir.
  As duas abrem por `POST /api/nidus/abrir` com a origem: a do acervo passa
  por `radai_tabela_acervo.resolver` (só o que está no acervo), a da pasta
  pelo bilhete. O `GET /api/nidus/forma` ficou para as baterias da Suite, e
  chama a mesma função.
  Ferramentas em cima, os três MPR empilhados à direita do visor, sem rolar
  em 1280×800. O brilho de processamento da casca acende na projeção e nos
  MPR; a barra da fila aparece recolhida, com contador.

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
- **GitHub** (`radioterapia-ai/nidus-rt`, privado): nada sobe daqui. A
  publicação é montada pela Suite, por manifesto, e o envio é ato do autor; a
  pasta não tem remote.
