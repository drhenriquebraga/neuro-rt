# NEURO RT 1.0.2 — instalador leve

O NEURO RT instala apenas o código do plugin, termo e licenças. Ele reutiliza o mesmo Python e os recursos já presentes no Local Suite completo. Para o Nidus habilitado nesta entrega, o delta de pacotes e pesos é zero.

Requer Local Suite 8.11 ou posterior com o bootstrap desta revisão. Nidus RT está habilitado; Glioma RT, Metastasis RT, Meningioma RT e Anatomia RT permanecem em construção, sem provocar downloads científicos.

## Distribuição

Somente dois assets: NEURO_RT_SETUP_v1.0.2.zip e NEURO_RT_SETUP_LATEST.zip, byte a byte idênticos, com aproximadamente 323 KB. O GitHub não recebe OFFLINE, PLUGIN, Python, wheels ou pesos. O cliente fixa o SETUP versionado e seu digest SHA256 da API; não baixa manifesto de inventário separado nem resolve LATEST outra vez durante o preparo.

## Correções

- Instalação CODE-only com execution_mode=host e binding do Python fornecido pela própria suíte. Nenhum pip, ambiente paralelo, downgrade ou cópia de bibliotecas do desenvolvedor.
- Pendências do desenho antigo são migradas para o SETUP leve antes de ativar. Dados, configurações e caches anteriores são preservados.
- Limpeza ReadOnly segura e best-effort após commit: falhar ao remover temporários não invalida a instalação boa. Falhas de rollback conservam o erro original.
- Progresso por fase/arquivos/bytes, diagnósticos controlados e reserva da fila. Ativação permanece ocupada e reabertura exige recibo explícito.
- Sucesso visual exige PID/token novos, versão esperada e montagem confirmada. Reload de configurações não é confirmação de reabertura.

## Verificação e limites

172 testes por Python 3.10 e 3.12, além de testes de navegador. A prova real isolada com API/provider da suíte completou em 8,95 s: um download de SETUP, zero antes do aceite, zero Python/wheels/modelos, mesmo interpretador 3.10.11, novo processo e montagem 1.0.2 pronta. Dez arquivos críticos e versões da base permaneceram idênticos. O recibo detalhado está em INSTALL_VERIFICATION_v1.0.2.json.

O transporte GitHub foi simulado nessa prova local e é conferido separadamente na publicação anônima. Nenhum aplicativo real foi fechado e nenhuma inferência foi executada. O recorte de pesquisa e o estado UNAPPROVED dos resultados permanecem.

O Polish gratuito foi concluído no acompanhamento novo; não houve correção elegível nem mudança nas animações existentes.
