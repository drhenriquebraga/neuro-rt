# NeuroRT — módulo externo do Local Suite

## Entrega atual — 30/10/2026

O pedido explícito mais recente autoriza a fase de testes 1.1.0, substituindo o
recorte Nidus-only abaixo: cinco cards habilitados, aceite de testes por entrada,
motores e pesos disponíveis, consenso Nidus ajustável/exportável UNAPPROVED e
MPR principal. Local Suite 8.12 é responsabilidade do chat LOCAL SUITE I: manutenção
externa visível, encerramento/reabertura e seleção de instalador/bundle local.
Neuro fornece SDK confiável, START HERE guiado e montagem de bundle offline LOCAL.
GitHub recebe somente SETUP versionado e SETUP_LATEST. Reutilizar o Python completo
da suíte e suas bibliotecas; extras compatíveis em overlay próprio, sem copiar
Python/venv nem substituir versões da base. Inferências solicitadas usam somente
fantomas e demos públicas desidentificadas, nunca dados clínicos do serviço.
Leia o desenho e plano `2026-10-30-neuro-beta-110` antes de continuar.

A revisão 1.0.1 habilita somente Nidus RT. Os outros quatro cards permanecem
`[em construção]`, apagados e sem execução por URL/API. Não ampliar catálogo ou
rodar novas inferências para esta integração. Leia `docs/INTEGRACAO.md` e
`docs/HANDOFF_LOCAL_SUITE_2026-10-30.md`: o bootstrap e o primeiro uso compartilham
um termo versionado; os dois atos são explícitos e distintos. A montagem é tardia
no host; não usar app.add_middleware depois que FastAPI iniciou.

O Dr. Henrique autorizou tornar neuro-rt público e publicar a revisão como Latest
com instalador versionado e SETUP_LATEST, após auditoria de fontes/histórico e
verificação do pacote. A integração atual de AUTO_CONTORNO e sua release 8.10
pertencem ao agente da Local Suite; não editar o host nesta coordenação.

## Alinhamento atual — 29/10/2026

O desenho e o roadmap foram aceitos. O usuário autorizou explicitamente
**iniciar a codificação** em 29/10/2026. Leia
`docs/superpowers/specs/2026-10-29-neuro-rt-plugin-local-suite-design.md` e
`docs/superpowers/plans/2026-10-29-neuro-rt-roadmap.md` antes de continuar.
O roadmap liga os cinco planos por subsistema e distingue fontes existentes de
arquivos propostos. As instruções abaixo descrevem a base v0.2; a integração do
host prevista no novo desenho está autorizada. Registre progresso e evidências
em `docs/IMPLEMENTACAO_PLUGIN.md`; não declare o plugin concluído antes dos marcos.

Responda em português. O escopo inclui este projeto, a migração de NIDUS_RT e
as mudanças necessárias de integração no host AUTO_CONTORNO. Preserve outros apps.

Leia primeiro README.md e docs/INTEGRACAO.md. Consulte somente os arquivos do
módulo ou da interface que estiver mudando. Não releia o Local Suite inteiro.

Não leia nem imprima PHI; testes usam imagens sintéticas. Por pedido explícito
de 11/10/2026, demos públicas desidentificadas podem ser baixadas e processadas
em cache local, com fonte/licença registradas, sem dados clínicos do serviço.
Toda segmentação exige pedido explícito. RTSTRUCT sempre UNAPPROVED, com
procedência nas ROIs. Nenhuma aprovação automática, CTV ou transferência
RM–TC implícita. Use o gravador existente do host; não crie outro.

Não inclua imagens, resultados, ambientes Python nem pesos no Git. Preserve
as licenças originais em qualquer distribuição de código ou pesos.

Verificação: `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Servidor: `.venv\Scripts\python.exe -m neuro_rt.server`.
