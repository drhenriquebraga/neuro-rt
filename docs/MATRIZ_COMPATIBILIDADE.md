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



## Distribuição pós-revisão final — 1.0.0 local, sem publicação

FINAL_REREVIEW.md aprovou HEAD 67961ff, F1–F6 ADDRESSED, ReadyToMerge YES.
O escopo congelado de 18 arquivos coincide com FINAL_FIX_FILES.json, identidade
3b4f77d731fc3b370e03c93c80722164ed5d05b10aed64da792f8062b4634fc7.
O ZIP 8605b82bcd897d263c171c99e5ab8b2194c98b31491064416e0e74132a870d27
é **pré-correções F1–F6** e foi substituído pelo refresh abaixo. O processo
levou 39.473s, com verificação integral única dos SHA, allowlist e catálogo do
novo ZIP; não houve reinstalação, inferência ou nova descoberta fria.

Resultado: **35.985 arquivos**, **77 CODE (52 .py)**, **2 runtimes**,
**10 componentes de modelos**, **3.074.791.556 bytes** de payload descomprimido
e manifesto compacto de **9.057.759 bytes**.

| Artefato em dist/v1.0.0 | Bytes exatos | SHA256 |
|---|---:|---|
| NEURO_RT_OFFLINE_v1.0.0.zip | 1200594357 | `7453a93ef0c6c1e9daca574ecd07602274aea935680ecfd609b8571689694ef5` |
| NEURO_RT_PLUGIN_v1.0.0.zip | 2095512 | `ec50df20474db2a44e8d13bc76c3bac86afb1f23b00e136828cb644834257c89` |
| release-manifest.json | 9057759 | `fc528cd9b0ba1ea68422046a5ec08c4f856f3a7432e3a86b06b0d540271b679d` |
| NEURO_RT_SETUP_v1.0.0.zip | 1833700 | `01b28bfd9bd9128df6d3c8656141052d3bb8d92e77f18fcb1a25be328b8935e7` |
| NEURO_RT_SETUP_LATEST.zip | 1833700 | `01b28bfd9bd9128df6d3c8656141052d3bb8d92e77f18fcb1a25be328b8935e7` |

A comparação de código extraído confirmou 77/77 fontes congeladas, incluindo
execution_errors.py. Foram conferidos os 18/18 hashes do escopo aprovado.
O catálogo, removendo somente help, é semanticamente idêntico ao catálogo
anterior. Pesos, revisões, classes, licenças, atlas e runtimes não mudaram;
todos os registros não CODE são exatamente iguais aos do ZIP 8605. Contra o
candidato histórico, há 25 CODE alterados, quatro novos e exclusivamente os
11 exemplos/testes públicos de wheels removidos na sanitização autorizada;
seus caminhos constam no relatório I04 e no recibo de exclusão.

D03: 8/9 hashes históricos permanecem; _scientific.py mudou no F3 aprovado
para registrar contagens/proveniência, SHA atual
79d7b8e3dd5358a8c96b9e64a17fcf200e30b9d9ea6804a6151ed30e8a22f5eb.
O ledger histórico não foi reescrito: docs/RELEASE_v1.0.0_CODE_LEDGER.json
registra os 77 hashes-fonte e de pacote, 18 hashes de escopo e a substituição
aprovada. Recibos finais: runtime/final-package-evidence.json e
runtime/final-refresh-timing.json.

Os tempos de primeira instalação acima pertencem ao candidato histórico de
1.200.712.705 bytes. O ensaio R01 instalado Motaz real de 70,64s usou snapshot
coerente de 49 .py e os mesmos componentes canônicos instalados. Destes,
40 permanecem idênticos; os nove arquivos diferentes estão listados no
relatório I04. execution_errors.py é novo e não fazia parte dos 49. As
mudanças posteriores de UI/avisos/segurança de processos/I/O têm provas
específicas aprovadas: batches 50 (48 pass/2 skips), 37, 10 e 6 testes, com
sobreposição; Tiny ONNX no backend Raidionics em Python 3.10/3.12. Essas provas,
R01 e a verificação integral final são complementares; não se declara uma nova
inferência de pesos treinados diretamente deste ZIP.

Nenhuma release/asset/publisher remoto foi criado. A base privada SETUP clean
5d46/Recon 41052 não foi reconstruída nesta frente. Permanecem os limites de
outras unidades, Windows, GPU, TPS e máquina sem Python global descritos acima.
