# Handoff ao Local Suite — 30/10/2026

Este documento passa ao responsável atual do Local Suite a fotografia auditada
da entrega privada Neuro 1.0 e da revisão pública 1.0.1. O repositório foi aberto,
a revisão foi incorporada em main e a release foi publicada como Latest em
30/10/2026, 12:19:56 UTC. Não declara instalação em estação de uso. Os SHA da seção
1.0 são recibos históricos; os da seção 1.0.1 foram verificados nesta publicação.

## Responsabilidade e coordenação

O agente do Local Suite é o dono de AUTO_CONTORNO nesta coordenação. O trabalho
Neuro ocorre em NEURO_RT. O recorte autorizado e entregue é liberar
Nidus e deixar Glioma, Metastasis, Meningioma e Anatomia desativados como
“em construção”. A entrega 1.0 abaixo antecede esse recorte e não comprova seu
aceite. O contrato final de consentimento, instalação e primeiro uso está na
seção 1.0.1; o responsável da suíte o incorpora no host.

## Fotografia auditada da entrega 1.0

Fonte detalhada: `.superpowers/sdd/neuro-plugin/2026-10-30-delivery-audit.md`.
As consultas foram somente leitura, com Git local e GitHub autenticado, sem
baixar payloads ou expor credenciais.

| Componente | Revisão local registrada | Publicação observada na auditoria |
|---|---|---|
| Neuro | `344f20a1240dd98116b122eb847d954f05077fec` — documentos; código revisado `67961ff56fd2b092874865641083c565f03c1cbe` | Repositório privado `drhenriquebraga/neuro-rt`; [PR #1](https://github.com/drhenriquebraga/neuro-rt/pull/1) aberta, não draft, não mesclada; nenhuma release/asset; latest HTTP 404 |
| Local Suite | `5d46a4dfab1817532c5df42d94c903a94b184b82` | Integração 8.10 local privada; repositório `drhenriquebraga/local-suite` público, latest publicado v8.9 |
| Recon | `41052d873f38ebe12f3f2f7841973b3364074020` | Helpers adaptados locais; repositório `drhenriquebraga/recon-3d` público; latest HTTP 404 na consulta |

Branches locais registradas: Neuro/Host `codex/neuro-plugin`, Recon
`codex/neuro-shared-core`. Os repositórios locais Host e Recon não tinham remote
configurado. Main remoto Neuro era `7c024c9aa358a3322cd30552d182be92bdaf7839`;
Local Suite `359a112cb0c8e9958d14b8bd6ef6109789535500`; Recon
`afc1b4a868367d59dffe89b3175503362109222f`. São observações históricas, não uma
trava sobre o trabalho posterior dos respectivos donos.

O SETUP público Local Suite v8.9 tem 6115950 bytes, digest API
`sha256:8c9e10075658cb63dc847797c7666060419206bccba2b6cbe5a5328189c4543b`.
Não confundir esse arquivo com a base privada 8.10 abaixo. O workflow Neuro
release.yml cria somente um rascunho privado de fontes; não publica um OFFLINE
instalável nem torna releases/latest disponível automaticamente.

## Arquivos locais 1.0 e identidade registrada

Todos os caminhos da tabela são relativos a `C:/AI_PROJETOS/NEURO_RT`.

| Arquivo | Bytes | SHA256 registrado |
|---|---:|---|
| `dist/v1.0.0/NEURO_RT_OFFLINE_v1.0.0.zip` | 1200594357 | `7453a93ef0c6c1e9daca574ecd07602274aea935680ecfd609b8571689694ef5` |
| `dist/v1.0.0/NEURO_RT_PLUGIN_v1.0.0.zip` | 2095512 | `ec50df20474db2a44e8d13bc76c3bac86afb1f23b00e136828cb644834257c89` |
| `dist/v1.0.0/release-manifest.json` | 9057759 | `fc528cd9b0ba1ea68422046a5ec08c4f856f3a7432e3a86b06b0d540271b679d` |
| `dist/v1.0.0/NEURO_RT_SETUP_v1.0.0.zip` | 1833700 | `01b28bfd9bd9128df6d3c8656141052d3bb8d92e77f18fcb1a25be328b8935e7` |
| `dist/v1.0.0/NEURO_RT_SETUP_LATEST.zip` | 1833700 | `01b28bfd9bd9128df6d3c8656141052d3bb8d92e77f18fcb1a25be328b8935e7` |
| `dist/base-local-suite/LOCAL_SUITE/v8.10/RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_v8.10.zip` | 6173463 | `6577c069a011d2926d496e756266e409d3349cdac917ab45e6a2e87e4947060e` |
| `dist/NEURO_RT_SOURCE_v1.0.0.zip` | 731356 | `adfa4a80cb3c06de03f6c68e91028a8ce8475cd94cc28faafb7b9a601b27fc67` |

- OFFLINE contém plugin, dois runtimes privados, pesos e atlas. Inventário:
  35.985 arquivos, 77 CODE (52 .py), dez componentes de modelos e dois runtimes;
  manifesto de 9.057.759 bytes. Verificação integral anterior: 39,473 s.
- PLUGIN é atualização de código com inventário; exige componentes exatos já
  presentes. SETUP Neuro é bootstrap/scripts confiáveis; não contém o payload
  completo. SOURCE contém fontes e não substitui instalação. SETUP_LATEST é
  alias idêntico ao SETUP versionado.
- Base privada 8.10: BUILD `2026-10-29.5d46a4d`, 269 entradas, código de seis
  revisões limpas; contém os helpers Recon adaptados. O SETUP de 6,2 MB não
  contém runtime Python ou pesos da base, nem Neuro já instalado.
- Contrato Neuro: host mínimo 8.10, `local-suite/plugins/1`, Python host >=3.10;
  workers privados Raidionics 3.10.11 e científico CPU 3.12.10.
- Evidências: `runtime/final-package-evidence.json`,
  `runtime/final-refresh-timing.json`, `docs/RELEASE_v1.0.0_CODE_LEDGER.json`,
  `docs/MATRIZ_COMPATIBILIDADE.md` e `docs/ENTREGA_V1.md`. São da entrega 1.0;
  não comprovam o código ou o recorte de uma futura 1.0.1.

## Instalação sem credenciais de desenvolvimento

Hoje o caminho disponível é entregar os arquivos offline por canal autorizado.
Não é necessário clonar o repositório privado, copiar a .venv ou fornecer o token
do desenvolvedor ao usuário. Uma instalação base nova precisa também do
preparo/runtime da própria suíte ou de seu bundle offline; o SETUP 8.10 pequeno
não basta sozinho, e o runtime Neuro não substitui o runtime da base.

A sequência documentada para 1.0 é preparar/atualizar a base compatível, extrair
o SETUP Neuro confiável, fornecer o OFFLINE e seu SHA externo a
installer/INSTALL.ps1 e concluir a ativação/reabertura pelo host com fila segura.
O script prepara a versão e deixa `installed_pending_restart`; não faz troca de
imports vivos. O fluxo do host acompanha verificação e reinício até mounted.
Essa sequência ainda deve ser alinhada ao consentimento e primeiro uso da 1.0.1.

O caminho online não está pronto: não existe release Neuro com OFFLINE/digest
na API. O cliente procura o nome exato NEURO_RT_OFFLINE_v<versão>.zip e exige o
SHA256 externo do asset. Enquanto o repositório for privado, será necessário
acesso individual autorizado ou outro canal de distribuição aprovado. Não
embutir tokens e não anunciar instalação online anônima com base no ZIP SOURCE.
Desativar quatro cards não reduz, por si só, o OFFLINE de 1,2 GB. Não remover
componentes manualmente de um ZIP inventariado; uma distribuição menor precisaria
de construção e identidade próprias, conforme decisão do coordenador.

## Integração do host: não aplicar patches antigos às cegas

integration/host_updates preserva snapshots privados de 29/10: 21 arquivos
Host e oito Recon, com bases e hashes no manifesto. Eles documentam a integração
anterior; não representam um patch automaticamente correto sobre o host que
agora está sendo incorporado pelo dono atual.

Antes de qualquer aplicação, o responsável do host deve confrontar sua revisão,
mudanças locais e módulos já integrados com os manifests. Não aplicar sobre
trabalho existente nem sobrescrever a incorporação atual. O pin Recon público
v8.9 não fornece os helpers comuns necessários. Preservar Plugins, configuração,
pesos, dados e resultados na integração/atualização da base.

O bootstrap app/radai_neuro_install.py deve ser **regenerado das fontes Neuro
aprovadas da revisão de destino**, pelo gerador confiável:

```powershell
# Exemplo para o responsável do host; não executado por este handoff.
Set-Location C:/AI_PROJETOS/NEURO_RT
.venv/Scripts/python.exe scripts/build_host_bootstrap.py C:/AI_PROJETOS/AUTO_CONTORNO/app/radai_neuro_install.py
```

Não copiar por conveniência um bootstrap histórico de patch/ZIP: ele embute os
módulos stdlib de instalação com hashes e o controlador/catálogo da UI inicial.
Mudanças aprovadas em instalação ou primeiro uso precisam estar refletidas na
base distribuída. Nenhum código de ZIP não verificado deve ser executado para
obter o próprio instalador. O responsável deve registrar revisão geradora,
identidade resultante e compatibilidade dos contratos; este documento não
regenera nem altera o host.

## Revisão 1.0.1 — contrato final

O Dr. Henrique autorizou explicitamente tornar neuro-rt público e publicar o
instalador como última versão e `_LATEST`. O recorte está implementado e revisado:
somente Nidus ativo; quatro cards apagados e sem foco/link; URLs retornam 503;
novos POSTs de segmentação/retry retornam 409 após origem/token. Leituras de
histórico e cancelamento são preservados. A barreira é uma rota Starlette
denial-only, inserida antes da publicação dos endpoints, compatível com a
montagem tardia da suíte; não altera a pilha de middleware de um app iniciado.

O termo PT-BR é `neuro_rt/plugin_consent.py`, versão 1.0, SHA-256
`ae6fd4434ec42a08ffe6a4be6eaf002940a903de15a516a1b5fce3275ab772b0`.
O host deve regenerar seu bootstrap com as fontes desta revisão e implementar
**os dois pontos** abaixo antes de distribuir a base 8.10:

1. Status `/api/plugins/neuro-rt`: incluir `consent` com `policy` retornada por
   `provider.consent_policy()` e os dois booleanos de `provider.consent_status()`.
   O UI confiável incluído no bootstrap mostra o texto e checkbox desmarcado.
2. POST install/update: após sua validação local/token, se o recibo atual não
   existir, validar `body.consent` e chamar `provider.accept_consent(...)` antes
   de install/request_plugin_update. O payload é accepted boolean true, version
   e digest exatos. Não inferir aceite do clique antigo de instalar ou atualizar.

O provider recusa agir sem recibo, antes de download/fila/cancelamento. Instalação
antiga sem receipt também exige a confirmação. A UI reconhece mudança de hash e
descarta o checkbox marcado. Atualizações futuras com o mesmo termo reutilizam
o receipt. No primeiro acesso, o plugin registra outro ato `first_use` sobre o
mesmo documento; protege a tela e todas as APIs Nidus. Detalhes e exemplos:
`INTEGRACAO.md`. O consentimento não é aprovação clínica nem licença geral de pesos.

Bootstrap local para inspeção, sem modificar o host:
`dist/handoff-1.0.1/radai_neuro_install.py`. Regenerar no host com o script
versionado é a fonte de verdade. Não copiar o bootstrap histórico do patch 1.0.

Identidade exata Windows: **143.658 bytes**, SHA-256
`1e2d53a07444bdb1d196159f09e752c8a461b297c8fa79531bb801d9ea938480`.
Gerador SHA-256
`cacd1ed64596ab694027deb268295fdf4b46161b6aed980b1a6697270c1f9487`.
Fonte aprovada: commit Neuro `70140b4744e3a8feb8e15433a5c415be427b516a`;
incorporação em main `25d7ee8d6a01cb257dd42f2bd28225fc30e42ee0`, mesma árvore.
O arquivo embute seis fontes: plugin_consent, plugin_manifest, model_paths,
model_registry, install_state e plugin_update; inclui provider e controlador UI
de aceite atualizados. `BOOTSTRAP_HOST_v1.0.1.json` fornece os hashes individuais.
São hashes dos bytes presentes neste checkout Windows; uma geração com finais
de linha distintos terá outra identidade e deve ser registrada pelo responsável.

## Núcleo de projeção real para testes de privacidade

O módulo comum é **radai_projection**, em
`C:/AI_PROJETOS/RECON_3D/app/radai_projection.py`, fornecido pelo Recon/base.
Contém SEM_VOLUME, LIMITACAO_CLINICA, LIMITACAO_RM, incidências, projetar, tubo,
intersecao, cortes e malhas. Seu auxiliar de reaproveitamento do osso é
`C:/AI_PROJETOS/RECON_3D/app/radai_projection_bone.py`, com
osso_da_segmentacao e os limites SEM_SEGMENTACAO/SEM_UID/SEM_OSSO_NA_ENTREGA.
Ambos estão no commit local Recon `41052d873f38ebe12f3f2f7841973b3364074020`.
Não presumir que o pin público histórico Recon v8.9 já contém esses módulos.

`NEURO_RT/app/radai_nidus.py` é somente um alias Apache-2.0:
importa radai_projection e aponta sys.modules para o **mesmo objeto**, sem cópia
das constantes/funções. A tela e os endpoints Nidus reais foram migrados para
`NEURO_RT/app/radai_nidus_screen.py`; esse arquivo também importa o auxiliar comum.
Testes que observam privacidade/geometria devem inspecionar esses módulos reais
e a tela migrada, e verificar `radai_nidus is radai_projection`. Observar apenas
o arquivo legado removido de NIDUS_RT ou somente o alias não testa o código que
roda na suíte. A ponte `integration/nidus_bridge.py` recusa um core/tela já
importado de uma origem conflitante. Não houve edição de host ou Recon nesta revisão.

## Verificação e artefatos 1.0.1

107 testes selecionados passaram (dois skips de symlink Windows), sete HTTP e
quatro fluxos Chrome dirigidos passaram. Revisão independente resolveu quatro
achados e não deixou bloqueante conhecido. Nenhuma nova inferência ou instalação
clínica foi feita. Ver `VALIDACAO_PLUGIN.md`; a base/runtime 8.10 efetivos e o
commit de incorporação continuam sob responsabilidade do dono da Local Suite.

Os novos arquivos ficam em `dist/v1.0.1`; OFFLINE e PLUGIN têm o mesmo inventário
de componentes científicos de 1.0. A verificação integral do ZIP passou e 80
arquivos CODE coincidem com a fonte final, sem reutilizar hashes 1.0.

## Publicação efetiva e contrato de download

- Repositório público: https://github.com/drhenriquebraga/neuro-rt
- Release estável e Latest: https://github.com/drhenriquebraga/neuro-rt/releases/tag/v1.0.1
- API Latest: https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/latest
- Release ID: `428993582`; commit da tag: `70140b4744e3a8feb8e15433a5c415be427b516a`.
- Instalador de nome fixo:
  https://github.com/drhenriquebraga/neuro-rt/releases/latest/download/NEURO_RT_SETUP_LATEST.zip

| Asset | Bytes | SHA256 |
|---|---:|---|
| NEURO_RT_OFFLINE_v1.0.1.zip | 1200606005 | `f2612f8c30b7f3a2151b42c36b23bc09f151154e5397526fcaa1c7ada19cc44e` |
| NEURO_RT_PLUGIN_v1.0.1.zip | 2106927 | `9a7386e7d6914c04a9bbf098bed483aed070d7b29b3f0e26334692f29f67cbf9` |
| NEURO_RT_SETUP_v1.0.1.zip | 1837462 | `297f360b850bbdcc48c5f161e2c45d5d8529b46eb749d858ac8494f5354eb25e` |
| NEURO_RT_SETUP_LATEST.zip | 1837462 | `297f360b850bbdcc48c5f161e2c45d5d8529b46eb749d858ac8494f5354eb25e` |
| release-manifest.json | 9058159 | `faf3ba28b4865c29489c17950e18d95a02d4110e1d79076a518d9256ee495e1b` |
| SHA256SUMS.txt | 558 | `6138c34c3c61e55a366381ad69d87929f4658e12a485631f15e87b901a3f20bf` |
| NEURO_RT_SOURCE_v1.0.1.zip | 769776 | `988bc0e15d0a5abb70438b8b5d0aa05aec5fe388a257a93f0d579b8af503e1cc` |

O asset OFFLINE ID `692020525` está em
https://api.github.com/repos/drhenriquebraga/neuro-rt/releases/assets/692020525
e o download público versionado é
https://github.com/drhenriquebraga/neuro-rt/releases/download/v1.0.1/NEURO_RT_OFFLINE_v1.0.1.zip
O conector usa o ID, tamanho e digest SHA256 fornecidos pela API e não troca a
seleção por uma segunda consulta Latest durante o download.

A API confirmou digest/tamanho dos oito assets (incluindo .sha256 das fontes).
Repositório e sete assets menores já passaram por HTTP 200 sem Authorization,
com hash/tamanho conferidos. O alias estável Latest também passou, idêntico ao
SETUP versionado. O download completo anônimo do OFFLINE pelo ReleaseClient real
**concluiu: 1.200.606.005 bytes, SHA256 f2612f8c...19cc44e**, igual à API e ao
pacote local. O cliente reportou `available` para instalação e `current` quando
informado 1.0.1 já instalado. Recibo público: `ANONYMOUS_RELEASE_v1.0.1.json`;
recibo local original: `dist/v1.0.1/anonymous-download-evidence.json`.

Estações não precisam de credenciais de desenvolvimento para esses downloads.
Precisam da base 8.10 compatível, de seu próprio runtime preparado e do contrato
de aceite descrito acima. A instalação do plugin não substitui a montagem da
base nem deve embutir PAT. O SOURCE é snapshot do commit da tag; documentos de
handoff posteriores em main registram a publicação sem alterar os assets imutáveis.

## Host incorporado e última conferência

O responsável informou ter aplicado a proposta e o bootstrap no host. Esta
coordenação não editou AUTO_CONTORNO. A conferência final observou:

- Registry `app/radai_plugins.py`: SHA256
  `9bb5a6bd85a6366d98e2bce1a5b59d835aca6d407d436f677030031c525ab07c`.
- Bootstrap do host reformulado para seu verificador: SHA256
  `3065f7da443a50e7e084703f6c9b8daaeb58905b7fb7e5a6cac2182bcbb516f9`.
- Comparação com a referência gerada Neuro: SOURCES, INSTALL_UI_SCRIPT e
  INSTALL_UI_CATALOG idênticos; AST das funções _load_private_installer e
  build_provider idêntica. A diferença de hash do arquivo é de representação.
- `tests/test_plugin_host.py`: 16/16 aprovados, após adaptar somente as fixtures
  de sucesso ao aceite obrigatório. Recusas de segurança foram preservadas.
- `tests/test_consent_update_ui.py`: 1/1 aprovado no navegador.

Uma edição concorrente foi detectada na primeira rodada; os testes foram
repetidos com os hashes finais estáveis. Relatório reproduzível:
`host-integration-v1.0.1/VALIDACAO_HOST_APLICADO_2026-10-30.md`.
O patch original e seus SHAs ficam em `host-integration-v1.0.1/README.md`;
não reaplicá-lo às cegas sobre o host já integrado.

Os parâmetros de privacidade foram confirmados sem instalação na base:
`SHA256('uid:'+UID.strip())[:24]`, desenho/parâmetros em sessionStorage;
cache de até nove STL e 24 MiB; 600 segundos de inatividade liberam série aberta,
tubos e malhas, **não** as quatro sessões FIFO separadas. Não há TTL de dez
minutos para todo dado nem para o sessionStorage. Valores, linhas, testes
sintéticos e recomendações aos testes-base estão em `PRIVACIDADE_NIDUS_v1.0.1.md`.

## Recomendações ao dono da base

1. Finalizar seus testes de termo 2.3, templates, menu e rotas usando o core real
   radai_projection e a tela do plugin. Não recolocar NIDUS_RT no integrador para
   satisfazer referências antigas dos testes-base.
2. Manter o runtime e os helpers Recon efetivos da base 8.10 no bundle; o SETUP
   pequeno da suíte não é, sozinho, uma instalação científica offline completa.
3. Ajustar a frequência de consulta de Latest no host: o snapshot examinado
   repete a cada 60 segundos enquanto o status é consultado. Cada consulta real
   também baixa o manifesto de cerca de 9 MB para compatibilidade. Recomenda-se
   consultar ao entrar na minipágina e usar cache/backoff persistente, respeitando
   Retry-After e X-RateLimit-Reset, em vez de renovar a cada minuto. O GitHub
   limita requisições REST anônimas por IP (60/h), compartilhadas entre estações:
   [documentação oficial](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).
   É uma recomendação de integração; nenhum token deve ser embutido e nenhum
   código da release publicada foi alterado para isso nesta rodada.
