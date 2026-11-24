"""Compose the two-step Neuro workflow from the suite's shared controls."""
from pathlib import Path

from integration.localization import with_catalog


def pagina_processo(host_services=None):
    import radai_menu
    import radai_tabela_acervo
    import radai_todo
    import radai_ui

    web = Path(__file__).resolve().parents[1] / 'web'
    page = (web / 'process.html').read_text(encoding='utf-8')
    header = radai_ui.cabeca_de_funcao(
        'neuro_anatomia', 'AutoContorno Neuro',
        'Escolha as séries e os modelos para estudar a anatomia e as lesões na referência.',
        ajuda_html=radai_ui.ajuda('Os contornos gerados são sugestões para estudo.',
                                 'Confira as séries de entrada, a referência e os contornos no TPS antes de usar o resultado.'),
        chave_modulo='nidus')
    page = page.replace('<!--HEADER-->', header)
    buttons, dialogs = [], []
    for modality, title in (('CT', 'Adicionar novas séries de Tomografia'),
                            ('MR', 'Adicionar novas séries de Ressonância')):
        ident = 'nr-add-' + modality
        def wrap(folder, prefix=ident):
            return radai_ui.abas_de_serie(prefix + '-source', [
                ('folder', 'Aponte uma pasta', folder),
                ('archive', 'Acervo Local', radai_tabela_acervo.html(prefix + '-archive')),
            ], cor_var='--mod-nidus', lembrar=True)
        dialogs.append(radai_ui.formulario_carregar_imagens(ident, dias='0', titulo=title, envolver=wrap))
        card = radai_ui.cartao_de_serie(ident + '-open', ident, title,
            vazio='Nenhuma série selecionada.', ident_rot=ident + '-count', chave_modulo='nidus')
        buttons.append(card.replace('type="button"', 'type="button" disabled', 1))
    before, sources, selected, after = page.split('<!--STEP-->')
    page = before + radai_ui.passo(1, 'Séries do exame', sources.replace('<!--PICKERS-->', ''.join(buttons)))
    page += radai_ui.passo(2, 'Séries selecionadas', selected) + after.replace('<!--DIALOGS-->', ''.join(dialogs))
    page = radai_menu.aplicar(radai_ui.aplicar(page), 'neuro_anatomia')
    return with_catalog(radai_todo.aplicar(page, tela='neuro_anatomia'), 'study', 'process')
