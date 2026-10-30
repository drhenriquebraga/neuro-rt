# NEURO RT — plugin do Local Suite

Primeiro plugin opcional da suíte. Na versão 1.0.1, **Nidus RT está habilitado**;
Glioma RT, Metastasis RT, Meningioma RT e Anatomia RT aparecem desativados com
`[em construção]`. Seus motores ficam preservados para desenvolvimento, com
novas execuções bloqueadas nesta entrega. A instalação fica em `Plugins/NEURO RT`; navegação,
fila, carregamento de séries, configurações e visores pertencem ao Local Suite.

O [handoff 1.0.1](docs/HANDOFF_LOCAL_SUITE_2026-10-30.md) registra o recorte de
disponibilidade, o aceite comum e a situação efetiva da publicação.
A versão anterior 1.0.0 foi implementada, revisada e empacotada para entrega privada
offline. Os arquivos e as instruções estão em [ENTREGA_V1](docs/ENTREGA_V1.md),
com [evidências e limites](docs/VALIDACAO_PLUGIN.md). Naquela entrega privada não
houve publicação de assets. A disponibilização pública da revisão 1.0.1 é
registrada no handoff e nas [notas da versão](docs/RELEASE_NOTES_v1.0.1.md).

## Uso e comportamento

1. Abra NEURO RT na home da suíte compatível (contrato `local-suite/plugins/1`,
   versão mínima 8.10 com bootstrap desta revisão). Se ausente, leia e aceite o
   termo do plugin antes de confirmar a instalação.
2. Na primeira abertura, confirme o mesmo documento versionado. O aceite da
   instalação e o primeiro uso são atos distintos; nenhum deles aprova resultados.
3. Escolha Nidus RT e use suas ferramentas geométricas e os visores da suíte.
   A interseção é uma referência visual e não é exportada como alvo.
4. As demais funcionalidades estão em construção, inclusive por URL e API.
   O catálogo científico abaixo documenta motores preservados, sem os habilitar.

Resultados continuam `UNAPPROVED`; revisão, edição, fusão e aprovação clínica
pertencem ao TPS e ao profissional responsável. Não há criação de CTV.

O seletor de modelos não tem modos AUTO ou FAST. A preferência global de
processamento auto/CPU/GPU é uma configuração diferente; GPU estrita não faz
fallback silencioso. Os ambientes distribuídos e testados nesta entrega são CPU.

## Catálogo científico preservado — em construção

| Motor | Entrada | Saída |
|---|---|---|
| Raidionics GBM pré-operatório | T1 com contraste | Tumor binário |
| Raidionics glioma de baixo grau | FLAIR | Tumor binário |
| Raidionics meningioma | T1 com contraste | Tumor binário |
| Raidionics metástase | T1 com contraste | Tumor binário |
| Raidionics GBM pós-operatório 1p | T1 com contraste | Tumor residual |
| Raidionics GBM pós-operatório 3p — novo | T1 com contraste, T1, FLAIR | Tumor residual |
| Attention U-Net 3D — novo | FLAIR, T1, T1 com contraste, T2 | TC, WT e ET independentes |
| SynthSeg/DIPY — novo | T1 | 32 estruturas anatômicas |
| CerebrA/ANTs — novo | T1 | 102 labels por registro deformável |
| Buti/nnU-Net — existente no host | TC | Oito labels originais |

Quatro adições estão incluídas; QTIM foi adiado. O Brain auxiliar de alguns
motores Raidionics é dependência, não outra opção de segmentação. Buti reaproveita
pesos e runtime do host. A disponibilidade efetiva depende de entradas, artefatos
e ambientes verificados; o catálogo não habilita modelos apenas por seu nome.

Séries diferentes exigem alinhamento explícito no espaço físico. O fluxo não
transfere resultados implicitamente entre RM e TC nem mistura sujeitos/estudos.
Falha de um motor preserva os demais. A repetição produz uma revisão completa e
reutiliza somente resultados íntegros cuja identidade de execução permaneceu igual.

## Instalação e atualização

O conector GitHub usa release/asset fixados e SHA-256 externo. A entrega pública
autorizada usa o repositório `drhenriquebraga/neuro-rt` e assets da release Latest;
confira a publicação e as identidades no handoff. Não há token embutido. A
instalação offline também recebe pacote e hash externo.
Código, runtimes e modelos só são ativados após conferência; a versão anterior,
configuração e dados são preservados. A atualização aguarda a fila ou usa a
interrupção explícita do padrão da suíte e reabre o aplicativo.

Layout, manifesto e bootstrap: [integração](docs/INTEGRACAO.md) e
[formato do pacote](installer/PACKAGE_FORMAT.md). O ZIP de fontes antigo não
substitui o pacote transacional. Não copie um ambiente `.venv` para a estação.

## Desenvolvimento e evidências

- [Desenho aprovado](docs/superpowers/specs/2026-10-29-neuro-rt-plugin-local-suite-design.md)
- [Roadmap e cinco planos](docs/superpowers/plans/2026-10-29-neuro-rt-roadmap.md)
- [Migração do Nidus](docs/MIGRACAO_NIDUS.md)
- [Artefatos, fontes e licenças dos modelos](docs/MODEL_ASSETS_V1.md)

Bateria principal: `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
Testes HTTP também usam o Python do host, com FastAPI/httpx; quando há restrições
locais de socket/IPC, precisam de execução autorizada. Dados de teste são
sintéticos. Pesos, runtimes, imagens, configuração privada e resultados não entram
no Git. Os contratos comuns funcionam em Python 3.10 ou posterior; as versões
científicas são fixadas separadamente por runtime.

Inferências completas com pesos reais e restauração geométrica foram verificadas
em fantomas. Isso não comprova precisão clínica nem desempenho anatômico. GPU,
Windows LTSB e outras estações físicas não foram validados nesta entrega.

Nossa integração é MIT. Os componentes preservam suas próprias licenças e avisos:
Nidus/serviços compartilhados Apache 2.0, Raidionics BSD, Motaz MIT, adaptação
SynthSeg/DIPY e suas dependências, CerebrA CC0 com template MNI separado, ANTs e
Buti conforme seus arquivos originais. Não tratar a licença do código da integração
como licença de todos os pesos. Consulte `catalog/models.json`, `licenses/` e os
avisos incluídos nos pacotes.

A interface standalone/API v1 do protótipo permanece para compatibilidade de
desenvolvimento; sua documentação está em [legado v0.2](docs/LEGADO_V02_README.md).
