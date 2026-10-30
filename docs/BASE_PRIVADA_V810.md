# Base privada Local Suite 8.10

Gerada em 29/10/2026 pelo empacotador formal do host, a partir de seis clones
Git locais limpos nas revisões abaixo. O BUILD dentro do ZIP é
`2026-10-29.5d46a4d`, sem marca de árvore alterada. Esta é uma entrega local
privada de desenvolvimento; não houve publicação de versão 8.10.

| Campo | Valor |
|---|---|
| Arquivo | `dist/base-local-suite/LOCAL_SUITE/v8.10/RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_v8.10.zip` |
| Tamanho | 6173463 bytes, aproximadamente 6,2 MB |
| SHA-256 | `6577c069a011d2926d496e756266e409d3349cdac917ab45e6a2e87e4947060e` |
| Entradas ZIP | 269 |
| BUILD | `2026-10-29.5d46a4d` |
| Manifesto durável | `docs/BASE_PRIVADA_V810.manifest.json` |

O SETUP contém o código e o preparador. Runtime e pesos não foram preparados
nesta operação. O ZIP Neuro OFFLINE existente não foi reconstruído ou alterado.

## Fontes exatas

| Repositório | HEAD local usado |
|---|---|
| AUTO_CONTORNO | `5d46a4dfab1817532c5df42d94c903a94b184b82` |
| CONTOURLAB | `f84e5e694381ece3cef222fa27a4bbd08555b1d0` |
| DICOM_BRIDGE | `1433abd29509383861c2d5c85aa85f6feac1d306` |
| RECON_3D | `41052d873f38ebe12f3f2f7841973b3364074020` |
| ELASTIC_RT | `3274d8bac3a5124db3b2d0dbbccf5130eb7389fb` |
| 3D_PRINTED_BOLUS | `bc9be52aa3d2f1cbec2f8e7e3dfc98e6207dd550` |

NIDUS_RT e NEURO_RT não fizeram parte da árvore de componentes da base.
O Recon3D usado contém os helpers compartilhados da integração privada. O pin
público Recon3D v8.9 permanece incompatível e não foi alterado por inferência.

## Construção e conferência

Foram criados seis clones `git clone --shared --no-checkout`, com checkout
detached nos HEADs registrados, em pasta nova sob `.research/newcleanbase`.
Arquivos ignorados ou não versionados dos originais não foram copiados. Os
documentos pessoais existentes no host permaneceram intactos em suas pastas.
Os seis clones estavam limpos antes e depois da construção; os seis HEADs e
hashes dos índices originais permaneceram iguais.

Foi executado somente `build/empacotar_instalador.py` do clone do host, usando
o Python API 3.14 original, com:

```powershell
$env:RADAI_COMPONENTES_DIR = '<pasta dos seis clones>'
$env:RADAI_RAIZ_DEPLOY = 'C:/AI_PROJETOS/NEURO_RT/dist/base-local-suite'
& '<Python API original do host>' '<clone AUTO_CONTORNO>/build/empacotar_instalador.py'
```

Não houve `--dos-repositorios`, rede, pip, download ou preparação do bundle de
runtime/pesos. As verificações formais de fontes versionadas, compatibilidade,
PHI e montagem do ZIP foram mantidas e passaram.

A conferência independente confirmou:

- `zipfile.testzip()` aprovado e nenhuma entrada duplicada.
- Presença de `radai_neuro_install.py`, `radai_plugins.py`, `radai_projection.py`
  e `radai_projection_bone.py` em `programa/app/`.
- Ausência de `radai_nidus*.py`, árvore NIDUS_RT, pacote do plugin Neuro,
  diretórios de execução, runtime Python e pesos.
- Nenhum arquivo de imagem clínica. As seis imagens presentes são os ícones,
  favicons e a imagem estática de marca já versionados pelo host.
- Cópia `LOCAL_SUITE/latest/RADIOTERAPIA_AI_LOCAL_SUITE_SETUP_LATEST.zip`
  idêntica byte a byte ao SETUP versionado.

O manifesto conserva os seis HEADs, os hashes dos índices antes/depois, o BUILD,
as exigências de conteúdo, o tamanho e o SHA-256 do artefato. A evidência local
da execução está em `.superpowers/sdd/neuro-plugin/R05-clean-base-report.md`.
