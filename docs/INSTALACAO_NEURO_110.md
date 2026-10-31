# Instalação e transporte do NEURO RT1.1.0

Use primeiro a Local Suite8.12 ou posterior completamente instalada. O plugin
aproveita o Python e as bibliotecas dessa instalação.

## Pela suíte

Abra NEURO RT na home ou a seção NEURO RT nas Configurações. Leia o termo atual
e confirme a instalação/atualização. Aguarde os trabalhos da fila ou use a
interrupção explícita oferecida pela suíte. O preparo abre sua própria janela
de progresso, encerra a aplicação de forma coordenada, confere código e recursos
e reabre a suíte. Não feche a janela de preparo durante uma etapa em andamento.

No primeiro uso, o termo do plugin é confirmado separadamente. Cada abertura de
card também apresenta o aviso da fase de testes. Isso não aprova contornos.

## Computador com rede bloqueada

Em outro computador com internet e Local Suite compatível, obtenha o SETUP do
NEURO RT e extraia todo o ZIP. Abra START_HERE.cmd, selecione a suíte instalada,
leia os termos/licenças e escolha **Montar pacote offline para transportar**.
Escolha uma pasta nova. Aguarde a confirmação final antes de copiar a pasta.

Leve a pasta completa para a outra estação. Nela, abra Local Suite→Configurações
→NEURO RT e selecione a pasta local. A pasta correta contém START_HERE.cmd,
release-manifest.json, code e os recursos preparados. Não é necessário executar
scripts recebidos nessa estação; a própria suíte confere e instala a fonte.

O SETUP leve contém código e instruções de preparo. Em uma estação sem recursos
Neuro e sem rede, ele precisa ser complementado pela pasta offline completa.
Para atualizar só código, recursos íntegros já presentes podem ser reaproveitados.
Se o código local não for reconhecido, atualize também a suíte para uma versão
compatível; um arquivo de checksum colocado ao lado do pacote não concede confiança.

## Recuperação

Falha de download ou cópia não substitui a versão ativa nem os estudos. Corrija a
fonte/rede e tente novamente pelas Configurações. Downloads íntegros são
reaproveitados; arquivos parciais não são tratados como concluídos. A janela de
preparo mantém a indicação da etapa e um diagnóstico seguro.

O bundle offline fica apenas no computador que o montou e no meio de transporte
escolhido. Ele não é publicado como asset do GitHub e não inclui uma segunda
cópia do Python, um venv ou os dados clínicos da estação.
