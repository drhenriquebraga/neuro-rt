# NEURO RT

Plugin opcional de estudo e pesquisa da Local Suite. A versão 1.3.0 inclui Nidus RT, Glioma RT, Metastasis RT, Meningioma RT e AutoContorno Neuro. Requer a Local Suite 8.14 ou posterior, com o bootstrap compatível com esta release.

## Instalação

Abra NEURO RT na home da suíte e confirme a instalação. Também é possível extrair o SETUP e abrir `START_HERE.cmd`. A suíte usa o Python já instalado, verifica o código e prepara os recursos licenciados em `Plugins/NEURO RT`. O GitHub e o espelho oficial oferecem o mesmo instalador leve. O START HERE também monta um pacote offline para levar a outra estação.

## Estudos

Carregue as séries por pasta ou ZIP e confirme os canais exigidos por cada modelo. O processamento usa a fila da suíte. O Nidus guarda desenhos por incidência e permite ajustar e revisar o consenso. A exportação é explícita, produz um RTSTRUCT `UNAPPROVED` por série de referência e se destina a estudo.

O processamento dos exames é local. Consulte o catálogo e os avisos de licença para cada componente. A integração usa MIT e o núcleo do Nidus preserva Apache-2.0. [Catálogo](catalog/models.json) · [Avisos](NOTICE)

## Desenvolvimento

Os testes usam dados sintéticos. Os testes com o host e o navegador aceitam os caminhos `NEURO_HOST_APP`, `NEURO_STUDY_HOST_PYTHON` e `NEURO_PLAYWRIGHT_MODULE` no ambiente. [Formato do SETUP](installer/PACKAGE_FORMAT.md)
