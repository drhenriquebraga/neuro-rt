## Integração NEURO RT — base 8.10 em desenvolvimento

NEURO RT é o primeiro plugin opcional, instalado em `Plugins/NEURO RT`, com
repositório próprio privado. A home mostra NEURO RT no lugar de NIDUS RT.
Nidus, Glioma, Metastasis, Meningioma e Anatomia pertencem à minipágina do plugin;
fila, carregador, configurações, gravação RTSTRUCT e visores continuam comuns.
NIDUS_RT não integra a trava nem o bundle base. Sua origem permanece intacta;
o core de projeção foi extraído sem mudança funcional para Recon3D.

A implementação é coordenada em `C:/AI_PROJETOS/NEURO_RT`, cujo AGENTS, desenho,
roadmap e `docs/IMPLEMENTACAO_PLUGIN.md` são a referência desta migração. Não
reintroduzir a dependência reversa de Recon3D na tela Nidus. Os helpers comuns
novos e o bootstrap precisam da base adaptada; o pin público Recon3D v8.9 ainda
não contém esses helpers. Os patches da entrega são privados, sem publicação
implícita nos repositórios públicos da base. A seção de sete pastas abaixo
registra a separação anterior e deve ser lida com esta atualização.

A seleção Neuro é manual por modelo, inicialmente desligada; não adicionar
AUTO/FAST nesse seletor. Ausência real de canal desativa, classificação incerta
avisa sem bloquear. A preferência global de dispositivo é independente. Não
misturar pacientes/estudos, não transferir RM–TC implicitamente, não mudar os
limites de aprovação descritos nas regras clínicas abaixo.
