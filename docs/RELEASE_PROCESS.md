# Preparação e publicação da release

O código é verificado por `verify.yml` no Windows com Python 3.10 e 3.12.
Essa etapa usa somente contratos e pacotes sintéticos; não baixa pesos, não faz
inferência e não substitui a matriz de instalação nem os ensaios científicos.
As actions estão fixadas por commit, conferidos nas fontes oficiais de
[checkout](https://github.com/actions/checkout/commit/3d3c42e5aac5ba805825da76410c181273ba90b1)
e [setup-python](https://github.com/actions/setup-python/commit/6d4fd22b20465ccc0f7354476588e8df7c9ca0e0).

O workflow manual `release.yml` repete esses contratos e cria somente um
**rascunho em repositório privado**, com o ZIP de fontes e seu checksum.
Não publica `latest`, não monta runtimes no runner e não declara que esse ZIP
de fontes instala o produto. A versão precisa coincidir com `module.json`.
Uma release existente não é sobrescrita automaticamente.

Antes de criar o rascunho, o workflow consulta as referências de tags remotas e
exige que a tag exata esteja ausente. Qualquer tag preexistente é recusada,
leve ou anotada, inclusive se apontar para o mesmo commit; uma referência como
`v1.0.0-extra` não equivale a `v1.0.0`. Erro de consulta ou resposta inválida
interrompe o fluxo. Nenhuma tag é movida ou sobrescrita. Para uma tag ausente,
`--target GITHUB_SHA` conserva a criação no commit que gerou o ZIP e o checksum.

Antes de transformar o rascunho em release publicada:

1. Fixar o commit revisado, os patches privados da base e o catálogo distribuído.
2. Executar a verificação completa apropriada às mudanças e registrar ambientes,
   resultados, skips e limites em `VALIDACAO_PLUGIN.md` e na matriz.
3. Gerar os dois runtimes portáteis a partir dos locks e conferir procedência e
   licenças. O runtime CPU da entrega não implica disponibilidade de CUDA.
4. Construir OFFLINE, PLUGIN, SETUP, alias SETUP_LATEST, manifesto e checksums
   conforme `RELEASE_BUILD.md`; executar `verify_release` no OFFLINE final.
5. Conferir inventário final, atlas autorizados, ausência de DICOM/configuração
   privada e todos os hashes. Preservar as licenças originais.
6. Anexar os artefatos imutáveis da mesma versão ao rascunho privado por acesso
   autorizado. Conferir tamanho e `digest` SHA-256 do asset OFFLINE na API GitHub.
7. Decidir a publicação e o acesso de distribuição. Enquanto privado, somente
   usuários autorizados conseguem baixar; nenhum token integra o pacote.
8. Após publicar, testar `releases/latest` com acesso autorizado e uma instalação
   isolada. Não prometer download público enquanto o repositório continuar privado.

A base Local Suite e o Recon3D públicos não recebem os novos patches por efeito
deste workflow. Aplicar ambos privadamente ou preparar uma base privada compatível.
Publicação pública, merge e exclusão futura do Nidus são decisões separadas.
