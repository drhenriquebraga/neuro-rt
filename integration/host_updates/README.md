# Integração privada do Neuro RT no host

Os dois snapshots privados foram concluídos e conferidos contra suas bases
exatas. Local Suite contém 21 arquivos de implementação; Recon3D contém oito.
Os originais, índices e HEADs dos repositórios permaneceram intactos.

Estes patches preservam a implementação local necessária ao plugin. Fazem parte
da entrega **privada** do Neuro RT. Não foram enviados aos repositórios públicos
Local Suite e Recon3D. Não incluem documentos pessoais, transcrições, exames,
configuração local, runtime ou pesos.

`manifest.json` registra as revisões exatas de base, os arquivos incluídos e os
hashes SHA-256 dos patches. A entrega declara o host **8.10 em desenvolvimento**;
não representa uma versão 8.10 publicada. O pin público Recon3D `v8.9` continua
incompatível com esta integração: faltam os módulos comuns de projeção extraídos.
É necessário aplicar **ambos** os patches antes de montar o plugin, ou usar uma
entrega privada posterior que já contenha todas essas alterações.

O coletor do instalador exige que o Recon3D forneça
`app/radai_projection.py` e `app/radai_projection_bone.py`. Se faltar qualquer
um, a coleta para com o motivo e os nomes ausentes antes de gerar o pacote.
Isso também vale para `--dos-repositorios`: baixar o pin público Recon3D
`v8.9` não satisfaz essa exigência. A árvore adaptada pelos patches privados
contém os dois helpers; as conferências existentes de versão e árvore Git
continuam exigidas.

| Patch | Base | Bytes | SHA-256 |
|---|---|---:|---|
| `local-suite.patch` | `ed6f3f0169de0f1c589565362e60751ebcf97751` | 200032 | `2f8e636f59271004aea1f5ebeef4a5d95ba8127f1325e7a8ca654b88a61f6b23` |
| `recon-3d.patch` | `4841690db00104eecfe548d2afa9781891551a39` | 48512 | `73d34c8315fef2496cd228c2b5b7c2319a4934b436a88acb5a8e09b66a57ed5d` |

`AGENTS.md` ignorado e seu conteúdo histórico privado não constam dos patches.
`AGENTS_NEURO_CONTEXT.md` contém exclusivamente a seção NEURO RT autorizada
pelo coordenador. Se necessário, incorpore esse trecho ao contexto local de
instruções do host, preservando o restante do arquivo existente. Esse snippet
não modifica nem versiona automaticamente o arquivo ignorado.

## Aplicação em checkouts locais novos

Use cópias locais limpas dos dois repositórios nas revisões `base_commit` do
manifesto. Mantenha os nomes e a disposição de pastas irmãs esperados pelo
resolvedor de componentes. No host, confira:

```powershell
git rev-parse HEAD
git status --short
git apply --check --index C:/caminho/NEURO_RT/integration/host_updates/local-suite.patch
git apply --index C:/caminho/NEURO_RT/integration/host_updates/local-suite.patch
git diff --cached --stat
```

No checkout Recon3D correspondente:

```powershell
git rev-parse HEAD
git status --short
git apply --check --index C:/caminho/NEURO_RT/integration/host_updates/recon-3d.patch
git apply --index C:/caminho/NEURO_RT/integration/host_updates/recon-3d.patch
git diff --cached --stat
```

O primeiro comando de aplicação só verifica; o segundo prepara as alterações
localmente para revisão. A execução destes comandos não publica mudanças.
Não aplique por cima de trabalho existente: se a revisão ou a árvore diferirem,
use outro checkout limpo e confira o conflito antes de continuar. Não envie os
patches ou os commits resultantes a remotos públicos nesta entrega.

Antes de preparar o programa final, execute os testes de integração do Neuro,
Nidus, Recon3D, resolvedor e instalador registrados no relatório R05. O host
necessita Python com FastAPI para os testes HTTP; o Python científico do Neuro
não substitui esse runtime. A base continua sem Nidus e o plugin fornece a tela
uma única vez pelo adaptador. O core comum pertence à entrega Recon3D adaptada.

As tags e hashes públicos da trava continuam sendo os publicados; o patch não
transforma Recon3D público `v8.9` em uma dependência compatível. Distribuir uma
montagem exige preservar a árvore Recon3D adaptada e revisar a trava da entrega
privada junto ao coordenador. Não há download, atualização automática ou
publicação por meio destes arquivos.
