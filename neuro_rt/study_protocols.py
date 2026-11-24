"""Per-series delivery profiles. Model IDs and on-disk weights remain canonical."""

SIMPLE = 'snc_rm_simples'
ADVANCED = 'snc_rm_avancado'
SYNTHSEG = 'anatomy_synthseg'
CEREBRA = 'anatomy_cerebra_ants'
BUTI = 'cranio_buti'
TUMOUR_GROUPS = {'glioma', 'meningioma', 'metastasis'}

# Same native SynthSeg values and TPS names as the suite's radai_snc_rm.
# The merges operate on the predicted label image, before mask restoration.
OARS = {
    'Brainstem': (16,), 'Hippocampus_L': (17,), 'Hippocampus_R': (53,),
    'Cerebellum': (7, 8, 46, 47), 'Ventricles': (4, 5, 14, 15, 43, 44),
    'Thalamus_L': (10,), 'Thalamus_R': (49,),
    'Amygdala_L': (18,), 'Amygdala_R': (54,), 'GlobusPallidus': (13, 52),
}

# Abbreviations retain laterality within the suite's 16-character TPS limit
# (including "_ai"). C marks an independent CerebrA atlas ROI.
_ANATOMY = {
    '3rd_ventricle': 'Vent3', '4th_ventricle': 'Vent4', 'CSF': 'CSF',
    'accumbens_area': 'Accumbens', 'amygdala': 'Amygdala', 'basal_forebrain': 'BasalFore',
    'brain-stem': 'Brainstem', 'brainstem': 'Brainstem',
    'caudal_anterior_cingulate': 'CaudAntCng', 'caudal_middle_frontal': 'CaudMidFr',
    'caudate': 'Caudate', 'cerebellum_cortex': 'CerebelCtx', 'cerebellum_gray_matter': 'CerebelGM',
    'cerebellum_white_matter': 'CerebelWM', 'cerebral_cortex': 'CerebrCtx',
    'cerebral_white_matter': 'CerebrWM', 'cuneus': 'Cuneus', 'entorhinal': 'Entorhinal',
    'fourth_ventricle': 'Vent4', 'fusiform': 'Fusiform', 'hippocampus': 'Hippocamp',
    'inferior_lateral_ventricle': 'InfLatVent', 'inferior_parietal': 'InfPariet',
    'inferior_temporal': 'InfTemp', 'insula': 'Insula', 'isthmus_cingulate': 'IsthmCng',
    'lateral_occipital': 'LatOccip', 'lateral_orbitofrontal': 'LatOrbFr',
    'lateral_ventricle': 'LatVent', 'lingual': 'Lingual', 'medial_orbitofrontal': 'MedOrbFr',
    'middle_temporal': 'MidTemp', 'optic_chiasm': 'Chiasm', 'pallidum': 'Pallidum',
    'paracentral': 'Paracent', 'parahippocampal': 'Parahipp', 'pars_opercularis': 'ParsOper',
    'pars_orbitalis': 'ParsOrbit', 'pars_triangularis': 'ParsTriang', 'pericalcarine': 'PeriCalc',
    'postcentral': 'Postcentr', 'posterior_cingulate': 'PostCng', 'precentral': 'Precentr',
    'precuneus': 'Precuneus', 'putamen': 'Putamen', 'rostral_anterior_cingulate': 'RostAntCng',
    'rostral_middle_frontal': 'RostMidFr', 'superior_frontal': 'SupFront',
    'superior_parietal': 'SupPariet', 'superior_temporal': 'SupTemp', 'supramarginal': 'Supramarg',
    'thalamus': 'Thalamus', 'third_ventricle': 'Vent3', 'transverse_temporal': 'TransvTemp',
    'ventral_DC': 'VentDC', 'ventral_diencephalon': 'VentDC', 'vermal_lobules_i_v': 'Verm1to5',
    'vermal_lobules_vi_vii': 'Verm6to7', 'vermal_lobules_viii_x': 'Verm8to10',
}


def anatomical_tps_name(model_id, class_id):
    if model_id == BUTI:
        return 'Ventricles' if class_id == 'Ventricles_connected' else class_id
    if model_id == 'glioma_attention_unet3d':
        return {'whole_tumor': 'GliomaWhole', 'tumor_core': 'GliomaCore',
                'enhancing_tumor': 'GliomaEnh'}[class_id]
    if class_id == 'tumor':
        return {'MRI_GBM': 'GBM_Pre', 'MRI_LGGlioma': 'LGGlioma',
                'MRI_GBM_Postop_FV_1p': 'GBM_Post1seq', 'MRI_GBM_Postop_FV_3p': 'GBM_Post3seq',
                'MRI_Meningioma': 'Meningioma', 'MRI_Metastasis': 'Metastasis'}.get(model_id)
    if model_id not in (SYNTHSEG, CEREBRA):
        return None
    if model_id == SYNTHSEG and class_id.startswith('oar_') and class_id[4:] in OARS:
        return 'GlobPallidus' if class_id == 'oar_GlobusPallidus' else class_id[4:]
    stem = class_id.removeprefix('left_').removeprefix('right_')
    side = '_L' if class_id.startswith('left_') else '_R' if class_id.startswith('right_') else ''
    return ('C' if model_id == CEREBRA else '') + _ANATOMY[stem] + side


def result_classes(spec):
    """Native classes plus the labelled exports a persisted SynthSeg result can contain."""
    native = spec['classes']
    if spec['id'] != SYNTHSEG:
        return native
    return [*native, *({'class_id': 'oar_' + name, 'label': name} for name in OARS)]


def plan_outputs(modality, catalog):
    """STUDY tags for each independently selectable option, before inference."""
    options = protocols_for(modality, catalog)
    if modality == 'MR' and CEREBRA in catalog:
        options.append({'id': CEREBRA, 'model_id': CEREBRA})
    outputs = {}
    for option in options:
        mid, key = option['model_id'], option['id']
        classes = ([{'class_id': 'oar_' + n, 'label': n} for n in OARS] if key == SIMPLE
                   else catalog[mid]['classes'])
        outputs[key] = [{'class_id': c['class_id'], 'label': c['label'],
                         'roi_name': (anatomical_tps_name(mid, c['class_id']) or c['class_id']) + '_ai'}
                        for c in classes]
    return outputs


def validate_delivery_plan(value, modality, catalog):
    """Normalize station presets and per-series requests against the same catalog."""
    if not isinstance(value, dict) or set(value) != {'anatomy','findings','rois'}:
        raise ValueError('Informe anatomia, achados e estruturas do STUDY.')
    anatomy, findings, selected = value['anatomy'], value['findings'], value['rois']
    allowed = {SIMPLE, ADVANCED, CEREBRA} if modality == 'MR' else {BUTI} if modality == 'CT' else set()
    if not allowed or (anatomy is not None and (not isinstance(anatomy, str) or anatomy not in allowed)):
        raise ValueError('Escolha um protocolo anatômico da modalidade ou nenhum.')
    if (not isinstance(findings,list) or not all(isinstance(mid,str) for mid in findings)
            or len(set(findings)) != len(findings)):
        raise ValueError('Selecione individualmente os achados desejados.')
    if any(modality != 'MR' or mid not in catalog or not TUMOUR_GROUPS.intersection(catalog[mid]['groups'])
           or catalog[mid]['catalog_state'] not in ('verified', 'distributed') for mid in findings):
        raise ValueError('O achado não está disponível para essa modalidade.')
    options = ([anatomy] if anatomy else []) + findings
    outputs = plan_outputs(modality, catalog)
    ids = [SYNTHSEG if opt in (SIMPLE,ADVANCED) else opt for opt in options]
    if not isinstance(selected,dict) or set(ids) != set(selected):
        raise ValueError('As estruturas precisam pertencer às tarefas selecionadas.')
    normalized = {}
    for option,mid in zip(options,ids):
        if option not in outputs:
            raise ValueError('A tarefa não pertence ao catálogo instalado.')
        chosen = selected[mid]
        valid = [row['class_id'] for row in outputs[option]]
        if (not isinstance(chosen,list) or not all(isinstance(key,str) for key in chosen)
                or len(set(chosen)) != len(chosen) or not set(chosen) <= set(valid)):
            raise ValueError('A estrutura não pertence ao plano desse modelo.')
        normalized[mid] = [k for k in valid if k in chosen]
    if not any(normalized.values()):
        raise ValueError('Selecione pelo menos uma estrutura para entregar ao STUDY.')
    return {'anatomy':anatomy, 'findings':list(findings), 'rois':normalized}


def protocols_for(modality, catalog):
    if modality == 'CT':
        return [{'id': BUTI, 'label': 'Crânio em TC · Buti', 'model_id': BUTI}] if BUTI in catalog else []
    if modality != 'MR':
        return []
    protocols = []
    if SYNTHSEG in catalog:
        protocols.extend([{'id': SIMPLE, 'label': 'SNC RM Simples', 'model_id': SYNTHSEG},
                          {'id': ADVANCED, 'label': 'SNC RM Avançado', 'model_id': SYNTHSEG}])
    protocols.extend({'id': mid, 'label': spec['label'], 'model_id': mid}
                     for mid, spec in catalog.items() if TUMOUR_GROUPS.intersection(spec['groups']))
    return protocols


def accepts_channel(spec, descriptor, role):
    """For protocol suggestions, unidentified MR channels never imply tumour contrast."""
    if role == 'CT':
        return descriptor.modality == 'CT'
    if descriptor.modality != 'MR':
        return False
    known = {c.get('role') for c in descriptor.sequence_candidates if c.get('role')}
    if spec['id'] in (SYNTHSEG, CEREBRA):
        return role == 'T1' and (not known or bool(known.intersection(('T1', 'T1c'))))
    if role == 'T1c':
        return any(c.get('role') == 'T1c' and c.get('certainty') == 'certain'
                   for c in descriptor.sequence_candidates)
    return role in known


def validate_protocol(protocol, catalog, reference, models, bindings, series_index, selected_classes):
    rows = protocols_for(reference.modality, catalog)
    main = next((row['model_id'] for row in rows if row['id'] == protocol), None)
    if not main and protocol != 'personalizado':
        raise ValueError('Protocolo incompatível com a modalidade selecionada.')
    allowed = {row['model_id'] for row in rows}
    if reference.modality == 'MR':
        allowed.add(CEREBRA)
    if (main and main not in models) or not set(models) <= allowed or selected_classes:
        raise ValueError('Seleção de tarefas ou estruturas incompatível com o protocolo.')
    for mid in models:
        spec = catalog[mid]
        for b in bindings[mid]:
            source = series_index[b.series_ticket]
            if source.geometry.get('readable') is False or source.geometry.get('valid') is False or source.geometry.get('errors'):
                raise ValueError('Uma série do protocolo tem falha de leitura ou geometria.')
            if mid != CEREBRA and b.role == spec['reference_role'] and b.series_ticket != reference.ticket:
                raise ValueError('O canal de referência do protocolo deve usar a série selecionada.')
            if not accepts_channel(spec, source, b.role):
                raise ValueError('Sequência incompatível com o canal exigido pelo protocolo.')
            if mid == CEREBRA:
                from .series_selection import atlas_binding_allowed
                if not atlas_binding_allowed(spec, source, reference):
                    raise ValueError('O T1 do atlas precisa cobrir a referência no mesmo quadro DICOM.')
