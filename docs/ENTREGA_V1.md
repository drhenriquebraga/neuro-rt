# Entrega privada do NEURO RT 1.0.0

**Estado do código:** implementação e revisão independente concluídas no commit
`67961ff`. As seis correções da revisão geral foram aprovadas. O pacote pós-revisão
passou pela verificação integral e contém 77/77 arquivos CODE conferidos. ZIPs
anteriores à correção não representam esse mesmo código.

O OFFLINE final tem **1.200.594.357 bytes**, SHA-256
`7453a93ef0c6c1e9daca574ecd07602274aea935680ecfd609b8571689694ef5`.
A base privada 8.10 tem 6.173.463 bytes, SHA-256
`6577c069a011d2926d496e756266e409d3349cdac917ab45e6a2e87e4947060e`.

## Arquivos e finalidade

| Arquivo | Finalidade |
|---|---|
| `RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_v8.10.zip` | Base compatível, preparada de seis checkouts limpos; contém o código comum e os novos helpers |
| `NEURO_RT_OFFLINE_v1.0.0.zip` | Plugin completo com os ambientes privados, pesos e atlas fixados |
| `NEURO_RT_SETUP_v1.0.0.zip` | Bootstrap e scripts PowerShell confiáveis para preparar a instalação |
| `NEURO_RT_PLUGIN_v1.0.0.zip` | Atualização de código; requer componentes exatos já presentes e íntegros |
| `release-manifest.json` / `SHA256SUMS.txt` | Inventário e identidade dos arquivos dessa mesma construção |
| `NEURO_RT_SOURCE_v1.0.0.zip` | Fontes; não substitui a instalação com ambientes e pesos |

Nesta estação, os arquivos Neuro ficam em `C:/AI_PROJETOS/NEURO_RT/dist/v1.0.0`.
O SETUP da base fica em `dist/base-local-suite/LOCAL_SUITE/v8.10` e as fontes em
`dist`. A distribuição permanece privada e local. Não há release publicada
oferecendo instalação pública por `latest`.

## Instalação na base compatível

1. Use o instalador normal da base 8.10, no mesmo destino da instalação existente.
   Extraia todo o SETUP e abra `START_HERE.cmd`. O fluxo do Local Suite identifica
   a instalação e conserva configuração, pesos e resultados. Um SETUP é o
   preparador; uma instalação base nova ainda precisa dos componentes próprios
   da suíte, conforme suas opções online/offline.
2. Confira que a base é a entrega privada compatível. Use o Recon3D adaptado
   incluído nela; o pin público v8.9 não contém os helpers desta integração.
3. Para Neuro online, a home apresenta a instalação e consulta a release acessível
   do repositório autorizado. Enquanto não houver uma release publicada ou acesso
   privado, esse caminho não tem payload remoto disponível. Não embuta tokens.
4. Para a instalação offline, extraia o SETUP Neuro e mantenha o OFFLINE e seu
   checksum externo da mesma construção. O script abaixo **prepara** a versão;
   a ativação/reabertura é coordenada pelo host depois que a fila estiver segura.

Exemplo PowerShell; ajuste apenas os destinos reais da estação:

```powershell
$suite = 'C:\RADIOTERAPIA_AI\LOCAL_SUITE'
$setup = 'D:\NeuroSetup'
$offline = 'D:\Entrega\NEURO_RT_OFFLINE_v1.0.0.zip'
$shaExterno = '<SHA-256 do OFFLINE conferido em SHA256SUMS.txt>'
$transacao = [guid]::NewGuid().ToString('N')
& ($setup + '\installer\INSTALL.ps1') -SuiteRoot $suite -PackagePath $offline -PackageSha256 $shaExterno -TransactionId $transacao
```

Informe o SHA-256 externo da entrega conferida. O instalador o compara com o
arquivo recebido antes de preparar os componentes. O preparo não baixa pacotes
Python globais nem troca o código já importado.

5. Abra NEURO RT na home e conclua a ativação pelo fluxo da suíte. A interface
   acompanha preparo/reabertura; com trabalhos ativos, oferece aguardar ou
   interromper explicitamente. Depois da nova sessão montada, abre os cinco cards.
6. Escolha a ferramenta, carregue as séries, associe canais e referência e ligue
   os modelos desejados. Todas as chaves começam desligadas. A ajuda de cada
   modelo explica entradas, processamento, equipamento e limites.
7. Revise a série segmentada nos MPRs e no 3D. O RTSTRUCT contém ROIs independentes
   por modelo/classe e mantém `UNAPPROVED`. Fusão, edição e aprovação ficam no TPS.

## Atualização, recuperação e rastreabilidade

A consulta `latest` procura uma release publicada do próprio Neuro, sem atualizar
pesos de terceiros arbitrariamente. Falha de rede conserva a instalação íntegra.
Código, componentes e resultados são versionados separadamente. A atualização da
base conserva `Plugins`; a do plugin conserva dados e versão anterior.

Os patches privados da base e Recon, com bases Git e hashes, estão em
`integration/host_updates`. O repositório Nidus original continua intacto.
O SETUP da base, seus seis commits e seu checksum estão em
[BASE_PRIVADA_V810.md](BASE_PRIVADA_V810.md).

As evidências e os limites observados ficam em [VALIDACAO_PLUGIN.md](VALIDACAO_PLUGIN.md)
e [MATRIZ_COMPATIBILIDADE.md](MATRIZ_COMPATIBILIDADE.md). Os ambientes distribuídos
são CPU. Nenhum teste sintético comprova precisão clínica, GPU, LTSB ou outra
estação física. Publicação/merge e eventual exclusão do repositório Nidus são
etapas separadas da entrega privada preparada aqui.
