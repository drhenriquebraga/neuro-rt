# NeuroRT — módulo externo do Local Suite

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
