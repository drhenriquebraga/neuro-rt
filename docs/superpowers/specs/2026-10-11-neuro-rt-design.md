# NeuroRT — desenho aprovado pela discussão fornecida

O pedido de 11/10/2026 autoriza construir o módulo independente em NEURO_RT,
com HTML em iframe, motor headless Raidionics e acoplamento posterior ao Local
Suite. Não autoriza instalar agora em AUTO_CONTORNO.

## Arquitetura

Página estática local sem CDN; API leve e jobs em processo separado. O módulo
roda sozinho em 127.0.0.1:8766 ou tem suas rotas montadas em /neuro/ pelo
FastAPI existente. O worker usa Python próprio configurável, impedindo colisão
entre SimpleITK/ONNX do Raidionics e os motores do host. Sem PyQt, RADS ou ANTs.

Outras opções: copiar o motor para o monólito conflita com o isolamento pedido;
microserviço obrigatório acrescenta uma porta/processo ao ambiente clínico.
A montagem opcional no servidor existente conserva o iframe e os arquivos
independentes, sem obrigar outro servidor na entrega.

## Escopo da primeira versão

Cinco modelos binários oficiais da release estável 1.2.0: GBM, LGGlioma,
Meningioma, Metastasis e GBM_Postop_FV_1p. Uma sequência por modelo, T1-CE
ou FLAIR conforme os metadados. Modelos multissequência exigiriam validação
de registro entre entradas e ficam fora desta primeira versão.

Entrada NIfTI ou uma série DICOM MR escolhida por UID. Saída: máscaras binárias
na geometria de origem e manifest.json versionado. Job só começa com
explicit_request=true. Não se chama segmentação de GTV/CTV aprovado.

Uso offline após preparo explícito. O motor recebe [System] inputs_folder,
output_folder e model_folder e [Runtime] reconstruction_method=thresholding.
O pacote preserva pre_processing.ini e pesos, com SHA256 e licenças.

## Conexão com o host

Exportação opcional em subprocesso usando o Python do host e
engine.build_rtstruct(clean_dir, masks, cru=True, descontar=False,
modalidade='MR', rotulo='RadAI_NEURO'). Só a série MR original é aceita;
o FrameOfReferenceUID e SOPInstanceUIDs são conferidos após a gravação.
UNAPPROVED e sufixos de procedência são obrigatórios. O arquivo é separado
dos conjuntos FULL/OAR e fica na pasta de saída do job, nunca no share por padrão.

postMessage restrito à mesma origem/source, com ready/status/completed e
context/theme. Não usar '*', file:// ou localStorage para compartilhar dados.

## Erros e testes

Rejeitar modelo ausente, metadados incompatíveis, pasta com múltiplas séries
sem escolha, MR irregular/multiframe, máscara probabilística ou desalinhada,
entrada CT, exportação sem host configurado. Não transformar máscara vazia em
falha: registrar 'empty' e não produzir RTSTRUCT vazio.

Testes sintéticos: geometria oblíqua/anisotrópica, seleção de série,
contrato do backend real com ONNX sintético, jobs/HTTP, exportação pelo host,
pacote e iframe. Teste com peso oficial mede funcionamento técnico, não
acurácia clínica. Usabilidade conferida no navegador.
