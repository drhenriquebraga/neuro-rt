# Handoff ao Local Suite — 30/10/2026

Este documento passa ao responsável atual do Local Suite a fotografia auditada
da entrega privada Neuro 1.0 e da revisão 1.0.1 preparada para publicação autorizada.
Não declara instalação na estação de uso, publicação, merge ou disponibilidade
online. Os SHA abaixo vêm dos recibos da construção anterior; não foram
recalculados nesta passagem.

## Responsabilidade e coordenação

O agente do Local Suite é o dono de AUTO_CONTORNO nesta coordenação. O trabalho
Neuro ocorre em NEURO_RT. O recorte autorizado para a próxima entrega é liberar
Nidus e deixar Glioma, Metastasis, Meningioma e Anatomia desativados como
“em construção”. A entrega 1.0 abaixo antecede esse recorte e não comprova seu
aceite. Consentimento, instalação e primeiro uso ainda serão completados pelo
coordenador nos campos da seção 1.0.1.

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

107 testes selecionados passaram (dois skips de symlink Windows), sete HTTP e
quatro fluxos Chrome dirigidos passaram. Revisão independente resolveu quatro
achados e não deixou bloqueante conhecido. Nenhuma nova inferência ou instalação
clínica foi feita. Ver `VALIDACAO_PLUGIN.md`; a base/runtime 8.10 efetivos e o
commit de incorporação continuam sob responsabilidade do dono da Local Suite.

Os novos arquivos ficam em `dist/v1.0.1`; OFFLINE e PLUGIN têm o mesmo inventário
de componentes científicos de 1.0. A verificação integral do ZIP passou e 80
arquivos CODE coincidem com a fonte final. Identidades e estado da publicação
serão registrados abaixo após o upload, sem reutilizar hashes 1.0.
