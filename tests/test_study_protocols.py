import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from neuro_rt.contracts import validate_study_request
from neuro_rt.model_registry import load_catalog
from neuro_rt.roi_registry import make_roi_identity
from neuro_rt.series_selection import describe_resolved_series, suggest_protocol_bindings
from neuro_rt.service import Settings
from neuro_rt.study_protocols import ADVANCED, BUTI, CEREBRA, OARS, SIMPLE, SYNTHSEG, protocols_for
from neuro_rt.study_service import StudyService
from neuro_rt.protocol_presets import ProtocolPresets
from neuro_rt.orchestrator import build_study_plan
from neuro_rt.study_types import SeriesDescriptor


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {s['id']: s for s in load_catalog()}
        self.ref = SeriesDescriptor('ce', '1.2.3', 'subject', 'study', 'MR',
            geometry={'size_xyz':[32,32,32], 'spacing_xyz_mm':[1,1,1], 'origin_lps_mm':[0,0,0],
                      'direction_lps':[1,0,0,0,1,0,0,0,1]}, frame_of_reference_uid='1.2.99')
        self.ref = self.describe(self.ref, 'T1_COR_PÓS_CONTRASTE')
        self.flair = self.describe(replace(self.ref, ticket='flair', series_uid='1.2.4'), 'T2 FLAIR')
        self.pre = self.describe(replace(self.ref, ticket='pre', series_uid='1.2.5'), 'T1 sem contraste')
        self.ct = self.describe(replace(self.ref, ticket='ct', series_uid='1.2.6', modality='CT'), 'CT')
        self.series = [self.ref, self.flair, self.pre, self.ct]
        self.index = {s.ticket: s for s in self.series}

    @staticmethod
    def describe(raw, description):
        return describe_resolved_series(raw.ticket, dict(raw.to_dict(), metadata={'SeriesDescription': description}))

    def bindings(self, model, reference, series=None):
        return [b.to_dict() for b in suggest_protocol_bindings(
            self.series if series is None else series, self.catalog[model], reference)]

    def request(self, protocol, ref, models):
        return {'schema': 'neuro-rt/request/2', 'explicit_request': True, 'request_id': 'request',
                'studies': [{'study_id': 'study', 'reference': ref.ticket, 'protocol_id': protocol,
                            'model_ids': models, 'bindings_by_model': {
                                mid: self.bindings(mid, ref) for mid in models}}]}

    def test_scoped_anatomy_on_explicit_postcontrast_and_ct_only_buti(self):
        self.assertEqual([row['model_id'] for row in protocols_for('CT', self.catalog)], [BUTI])
        self.assertNotIn(BUTI, [row['id'] for row in protocols_for('MR', self.catalog)])
        for p, ref, models in [(SIMPLE, self.ref, [SYNTHSEG, CEREBRA]),
                              (ADVANCED, self.ref, [SYNTHSEG]), (BUTI, self.ct, [BUTI])]:
            request = validate_study_request(self.request(p, ref, models), self.catalog, self.index)
            self.assertEqual(request.studies[0].protocol_id, p)
            self.assertEqual(request.studies[0].bindings_by_model[models[0]][0].series_ticket, ref.ticket)
        self.assertEqual(self.bindings('MRI_GBM', self.pre), [])
        self.assertEqual(self.bindings('MRI_GBM', self.flair), [])
        ambiguous = self.describe(self.ref, 'T1 COR')
        for model in ('MRI_GBM', 'MRI_Metastasis', 'MRI_Meningioma'):
            self.assertEqual(self.bindings(model, ambiguous, [ambiguous]), [])
        self.assertTrue(self.bindings(SYNTHSEG, ambiguous, [ambiguous]))

    def test_multichannel_never_substitutes_other_reference_or_another_patient(self):
        mid = 'MRI_GBM_Postop_FV_3p'
        supplied = self.bindings(mid, self.ref)
        self.assertEqual({b['role']: b['series_ticket'] for b in supplied},
                         {'T1c': 'ce', 'T1': 'pre', 'FLAIR': 'flair'})
        foreign = replace(self.flair, subject_key='other')
        self.assertNotIn('FLAIR', [b['role'] for b in self.bindings(mid, self.ref, [self.ref,self.pre,foreign])])
        request = self.request(mid, self.ref, [mid])
        request['studies'][0]['reference'] = self.pre.ticket
        with self.assertRaisesRegex(ValueError, 'referência'):
            validate_study_request(request, self.catalog, self.index)
        request = self.request('MRI_GBM', self.pre, ['MRI_GBM'])
        request['studies'][0]['bindings_by_model']['MRI_GBM'] = [{'role': 'T1c','series_ticket':'pre'}]
        with self.assertRaisesRegex(ValueError, 'Sequência'):
            validate_study_request(request, self.catalog, self.index)
        request = self.request('MRI_LGGlioma', self.flair, ['MRI_LGGlioma', CEREBRA])
        self.assertNotEqual(request['studies'][0]['bindings_by_model'][CEREBRA][0]['series_ticket'], 'flair')
        validate_study_request(request, self.catalog, self.index)

    def test_atlas_prefers_covered_native_t1_and_preserves_reference_when_no_compatible_volume(self):
        def choice(items):
            return self.bindings(CEREBRA,self.ref,[self.ref,*items])[0]['series_ticket']
        self.assertEqual(choice([self.pre]), 'pre')
        self.assertEqual(choice([]), 'ce')
        finer = replace(self.pre, geometry=dict(self.pre.geometry, size_xyz=[63,63,63], spacing_xyz_mm=[.5,.5,.5]))
        self.assertEqual(choice([finer]), 'pre')
        for incompatible in (replace(self.pre, subject_key='other'), replace(self.pre, study_key='older'),
                replace(self.pre, frame_of_reference_uid='different'), replace(self.pre, geometry={}),
                replace(self.pre, geometry=dict(self.pre.geometry, origin_lps_mm=[0,0,30]))):
            self.assertEqual(choice([incompatible]), 'ce')
        request = self.request(ADVANCED, self.ref, [SYNTHSEG,CEREBRA])
        chosen = request['studies'][0]['bindings_by_model'][CEREBRA][0]
        chosen.update(series_ticket='ce', association_source='manual')
        accepted = validate_study_request(request,self.catalog,self.index)
        self.assertEqual(accepted.studies[0].bindings_by_model[CEREBRA][0].series_ticket,'ce')

    def test_picker_grid_matches_oblique_dicom_axes_and_slice_order(self):
        from integration.default_host_services import _picker_geometry
        ds = SimpleNamespace(ImageOrientationPatient=[0,1,0, 0,0,-1],
            PixelSpacing=[.85,.7], Rows=52, Columns=46)
        files = [{'ipp':[10 - i*1.5,20,30]} for i in range(8)]
        g = _picker_geometry(ds, files)
        self.assertEqual(g['size_xyz'], [46,52,8])
        self.assertEqual(g['spacing_xyz_mm'], [.7,.85,1.5])
        self.assertEqual(g['origin_lps_mm'], [10,20,30])
        self.assertEqual(g['direction_lps'], [0,0,-1,1,0,0,0,-1,0])
        self.assertEqual(_picker_geometry(ds,[{'ipp':[]}, {'ipp':[]}]), {})

    def test_failed_registration_uses_reference_only_for_suggested_atlas_input(self):
        from neuro_rt.adapters.base import ModelRunContext
        from neuro_rt.study_types import InputBinding, ModelResult
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(root)
            service = StudyService(settings, SimpleNamespace(), catalog=self.catalog)
            spec = dict(self.catalog[CEREBRA], protocol_id=ADVANCED)
            ctx = ModelRunContext(spec,[InputBinding('T1','pre','certain','suggested')],
                self.ref,self.index,{'ce':root/'ce.nii','pre':root/'pre.nii'},
                root/'job',root,'cpu')
            settings.model_runtime_status = Mock(return_value={'available':True})
            settings.worker_command = Mock(return_value=['synthetic'])
            def run(command, job, *args, **kwargs):
                configured = json.loads((job/'model-context.json').read_text(encoding='utf8'))
                self.assertEqual(configured['bindings'][0]['series_ticket'],'ce')
                (job/'model-result.json').write_text(json.dumps(ModelResult(CEREBRA,'empty').to_dict()))
            service._execute = run
            result = service.run_model(spec,ctx,threading.Event())
            self.assertEqual(result.warnings[0].code,'atlas_reference_fallback')
            ctx.bindings = [InputBinding('T1','pre','certain','manual')]
            with self.assertRaisesRegex(ValueError,'registrar'):
                service.run_model(spec,ctx,threading.Event())

    def test_picker_header_before_selection_and_one_weight_check_for_multiple_cards(self):
        with tempfile.TemporaryDirectory() as folder:
            host = SimpleNamespace(device_preference=lambda: 'auto', resolve_series_ticket=lambda ticket: dict(self.index[ticket].to_dict(),
                preview_header=[['Matriz', '64 × 64']]))
            service = StudyService(Settings(Path(folder)), host, catalog=self.catalog)
            checked = []
            def caps():
                checked.append(1)
                return {'models':{m:{'status':'ready'} for m in self.catalog},
                        'runtimes':{s['runtime_id']:{'available':True} for s in self.catalog.values()
                                    if 'runtime_id' in s}}
            service.capabilities = caps
            tickets = list(self.index)
            identified = service.selection(tickets, 'unified', identify_only=True)
            self.assertTrue(identified['series'][0]['preview_header'])
            self.assertFalse(checked)
            selected = service.selection(tickets, 'unified', reference='ce')
            ct = service.selection(tickets, 'unified', reference='ct')
            self.assertEqual(len(checked), 1)
            self.assertEqual([row['id'] for row in ct['protocols']], [BUTI])
            atlas = next(m for m in selected['models'] if m['id'] == CEREBRA)
            self.assertEqual(set(atlas['binding_options']['T1']), {'ce','pre'})
            self.assertEqual(atlas['bindings'][0]['series_ticket'], 'pre')
            self.assertTrue(next(m for m in selected['models'] if m['id'] == SYNTHSEG)['eligibility']['selectable'])
            self.assertFalse(next(m for m in selected['models'] if m['id'] == 'MRI_LGGlioma')['eligibility']['selectable'])
            host.device_preference = lambda: 'cuda'
            gpu = service.selection(tickets, 'unified', reference='ce')
            synth = next(m for m in gpu['models'] if m['id'] == SYNTHSEG)
            self.assertIn('unsupported_device', [r['code'] for r in synth['eligibility']['technical_reasons']])

    def test_all_selected_native_names_are_distinct_with_an_atlas_in_one_study(self):
        for profile, classes in [(ADVANCED, self.catalog[SYNTHSEG]['classes']),
                                 (SIMPLE, [{'class_id': 'oar_' + n} for n in OARS])]:
            names = [make_roi_identity(mid, c['class_id'], 1, catalog=self.catalog, protocol=profile).roi_name
                     for mid, rows in [(SYNTHSEG, classes), (CEREBRA, self.catalog[CEREBRA]['classes'])]
                     for c in rows]
            self.assertEqual(len(set(names)), len(names))
            self.assertLessEqual(max(map(len, names)), 16)

    def test_new_plan_explicitly_combines_findings_and_limits_execution_to_nonempty_outputs(self):
        findings = ['MRI_GBM','MRI_Meningioma','MRI_Metastasis']
        models = [SYNTHSEG, *findings[:2]]
        payload = self.request(None,self.ref,models)
        item = payload['studies'][0]
        item['plan'] = {'anatomy':SIMPLE,'findings':findings,
            'rois':{SYNTHSEG:['oar_Brainstem'], findings[0]:['tumor'],findings[1]:['tumor'],findings[2]:[]}}
        request = validate_study_request(payload,self.catalog,self.index)
        plan = build_study_plan(request.studies[0],self.catalog)
        self.assertEqual(plan.selected_model_ids,tuple(models))
        self.assertEqual(plan.model_steps[0]['study_classes'],['oar_Brainstem'])
        # A retried request has precisely the same delivery plan.
        self.assertEqual(validate_study_request(request.to_dict(),self.catalog,self.index).to_dict(),request.to_dict())
        removed = item['plan']['findings'].pop()
        with self.assertRaises(ValueError): validate_study_request(payload,self.catalog,self.index)
        del item['plan']['rois'][removed]
        item['plan']['rois'][SYNTHSEG] = ['left_hippocampus']
        with self.assertRaises(ValueError): validate_study_request(payload,self.catalog,self.index)
        item['plan']['rois'][SYNTHSEG] = []
        with self.assertRaises(ValueError): validate_study_request(payload,self.catalog,self.index)

    def test_anatomy_is_optional_and_competing_anatomy_is_rejected(self):
        payload = self.request(None,self.ref,['MRI_GBM'])
        item = payload['studies'][0]
        item['plan']={'anatomy':None,'findings':['MRI_GBM'],'rois':{'MRI_GBM':['tumor']}}
        self.assertEqual(validate_study_request(payload,self.catalog,self.index).studies[0].model_ids,['MRI_GBM'])
        item['plan']['anatomy']=[SIMPLE,CEREBRA]
        with self.assertRaises(ValueError): validate_study_request(payload,self.catalog,self.index)
        # Previously accepted two-atlas requests can still be reopened and retried.
        old = self.request(SIMPLE,self.ref,[SYNTHSEG,CEREBRA])
        self.assertEqual(len(validate_study_request(old,self.catalog,self.index).studies[0].model_ids),2)

    def test_station_preset_roundtrip_without_identifiers_and_by_modality(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProtocolPresets(self.catalog,directory)
            row = {'name':'Parcial','modality':'CT','plan':{'anatomy':BUTI,'findings':[],'rois':{BUTI:['Chiasm']}}}
            store.save(row); store.save(row)
            loaded = ProtocolPresets(self.catalog,directory).list('CT')
            self.assertEqual(len(loaded),1)
            self.assertEqual(loaded[0]['plan'],row['plan'])
            self.assertEqual(store.list('MR'),[])
            with self.assertRaises(ValueError): store.save(dict(row,patient_id='inventado'))
            store.save(dict(loaded[0], name='Crânio'))
            self.assertEqual(store.list()[0]['name'],'Crânio')
            store.delete(loaded[0]['id'])
            self.assertEqual(store.list(),[])
