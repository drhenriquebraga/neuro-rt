"""Compose the plugin landing page with the host's shared module renderer."""
import html
import json
import re
from pathlib import Path


def _pagina_ferramentas(renderer):
    """Use the host's own cards without modifying its shared module globals."""
    from neuro_rt.tool_availability import TOOLS
    tools = {tool.card_id: tool for tool in TOOLS}
    cards = renderer.FERRAMENTAS.get('neuro', ())
    if len(cards) != len(tools) or {card[0] for card in cards} != set(tools):
        raise RuntimeError('O contrato de ferramentas NEURO RT do host não corresponde ao plugin.')
    page = renderer.pagina_completa('neuro')
    color = renderer.CORES.get('neuro', ('--accent', '--accent-fraco'))[0]
    for card in cards:
        tool = tools[card[0]]
        entry = list(card)
        while len(entry) < 6:
            entry.append('')
        entry[2] = tool.display_title
        entry[3] = '/neuro/testing/' + tool.id
        entry[5] = tool.label
        original = renderer._cartao(card, color)
        replacement = renderer._cartao(entry, color)
        if page.count(original) != 1:
            raise RuntimeError('O renderer de ferramentas NEURO RT do host mudou.')
        page = page.replace(original, replacement, 1)
    return page


def pagina_neuro(host_services, plugin_status):
    import radai_menu
    import radai_modules
    from neuro_rt import plugin_consent

    page = _pagina_ferramentas(radai_modules)
    help_html = radai_modules.ajuda_do_modulo('neuro')
    if help_html and help_html in page:
        policy = plugin_consent.policy()
        title = html.escape(f"{policy['title']} — {policy['version']}")
        terms = f'<p id="neuro-terms-help" translate="no"><b class="hm-aj-t">{title}</b></p>'
        terms += ''.join('<p translate="no">' + html.escape(clause['text']) + '</p>'
                         for clause in policy['clauses'])
        terms += '<p>Na interface atual, o aceite da fase de testes é lembrado por ferramenta.</p>'
        close = '</span></span>'
        if help_html.endswith(close):
            page = page.replace(help_html, help_html[:-len(close)] + terms + close, 1)
    panel = '''<section id="neuro-update" hidden aria-labelledby="neuro-update-title">
<h2 id="neuro-update-title">Atualização do NEURO RT</h2>
<p id="neuro-update-message" role="status" aria-live="polite"></p>
<progress id="neuro-update-progress" max="100" hidden aria-label="Atualização do NEURO RT"></progress>
<div id="neuro-update-actions"></div></section>'''
    page = page.replace('<div class="md-grade"', panel+'<div class="md-grade"', 1)
    page = page.replace('</head>', '''<style>
#neuro-update{padding:14px 16px;border:1px solid var(--line);border-radius:var(--r-md,6px);font:14px/1.5 var(--font-ui,Segoe UI,sans-serif)}
#neuro-update[hidden]{display:none}#neuro-update h2{font:600 15px/1.4 var(--font-ui,Segoe UI,sans-serif);margin:0 0 6px}
#neuro-update p{margin:0 0 10px}#neuro-update-actions{display:flex;gap:8px;flex-wrap:wrap}
#neuro-update progress{display:block;width:100%;height:7px;margin:8px 0;accent-color:var(--accent)}
#neuro-update progress[hidden]{display:none}
</style></head>''')
    reason = html.escape(str(plugin_status.get('reason') or ''))
    if reason:
        page = page.replace('</body>', '<p role="status">' + reason + '</p></body>')
    page = radai_menu.aplicar(page, 'neuro')
    import radai_languages
    root = Path(__file__).resolve().parents[1]
    catalog = json.loads((root / 'web/plugin-update-i18n.json').read_text(encoding='utf-8'))
    addition = ('var neuroUpdateExtra=' + json.dumps(catalog,ensure_ascii=True) +
        ';Object.keys(neuroUpdateExtra).forEach(function(c){FRASES[c]=Object.assign({},FRASES[c]||{},neuroUpdateExtra[c]);});\n')
    script = radai_languages.corpo_js().replace('var ALIAS=', addition+'var ALIAS=', 1)
    page = re.sub(r'<script id="radai-idioma-js" src="[^"]+" defer></script>',
        lambda _: '<script id="radai-idioma-js">'+script+'</script>', page)
    controller = (root / 'web/plugin-update.js').read_text(encoding='utf-8')
    return page.replace('</body>', '<script>'+controller+'</script></body>')


def pagina_estudo(category, host_services):
    import radai_menu
    import radai_ui
    import radai_todo
    from neuro_rt.tool_availability import require_tool

    icons = {'glioma': 'glioma', 'metastasis': 'metastases',
             'meningioma': 'meningioma', 'anatomia': 'neuro_anatomia'}
    if category not in icons:
        raise ValueError('Categoria Neuro desconhecida.')
    title = require_tool(category).display_title
    page = (Path(__file__).resolve().parents[1] / 'web' / 'study.html').read_text(encoding='utf-8')
    page = page.replace('__NEURO_TITLE__', html.escape(title)).replace('__NEURO_CATEGORY__', category)
    help_html = radai_ui.ajuda(
        'Esta ferramenta está em fase de testes. Os contornos gerados são sugestões para estudo.',
        'Confira as séries de entrada, a referência e os contornos no TPS antes de usar o resultado.',
    )
    header = radai_ui.cabeca_de_funcao(icons[category], title,
        'Escolha as séries e os modelos para estudar a anatomia e as lesões na referência.',
        ajuda_html=help_html, chave_modulo='nidus')
    alert = radai_ui.alerta('Resultados exigem revisão no TPS.', esquerda=True)
    page = page.replace('<!--NEURO_STUDY_HEADER-->', header + alert)
    prefix, series, models, results, suffix = page.split('<!--NEURO_STEP-->')
    steps = [('series-title', 'Séries do exame', series), ('models-title', 'Modelos', models),
             ('results-title', 'Estudos e resultados', results)]
    page = prefix + ''.join(
        radai_ui.passo(number, label, body).replace(
            '<span data-radai-frase>', f'<span id="{ident}" data-radai-frase>', 1)
        for number, (ident, label, body) in enumerate(steps, start=1)
    ) + suffix
    # The renderer remains owned by the host. Include its current implementation
    # at composition time instead of shipping a fork or opening another iframe.
    import radai_viewer
    import radai_recon3d_screen
    from integration.study_series_picker import render_series_picker

    renderer = radai_viewer.JS_3D + '\n' + radai_recon3d_screen.JS_MALHA
    page = page.replace('<!--NEURO_HOST_RENDERER-->', '<script>' + renderer + '</script>')
    page = render_series_picker(page)
    page = radai_menu.aplicar(radai_ui.aplicar(page), 'neuro_' + category)
    page = radai_todo.aplicar(page, tela='neuro_' + category)
    # Extend the shared translator only for this page; retain its language
    # selection, templates, accessibility attributes and RTL behavior.
    import radai_languages
    catalog=json.loads((Path(__file__).resolve().parents[1] / 'web/study-i18n.json').read_text(encoding='utf-8'))
    addition = 'var neuroExtra=' + json.dumps(catalog,ensure_ascii=True) + ';Object.keys(neuroExtra).forEach(function(c){FRASES[c]=Object.assign({},FRASES[c]||{},neuroExtra[c]);});\n'
    script = radai_languages.corpo_js().replace('var ALIAS=',addition+'var ALIAS=',1)
    page = re.sub(r'<script id="radai-idioma-js" src="[^"]+" defer></script>',lambda _: '<script id="radai-idioma-js">'+script+'</script>',page)
    page=page.replace('</head>','<script>window.NEURO_TRANSLATION_KEYS='+json.dumps(list(catalog['pt-BR']),ensure_ascii=True)+';</script></head>')
    return page
