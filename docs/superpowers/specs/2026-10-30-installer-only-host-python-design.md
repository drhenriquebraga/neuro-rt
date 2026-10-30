# NEURO RT — instalador leve e Python compartilhado

## Instruções autoritativas do usuário

- “não é para subir bundle, não distribuímos direto”;
- “o usuário aceita e o instalador quem monta o bundle”;
- “O repositório recebe só o instalador”;
- “já está no bundle do local suite, o NEURO RT é um plugin”;
- “assumo que o LOCAL SUITE já foi instalado por completo, e só puxa o que for novo”.

Essas instruções substituem a distribuição OFFLINE e os dois runtimes privados
da implementação anterior. Não se pede nova aprovação para corrigir o código.
O usuário já autorizou o trabalho autônomo; sua correção limita os uploads aos
instaladores leves.

## Recorte desta entrega

Local Suite mínimo 8.11, contrato `local-suite/plugins/1`. Somente Nidus está
habilitado. Glioma, Metastasis, Meningioma e Anatomia continuam em construção.
O Nidus usa o core de projeção/reconstrução, fila, carregador, visores e exportador
da suíte. A base completa já tem os módulos necessários. **O delta de pacotes e
pesos para esta entrega é zero.** Os quatro cards inativos não provocam downloads.

O SETUP instala código, termo e licenças do plugin. Nenhum CPython, venv, Torch,
CUDA, NumPy, SimpleITK ou ambiente científico é baixado/copied/reinstalado. Nenhum
lock científico antigo é reaplicado à base. Nenhuma pasta de bibliotecas de uma
venv do desenvolvedor participa do build público.

## Distribuição

Somente dois assets públicos: `NEURO_RT_SETUP_v1.0.2.zip` e
`NEURO_RT_SETUP_LATEST.zip`, byte a byte idênticos. O primeiro fixa a versão; o
segundo é alias para download humano. O cliente resolve Latest uma vez e fixa
release/asset/URL/tamanho/SHA256 antes do download confirmado. Não seleciona nem
busca OFFLINE, PLUGIN, runtimes ou pesos da nossa release.

O SETUP contém CODE, instaladores PowerShell, termos, licenças e um inventário
pequeno dos seus próprios arquivos. O inventário completo de 35 mil arquivos e
os componentes científicos não entram no SETUP. O cliente usa o digest SHA256
fornecido para o asset pela API GitHub, sem exigir um terceiro asset de manifestos.
Sem digest verificável, recusa o preparo. Um arquivo LATEST cujo conteúdo mude
durante a transação não troca a versão já fixada.

## Contrato compartilhado

- `module.json`: `execution_mode="host"`, `runtime="host-shared"`, `runtimes={}`,
  `enabled_tools=["nidus"]`, `artifacts=[]`.
- Inventário `neuro-rt/release-package/1`: `execution_mode="host"`, `runtime=null`,
  `runtimes=[]`, `models=[]`; arquivos somente em `code/`.
- Esse modo é fechado: payload de runtime/peso, modelo ativo não suportado,
  executável ou wheel oculto no CODE é rejeitado. O modo legado isolado continua
  somente para compatibilidade de dados e testes locais, sem distribuição remota.
- `installation.json` conserva `pending_execution_mode` no preparo e publica
  `execution_mode="host"` na ativação. Nenhum caminho de Python recebido de
  pacote/receita/estado é usado como autoridade.
- O host fornece `host_info["python_executable"]` a partir de seu próprio
  `sys.executable`. O provedor o passa como binding interno ao coordenador.
- `resolve_plugin_paths(..., host_python=...)` recebe esse binding confiável.
  `worker_python` e `Settings.python/host_python` apontam para o mesmo Python
  da suíte; `runtime_dir=None`. Não há busca de um Python global alternativo.
- O preflight verifica o binding, Python >=3.10 e metadados das dependências
  necessárias ao Nidus sem importar bibliotecas científicas na home. Base
  incompleta/incompatível gera diagnóstico antes de modificar componentes.
- Prontidão e integridade avaliam o código Neuro e as capacidades habilitadas;
  não exigem inventariar/copiar/reverificar as bibliotecas pertencentes à base.

## Transação e interface

Reutilizar o instalador transacional existente para um pacote realmente CODE-only:
SHA externo, limites, recusa de aliases/reparse/ZIP slip, staging privado,
promoção imutável, apontador pendente e rollback. Não criar outro montador de
ambientes para um delta vazio. As correções de ReadOnly, limpeza best-effort
póscommit, erro primário preservado, progresso limitado a 4 Hz e status durável
continuam válidas.

Aceite precede o download do SETUP. Fila compartilhada reservada; ativação
ocupada; callback dedicado de reabertura exige `ok=true, scheduled=true`;
sucesso visual exige PID/token novos, versão preparada e montagem confirmada.
Sem novas animações/CSS e sem alterar as já implementadas. Reutilizar as fases
existentes, sem mostrar uma montagem de bibliotecas/modelos que não acontece.
PowerShell usa o mesmo Python da base e imprime fases/resultados claros.

## Futuras funcionalidades

Para cada modelo efetivamente habilitado, calcular somente seu delta contra
as capacidades da base e caches com identidade SHA. Pesos vêm de fontes
originais fixadas por revisão, tamanho, SHA e licença. Se faltar pacote, um
overlay próprio poderá usar o MESMO interpretador, sem sombrear/alterar libs
da base. Nenhum gerenciador genérico de overlay é implementado nesta entrega.

Incompatibilidades já observadas ficam para a liberação científica: Raidionics
1.5.2 exige SimpleITK <=2.4.1, incompatível com 2.5.6 da suíte; DIPY 1.12 não tem
wheel CPython 3.10 para o SynthSeg desejado. Não rebaixar a base nem habilitar
essas ferramentas como efeito da instalação Nidus.

## Responsabilidades e aceite

NEURO_RT: schema/paths/Settings, cliente e SETUP leve, PS, testes e novo bootstrap.
LOCAL SUITE I: binding do Python no host, integração do bootstrap, build 8.11 e
retirada coordenada de assets de bundle. Não apagar assets em paralelo.

Aceite: SETUP pequeno sem Python/wheels/pesos; zero tentativas de baixá-los na
instalação Nidus; reuso do mesmo exe da suíte; quatro cards ainda bloqueados;
preservação de dados/base em falha; prova real CODE-only com novo processo,
HTTP/consentimento, PID/token/versão/montagem. O grande ensaio OFFLINE local
anterior prova correções legadas, não define a distribuição autorizada.
