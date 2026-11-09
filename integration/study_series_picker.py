"""Compose Neuro's series picker with the Local Suite renderer."""
from inspect import signature


def _legacy_folder(radai_ui):
    return '''<form id="nr-picker-form" class="nr-picker-form">
<div class="nr-picker-field"><input type="text" id="nr-picker-folder" spellcheck="false"
 autocomplete="off" aria-label="pasta com as séries" placeholder="pasta com as séries">{favorite}</div>
<button type="button" class="ui-bt" id="nr-picker-browse">{folder_icon}<span data-radai-frase>Procurar</span></button>
<button type="submit" class="ui-bt pri"><span data-radai-frase>Listar séries</span></button>
</form>
{date_filter}
<div class="ui-vl-est" id="nr-picker-scan-status" role="status" aria-live="polite"></div>'''.format(
        favorite=radai_ui.botao_favorita('nr-picker-folder'),
        folder_icon=radai_ui.icone('pasta'),
        date_filter=radai_ui.filtro_de_data('nr-picker-days', valor='0'),
    )


def render_series_picker(page):
    import radai_tabela_acervo
    import radai_ui

    def content(folder):
        results = '<div id="nr-picker-results" class="nr-picker-results" aria-label="séries da pasta"></div>'
        help_html = radai_ui.ajuda('No Acervo Local estão as séries que este programa contornou nesta estação.',
                                  'Para ver uma série contornada em outra estação, use a aba Aponte uma pasta.')
        archive = '<div class="nr-picker-help">' + help_html + '</div>' + radai_tabela_acervo.html('nr-picker-archive')
        tabs = radai_ui.abas_de_serie('nr-picker-source', [
            ('folder', 'Aponte uma pasta', folder + results),
            ('archive', 'Acervo Local', archive),
        ], cor_var='--mod-nidus', lembrar=True)
        return tabs + '<p id="nr-picker-status" role="status" aria-live="polite" hidden></p>'

    ident = 'nr-series-picker'
    title = 'Carregar imagens'
    shared = getattr(radai_ui, 'formulario_carregar_imagens', None)
    if shared and 'envolver' in signature(shared).parameters:
        popup = shared(ident, dias='0', titulo=title, envolver=content)
    else:
        popup = radai_ui.popup_de_serie(ident, content(_legacy_folder(radai_ui)), titulo=title, largura=920)
    trigger = radai_ui.cartao_de_serie('nr-picker-open', ident, 'Adicionar novas séries',
                                      vazio='Nenhuma série selecionada.', chave_modulo='nidus',
                                      ident_rot='nr-picker-count')
    trigger = trigger.replace('type="button"', 'type="button" disabled', 1)
    return page.replace('<!--NEURO_SERIES_TRIGGER-->', trigger).replace('<!--NEURO_SERIES_POPUP-->', popup)
