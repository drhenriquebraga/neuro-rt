# Integração NEURO RT / Local Suite

Este é o contrato do plugin 1.0, com o recorte de disponibilidade 1.0.1 descrito
abaixo. O protótipo iframe/API v1 está preservado em
LEGADO_V02_INTEGRACAO.md; ele não define a instalação integrada atual.

## Responsabilidades

**Disponibilidade 1.0.1:** somente Nidus RT está habilitado. Os outros quatro
cards usam o renderer comum com rota vazia, `aria-disabled=true`, `[em construção]`
e opacidade do host. `neuro_rt/tool_availability.py` é a fonte canônica;
`module.json.enabled_tools` permite inspeção sem importar motores. As URLs dessas
ferramentas devolvem 503, e POST selection/studies/jobs/retry devolvem 409 após
os controles de origem/token. Leituras históricas e cancelamento são preservados.
O servidor stdlib de desenvolvimento também recusa novas execuções.

## Aceite compartilhado com o host

`neuro_rt/plugin_consent.py` contém o documento PT-BR, versão 1.0 e impressão
SHA-256 do conteúdo canônico. O bootstrap confiável inclui a mesma fonte. Texto
alterado exige versão nova, hash novo e coordenação com o bootstrap da base;
nunca buscar um termo executável no payload para autorizar sua própria instalação.

O provider gerado fornece `consent_policy()`, `consent_status()` e
`accept_consent(payload)`. Este último registra somente a etapa `installation`.
O host deve expor no status do plugin:

```json
{"consent":{"policy":"objeto retornado por consent_policy()",
            "installation_accepted":false,"first_use_accepted":false}}
```

O objeto `policy` real inclui title/version/digest/clauses, não a string ilustrativa.
O consumidor UI confiável mostra o texto e envia `consent={accepted:true,version,
digest}` no POST install/update quando necessário. O host valida sua origem/token
e JSON, chama `provider.accept_consent(body['consent'])` e só então `install()` ou
`request_plugin_update(...)`. A guarda do provider recusa qualquer ação sem recibo
atual, antes de segurar a fila, cancelar trabalho ou iniciar download. Instalações
antigas sem recibo também exigem essa confirmação antes de atualizar.

Na primeira entrada, `/neuro/onboarding` usa o mesmo documento. GET/POST
`/neuro/api/consent` fornecem estado/token e registram `first_use`, com origem e
token próprios da instância. Sem esse recibo, `/neuro/`, `/neuro/nidus`,
`/nidus/projecao` redirecionam ao onboarding e `/api/nidus/*` responde 428. Um
registro não substitui o outro. A tela inicial não tem checkbox marcado por padrão.
Os arquivos separados `config/consent-installation.json` e
`config/consent-first_use.json` guardam versão/hash/etapa/instante UTC, sem paciente
ou operador. São locais à instalação, não um serviço de autenticação pessoal.

O aceite complementa os termos da suíte; mantém MIT da integração, Apache-2.0 do
Nidus/core e licenças por componente, e não constitui aprovação clínica.

O host é dono da aplicação FastAPI, origem, home, menu, idioma, tema, carregador
DICOM e bilhetes, preferência de dispositivo, fila, acervo, gravador DICOM-RT e
visores. O plugin é dono do catálogo Neuro, bindings, coordenação dos estudos,
adaptadores e dados privados. Bibliotecas científicas ficam nos workers.

A pequena entrada do host funciona com o plugin ausente. Ao instalar, NEURO RT
usa a mesma origem e os componentes visuais existentes. Não abre outro servidor.

## Layout instalado

```text
<LocalSuite>/Plugins/NEURO RT/
  installation.json
  versions/<version>/
    module.json
    release-manifest.json
    neuro_rt/
    integration/
    catalog/
    app/                       # tela Nidus e alias do core compartilhado
    web/
    licenses/
  runtimes/<id>/<lock_digest>/  # imutáveis, com Python e dependências próprias
  models/<id>/<revision>/       # pesos e textos originais verificados
  data/jobs/<study_id>/         # entradas, execução e logs privados
  data/studies/<study_id>/revisions/<n>/
  config/
  staging/
```

`PluginPaths` resolve essa árvore a partir da raiz real do host. O código de
produção não usa diretórios de desenvolvimento como fallback. Instalação em disco
e ativação são passos diferentes; uma versão em uso não é substituída por arquivos
novos. A versão anterior, modelos válidos e dados são preservados.

## Contrato do host

O manifesto 1.0.2 exige `local-suite/plugins/1` e Local Suite 8.11 ou posterior. O host
carrega a entrada conhecida e chama `montar(app, code_dir, host_services=...)` uma
vez. HostServices fornece:

- `resolve_series_ticket`: descritor autorizado e origem privada do bilhete do
  carregador existente; nunca interpreta um path vindo da API Neuro v2.
- `queue_bridge`: enqueue/await/report/finish/cancel na arbitragem única da estação.
- `device_preference`: a preferência global é congelada quando o item recebe a vez.
- `register_result`: publicação confirmada no acervo comum, sem substituir um arquivo
  válido por resultado de exportação incompleta.
- `export_rtstruct` e `viewer_routes`: capacidades do host; a execução usa seus
  motores em subprocessos, sem importar bibliotecas científicas na home.

Os callbacks de produção são composição interna, não opções técnicas a preencher
pelo usuário. Os descritores expostos à seleção contêm bilhetes e grupo opaco;
UIDs, paths, PatientID e logs não pertencem ao StudyView.

## API de estudos

A API integrada usa `/neuro/api/`. Mutações exigem conexão local, host/origem
permitidos e `X-Neuro-Token` obtido no status. Respostas sensíveis usam `no-store`.

- `GET status`: estado e token da instância.
- `POST selection`: `{tickets, category}`; retorna modelos, bindings sugeridos,
  elegibilidade, avisos e séries/grupos opacos.
- `POST studies`: `neuro-rt/request/2`, pedido explícito, estudos/referências,
  modelos e canais distintos por modelo.
- `GET studies`: trabalhos atuais e revisões publicadas no store.
- `GET studies/{id}?revision=N`: estado ou revisão específica.
- `POST studies/{id}/cancel`: cancelamento explícito.
- `POST studies/{id}/retry`: `{explicit_request:true}`; revisão completa posterior.
- `GET studies/{id}/artifacts/{opaque_id}`: somente artefato declarado, confinado e
  íntegro. O ID não é um nome de arquivo nem um caminho recebido livremente.

Os endpoints legados por path servem o protótipo de desenvolvimento. A montagem
integrada recusa sua submissão. Nenhuma seleção, abertura de página ou reabertura
de resultado inicia inferência por omissão.

## Execução e resultados

Cada item tem uma referência. Entradas devem pertencer ao mesmo sujeito, estudo e
modalidade. Classificação incerta não é ausência de volume. Preparação usa o leitor
do host; registros são explícitos em coordenadas físicas LPS. As máscaras voltam à
grade completa da referência e são verificadas antes da entrega.

A fila dá uma concessão por item; os modelos rodam sequencialmente. Workers usam
runtimes fixados, processo oculto e, no Windows, JobObject com handshake antes da
entrada científica. O cancelamento encerra e confirma os descendentes antes de
liberar a vez. Falhas independentes não descartam saídas válidas dos demais.

O store publica revisões completas, preserva anteriores e resolve artefatos por
IDs opacos. Retry só reutiliza entradas/máscaras íntegras e fingerprints iguais.
Reiniciar recupera resultados e marca trabalho interrompido; não o reinicia sozinho.

Um RTSTRUCT é gravado por referência/execução com ROIs por modelo/classe. O mesmo
`engine.build_rtstruct` da suíte grava e o leitor nativo `radai_rt.SessaoRT` confere
voxels, SOPs e planos. Uma ROI pequena não desaparece silenciosamente. Erro ou
omissão preserva máscaras e declara exportação falha/incompleta. A publicação usa
nome exclusivo e conserva os arquivos anteriores. Todas as estruturas são
`UNAPPROVED`; fusão/edição/aprovação pertencem ao TPS e ao operador.

## Nidus e Recon3D

A tela Nidus pertence ao plugin e é montada por `integration/nidus_bridge.py`.
O alias `radai_nidus` aponta para o core compartilhado `radai_projection` do
Recon3D. O helper de osso também pertence ao serviço compartilhado. Assim Recon3D
funciona sem instalar a tela Nidus, com uma implementação geométrica.

A entrada é `/neuro/nidus`; `/nidus/projecao` e APIs legadas continuam compatíveis.
Não montar a tela Nidus novamente no laço base do painel. O repositório antigo só
poderá ser removido em etapa posterior, após conferência da migração.

## Pacotes e compatibilidade

O manifesto transacional inventaria todos os arquivos, tamanhos, hashes e licenças.
Atlas NIfTI só entra pela allowlist de origem/hash; dados de trabalho nunca entram.
Buti é gerido pelo host e não é duplicado no payload do plugin. O Brain auxiliar
Raidionics e a prova de licença do atlas também entram na verificação de preflight.

O conector latest fixa a release/asset e confere SHA externo. Acesso privado é
explícito; nenhum token viaja no código. Sem rede, uma versão íntegra continua
utilizável. A atualização respeita a fila e a reabertura controlada do host. Consulte
`installer/PACKAGE_FORMAT.md` e `docs/IMPLEMENTACAO_PLUGIN.md` para estado e provas.

O contrato comum exige Python 3.10 ou posterior. Os runtimes científicos são
separados e têm versões próprias fixadas; essa exigência não autoriza atualizar o
Python do host para satisfazer um motor. GPU e outras estações/Windows precisam
de suas provas próprias antes de serem anunciadas como compatíveis.
