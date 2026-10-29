# Pedido pronto para a próxima sessão do Local Suite

Incorpore o módulo NeuroRT já construído em C:\AI_PROJETOS\NEURO_RT à próxima
versão do Local Suite em C:\AI_PROJETOS\AUTO_CONTORNO.

Leia somente README.md, docs/INTEGRACAO.md e module.json do NeuroRT para conhecer
o contrato. Use dist/NEURO_RT_OFFLINE_v0.2.0.zip, com runtime e seis modelos.
Não reimplemente o módulo nem copie suas fontes para o monólito.

Monte integration/radai_neuro.py no FastAPI e acrescente o iframe /neuro/ ao
catálogo/menu da suíte. Configure os paths relativos do worker, pesos, jobs e
gravador existente. Inclua licenças e modelos no preparador/pacote da versão.

Valide a conexão com dados sintéticos, o runtime no Windows LTSB 14393 e a
exportação pelo engine.build_rtstruct. Preserve UNAPPROVED, procedência,
FrameOfReferenceUID e SOPInstanceUIDs da MR original. Não ligue achados no
AUTO/vigia e não acrescente máscaras NeuroRT ao FULL/OAR. A v0.2.0 não faz
registro RM–TC nem CTV automático.

As fontes do host ainda não foram alteradas por este trabalho. A integração
em uma nova versão é a tarefa restante, conforme o pedido original.

## Pendência de compartilhamento de configurações (11/10/2026)

O processamento já pertence às Configurações do Local Suite. Na incorporação,
usar a mesma preferência global DEVICE: auto (padrão), somente CPU e somente
GPU. Não criar um segundo seletor de processamento no NeuroRT. A conexão com
essa configuração e suas mudanças durante a sessão é pendência explícita do
acoplamento. Só CPU nunca usa GPU; só GPU deve falhar de modo claro se ela não
estiver utilizável; auto usa o mesmo resolvedor/dispositivo da suíte.

A identidade pública é NeuroRT. Créditos de motores/pesos ficam na bibliografia,
nos avisos de instalação e nas licenças, sem marca externa nos títulos da tela.

O resultado do pipeline abre automaticamente segmentação em axial central,
planos menores e reconstrução 3D, reutilizando os motores de PNG/geometria/3D
existentes da suíte. Na série DICOM, o RTSTRUCT final deve ser publicado na
pasta original da série carregada, com nome exclusivo e sem sobrescrever.

Decisões confirmadas na rodada grilling: visualização apenas (editar no TPS);
saída completa dos modelos, com múltiplos focos numa ROI única; botão Ampliar
troca sagital/coronal com o axial no visor principal; demos mostram automação
e não precisam provar diagnóstico. Leia também docs/ESCOPO.md.
