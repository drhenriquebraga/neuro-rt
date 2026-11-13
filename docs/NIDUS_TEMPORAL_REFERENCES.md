# NIDUS — TOF fiel e CINE temporal

Pesquisa em 12/11/2026. Nota de suporte à implementação; não representa validação clínica do Local Suite. Foram extraídos os textos integrais dos cinco PDFs fornecidos e examinados seus métodos, resultados, figuras e limitações pertinentes ao visualizador. As páginas abaixo são páginas do PDF, contando a capa quando existe. Foram renderizadas e conferidas visualmente a figura 7 de Bollmann (p. 13), a discussão de Cosottini (p. 11) e as reconstruções de Yanamadala (p. 3).

## Conclusão prática

Há duas operações diferentes: **rotação da angiografia estática** e **reprodução de volumes adquiridos em diferentes tempos**. É correto oferecer ambas, mas só a segunda mostra enchimento dinâmico. A série `AXI 3D TOF 3SLAB FS MT ASSET` sugere uma TOF 3D com três blocos espaciais, supressão de gordura, transferência de magnetização e aquisição paralela; **3SLAB não significa três fases temporais**. A identificação exata depende dos metadados, não somente do texto da descrição.

Cosottini, p. 11, afirma expressamente: “TOF-MRA is a static technique”. A mesma discussão informa que a dinâmica da drenagem venosa não está contida na TOF e requer técnica resolvida no tempo. Portanto, para CINE de enchimento, procurar séries temporais realmente adquiridas, como TRICKS, TWIST, 4D CE-MRA ou sequências temporais de marcação arterial, e conservar a TOF como referência anatômica de maior resolução quando disponível.

## Evidência dos cinco PDFs fornecidos

### 1. Rutman et al. — Incidental vascular findings on brain magnetic resonance angiography

**DOI:** [10.1259/bjr.20220135](https://doi.org/10.1259/bjr.20220135). [Texto completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC9975521/).

Arquivo: `866df068-1f63-480f-81a8-854a9c439983/bjr.20220135.pdf`, 13 páginas.

- **Páginas 1–2, “Time-of-flight MRA technique”:** o contraste resulta de entrada de sangue não saturado em tecido estacionário saturado. Fluxo lento, orientação paralela ao plano e turbulência podem diminuir o sinal; movimento também degrada a imagem.
- **Página 3, AVM e dAVF:** a representação de nidus e drenagem venosa pode ser limitada; sinal brilhante em veias não equivale automaticamente a informação temporal. A discussão registra a ausência de informação hemodinâmica na TOF convencional.
- **Página 4, figura 4:** sinal residual perceptível na imagem axial fonte pode desaparecer no MIP, produzindo aparência de oclusão.

**Aplicação:** manter MPR/imagem fonte facilmente acessível ao lado da projeção; preservar os intensidades originais e não completar vasos ausentes por IA. Ausência de sinal na reconstrução não comprova ausência anatômica. O artigo não valida segmentação automática nem o motor do NIDUS.

### 2. Lu et al. — Clinical Evaluation of Highly Accelerated Compressed Sensing Time-of-Flight MR Angiography for Intracranial Arterial Stenosis

**DOI:** [10.3174/ajnr.A5786](https://doi.org/10.3174/ajnr.A5786). [Texto completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC7410741/).

Arquivo: `dc906922-0373-47a9-958f-850f5fa1a76d/1833.full.pdf`, 7 páginas; a primeira é capa AJNR.

- **Página 3 / impressa 1834, métodos:** CS-TOF adquiriu voxel 0,6 × 0,6 × 0,6 mm e reconstruiu 0,4 mm isotrópico; PI-TOF adquiriu 0,6 × 0,6 × 1,2 mm e reconstruiu 0,4 × 0,4 × 0,6 mm. Isso diferencia resolução adquirida e matriz reconstruída.
- Reconstrução iterativa utiliza dados de k-space e protótipo de aquisição; posteriormente são produzidas MIPs axial, coronal e sagital.
- **Página 6 / impressa 1837:** artefatos de subamostragem visíveis nas fontes podem ficar discretos na MIP. Há limitações pela amostra pequena e referência DSA disponível em poucos casos.

**Aplicação:** aproveitar DICOM reconstruído pelo equipamento na sua resolução entregue; não prometer reproduzir compressed sensing a partir de imagens prontas. Mais pixels no canvas ou interpolação não recuperam a informação de aquisição ausente.

### 3. Cosottini et al. — Time-of-flight MRA of intracranial vessels at 7 T

**DOI:** [10.1186/s41747-024-00463-z](https://doi.org/10.1186/s41747-024-00463-z). [Texto completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC11156832/).

Arquivo: `a08b8a49-7b62-4a50-a4f9-657fc2b6e450/s41747-024-00463-z.pdf`, 13 páginas.

- **Página 3:** protocolo descreve seis slabs com sobreposição de 50%; são blocos espaciais. Registros sucessivos são compostos e aplicados de uma só vez para evitar múltiplas interpolações.
- **Página 5:** estação reconstrói MPR e volume rendering e salva incidências AP, laterais e oblíquas para comparação com angiografia.
- **Páginas 8–10:** exemplos de aneurisma, MAV e FAVd; são casos de 7 T, não prova de equivalência geral entre todas as TOFs e DSA.
- **Página 11:** TOF é estática; a avaliação da dinâmica requer aquisição temporal. O próprio artigo limita a extrapolação por se tratar de série pequena.

**Aplicação:** fundamenta preservação das incidências, MPR e VR; não fundamenta gerar enchimento a partir de 3SLAB nem prometer resolução de 7 T em exames convencionais.

### 4. Bollmann et al. — Imaging of the pial arterial vasculature of the human brain in vivo using high-resolution 7T time-of-flight angiography

**DOI:** [10.7554/eLife.71186](https://doi.org/10.7554/eLife.71186). [Texto completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC9150892/).

Arquivo: `6eeabd82-dd86-4e52-b0b2-cb86ea920a6c/elife-71186-v2.pdf`, 35 páginas.

- **Páginas 10–13, figuras 5–7:** diminuir o voxel efetivamente adquirido reduz volume parcial e revela ramos que não se distinguem em voxels maiores. MIP e segmentação sobreposta são apresentados separadamente.
- **Página 14, figura 8:** movimento do sangue durante codificação pode deslocar a localização aparente de vasos; o visualizador não deve interpretar toda discrepância como falha de registro.
- **Página 17:** zero-filling pode melhorar aparência sem equivaler à aquisição mais fina; as imagens do estudo foram reconstruídas sem zero-filling. Também discute limitações para corrigir deslocamento vascular em pós-processamento.
- **Páginas 19–20:** limiar/region-growing pode unir veias e artérias indevidamente; remover veias exige informação adicional e pode remover artérias conectadas por erro.

**Aplicação:** manter fonte fiel como representação primária, reconstrução espacial sem anatomia inventada e controles de janela explícitos. Uma imagem suavizada ou segmentada não deve substituir silenciosamente a fonte.

### 5. Yanamadala et al. — Non-contrast 3D time-of-flight magnetic resonance angiography for visualization of intracranial aneurysms in patients with absolute contraindications to CT or MRI contrast

**DOI:** [10.1016/j.jocn.2012.12.005](https://doi.org/10.1016/j.jocn.2012.12.005). [Texto completo](https://pmc.ncbi.nlm.nih.gov/articles/PMC3707952/).

Arquivo: `d701d510-bd0c-48c9-81f2-a45ca1ed2d1f/yanamadala2013.pdf`, 5 páginas.

- **Página 2:** múltiplos slabs finos sobrepostos reduzem saturação ao longo do volume; reconstrução 1024 × 1024 com MIP e VR em estação dedicada.
- **Página 3, figuras 2–3:** exemplos de VR para relações anatômicas.
- **Página 4:** fluxo lento/turbulento pode apagar sinal. Discute complementaridade: VR facilita relações tridimensionais e tecidos vizinhos; MIP pode favorecer pequenos ramos. Estudo tem apenas três casos.

**Aplicação:** MIP e VR devem ser escolhas de representação do volume, não modelos que desenham novos vasos. O estudo apoia viabilidade de reconstrução estática; não contém aquisição de enchimento temporal. Recomendações antigas sobre contraste/gestação não foram usadas como orientação clínica atual.

## Quatro textos completos adicionais úteis

### A. Riederer et al. (2015): Recent Advances in 3D Time-Resolved Contrast-Enhanced MR Angiography

[DOI 10.1002/jmri.24880](https://doi.org/10.1002/jmri.24880) · [Texto integral aberto](https://pmc.ncbi.nlm.nih.gov/articles/PMC4478169/).

Ler especialmente “View Sharing” e figuras 3, 5 e 7. Explica como TRICKS/TWIST reutilizam amostras de k-space entre frames. Intervalo de atualização e **temporal footprint** não são a mesma coisa. A figura 7 compara frames igualmente espaçados de 2,5 s com footprints diferentes. É a base para não rotular a velocidade de reprodução como resolução temporal adquirida. As técnicas descritas dependem da aquisição/reconstrução de k-space; não são filtros que possam ser aplicados retroativamente a DICOM convencional para criar tempo novo.

### B. Blackham et al. (2011): Applications of Time-Resolved MR Angiography

[DOI 10.2214/AJR.10.4227](https://doi.org/10.2214/AJR.10.4227) · [Texto integral aberto](https://pmc.ncbi.nlm.nih.gov/articles/PMC12974259/).

Ler “Technique”, “Head and Neck”, figura 1 e suplementos de cine. Explica TWIST e mostra como volumes sucessivos distinguem alimentação arterial e drenagem precoce de MAV. Os exemplos utilizam volumes 3D adquiridos repetidamente e reconhecem dependência do footprint no compartilhamento de dados. Útil para o fluxo de seleção de conjunto temporal, reprodução e inspeção de um mesmo ângulo entre fases.

### C. Hadizadeh et al. (2012): Noninvasive Evaluation of Cerebral Arteriovenous Malformations by 4D-MRA for Preoperative Planning and Postoperative Follow-Up in 56 Patients

[DOI 10.3174/ajnr.A2921](https://doi.org/10.3174/ajnr.A2921) · [Texto integral aberto](https://pmc.ncbi.nlm.nih.gov/articles/PMC8013249/).

Ler métodos 4D-MRA/análise qualitativa e discussão. Foram adquiridos 50 volumes dinâmicos por exame e analisadas imagens originais, MPR e MIP. A identificação de pequenos aferentes permaneceu limitada; discute complementar a 4D-MRA com MRA estática de maior resolução. Isso apoia oferecer TOF anatômica e CINE temporal no mesmo ambiente, sem tratá-los como equivalentes nem extrapolar o desempenho do estudo para o app.

### D. Rapacchi et al. (2015): Reducing view-sharing using compressed sensing in time-resolved contrast-enhanced magnetic resonance angiography

[DOI 10.1002/mrm.25414](https://doi.org/10.1002/mrm.25414) · [PDF integral do editor, oito páginas](https://onlinelibrary.wiley.com/doi/pdfdirect/10.1002/mrm.25414).

Ler páginas 474–475 e 477–479, sobretudo figuras 1, 3 e 4. Estudo original com phantom e nove pacientes: mesmos dados brutos podem produzir frames com a mesma frequência e footprints diferentes. Compartilhar dados de tempos anteriores/posteriores altera a aparência do momento de enchimento/esvaziamento. A reconstrução proposta exige k-space e dados das bobinas; não pode ser obtida de uma exportação DICOM de magnitude apenas. É a referência mais direta sobre o risco de confundir fluidez visual e fidelidade temporal.

Todos os quatro DOIs foram conferidos nas páginas integrais, no editor ou no registro PubMed. Os links integrais estão disponíveis; não é necessário pedir estes quatro PDFs ao usuário. O PMC do artigo C respondeu intermitentemente com verificação de navegador, mas seu conteúdo integral indexado (métodos, resultados e discussão) pôde ser consultado.

## Requisitos derivados para implementação (inferência de engenharia)

Estas recomendações são derivadas dos resultados e limites acima; os artigos não prescrevem a interface do Local Suite.

1. **Não habilitar enchimento por nome somente.** `TOF`, `3SLAB`, diferentes ângulos de MIP, diferentes ecos ou diferentes janelas não são prova de fases temporais. Confirmar pelo agrupamento DICOM de volumes repetidos e geometria consistente. Se só há MIPs exportadas, reconhecer sequência 2D derivada; não oferecer rotação volumétrica livre como se existissem os volumes originais.
2. **Separar duas dimensões do controle:** roda do mouse sobre angio muda ângulo; nos MPR percorre cortes; a timeline muda fase. No CINE de enchimento, manter orientação, corte, zoom e janela iguais ao longo dos frames, salvo alteração explícita do usuário. Ajustar janela automaticamente a cada fase pode dar impressão artificial de enchimento.
3. **Manter os valores e espaços:** reconstruir a partir das intensidades originais, orientação e espaçamento DICOM; preservar transformações para o consenso. Os dados de RM não são HU. Não usar limiares de TC ou remover osso por valores de RM.
4. **Carregamento honesto:** bloquear manipulação durante preparação inicial, informar etapa/progresso real, permitir cancelamento. Liberar primeira série apenas com volume decodificado e primeiro conjunto de vistas pronto. Pré-carregar as fases efetivamente usadas pelo CINE antes de Play, com limite de memória e cancelamento ao trocar paciente. Não mascarar falta de frames com repetição silenciosa ou interpolação de anatomia.
5. **Resolução:** render final na maior resolução permitida pelo dado e pelo visor; mostrar espaçamento de origem quando útil. Remover seletor de baixa resolução conforme pedido não torna a aquisição original mais fina. Medir desempenho de rotação separadamente do tempo de download/decodificação.
6. **Player:** Play/Pause, loop, avanço de uma fase, timeline e velocidade de exibição. Informar índice/tempo adquirido se disponível. Velocidade de playback não altera resolução temporal. Se tempo real é desconhecido, mostrar ordem das fases em vez de inventar segundos.
7. **Não inferir hemogramas/fluxos quantitativos:** estes exames de intensidade não são automaticamente 4D-flow velocity MRI. Não converter intensidade em velocidade sanguínea nem atribuir anatomia arterial/venosa exclusivamente pela intensidade.
8. **MPR e TOF simultâneas:** disponíveis para conferir anatomia de pequenos ramos e consenso, inclusive quando a série temporal tem resolução mais grossa. Um bom MIP não elimina a necessidade de inspeção das fontes.

### Metadados temporais: fonte normativa adicional

O DICOM distingue índices espaciais e temporais no Frame Content Macro. `TemporalPositionIndex (0020,9128)` é ordinal temporal; `StackID` e `InStackPositionNumber` organizam espacialmente os frames. O Temporal Position Macro usa `TemporalPositionTimeOffset (0020,930D)` em segundos. Consultar a organização de dimensões por frame no Enhanced MR, sem assumir que número de instância representa tempo. [DICOM PS3.3, C.7.6.16.2](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.6.16.2.html).

No MR clássico, o atributo `TemporalPositionIdentifier (0020,0100)` identifica ordem temporal. Ainda é necessária validação espacial do conjunto, pois atributos opcionais podem estar ausentes ou mal preenchidos. O agrupamento por descrição ou nome de arquivo isoladamente deve ser apenas uma indicação, não confirmação de aquisição 4D.

## Verificação mínima sugerida

- TOF convencional de vários slabs: **CINE de enchimento indisponível**, rotação disponível.
- Volumes dinâmicos com vários tempos e cortes completos: ordenação temporal correta, MPR por tempo e câmera fixa no loop.
- Exportação derivada de MIPs giratórias: não classificar ângulo como enchimento.
- Fase incompleta/geometria diferente: não unir silenciosamente; explicar impossibilidade de reconstrução coerente.
- Troca de paciente durante carregamento: cancelar trabalhos e não misturar volume/cache/consenso.
- Frame inicial completo com preset: primeira interação deve ser testada em máquina representativa; não afirmar ausência de atraso somente porque o preloader chegou a 100%.
