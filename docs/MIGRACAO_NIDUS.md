# Preparação da migração Nidus RT

Data: 29/10/2026. Estado: **migração funcional implementada e verificada**;
integração de release e aceite R05 permanecem com o coordenador. A origem
NIDUS_RT continua intacta. Os registros de cópia abaixo descrevem a preparação
I05; os arquivos operacionais app/tools foram depois adaptados por U05.

## Atualização U05 — propriedade e provas

O core geométrico foi extraído para `RECON_3D/app/radai_projection.py`, sem
alteração da árvore sintática Python da baseline. `app/radai_nidus.py` agora
é um alias do mesmo objeto de módulo, incluindo funções privadas e a classe
Serie; não há segunda implementação científica. A leitura de osso existente
foi extraída para `radai_projection_bone.py`, compartilhada pelas duas telas.
As atribuições Apache-2.0 foram mantidas no Recon3D e no NOTICE do host.

Nidus sai da trava, da descoberta e das cópias da base. O diretório antigo
não é apagado nem alterado. `_componentes.ligar_caminho(..., extras=(app,))`
liga a fonte do plugin apenas na montagem e resolve seus arquivos para a
bateria. O coletor e o preparador usam somente as pastas da base, inclusive
se o plugin foi ligado no mesmo processo. Caminhos antigos NIDUS_RT vindos
de `.pth` são descartados dessa ligação.

`integration/nidus_bridge.py:montar(app, host_services)` monta a tela uma vez.
O adaptador principal o chama somente na integração com o host. O recibo em
`app.state.neuro_nidus` e a guarda da própria tela impedem nova montagem e
novos closures. `/neuro/nidus` delega a `/nidus/projecao`; as APIs antigas
`/api/nidus/...` e a chave de estado da série continuam iguais.

Provas de 29/10: Nidus **519/519**, Recon3D **443/443**, Recon3D v8.4
**181/181**, resolvedor/trava **84/84** e seis testes de migração. O navegador
usou fantomas TC e RGB em 1600×900 e 1280×800. A bateria original do Nidus
teve 489/493: três expectativas da navegação anterior e um clique durante a
varredura incremental. As expectativas foram atualizadas para NEURO RT e o
roteiro agora aguarda bilhetes válidos antes de escolher, sem alterar o fluxo
do produto. A prova isolada de Recon3D abre páginas e o Vascular sem importar
Nidus, sua tela, NumPy ou SimpleITK. O relatório detalhado está em
`.superpowers/sdd/neuro-plugin/U05-report.md`.

As tabelas abaixo continuam sendo o registro dos bytes copiados inicialmente,
não os hashes dos arquivos operacionais adaptados. Os originais e seu histórico
continuam recuperáveis no repositório NIDUS_RT preservado e nos refs importados.

## Origem e rastreabilidade

Origem: `C:/AI_PROJETOS/NIDUS_RT`. Destino: `C:/AI_PROJETOS/NEURO_RT`.
O inventário de referência é
`.superpowers/sdd/neuro-plugin/host-migration-audit.md`. Os 16 hashes atuais
da origem foram comparados com esse audit antes da cópia; todos coincidiram.
Cada destino foi conferido com SHA-256 após cópia binária, sem adaptação.

Baseline histórica registrada pela auditoria de 29/10/2026:
HEAD `4067bddc3c875af62c6917362661d3d3d1d0036b`, 29 commits alcançáveis,
tags no HEAD `v8.7.1`, `v8.8` e `v8.9`; árvore limpa e nenhum remote
configurado na ocasião. Estes metadados vêm da auditoria, sem nova consulta Git
nesta preparação. As fontes e o repositório de origem permanecem intactos e
recuperáveis no local. Após a cópia, o coordenador importou os 29 commits no
Git do Neuro em `refs/remotes/nidus/source` e as tags sob `nidus/v*`, sem alterar
a origem. O repositório privado `drhenriquebraga/neuro-rt` foi criado. A retirada
do componente da base e a integração funcional continuam pendentes I05/U05/R05.
Nenhum repositório foi excluído.

## Inventário integral dos 16 arquivos

Caminhos relativos às raízes acima; SHA-256 da origem e do destino são iguais.

| Origem | Destino | SHA-256 de ambos |
|---|---|---|
| `.gitattributes` | `docs/nidus/original/gitattributes.txt` | `e0cb4c8e107fc4e41ec9be3b446bc0fe29e39d43a983c6f0ae2c79b034856072` |
| `.githooks/pre-commit` | `docs/nidus/original/.githooks/pre-commit` | `fbff5204c9b730363d7a4c604ad16ab3fe98eff13bcf65a57448d3dfd28338a6` |
| `.gitignore` | `docs/nidus/original/gitignore.txt` | `72010b2b8a2f831147214408c99ed1270855e28ec71a5533deb9c8c99706caa2` |
| `CLAUDE.md` | `docs/nidus/original/CLAUDE.md` | `3fec4530fcc4241fd8a005ee1d9255ad216ac8008f7dea85fbdb4ced5532b0b2` |
| `LICENSE` | `licenses/NIDUS_RT_APACHE_2.txt` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `README.md` | `docs/nidus/original/README.md` | `3cedcdb8e25523ee4cdac7e21e6bf5a13ec6178c98f170e889ab98a856e5afad` |
| `SECURITY.md` | `docs/nidus/original/SECURITY.md` | `979d89ee61f34f1201f79985552a3d77127ee6f89b8810fac112bdfbe58c990c` |
| `app/radai_nidus.py` | `app/radai_nidus.py` | `f02c9016736b463190f9e3a6452cdb9030c5afbbc20896446b8a396ba965f1d8` |
| `app/radai_nidus_screen.py` | `app/radai_nidus_screen.py` | `56fc6d64c23273bc65005e7e2bbc44e621c95ef10c4e072683cabfebb0c7f8cc` |
| `componente.json` | `docs/nidus/original/componente.json` | `708187182d799fb7b10db6d68d6cba400f165acd1e0f0654a5e3d1b5ea3d9fd9` |
| `docs/DECISOES-V85.md` | `docs/nidus/DECISOES-V85.md` | `07fa974d9581e5d039cee7d85c6c62b0e46faa38d62bc1adce3caf978b985ddd` |
| `docs/aprendizado/app/radai_nidus.py.md` | `docs/aprendizado/app/radai_nidus.py.md` | `fd0bbeaa91b2aee1a0681b83c14fe778197d61def3e6713628e1b6f1c111e2d0` |
| `docs/aprendizado/app/radai_nidus_screen.py.md` | `docs/aprendizado/app/radai_nidus_screen.py.md` | `c642e59390ebfe3f9367d3ae2be8a7d51fcbe577ef986e6b4365553327a5a5c7` |
| `docs/aprendizado/tools/test_nidus.py.md` | `docs/aprendizado/tools/test_nidus.py.md` | `b702ca063defa35c87cb86b0abb946fa765a7ed1b24801a6672f9b591e4fb516` |
| `tools/test_nidus.py` | `tools/test_nidus.py` | `e6c5ee01899a24c255adcb5f220f12fe803f8c3d2d35f6e8f4c196112841a9cd` |
| `verify.cmd` | `docs/nidus/original/verify.cmd` | `b14cd5e34ece6a524bac8a0ddb013f945c6488b2ec15cb40c87a5ba76ac9af02` |

## Licenças e arquivos arquivados

A licença Apache-2.0 original permanece integral em
`licenses/NIDUS_RT_APACHE_2.txt`. O NOTICE recebeu apenas um aviso Nidus;
seus bytes anteriores, com os avisos MIT e BSD, foram conservados como prefixo.
README, CLAUDE, SECURITY, manifesto, verify, atributos Git, ignore e hook são
**documentos originais arquivados** em `docs/nidus/original`; não representam
instruções atuais nem ativação de hooks/manifesto. Não foi criado
`componente.json` na raiz do Neuro. Não foram editados LICENSE, AGENTS.md,
.gitignore nem quaisquer fontes copiadas.

Os antigos atributos e ignore foram arquivados com extensão `.txt` para que
suas regras não sejam ativadas pelo Git do destino. Seus bytes/hashes foram
preservados. Os 16 arquivos migrados usam atributos próprios de preservação de
bytes; whitespace histórico não foi normalizado durante a cópia.

Os destinos `docs/nidus/original` e `licenses/NIDUS_RT_APACHE_2.txt` seguem
a decisão explícita desta preparação; diferem dos nomes sugeridos no audit,
mas preservam os mesmos bytes e a rastreabilidade nesta tabela.

## Limites e continuidade

- Nenhum arquivo versionado do inventário foi excluído da cópia. Foram excluídos
  deliberadamente dados, imagens, resultados, pesos, runtimes, configuração
  privada, `_python.txt` e metadados internos de `.git`. Não foram lidos
  nem copiados dados clínicos, runtime ou segredos.
- A origem e o host não foram alterados. O core antigo continua necessário:
  Recon3D importa `radai_nidus` e `radai_nidus_screen`, inclusive abertura,
  geometria e remoção de osso. Não retirar NIDUS_RT da distribuição antiga
  antes de resolver essa dependência reversa e provar equivalência.
- Os arquivos em app/tools são cópias preparadas; não estabelecem carregamento
  nem propriedade ativa. A montagem futura precisa garantir uma única origem
  por módulo e uma única montagem/closure por rota. Nenhum renderer foi editado.
- A ativação do plugin, alteração dos coletores/travas/preparo do host, resolução
  dos consumidores Recon3D, regressão sintética Nidus/Recon3D e prova U05 estão
  pendentes. O teste e verify originais dependem da Suite; copiá-los não prova
  funcionamento isolado. Nenhuma bateria funcional foi executada nesta etapa.
- Antes de R05: preservar o histórico em artefato recuperável verificado,
  conferir o repositório privado de destino, completar os aceites de I05/U05
  e revisar o inventário. Nenhuma exclusão da origem está autorizada aqui.

## Verificação realizada

16/16 fontes coincidem com o audit e 16/16 destinos coincidem com as fontes por
SHA-256. Nenhum destino preexistente foi sobrescrito. Avisos anteriores do NOTICE
preservados byte a byte. Validação funcional não realizada; I05/U05 pendentes.
