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
