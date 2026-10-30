# NEURO RT 1.0.2 — instalação e reabertura

Esta revisão exige **Local Suite 8.11 ou posterior**, com o bootstrap de
instalação gerado desta revisão incorporado à base. Atualize a suíte antes do
plugin. Nidus permanece habilitado; os quatro cards em construção, os motores,
os pesos, os consentimentos e o estado `UNAPPROVED` permanecem com o mesmo
contrato da 1.0.1.

## Problemas identificados

O instalador anterior convertia exceções diferentes em uma mensagem genérica.
O callback de recarregar configurações também era aceito como se reabrisse o
processo. A extração e a conferência de dezenas de milhares de arquivos não
tinham acompanhamento suficiente na tela.

Uma reprodução isolada com o pacote público imutável 1.0.1, no Python 3.10.11,
durou 2.714,469 segundos. A publicação chegou a gravar
`installed_pending_restart` e a versão pendente correta, mas a limpeza de um
diretório temporário vazio com atributo ReadOnly falhou com `WinError 5` e
substituiu o resultado por erro. Isso comprova um defeito do fluxo antigo;
não determina a causa exata do relato da estação do usuário, cujo log não
estava disponível.

## Fluxo da revisão

1. A suíte reserva a fila compartilhada, obtém o pacote e verifica seu SHA256
   externo antes de interpretar o inventário. Código baixado não substitui o
   bootstrap confiável do host em uso.
2. O preparo informa a fase, arquivos e bytes durante cópia, extração,
   conferência e publicação. Atualizações persistentes são limitadas a quatro
   por segundo, além das mudanças de fase. Consulta de progresso não relê todos
   os pesos.
3. A publicação conserva a versão ativa anterior, grava a versão pendente e
   mantém os componentes imutáveis. Falha na limpeza após o commit conserva
   a instalação válida e permite repetir a limpeza segura. Uma falha secundária
   de limpeza no rollback não mascara a falha original.
4. A reabertura usa somente o callback dedicado `neuro_restart`, com retorno
   explícito `{"ok": true, "scheduled": true}`. Recarregar configurações não
   satisfaz esse contrato. A confirmação de reabertura é persistida antes de
   chamar o callback.
5. Sem callback disponível ou sem confirmação, o estado permanece pendente,
   para retomada sem novo download. Uma falha de ativação/reabertura restaura o
   apontador anterior e a pendência antes de liberar a fila. Falha ao restaurar
   mantém a reserva e informa `ROLLBACK_INCOMPLETE`.
6. Uma nova instância da suíte confere os artefatos com progresso próprio e
   monta o plugin. A tela só conclui a reabertura ao observar novo token/PID,
   versão esperada, estado pronto e montagem confirmada. Durante a espera, o
   indicador permanece abaixo de 100%. Uma pendência 1.0.1 é retomada como
   1.0.1, mesmo se a consulta anterior de Latest apontava 1.0.2.

Pedidos concorrentes que recebem `InstallReceipt.following=True` não ativam
versões nem solicitam reabertura. Erros expõem código e fase controlados;
paths, nomes de pacientes e texto bruto de exceções não entram no status.

Uma comparação isolada de 100 arquivos aquecidos mediu 1,186 s antes e
0,732 s após consolidar duas guardas duplicadas. O alvo continua tendo todos
os ancestrais conferidos, a resolução/contenção permanece igual e o hash só
é lido depois da guarda completa imediatamente anterior à abertura. Não há
cache de integridade. A amostra mede essa operação e não prevê o tempo total
de uma instalação fria.

## Distribuição e verificação

Os pacotes 1.0.1 e suas tags permanecem imutáveis. A candidata 1.0.2 deve ser
publicada sem promoção a Latest até que a base 8.11 esteja disponível. O
bootstrap gerado e os pacotes desta revisão devem corresponder às fontes
congeladas e aos respectivos SHA256. O recibo final de validação registra as
provas efetivamente executadas; build isolado não comprova instalação na
estação do usuário.

A rodada gratuita de Polish do transitions-agent preservou as animações
existentes. O recorte novo de acompanhamento da instalação já recebeu 100/100
e o serviço informou que não havia correção elegível a aplicar. O scan amplo
das fontes web do Neuro 0.11.1 marcou 96/100: nenhum componente reconhecido,
apenas um hover do protótipo legado, mantido conforme a restrição do usuário.
