# Nidus RT 1.0.1 — dados temporários e contrato de privacidade

Conferência de código em 30/10/2026, sem instalar o plugin na base Local Suite,
sem processar exames e sem alterar código do host ou do plugin.

Este documento descreve os mecanismos específicos da tela Nidus. Os limites
numéricos abaixo pertencem a caches diferentes: **24 MiB não é o limite de RAM
de todo o processo; 10 minutos não é a validade de todos os dados ou sessões.**

## Fontes e identidades conferidas

| Fonte | Revisão | Identidade do arquivo |
|---|---|---|
| `NEURO_RT/app/radai_nidus_screen.py` | `70140b4744e3a8feb8e15433a5c415be427b516a` | Git blob `61409aa6e2d95fda73718b099f0739b0e775a2eb`; SHA-256 `3a57ea71ea0e4eca55d46d34da47a39636bedf69a15a1418a9e218861b912ae6` |
| `RECON_3D/app/radai_projection.py` | `41052d873f38ebe12f3f2f7841973b3364074020` | Git blob `526fa89450343a827a9142ad3fa23c89053f4bb4`; SHA-256 `bad5aa99c2fc04fde018d7c5441d6e9b131c0225e9fc6ba90f1da2191a03b19a` |

São identidades das fontes locais lidas. A conferência deste documento não
atesta publicação do core Recon, instalação em estação, nem identidade de um
arquivo ZIP. O responsável pela entrega registra os hashes dos pacotes e os
pins efetivamente distribuídos.

## Chave estável da série e sessão do servidor

Em `radai_nidus_screen.py:46–50`, `chave_da_serie(pasta, uid)` calcula:

```text
uid = str(uid or '').strip()
base = 'uid:' + uid                         se houver UID
base = 'pasta:' + normcase(abspath(pasta))  se não houver UID
chave = SHA256(UTF8(base)).hexdigest()[:24]
```

Portanto são **24 caracteres hexadecimais**, equivalentes a 96 bits. A expressão
não é simplesmente `SHA256(UID)`: há o prefixo `uid:`. Com UID presente, mudar
a pasta não muda essa chave. Sem UID, a chave depende do caminho absoluto
normalizado. O nome do armazenamento inclui `radai_nidus_v2_` antes da chave
(`:398`). A chave é uma impressão estável para reencontrar o desenho; não é
uma declaração de anonimização de todo o exame.

Essa impressão não é o identificador de sessão da retroprojeção no servidor.
A sessão de tubos é criada como `bilhete + '|' + contador` em `:2874` e devolvida
como `sessao` em `:2882`. O bilhete é administrado pelo carregador do host.

## Desenhos e parâmetros no navegador

`ndFoto` (`:387–391`) faz uma cópia JSON destes campos:

| Campo | Conteúdo |
|---|---|
| `lao`, `cra` | Ângulos escolhidos |
| `modo`, `jan`, `laje` | MIP/MinIP, janela e espessura da projeção |
| `inverter`, `osso` | Preferências de visualização |
| `caixa` | Recorte escolhido |
| `guardadas` | Incidências, pontos e parâmetros guardados |
| `pontos` | Traço atual |
| `sessao` | Identificador da sessão de tubos retornado pelo servidor |

As incidências guardadas contêm ângulos, pontos, caixa, janela, modo, laje,
estado do osso e indicador `pendente` (`:1330–1333`). Esse snapshot não inclui
as imagens DICOM, nome de paciente ou UID bruto como campos próprios.

`ndRegistrar` grava o snapshot em `window.sessionStorage` (`:399–406`);
`ndSalvo` o lê (`:408–413`). A tela não usa `localStorage`. O histórico de
desfazer fica em `ND.historico` e tem teto de 60 entradas (`:357`, `:403`).

O contrato é armazenamento da sessão/aba do navegador, com reaproveitamento
durante essa sessão. O código não aplica TTL de 10 minutos a esse snapshot,
nem chama `sessionStorage.removeItem` para essa chave. Limpar o desenho grava
um novo estado sem as marcações (`:1339–1343`). O comentário do fonte que diz
“não vai a disco” deve ser entendido como ausência de um gravador de desenho
da aplicação: `sessionStorage` é gerenciado pelo navegador e esse código não
controla sua implementação interna ou restauração de sessão.

## Malhas STL e série aberta na memória do servidor

| Mecanismo | Comportamento real | Fonte da tela |
|---|---|---|
| `_MALHAS` | `OrderedDict` com bytes STL; IDs UUID opacos | `:2759–2769` |
| Teto de entradas | No máximo 9 entradas retidas após a inserção/remoção | `:2451`, `:2767` |
| Teto de bytes | Soma dos bytes STL retidos no cache até `24 * 1024 * 1024`, isto é, 24 MiB | `:2453`, `:2766–2770` |
| Evicção | Retira entradas mais antigas enquanto qualquer teto for excedido | `:2767–2770` |
| Entrega ao visor | Resposta binária do cache, `Cache-Control: no-store`; 404 se o ID saiu da memória | `:2821–2828` |
| Produção do STL | Converte a malha em bytes com `R.stl_da_malha` e a coloca em `_MALHAS` | `:2796–2797` |
| Troca da série | Libera a série aberta anterior e limpa `_TUBOS` e `_MALHAS` | `:2547–2551` |
| Inatividade | Temporizador de 600 segundos; confere o tempo desde o último uso da série | `:2449`, `:2478–2497` |

Essas funções não gravam os bytes STL em arquivo. O endpoint entrega os bytes
ao visor; não há, nesse fluxo, uma exportação de malha da caixa para o TPS.
Isso não estabelece um teto para arrays temporários da geração, memória do
SimpleITK/NumPy, buffers do navegador/WebGL ou todo o processo Python.

`_serie` atualiza `_ABERTA['visto']` ao reutilizar a série (`:2543–2545`) e ao
abri-la (`:2563–2565`). Ao atingir 600 segundos de inatividade, a rotina
`_soltar_se_ociosa` libera `_ABERTA['serie']`, limpa `_TUBOS` e `_MALHAS`; se
ainda não chegou ao prazo, rearma o temporizador pelo tempo restante. Esse é
um prazo de inatividade do cache, não uma contagem fixa desde a abertura.
Fechar a aba não envia aqui um comando de expurgo imediato ao servidor.

### Sessões de tubos têm outro limite

`_SESSOES` é um dicionário distinto (`:2465`). Ele conserva tubos compactados,
ângulos, forma, espaçamento e interseção (`:2875–2878`). Seu limite é **quatro
sessões**, por remoção FIFO quando uma quinta é criada (`:2467`, `:2879–2881`).

A rotina de 600 segundos não limpa `_SESSOES`; a troca de série também não
o limpa. Não existe, nessa implementação, TTL de 10 minutos para essas quatro
sessões. Elas deixam de estar disponíveis quando são retiradas pelo limite
ou quando o processo termina. O snapshot da aba pode conservar uma referência
à sessão mesmo depois de ela já ter saído desse dicionário.

Uma redação fiel para o comportamento é:

> O Nidus conserva o desenho e os parâmetros na sessão da aba, sob uma impressão
> estável de 24 caracteres da série. O servidor guarda temporariamente até nove
> malhas STL, somando até 24 MiB no cache; libera esse cache e a série aberta
> após 10 minutos sem uso, ou ao trocar a série. As sessões de tubos são um
> conjunto separado, limitado às quatro últimas durante o processo.

## Papel do core compartilhado Recon

O alias `NEURO_RT/app/radai_nidus.py:4–6` aponta para o mesmo objeto de módulo
`radai_projection`. O core `RECON_3D/app/radai_projection.py` contém a geometria,
`Compacto` e empacotamento de máscaras (`:424–451`), interseção (`:454`) e geração
das malhas (`:673`). Os tetos de triângulos por classe estão em `:639`: 50.000
para vaso, 20.000 para osso e 10.000 para pele.

A chave SHA, o `sessionStorage`, os 24 MiB e o temporizador pertencem à tela do
plugin, não ao core compartilhado. Nesse arquivo de core não foi encontrado
um gravador de arquivo ou cliente de rede para esses dados. As incidências
Towne/Caldwell, usadas por testes da base, estão no core em `:26–33`.

O Nidus usa o carregador e outros serviços do host. Por exemplo, falhas podem
ser encaminhadas a `radai_thumbnail.registrar_falha` (`tela:2506`), e a solicitação
opcional de segmentação de osso usa a fila do host (`:2730` e seguintes). Assim,
as conclusões sobre os caches/desenho não significam que toda ação do plugin,
os registros de falha ou os resultados de processamento jamais sejam gravados.
Esses serviços seguem os contratos próprios do Local Suite.

## Verificações executadas sem instalar o plugin na base

Foram executados três grupos dirigidos, todos aprovados:

1. **Python/AST da tela real:** foram extraídas e executadas apenas
   `chave_da_serie`, `_guardar_malha` e `_soltar_se_ociosa`, com dados sintéticos
   em memória e relógio substituído. Conferidos prefixo e 24 hexadecimais,
   independência de pasta quando há UID, fallback por pasta sem UID, evicção
   após dez inserções, descarte para manter 24 MiB, liberação após 601 segundos
   e rearmamento quando ainda faltavam 99 segundos. Confirmado também que
   `_SESSOES` permanece intacto nessa liberação.
2. **Node/VM do JavaScript real:** foram extraídas e executadas `ndCopia`,
   `ndFoto`, `ndChaveSalva`, `ndRegistrar` e `ndSalvo`. Um `sessionStorage`
   sintético confirmou a chave, os onze campos, leitura do snapshot, isolamento
   entre chaves e limite de 60 entradas do histórico. Nenhum `localStorage`
   foi utilizado ou consta no fonte da tela.
3. **Resolver real da base, sem extras de plugin:**
   `_componentes.ligar_caminho('C:/AI_PROJETOS/AUTO_CONTORNO')` e
   `importlib.util.find_spec` confirmaram `radai_nidus` e
   `radai_nidus_screen` ausentes, e `radai_projection` disponível em
   `C:/AI_PROJETOS/RECON_3D/app/radai_projection.py`. A resolução antiga de
   `app/radai_nidus_screen.py` não aponta para arquivo existente na base.

Nenhuma série, peso ou runtime foi baixado, instalado ou processado. Os testes
de fonte/VM não importaram a tela na base. A conferência do resolver foi feita
com bytecode desabilitado (`-B`). Não foi executada a bateria completa do host
nem declarada aprovação de testes que ainda precisam acompanhar a migração.

## Testes do host que precisam acompanhar a migração

Este é um mapeamento somente leitura do checkout do host no momento da
conferência. O responsável pelo host deve adaptar seus próprios arquivos.

| Teste/local | Pressuposto antigo encontrado | Adaptação recomendada |
|---|---|---|
| `tools/test_suite.py:424` | Lê modalidades de `app/radai_nidus_screen.py` pela resolução da base | Separar metadados do plugin e conferir CT/MR (`tela:18`) contra fonte/contrato Neuro versionado, sem recolocar a tela no bundle |
| `tools/test_consent.py:7645`, helpers `:8223–8252` | Extrai hash e campos do snapshot da tela dentro da base | Ler fonte externa explicitamente fixada, ou contrato versionado com hash de fonte; manter a prova correspondente na CI do plugin |
| `tools/test_consent.py:8802–8803`, `:8955–8958`, `:9011–9015` | Procura incidências no core Nidus antigo e 24/600 no arquivo da tela | Incidências vêm de `radai_projection`; limites da tela vêm do contrato Neuro 1.0.1. Não interpretar fonte ausente como valor válido |
| `tools/check_project.py:3874–3961` | Monta a base e compara chamadas JS dos componentes base com rotas vivas | Manter essa medida sem plugin. Conferir entrada/loader `/neuro` da base; chamadas `/api/nidus/*` pertencem à bateria do plugin |
| `tools/test_languages.py:222`, `:239` | Lista template e rota Nidus entre telas obrigatórias da base | Medir entrada/instalação Neuro na base; medir a tela Nidus e idioma na etapa com plugin ou por composição sintética em tarefa separada |
| `tools/test_neb_telas.py:127`, `:253`, `:318`, `:359`, `:424` | Importa tela/core Nidus e seus testes como se fossem da base | Geometria pode usar core Recon compartilhado; tela e endpoints Nidus ficam na bateria Neuro, com fontes e imports de teste explícitos |
| `tools/test_menu.py:352–375` | Exige card `/nidus` e nome Nidus na porta | A porta passa a NEURO RT e `/neuro`; Nidus é a ferramenta interna. Alias antigo só deve ser testado se mantido deliberadamente pelo host |
| `tools/test_ui.py:312`; `tools/test_ui_interacao.py:1440–1441`, `:1622`, `:1714`, `:2465` | Assume minipágina Nidus e tela funcional em toda base | Separar estado plugin ausente, instalação/primeiro uso e Nidus disponível. Preservar as medidas de design nas telas de cada estado |

A mudança deve preservar a fiscalização que os testes fazem. Não é suficiente
apagar os casos Nidus ou fazer todos passarem por `skip` irrestrito. Uma divisão
concreta é:

1. **Bateria da base sem plugin:** card Neuro, loader, consentimento de instalação,
   persistência de configuração, compartilhamento de fila e ausência de import
   ou empacotamento de `radai_nidus_screen`/alias antigo.
2. **Contrato versionado:** identidade do plugin, commit/hash da tela, modalidades,
   tamanho da impressão, tipo/campos do armazenamento, tetos de cache e regra de
   expiração. Conferir esse contrato contra a fonte publicada na CI do plugin.
   A base pode fixá-lo como metadado de compatibilidade sem instalar o plugin.
3. **Bateria do plugin:** composição da tela com serviços sintéticos da suíte,
   proteção antes do primeiro uso, acesso legado controlado, idioma/tema, cache
   e geometria. O contrato fixado deve continuar divergindo quando uma isca
   muda 24 caracteres, 24 MiB ou 600 segundos; não inventar esses valores como
   fallback quando uma fonte está ausente.

As fontes atuais continuam em seus repositórios próprios; nenhuma recomendação
exige instalar o plugin para fazer a checagem da base passar. Essa revisão não
acrescenta condição à publicação já em andamento.
