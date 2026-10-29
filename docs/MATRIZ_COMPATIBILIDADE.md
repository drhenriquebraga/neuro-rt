# Matriz de evidências de instalação e atualização

Registro em 29/10/2026. Sistema observado: Microsoft Windows NT 10.0.26200.0,
arquitetura AMD64. Estações de teste são diretórios sintéticos, sem exames
ou identificação de pacientes. Não representam validação clínica nem prova de
todas as versões de Windows.

| Cenário | Artefato e ambiente | Evidência | Limite |
|---|---|---|---|
| Primeira instalação offline, ativação e revisão exata | ZIP sintético release-package/1; Python 3.12; caminho com espaço e acento | test_plugin_install e test_release_manifest | Runtime/pesos de fixture não fazem inferência |
| Candidato histórico completo realmente instalado | OFFLINE de 1.200.712.705 bytes, 35.992 arquivos, runtimes e pesos reais; estação isolada, Python 3.12 | Preparo 2267.422s, ativação 389.979s, descoberta fria 109.669s; estado ready | Esta estação sob carga; nenhuma segmentação foi pedida nessa prova |
| Home com instalação completa presente | Mesmo pacote e Python do host 3.14.6; verificação integral sob demanda | Startup 0.0146s, Home 0.0045s, primeira abertura Neuro 0.0465s em checking | A descoberta completa continua obrigatória antes de montar e ocorre em segundo plano |
| Atualização 1.0.0 para 2.0.0 | Dois ZIPs sintéticos; mesmo host, modelos e runtime fixados | test_plugin_update preserva versão anterior e data | Reinício representado por callback controlado |
| Download, verificação e instalação | Resposta de asset GitHub fixada com bytes do ZIP sintético | test_plugin_update executa download→SHA→prepare→activate→restart | Transporte HTTPS exercitado por fixture; release real ainda não publicada |
| Latest sem rede ou mesma versão | Cliente concorrente com resposta e falha controladas | test_plugin_update | Rede de produção não é assumida disponível |
| Latest incompatível | Manifesto externo exige host 9.0; host 8.10 | Consulta informa incompatibilidade antes de baixar o payload | Não exercita outro sistema operacional |
| Falha de checksum, ZIP truncado, ponteiro e reinício | Pacotes e falhas sintéticos | test_plugin_install e test_plugin_update conservam instalação recuperável | Falha física de disco não simulada |
| Atualização da base 8.9 para 8.10 | Atualizador PowerShell real, base sintética e plugin com sentinelas | test_install_upgrade_scenarios | Não altera instalação de uso |
| Runtime científico portátil privado | CPython embeddable 3.12.10, bibliotecas do lock auditado | Importa torch, MONAI, DIPY, ANTs, SimpleITK, pydicom e nibabel com -I -B | Smoke de dependências; não prova corte completo de cada motor |
| Interface host | Python de desenvolvimento do host 3.14.6 e FastAPI/httpx | test_plugin_host, 16 testes incluindo consumidor Chrome de primeira instalação | Exportação RTSTRUCT usa ambiente compatível definido pelo host |

Ainda não exercitados nesta frente: instalação em outra unidade física, máquina
sem qualquer Python global com fluxo completo de segmentação, Windows LTSB,
Windows antigos, GPU/CUDA, queda real de energia e falta real de espaço/permissão.
As provas de limites de espaço e gravação de I02 usam falhas controladas.
Nenhuma dessas combinações é declarada suportada só porque os testes locais
passaram.

O gravador e o leitor RTSTRUCT são os componentes do próprio host. A prova
geométrica compara as máscaras reabertas pelo mesmo leitor da suíte; um leitor
externo com regras de arredondamento distintas não comprova, por si, perda de
voxels pelo gravador. Os ambientes globais não são alterados pelo plugin.


## Distribuição definitiva 1.0.0 — identidade local, sem publicação

O refresh definitivo após o ajuste CLI aprovado concluiu em 50.861s. A
verificação integral foi repetida somente pela mudança real de um arquivo de
código após o primeiro congelamento, sem reinstalação, inferência ou nova
medição de descoberta. O resultado tem 35.984 arquivos inventariados, 76 CODE
(51 .py), dois runtimes, dez componentes de modelos e 3.074.717.951 bytes de
payload descomprimido. Manifesto compacto: 9.057.626 bytes, abaixo de 16 MiB.

| Artefato em dist/v1.0.0 | Bytes exatos | SHA256 |
|---|---:|---|
| NEURO_RT_OFFLINE_v1.0.0.zip | 1200576062 | `8605b82bcd897d263c171c99e5ab8b2194c98b31491064416e0e74132a870d27` |
| NEURO_RT_PLUGIN_v1.0.0.zip | 2077289 | `6205c3c6391677a79d747b145a78cd011308e91421fa8ac815e89011d5bb7843` |
| release-manifest.json | 9057626 | `2b3956e18942db166ee05984144d02815a76cdd6b4d67b06f5e85884d07e07be` |
| NEURO_RT_SETUP_v1.0.0.zip | 1833639 | `cf774fe113ab411f2ff2ce38c90a67c9b60f07c0f2b02d538eb124e593b005b4` |
| NEURO_RT_SETUP_LATEST.zip | 1833639 | `cf774fe113ab411f2ff2ce38c90a67c9b60f07c0f2b02d538eb124e593b005b4` |

A comparação de código extraído confirmou 76/76 fontes congeladas, com as
normalizações JSON documentadas de module.json e catálogo distribuído. Os nove
hashes D03 do ledger atualizado coincidem. Só neuro_rt/build_study_views.py
mudou em relação ao snapshot pré-CLI, pela correção de import aprovada em
D03-unicode-cli-rereview.md. Em relação ao candidato histórico: 18 CODE
alterados, três novos e exclusivamente 11 arquivos públicos de exemplos/testes
dos wheels Matplotlib/nibabel/pydicom removidos; os caminhos exatos constam no
relatório I04-R02-R03 e runtime/seed_sample_exclusion.json. Todos os demais
registros de modelos/runtimes, seus metadados e licenças foram preservados e
seus SHA foram conferidos integralmente no ZIP definitivo.

A primeira instalação e os tempos de preparo/ativação acima são do candidato
histórico de 1.200.712.705 bytes; não são uma reinstalação deste ZIP definitivo.
O ensaio R01 instalado com Motaz real (70,64s, quatro MRs, três registros,
duas máscaras e RTSTRUCT UNAPPROVED com duas ROIs) usa snapshot coerente de 49
.py sobre os mesmos componentes canônicos instalados. Destes, 47 permanecem
idênticos; as diferenças finais são o consumidor de update da minipágina e o
import CLI aprovado do gerador de visores. R01, revisões direcionadas e
verificação integral do pacote são evidências complementares; não se declara
uma nova inferência diretamente deste ZIP final. Recibos:
runtime/final-package-evidence.json e runtime/final-refresh-timing.json.

Nenhuma release/asset/publisher remoto foi criado. A distribuição permanece
local e privada, aguardando a integração/publicação autorizada da base 8.10;
os limites de outras unidades, Windows, GPU e máquina sem Python global
continuam como descritos acima.
