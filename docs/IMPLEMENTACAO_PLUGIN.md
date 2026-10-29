# Implementação do plugin NEURO RT

Atualizado em 29/10/2026. Execução autorizada pelo usuário após o desenho e roadmap.
Este arquivo é o ponto de retomada versionado; o roadmap completo continua em
`docs/superpowers/plans/2026-10-29-neuro-rt-roadmap.md`.

## Estado real

| Unidade | Estado | Entrega |
|---|---|---|
| I01 | Implementado e revisado | Manifesto, compatibilidade, paths versionados, produção sem fallback de Python |
| D01 | Implementado e revisado | Contratos de estudo/resultado v2 e compatibilidade explícita v1 |
| D02 | Implementado e revisado | Associação de sequências e elegibilidade somente por metadados autorizados |
| M01 | Parcial | Catálogo declarativo, cinco adições candidatas, identidade dos artefatos; adapters novos pendentes |
| I05 | Preparação parcial | 16 arquivos copiados com SHA-256; histórico e tags importados; origem preservada |
| Exportação/visores legados | Corrigidos na fronteira atual | Imports modulares, gravador real, SVG/PNG e renderer do host |
| I02–I04, D03–D07, M02–M08, U01–U05, R01–R05 | Pendentes além das preparações descritas | Instalador transacional, integração nativa completa, novos motores e entrega final |

O plugin final ainda não está instalado/integrado na home. Os novos contratos
não substituem silenciosamente o fluxo HTTP v1. Os cinco novos candidatos não
estão anunciados como executáveis. Os motores novos exigem suas provas de pesos,
geometria e execução antes da distribuição. Não marcar os marcos C–H concluídos.

## Git e migração

- Repositório local criado em `C:/AI_PROJETOS/NEURO_RT`, branch `codex/neuro-plugin`.
- Baseline preservada em `7c024c9aa358a3322cd30552d182be92bdaf7839`.
- Repositório GitHub próprio criado privado: `drhenriquebraga/neuro-rt`.
- Histórico Nidus importado de fonte local em `refs/remotes/nidus/source`,
  commit `4067bddc3c875af62c6917362661d3d3d1d0036b`, 29 commits alcançáveis.
- Tags preservadas sob namespace `nidus/v8.5` até `nidus/v8.9`.
- Fontes, licença e inventário detalhados em `docs/MIGRACAO_NIDUS.md`.
- Nenhum repositório de origem foi excluído; não há release pública desta etapa.

## Decisões de integração descobertas no código

1. O host real é v8.9, commit `ed6f3f0`, e ainda não oferece o contrato novo.
   `host_min_version=null` é deliberado e resulta em incompatibilidade em produção
   até existir uma versão real com `local-suite/plugins/1`. Não substituir por 8.9
   para fazer um teste passar sem implementar o contrato no host.
2. Reconstruções 3D depende do core Nidus e de serviços de osso na tela Nidus.
   Antes de retirar o componente do bundle base, extrair o serviço compartilhado
   ou adaptar os consumidores com equivalência. A cópia das fontes não resolve isso.
3. O host modular tem engine em ContourLab e visores em Recon3D. A ponte usa o
   resolvedor existente `_componentes`, sem instalar `.pth` nem fixar diretórios
   de desenvolvimento na distribuição.
4. `radai_png` referenciado pelo protótipo não existe na suíte atual. A correção
   reaproveita `para_png`, `_png_com_contornos`, JS_3D e JS_MALHA reais. O viewer
   recebe o formato do metadata, com compatibilidade PNG de resultados antigos.
5. O acervo, fila nativa e instalador ainda precisam ser conectados aos novos
   contratos; nenhuma fila concorrente nova foi ativada nesta preparação.

## Regra de incerteza implementada

Classificação desconhecida ou contraditória permanece aviso. T1 sem informação
de contraste não prova ausência de contraste; T1/T1c são opções incertas nesse
caso. PRE/POST isolados podem ser cronologia operatória, por isso não bastam para
afirmar contraste. Agente nulo/em branco ou de tipo inválido não vira evidência
positiva. Marcadores explícitos e coerentes podem estreitar a sugestão.

Cada volume concreto é usado em no máximo um canal do mesmo modelo. Uma entrada
ausente não é preenchida por duplicação, e sujeitos/episódios não se misturam.
Runtime/peso indisponível gera razão técnica separada da ausência de sequência.

## Verificação

Baseline de 27 testes: dois testes de integração falhavam por imports antigos
(`engine` e `radai_png`) e o HTTP precisava de permissão de socket local.
Os imports/exportação foram corrigidos; o teste de exportação usa o gravador
real com DICOM sintético, conferindo UIDs, UNAPPROVED e arquivos exclusivos.

Na primeira rodada geral após as alterações, 118 testes foram executados com
resultado OK e três skips: FastAPI/httpx ausentes no Python Neuro e dois symlinks
com privilégio indisponível. O teste FastAPI passou separadamente pelo Python do
host; junctions reais passaram como alternativa aos symlinks comuns. Chrome real
verificou a imagem PNG embutida no SVG sob a CSP existente. A rodada final depois
das correções adicionais terminou com **121 testes, resultado OK, três skips**
em 14,976 s: 118 passaram nessa execução; o teste FastAPI pulado passou separado
pelo Python do host. Os dois skips restantes são symlinks comuns sem privilégio
Windows; os testes equivalentes com junctions reais passaram. O Chrome foi
executado na rodada final, sem skip de visualização.

Revisão independente: I01/D01 aprovados após correção da consistência de estado
(`failed` não aceita máscaras exportáveis); os três achados de incerteza D02 foram
reproduzidos, corrigidos e classificados como ADDRESSED na revisão focada final.
Os 16 arquivos copiados do Nidus tiveram seus hashes reconferidos pelo revisor.

Esses testes demonstram software/integração sintética, não validação clínica dos
modelos. Nenhum peso novo ou exame privado foi usado para esta etapa.

## Ordem recomendada para continuar

1. I02: implementar transação de instalação/ativação e o instalador PowerShell.
2. I03/I04: criar o conector conhecido do host, serviços e coordenação do atualizador.
3. Resolver a dependência reversa Recon3D/Nidus antes de remover o Nidus da base.
4. D03/D04/M02: primeiro corte vertical com um modelo existente e a fila compartilhada.
5. D05–D07/U01–U04: vários modelos por referência, saída única, persistência e UI.
6. M03–M08: motores novos individualmente, sem promover candidatos por omissão.
7. R01–R05: integração, instalação limpa, release e encerramento da migração.

Relatórios de trabalho e pacotes de revisão estão em `.superpowers/sdd/neuro-plugin`
(ignorados no Git). Os resultados relevantes e decisões devem continuar registrados
neste documento para sobreviver a outro checkout ou agente.
