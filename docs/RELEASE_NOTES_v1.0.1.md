# NEURO RT 1.0.1

Primeira disponibilização pública, com **Nidus RT habilitado**. Glioma RT,
Metastasis RT, Meningioma RT e Anatomia RT ficam apagados, sem acionamento e com
`[em construção]`. Novos processamentos dessas ferramentas também são recusados
por URL, API integrada e servidor de desenvolvimento.

O instalador e o primeiro uso apresentam o mesmo termo versionado. Cada etapa
exige uma confirmação explícita, registrada localmente. O termo complementa os
documentos da Local Suite e não aprova resultados.

Requer Local Suite 8.10 ou posterior **com o bootstrap e contrato de aceite
desta revisão** e o runtime preparado da base. O plugin usa o carregador, fila,
configurações e visores da suíte. Não instala bibliotecas no Python global.

- `NEURO_RT_OFFLINE_v1.0.1.zip`: payload completo transacional.
- `NEURO_RT_SETUP_v1.0.1.zip` e `NEURO_RT_SETUP_LATEST.zip`: instalador confiável,
  idênticos entre si; exigem payload e SHA externo ou consulta da release Latest.
- `NEURO_RT_PLUGIN_v1.0.1.zip`: atualização de código; exige os componentes exatos
  já instalados. Não é o instalador offline completo.
- `release-manifest.json` e `SHA256SUMS.txt`: inventários e identidades verificáveis.
- `NEURO_RT_SOURCE_v1.0.1.zip`: fontes; não substitui instalação.

O payload preserva os pesos, atlas e dois runtimes da entrega anterior. Desativar
cards não reduz seu tamanho. Nenhuma nova inferência científica foi executada
nesta revisão; foram verificados contratos, instalador, HTTP, interface e pacote.
Histórico, licenças, NOTICE e atribuições permanecem distribuídos.

Nidus faz construção geométrica e não detecta lesões. A interseção é referência
visual e não é exportada como alvo. Resultados são UNAPPROVED; a revisão e a
aprovação para tratamento cabem ao profissional responsável no TPS.
