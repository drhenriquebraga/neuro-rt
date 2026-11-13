"""Extend the host locale tables for NEURO RT pages."""
import json
from pathlib import Path
import re


def with_catalog(page, *names, study=False):
    import radai_languages

    root = Path(__file__).resolve().parents[1] / 'web'
    catalog = {}
    for name in names:
        if name == 'nidus-temporal':
            from neuro_rt.nidus_temporal_i18n import merge_catalog
            catalog = merge_catalog(catalog)
            continue
        data = json.loads((root / (name + '-i18n.json')).read_text(encoding='utf-8'))
        for language, phrases in data.items():
            catalog.setdefault(language, {}).update(phrases)
    addition = (
        'var neuroExtra=' + json.dumps(catalog, ensure_ascii=True).replace('<', '\\u003c')
        + ';Object.keys(neuroExtra).forEach(function(c){'
        + 'FRASES[c]=Object.assign({},FRASES[c]||{},neuroExtra[c]);});\n'
    )
    script = radai_languages.corpo_js().replace('var ALIAS=', addition + 'var ALIAS=', 1)
    page = re.sub(
        r'<script id="radai-idioma-js" src="[^"]+" defer></script>',
        lambda _: '<script id="radai-idioma-js">' + script + '</script>', page,
    )
    if study:
        keys = json.dumps(list(catalog['pt-BR']), ensure_ascii=True).replace('<', '\\u003c')
        page = page.replace('</head>', '<script>window.NEURO_TRANSLATION_KEYS=' + keys + ';</script></head>', 1)
    return page
