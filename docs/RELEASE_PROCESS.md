# Preparação e publicação — instalador leve

O contrato atual é installer-only, execution_mode=host, Local Suite mínimo8.11. A base completa fornece o Python, as bibliotecas e serviços do Nidus. Não construir/distribuir runtimes privados nem baixar Python, bibliotecas ou pesos para esta entrega.

1. Revisar e testar o código na branch, preservando main e tags históricas.
2. Rodar verify.yml (contratos sintéticos Windows/Python3.10 e3.12), os testes de navegador pertinentes e a prova CODE-only no Python real da base. Registrar skips e limites.
3. Gerar os dois arquivos com `python scripts/build_web_setup.py --output dist/web-setup`. O builder só aceita CODE/licenças/PS, modo host, Nidus-only, sem binários/pesos/ambientes, e limita a3MiB.
4. Conferir hashes e byte-identidade de SETUP_v e SETUP_LATEST. O digest externo do asset é fornecido pela API GitHub; nenhum terceiro asset de manifesto/checksum é necessário.
5. Gerar o bootstrap confiável com scripts/build_host_bootstrap.py e integrá-lo à base. Verificar equivalência de SOURCES/UI/catálogo e o binding sys.executable; nenhuma animação existente muda.
6. Preparar rascunho com somente NEURO_RT_SETUP_v<versão>.zip e NEURO_RT_SETUP_LATEST.zip. O workflow release.yml segue esse formato e não publica automaticamente.
7. Publicar a base compatível antes de promover o plugin a Latest. Em rascunhos já existentes, atualizar o target para o commit revisado e substituir somente esses dois assets; nunca alterar tags/código históricos.
8. Após publicação, verificar releases/latest e download anônimo do SETUP, tamanho, digest e inventário CODE-only. O cliente não pode voltar a OFFLINE/PLUGIN nem solicitar componentes científicos.

O chat LOCAL SUITE I é responsável pela retirada coordenada de assets de bundle antigos, preservando cópias locais e sem alterar código/tags. Não realizar exclusões concorrentes. Publicação e exclusão do repositório Nidus continuam assuntos separados.

Os builders/locks isolados anteriores são somente ferramentas de pesquisa e testes locais. Não os usar para gerar os assets públicos ou reaplicar seus pins ao ambiente da suíte.
