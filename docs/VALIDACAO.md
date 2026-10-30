# Validação técnica — 11/10/2026

Este documento registra o protótipo histórico. A integração atual como plugin
do Local Suite está em [VALIDACAO_PLUGIN.md](VALIDACAO_PLUGIN.md), com ambientes,
testes, inferências instaladas e limites próprios. As frases abaixo sobre não
alterar o host descrevem somente a fase anterior.

Dados exclusivamente sintéticos. Não houve leitura de exames de pacientes,
envio a TPS, instalação no host ou alteração de suas fontes.

Resultado final: 22 casos distintos aprovados. A bateria principal executou
21 e dispensou o caso FastAPI por ausência de FastAPI/httpx no ambiente de
inferência; esse caso passou separadamente no ambiente do host. Nenhuma falha.

## Evidência obtida

- Testes unitários/integrados em Python 3.12: pedido explícito, catálogo fechado,
  geometria, máscaras binárias/vazias, NIfTI, DICOM MR por UID, múltiplas séries,
  CT recusada, cortes irregulares, configuração oficial, jobs e recuperação
  após subprocesso com erro, token/origem HTTP e allowlist de artefatos.
- Backend real raidionicsseg 1.5.2 e ONNX Runtime: rede sintética pequena com
  máscara assimétrica esperada e RM oblíqua anisotrópica, sem substituir a
  função de inferência por mock. O registro de hashes é substituído somente
  dentro do processo de teste para autorizar a pequena rede sintética.
- Gravador real de AUTO_CONTORNO/app, pelo Python 3.10.11 do bundle: RTSTRUCT
  de MR sintética, uma ROI, UNAPPROVED, sufixo `_ai`, procedência NeuroRT,
  UID do frame/série/imagens originais e contornos nos z=4,6,8 mm esperados.
  Um arquivo adulterado para APPROVED foi recusado.
- Adaptador montado em FastAPI 0.141.1: /neuro/, arquivos estáticos e API,
  montagem idempotente, Host arbitrário, POST sem token e origem externa
  recusados. Preflight de hashes executado em threadpool, fora do event loop.
  Teste executado pelo ambiente de desenvolvimento do host com httpx.
- Navegador: seleção começa vazia, aceite começa desmarcado e botão bloqueado;
  processamento pelo formulário concluiu e ofereceu máscara/manifesto.
  O mesmo módulo carregou em iframe numa origem FastAPI própria de prova.
  Console da página sem erros durante esse fluxo.
- Seis redes oficiais 1.2.0 carregadas em ONNX Runtime CPU. GBM e cérebro
  executados sobre um fantoma de RM. Resultado tumoral: 65 voxels, 1.015625 cm³,
  geometria original preservada. Essa medida comprova execução, não acurácia.
- Runtime próprio Python 3.10.11 embeddable, NumPy 1.26.4, ONNX Runtime 1.20.1,
  SimpleITK 2.4.1 e SciPy 1.14.1 importados fora dos ambientes do host.
  GBM+cérebro também executados com sucesso nesse runtime portátil, produzindo
  a mesma máscara técnica do teste no ambiente Python 3.12.
  Conteúdo conserva as licenças de dependências nos dist-info.
- Preparo: tamanhos e SHA256 de ZIPs fixados em models.lock.json; ONNX e
  pre_processing.ini verificados contra o registro fixado e provenance.json
  obrigatório. Ausência de procedência e modificação do peso foram recusadas.
  Pacote usa
  allowlist, exclui configuração local, imagens, jobs e ambientes de desenvolvimento.

## Comandos reprodutíveis

Na v0.2, a suíte executou 25 casos: 24 passaram no ambiente do módulo e um
caso FastAPI foi executado separadamente no ambiente do host. A prova adicional
de publicação confirmou dois nomes exclusivos, preservação dos bytes do
primeiro RTSTRUCT e recusa depois de alterar o frame da série original.
O índice demo tolera um job ausente e reabre os demais depois de reiniciar,
sem subprocesso de inferência. Os planos e as malhas foram verificados com
imagem sintética anisotrópica no motor real do host.

Navegador v0.2: axial principal, 3D, sagital e coronal carregaram a demo GBM;
slider mudou de 72 para 73/141 e a camada cerebral foi desligada no 3D.
Layout estreito de 390 px sem overflow horizontal; sem erro no console.
Inspeção mecânica: imagens sem src ficam em seção oculta até receber o job,
portanto o aviso de imagem vazia é esperado no HTML inicial. Tipografia pequena
e borda de alerta foram ajustadas. Revisão do código corrigiu dados visuais
antigos durante a troca de job e respostas concorrentes de demos.

Os cinco pesos oficiais foram executados no runtime portátil em CPU, com
entrada pública e sem alterar pesos ou limiares. Os cinco resultados foram
não vazios e têm máscaras, cortes navegáveis e STL em cache. SHA256 da entrada
e do peso conferidos; índice reaberto numa nova instância de Service sem
iniciar subprocesso. Fontes/licenças estão em runtime/demos.json e na
bibliografia; imagens e resultados permanecem fora dos ZIPs.

| Modelo | Volume previsto na demo (cm³) | Tempo do pipeline nesta execução (s) |
|---|---:|---:|
| MRI_GBM | 24,483 | 530,5 |
| MRI_GBM_Postop_FV_1p | 0,433 | 196,1 |
| MRI_LGGlioma | 15,390 | 750,8 |
| MRI_Meningioma | 18,584 | 334,8 |
| MRI_Metastasis | 20,376 | 701,5 |

Tempos incluem concorrência com outras tarefas desta máquina. Os volumes são
saídas dos modelos, sem comparação clínica com contornos de referência.
Após a rodada grilling, foi confirmado que as demos mostram automação e não
precisam provar diagnóstico. A promoção de sagital e coronal no navegador
preservou o corte selecionado em todos os planos e manteve o 3D ao lado.

Dois testes adicionais cobrem a abertura das prévias: focos distantes não
podem produzir um corte inicial vazio pela média das posições; máscara vazia
deve abrir em índice válido. O corte inicial agora usa a maior área prevista
por plano. Os cinco view.json foram atualizados e cada corte selecionado foi
conferido como não vazio, sem alterar máscaras ou STL.

```powershell
$env:PYTHONUTF8='1'
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O teste do adaptador é dispensado no ambiente de inferência sem FastAPI/httpx;
foi executado separadamente e passou pelo Python do ambiente do host.
O teste do gravador precisa de neuro_rt.local.json válido.

scripts/smoke_official.py cria o fantoma; neuro_rt.worker executa o fluxo oficial.
Os resultados da prova ficam em runtime/ e são excluídos dos pacotes.

## Limites práticos

- Testes técnicos não são validação clínica ou medida de sensibilidade a
  metástases pequenas. Todos os contornos precisam de revisão humana.
- Não houve validação em pacientes, TPS/Eclipse, GPU ou Windows LTSB 14393.
- As demos públicas são provas de execução dos pesos oficiais, sem métricas
  de acurácia ou comparação com contornos de referência.
- Não existe transferência de Frame of Reference, registro RM–TC ou CTV.
- O plugin ainda precisa ser incorporado ao catálogo/preparador da próxima
  versão do Local Suite. O shell de prova é independente do produto instalado.
- Modelos multissequência, multiclasses e relatórios RADS não foram incluídos.
- CUDA só será considerada pronta após comissionamento de runtime/drivers no
  destino; o ZIP desta entrega usa CPU.
