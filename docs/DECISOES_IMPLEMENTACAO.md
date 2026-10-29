# Decisões de implementação e seus limites

Este registro reúne as decisões delegadas durante a construção. O desenho aprovado
continua sendo a referência funcional; estas escolhas não autorizam publicar código
privado nem alterar exames de uso.

| Decisão | Motivo | Custo de uma revisão futura |
|---|---|---|
| Repositório próprio e branch `codex/neuro-plugin` | A pasta NEURO_RT iniciou sem uma main anterior; pesos e runtimes não foram duplicados em outro checkout | Reorganizar a integração Git, preservando o histórico importado |
| A autorização de codificação substitui o bloqueio documental dos planos anteriores | O usuário aprovou explicitamente iniciar a implementação | Reverter commits se a autorização for reinterpretada |
| Trabalho paralelo somente em arquivos com dono definido | Evitar sobreposição de mudanças nos contratos comuns | Reorganizar tarefas e repetir apenas verificações afetadas |
| Baseline preservada antes das mudanças; dados e ambientes fora do Git | Permitir revisão e recuperação sem distribuir exames ou pesos pelo repositório | Preparar os artefatos externos ao clonar a fonte |
| Acesso autorizado ao host fora da pasta principal, preservando alterações alheias | A integração depende do Local Suite real; execução passou pelo revisor automático de acesso | Aplicar os patches em outro checkout se o host local mudar |
| Bytes históricos do Nidus preservados no histórico importado | Conservar procedência, licenças e comparação dos 16 arquivos migrados | Manter atributos locais de whitespace nos arquivos históricos |
| Runtime científico CPU adicional, isolado do host e do Raidionics | Compatibilizar Torch/MONAI/DIPY/ANTs com as bibliotecas distribuídas | Distribuição maior; GPU exige runtime próprio verificado |
| Nomes lógicos sintéticos associados a IDs opacos | Os visores precisam identificar seus arquivos sem publicar caminhos privados | Manter o mapeamento no store e preservar revisões |
| Manifesto limitado a 16 MiB, com os demais limites e SHA-256 preservados | O inventário real de cerca de 36 mil arquivos ultrapassou 8 MiB; não remover bibliotecas para caber | Maior leitura de metadados, ainda limitada e validada |
| Integração host/Recon preservada em patches privados | Os repositórios-base são públicos e o NEURO RT é privado; o bootstrap novo não foi divulgado publicamente | Aplicar ambos os patches ou preparar uma base privada compatível antes de instalar |

A entrega CPU não promete GPU, Windows LTSB ou precisão clínica a partir de
fantomas. Os tempos de instalação e inferência medidos pertencem à estação de
desenvolvimento e ficam na matriz de evidências. O repositório Nidus original
permanece intacto. A publicação da base e dos componentes públicos exige uma
decisão de distribuição separada.
