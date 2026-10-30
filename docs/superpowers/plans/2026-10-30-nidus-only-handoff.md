# Revisão de integração: Nidus disponível e aceite comum

Pedido recebido do responsável pela Local Suite em 30/10/2026, com autorização
expressa do Dr. Henrique. Esta revisão substitui a disponibilidade de cinco
ferramentas da entrega 1.0: somente Nidus RT fica acessível. Glioma, Metastasis,
Meningioma e Anatomia permanecem visíveis, apagadas, com `[em construção]` e sem
acionamento. O código científico fica preservado para desenvolvimento futuro.

## Trabalho autorizado

1. Auditar commits, pacotes, licenças e situação da publicação 1.0, sem inferência.
2. Centralizar a disponibilidade, compor cards pelo renderer existente e bloquear
   solicitações de novos estudos, novas tentativas e entrada direta nas ferramentas.
3. Criar um único termo versionado, com impressão SHA-256, usado pelo bootstrap
   confiável do instalador e pelo onboarding. Registrar atos separados de instalação
   e primeiro uso na configuração do plugin, sem identificar paciente ou operador.
4. Exigir primeiro uso antes da tela e APIs Nidus; não alterar o funcionamento
   geométrico do Nidus, o gravador do host nem os limites clínicos existentes.
5. Expor o contrato de aceite no provider para integração pelo agente do host;
   fornecer scripts PowerShell com aceite explícito. Não editar AUTO_CONTORNO.
6. Executar verificações sintéticas focadas, revisar a alteração e entregar versão
   1.0.1 em commit e pacotes. Não publicar release nem executar modelos reais.

## Critérios de entrega

- Card Nidus acessível; os quatro demais sem href, foco acionável ou execução API.
- Os mesmos itens, versão e hash são exibidos no instalador e primeiro uso.
- Aceite ausente, antigo ou corrompido não libera Nidus; nenhuma aceitação automática.
- Licenças originais e avisos preservados; aceite não aprova contornos e não concede
  licença geral aos pesos. Continua UNAPPROVED e revisão no TPS.
- Handoff informa o requisito real de acesso a assets em estações sem credenciais,
  os pontos do host a integrar e a diferença entre pacotes 1.0 e esta revisão.

Instalação e primeiro uso são atos distintos sobre o mesmo documento. Atualização
sem mudança do documento não exige novo aceite. Mudança de texto exige nova versão
e impressão, coordenada com o bootstrap fixado da base do host.

## Ampliação autorizada da entrega

Em 30/10, o responsável pela Local Suite transmitiu a autorização explícita do
Dr. Henrique: abrir o repositório e subir o instalador como última versão e
`_LATEST`. Isso substitui a restrição anterior de não publicar. Antes da mudança
de visibilidade, auditar histórico Git e arquivos publicáveis; concluir revisão
e build, publicar a 1.0.1 como Latest com assets versionados e SETUP_LATEST,
verificar identidades da API e download sem credenciais. AUTO_CONTORNO permanece
sob responsabilidade exclusiva do agente da Local Suite.
