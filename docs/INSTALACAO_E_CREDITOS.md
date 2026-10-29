# Instalação e origem dos componentes

Ao instalar NeuroRT, informe ao operador: os pesos tumorais e o modelo cerebral
auxiliar vêm do projeto Raidionics, release 1.2.0; o motor `raidionicsseg` 1.5.2
vem de SINTEF / David Bouget. São componentes de terceiros sob BSD-2-Clause.
Nossa interface e integração são MIT. Preservar NOTICE e os textos integrais
em licenses/, também na redistribuição de binários. A bibliografia na tela
apresenta o artigo e os links de origem. A marca pública do módulo é NeuroRT.

O preparo baixa pesos com hashes fixados em models.lock.json. Na estação de
uso os pesos permanecem locais. O pacote atual contém runtime CPU; não instala
CUDA nem muda ambientes do Local Suite.

O cache de demonstração desta máquina fica em runtime/demo_inputs,
runtime/jobs e runtime/demos.json. OpenNeuro ds007345 é CC0; PROTEAS, DOI
10.5281/zenodo.17253793, é CC BY 4.0. Fonte, sequência, SHA256 e tempo de execução
ficam no índice. Exemplos públicos do fornecedor têm licença de redistribuição
de imagens ainda não confirmada: ficam somente neste cache. Os pacotes de
código e offline excluem todas as imagens e resultados. Para levar demos à
clínica, distribuir somente as que tiverem licença confirmada, com créditos.

O cache abre resultados previamente executados, sem nova inferência. Demonstra
o funcionamento técnico; não mede acurácia ou adequação clínica dos modelos.
