"""Compose the plugin landing page with the host's shared module renderer."""
import html
import json
import re
from pathlib import Path


def pagina_neuro(host_services, plugin_status):
    import radai_menu
    import radai_modules
    page = radai_modules.pagina_completa('neuro')
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
    if category not in ('glioma', 'metastasis', 'meningioma', 'anatomia'):
        raise ValueError('Categoria Neuro desconhecida.')
    import radai_menu
    title = {'glioma': 'Glioma RT', 'metastasis': 'Metastasis RT',
             'meningioma': 'Meningioma RT', 'anatomia': 'Anatomia RT'}[category]
    import radai_ui
    import radai_todo
    page = (Path(__file__).resolve().parents[1] / 'web' / 'study.html').read_text(encoding='utf-8')
    page = page.replace('__NEURO_TITLE__', html.escape(title)).replace('__NEURO_CATEGORY__', category)
    # The renderer remains owned by the host. Include its current implementation
    # at composition time instead of shipping a fork or opening another iframe.
    import radai_viewer
    import radai_recon3d_screen
    renderer = radai_viewer.JS_3D + '\n' + radai_recon3d_screen.JS_MALHA
    page = page.replace('<!--NEURO_HOST_RENDERER-->', '<script>' + renderer + '</script>')
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
