"""Contract tests use only invented identifiers and metadata, never image files."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from neuro_rt import contracts


CATALOG = {
    'MRI_GBM': {'id': 'MRI_GBM', 'channels': [{'role': 'T1c'}],
                'classes': [{'class_id': 'tumor', 'label': 'Tumor'}]},
    'multi': {'id': 'multi', 'channels': [{'role': 'T1'}, {'role': 'T1c'},
                                        {'role': 'T2'}, {'role': 'FLAIR'}],
              'classes': [{'class_id': 1, 'label': 'Core'},
                          {'class_id': 2, 'label': 'Edema'}]},
}


def series(ticket, uid, subject='synthetic-subject', study='synthetic-study', **extra):
    return dict(ticket=ticket, series_uid=uid, subject_key=subject,
                study_key=study, modality='MR', geometry={'size': [8, 9, 10]},
                sequence_candidates=[], source_format='dicom', **extra)


def inventory():
    return {'t1': series('t1', '1.2.1'), 'ce': series('ce', '1.2.2'),
            't2': series('t2', '1.2.3'), 'flair': series('flair', '1.2.4')}


def binding(role, ticket, **extra):
    return dict(role=role, series_ticket=ticket, certainty='certain',
                association_source='manual', warnings=[], **extra)


def request():
    return {'schema': 'neuro-rt/request/2', 'request_id': 'intent-001',
            'explicit_request': True, 'studies': [
                {'study_id': 'study-001', 'reference': 'ce',
                 'model_ids': ['MRI_GBM', 'multi'], 'bindings_by_model': {
                     'MRI_GBM': [binding('T1c', 'ce')],
                     # Deliberately unordered: the artifact determines channel order.
                     'multi': [binding('FLAIR', 'flair'), binding('T2', 't2'),
                               binding('T1c', 'ce'), binding('T1', 't1')]}}]}


def result():
    return {'model_id': 'multi', 'status': 'completed', 'masks': [
        {'model_id': 'multi', 'class_id': 1, 'path': 'masks/core.nii.gz',
         'geometry': {'size': [8, 9, 10]}, 'space': 'reference',
         'provenance': {'adapter': 'synthetic'}}],
        'geometry': {'size': [8, 9, 10]},
        'transformations': [{'kind': 'identity', 'from': 'working', 'to': 'reference'}],
        'versions': {'engine': 'test-1'}, 'hashes': {'weights': 'a' * 64},
        'warnings': [{'code': 'UNCERTAIN_SEQUENCE', 'message': 'Synthetic warning'}],
        'errors': []}


class StudyContractTests(unittest.TestCase):
    def test_nonportable_windows_identifiers_are_rejected(self):
        reserved = ['CON', 'PRN', 'AUX', 'NUL'] + [f'{kind}{n}' for kind in ('COM', 'LPT') for n in range(1, 10)]
        values = ['study.', 'study..', 'study '] + reserved + [name.lower() + '.txt' for name in reserved]
        for field in ('request_id', 'study_id'):
            for value in values:
                with self.subTest(field=field, value=value):
                    payload = request()
                    (payload if field == 'request_id' else payload['studies'][0])[field] = value
                    self.check_error('invalid_identifier', payload)

    def check_error(self, code, payload, index=None, catalog=None):
        with self.assertRaises(ValueError) as caught:
            contracts.validate_study_request(payload, catalog or CATALOG,
                                             inventory() if index is None else index)
        self.assertEqual(caught.exception.code, code)

    def test_multiple_models_share_one_reference_and_preserve_channel_order(self):
        self.assertTrue(hasattr(contracts, 'validate_study_request'),
                        'Missing D01 study request validator')
        original = request()
        valid = contracts.validate_study_request(original, CATALOG, inventory())
        self.assertEqual(valid.request_id, 'intent-001')
        self.assertEqual(valid.studies[0].reference, 'ce')
        self.assertEqual(valid.studies[0].model_ids, ['MRI_GBM', 'multi'])
        self.assertEqual([b.role for b in valid.studies[0].bindings_by_model['multi']],
                         ['T1', 'T1c', 'T2', 'FLAIR'])
        self.assertEqual(original['studies'][0]['bindings_by_model']['multi'][0]['role'],
                         'FLAIR')
        encoded = json.loads(json.dumps(valid.to_dict()))
        self.assertEqual(contracts.validate_study_request(encoded, CATALOG, inventory()), valid)

    def test_explicit_act_is_boolean_true_only(self):
        for value in (None, False, 1, 'true'):
            with self.subTest(value=value):
                payload = request()
                payload['explicit_request'] = value
                self.check_error('explicit_request_required', payload)

    def test_unknown_model_reference_and_binding_ticket_have_specific_errors(self):
        for field, code in [('model', 'unknown_model'), ('reference', 'unknown_series'),
                            ('binding', 'unknown_series')]:
            with self.subTest(field=field):
                payload = request()
                item = payload['studies'][0]
                if field == 'model':
                    item['model_ids'][0] = 'not-in-catalog'
                elif field == 'reference':
                    item['reference'] = 'unknown-ticket'
                else:
                    item['bindings_by_model']['multi'][0]['series_ticket'] = 'unknown-ticket'
                self.check_error(code, payload)

    def test_binding_cannot_cross_subject_or_acquisition_study(self):
        for field in ('subject_key', 'study_key'):
            index = inventory()
            index['flair'][field] = 'another'
            self.check_error('inconsistent_subject' if field == 'subject_key'
                             else 'inconsistent_study', request(), index)

    def test_two_items_cannot_repeat_reference_even_through_alias_ticket(self):
        for alias in (False, True):
            payload = request()
            other = copy.deepcopy(payload['studies'][0])
            other['study_id'] = 'study-002'
            index = inventory()
            if alias:
                index['alias'] = series('alias', '1.2.2')
                other['reference'] = 'alias'
            payload['studies'].append(other)
            self.check_error('duplicate_reference', payload, index)

    def test_reference_uid_is_unique_even_if_inventory_subject_metadata_differs(self):
        payload = request()
        second = copy.deepcopy(payload['studies'][0])
        second.update(study_id='study-002', reference='alias')
        payload['studies'].append(second)
        index = inventory()
        index['alias'] = series('alias', '1.2.2', subject='other-subject')
        self.check_error('duplicate_reference', payload, index)

    def test_dicom_mr_to_ct_reference_is_not_an_implicit_transfer(self):
        index = inventory()
        index['ce']['modality'] = 'CT'
        self.check_error('inconsistent_modality', request(), index)

    def test_models_bindings_roles_and_inputs_cannot_be_duplicated_or_missing(self):
        cases = [('duplicate_model', lambda i: i['model_ids'].append('multi')),
                 ('missing_bindings', lambda i: i['bindings_by_model'].pop('multi')),
                 ('unexpected_bindings', lambda i: i['bindings_by_model'].update(extra=[])),
                 ('duplicate_role', lambda i: i['bindings_by_model']['multi'].append(binding('T1', 't1'))),
                 ('missing_roles', lambda i: i['bindings_by_model']['multi'].pop()),
                 ('unexpected_role', lambda i: i['bindings_by_model']['multi'].append(binding('CT', 'ce'))),
                 ('duplicate_input', lambda i: i['bindings_by_model']['multi'][0].update(series_ticket='t1'))]
        for code, mutate in cases:
            payload = request()
            mutate(payload['studies'][0])
            with self.subTest(code=code):
                self.check_error(code, payload)

    def test_uncertain_sequence_is_retained_without_blocking(self):
        payload = request()
        selected = payload['studies'][0]['bindings_by_model']['multi'][0]
        selected['certainty'] = 'uncertain'
        selected['association_source'] = 'suggested'
        selected['warnings'] = [{'code': 'SEQUENCE_UNCERTAIN', 'message': 'Check FLAIR'}]
        valid = contracts.validate_study_request(payload, CATALOG, inventory())
        chosen = valid.studies[0].bindings_by_model['multi'][3]
        self.assertEqual(chosen.certainty, 'uncertain')
        self.assertEqual(chosen.warnings[0].code, 'SEQUENCE_UNCERTAIN')

    def test_invalid_types_schema_device_and_identifiers_fail_at_boundary(self):
        cases = [('unsupported_schema', {'schema': 'neuro-rt/request/1'}),
                 ('invalid_type', {'studies': {}}),
                 ('empty_studies', {'studies': []}),
                 ('invalid_identifier', {'request_id': ''}),
                 ('invalid_device', {'device': 'AUTO'}),
                 ('invalid_type', {'export_rtstruct': 'yes'})]
        for code, change in cases:
            with self.subTest(change=change):
                self.check_error(code, {**request(), **change})
        payload = request()
        payload['studies'][0]['model_ids'] = 'multi'
        self.check_error('invalid_type', payload)
        payload = request()
        payload['studies'][0]['bindings_by_model']['multi'][0]['warnings'] = ['warning']
        self.check_error('invalid_type', payload)

    def test_untrusted_paths_and_unsupported_json_values_are_rejected(self):
        payload = request()
        payload['input_path'] = 'arbitrary-client-path'
        self.check_error('unexpected_field', payload)
        payload = request()
        payload['extra'] = float('nan')
        self.check_error('invalid_json', payload)
        index = inventory()
        index['ce']['ticket'] = 'wrong'
        self.check_error('invalid_series', request(), index)

    def test_reference_nifti_cannot_request_rtstruct_without_original_dicom(self):
        index = inventory()
        index['ce']['source_format'] = 'nifti'
        index['ce']['series_uid'] = ''
        valid = contracts.validate_study_request(request(), CATALOG, index)
        self.assertFalse(valid.export_rtstruct)
        self.check_error('dicom_reference_required', {**request(), 'export_rtstruct': True}, index)


class ResultContractTests(unittest.TestCase):
    def assert_result_error(self, code, payload):
        with self.assertRaises(ValueError) as caught:
            contracts.validate_model_result(payload, CATALOG['multi'])
        self.assertEqual(caught.exception.code, code)

    def test_masks_keep_stable_class_identity_versions_and_transformations(self):
        valid = contracts.validate_model_result(result(), CATALOG['multi'])
        self.assertEqual(valid.masks[0].class_id, 1)
        self.assertEqual(valid.versions, {'engine': 'test-1'})
        self.assertEqual(valid.transformations[0]['kind'], 'identity')
        self.assertEqual(valid.warnings[0].code, 'UNCERTAIN_SEQUENCE')
        self.assertEqual(contracts.validate_model_result(json.loads(json.dumps(valid.to_dict())),
                                                        CATALOG['multi']), valid)

    def test_unknown_class_ids_model_mismatch_and_duplicate_masks_are_rejected(self):
        for class_id in (999, True, '1'):
            payload = result()
            payload['masks'][0]['class_id'] = class_id
            self.assert_result_error('unknown_class', payload)
        payload = result()
        payload['model_id'] = 'wrong'
        self.assert_result_error('model_mismatch', payload)
        payload = result()
        payload['masks'][0]['model_id'] = 'MRI_GBM'
        self.assert_result_error('model_mismatch', payload)
        payload = result()
        payload['masks'].append(copy.deepcopy(payload['masks'][0]))
        self.assert_result_error('duplicate_class', payload)

    def test_terminal_result_cannot_claim_completed_empty_or_failed_inconsistently(self):
        for status, masks, errors in [('completed', [], []), ('empty', result()['masks'], []),
                                      ('failed', [], []), ('completed', result()['masks'],
                                       [{'code': 'ENGINE_FAILED', 'message': 'Failed'}])]:
            payload = {**result(), 'status': status, 'masks': masks, 'errors': errors}
            self.assert_result_error('inconsistent_result', payload)
        valid = contracts.validate_model_result({**result(), 'status': 'empty', 'masks': []},
                                                CATALOG['multi'])
        self.assertEqual(valid.masks, [])

    def test_failed_and_interrupted_reject_usable_masks_even_with_errors(self):
        errors = [{'code': 'CLASS_FAILED', 'message': 'Synthetic class failed'}]
        for status in ('failed', 'interrupted'):
            with self.subTest(status=status):
                self.assert_result_error('inconsistent_result',
                                         {**result(), 'status': status, 'errors': errors})

    def test_usable_masks_with_errors_require_partial_and_preserve_outputs(self):
        errors = [{'code': 'CLASS_FAILED', 'message': 'Synthetic class failed'}]
        valid = contracts.validate_model_result({**result(), 'status': 'partial',
                                                  'errors': errors}, CATALOG['multi'])
        self.assertEqual(valid.status, 'partial')
        self.assertEqual(valid.masks[0].class_id, 1)
        self.assertEqual(valid.errors[0].code, 'CLASS_FAILED')
        for change in ({'masks': []}, {'errors': []}):
            with self.subTest(change=change):
                self.assert_result_error('inconsistent_result',
                                         {**result(), 'status': 'partial',
                                          'errors': errors, **change})
        for status, masks in (('completed', result()['masks']), ('empty', [])):
            with self.subTest(status=status):
                self.assert_result_error('inconsistent_result',
                                         {**result(), 'status': status,
                                          'masks': masks, 'errors': errors})

    def test_cancellation_preserves_outputs_and_interruption_remains_failed_state(self):
        errors = [{'code': 'INTERRUPTED', 'message': 'Synthetic process interrupted'}]
        cancelled = contracts.validate_model_result({**result(), 'status': 'cancelled'},
                                                     CATALOG['multi'])
        self.assertEqual(cancelled.status, 'cancelled')
        self.assertEqual(cancelled.masks[0].class_id, 1)
        interrupted = contracts.validate_model_result({**result(), 'status': 'interrupted',
                                                       'masks': [], 'errors': errors},
                                                      CATALOG['multi'])
        self.assertEqual(interrupted.status, 'interrupted')
        self.assertEqual(interrupted.masks, [])
        self.assertEqual(interrupted.errors[0].code, 'INTERRUPTED')

    def test_result_status_structured_errors_and_metadata_types_are_checked(self):
        for change in ({'status': 'success'}, {'errors': ['traceback']},
                       {'versions': ['engine']}, {'transformations': 'identity'},
                       {'geometry': {'spacing': [float('inf'), 1, 1]}}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    contracts.validate_model_result({**result(), **change}, CATALOG['multi'])

    def test_study_manifest_serializes_reference_uids_revision_and_export_receipt(self):
        from neuro_rt.study_types import ExportReceipt, SeriesDescriptor, StudyManifest
        reference = SeriesDescriptor(**series('ce', '1.2.2', frame_of_reference_uid='1.2.5',
                                               sop_instance_uids=['1.2.6', '1.2.7']))
        receipt = ExportReceipt(published_file='RS_synthetic.dcm', sop_instance_uid='1.2.8',
                                reference='ce', delivered_rois=['multi/1'],
                                omitted_rois=[], revision=2)
        manifest = StudyManifest(request_id='intent-001', study_id='study-001',
                                 plugin_version='test-2', revision=2, reference=reference,
                                 requested_model_ids=['multi'],
                                 results=[contracts.validate_model_result(result(), CATALOG['multi'])],
                                 status='completed', device_preference='auto', effective_device='cpu',
                                 export_status='completed', export_receipt=receipt,
                                 artifacts=[{'artifact_id': 'synthetic-preview'}])
        encoded = json.loads(json.dumps(manifest.to_dict()))
        self.assertEqual(encoded['schema'], 'neuro-rt/result/2')
        self.assertEqual(encoded['reference']['series_uid'], '1.2.2')
        self.assertEqual(encoded['reference']['sop_instance_uids'], ['1.2.6', '1.2.7'])
        self.assertEqual(encoded['export_receipt']['revision'], 2)
        self.assertEqual(encoded['effective_device'], 'cpu')


class LegacyContractTests(unittest.TestCase):
    def legacy_result(self, **changes):
        return {'schema': 'neuro-rt/result/1', 'module_version': '0.2.0',
                'model_id': 'MRI_GBM', 'model_release': '1.2.0',
                'model_sha256': 'b' * 64, 'backend_version': 'test-1',
                'geometry': {'size': [8, 9, 10]},
                'source': {'kind': 'nifti', 'series_uid': '', 'frame_uid': ''},
                'masks': [{'label': 'Tumor', 'path': 'masks/unrelated-name.nii.gz', 'voxels': 12}],
                'status': 'completed', **changes}

    def test_explicit_v1_reader_uses_declared_model_and_label_never_filename(self):
        valid = contracts.read_result_v1(self.legacy_result(), CATALOG['MRI_GBM'])
        self.assertEqual(valid.model_id, 'MRI_GBM')
        self.assertEqual(valid.masks[0].class_id, 'tumor')
        self.assertEqual(valid.masks[0].path, 'masks/unrelated-name.nii.gz')
        self.assertEqual(valid.versions['model'], '1.2.0')
        self.assertEqual(valid.transformations, [])
        for change in ({'model_id': ''}, {'masks': [{'path': 'masks/Tumor.nii.gz', 'voxels': 12}]},
                       {'schema': 'neuro-rt/result/2'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                contracts.read_result_v1(self.legacy_result(**change), CATALOG['MRI_GBM'])

    def test_v1_empty_binary_masks_do_not_become_exportable_structures(self):
        legacy = self.legacy_result(status='empty', masks=[
            {'label': 'Tumor', 'path': 'masks/Tumor.nii.gz', 'voxels': 0}])
        valid = contracts.read_result_v1(legacy, CATALOG['MRI_GBM'])
        self.assertEqual(valid.status, 'empty')
        self.assertEqual(valid.masks, [])

    def test_legacy_nifti_input_remains_available_without_fabricating_dicom_export(self):
        index = {'nifti': {**series('nifti', ''), 'source_format': 'nifti'}}
        legacy = {'model': 'MRI_GBM', 'input_path': 'synthetic.nii.gz',
                  'explicit_request': True, 'export_rtstruct': True}
        valid = contracts.adapt_request_v1(legacy, CATALOG, index, request_id='old-001',
                                          study_id='study-old', series_ticket='nifti')
        self.assertFalse(valid.export_rtstruct)
        self.assertEqual(valid.studies[0].reference, 'nifti')
        self.assertTrue(valid.studies[0].legacy_input_path.endswith('synthetic.nii.gz'))
        self.assertEqual(index['nifti']['series_uid'], '')
        self.assertEqual(valid.studies[0].bindings_by_model['MRI_GBM'][0].role, 'T1c')

    def test_legacy_adapter_refuses_uid_mismatch_and_multichannel_guessing(self):
        payload = {'model': 'MRI_GBM', 'input_path': 'synthetic-folder',
                   'explicit_request': True, 'series_uid': '9.9'}
        with self.assertRaises(ValueError):
            contracts.adapt_request_v1(payload, CATALOG, inventory(), request_id='old-001',
                                       study_id='study-old', series_ticket='ce')

    def test_v1_adapter_never_guesses_missing_channels(self):
        catalog = copy.deepcopy(CATALOG)
        catalog['MRI_GBM']['channels'] = [{'role': 'T1'}, {'role': 'T1c'}]
        payload = {'model': 'MRI_GBM', 'input_path': 'synthetic-folder',
                   'explicit_request': True}
        with self.assertRaises(ValueError) as caught:
            contracts.adapt_request_v1(payload, catalog, inventory(), request_id='old-001',
                                       study_id='study-old', series_ticket='ce')
        self.assertEqual(caught.exception.code, 'legacy_multichannel')

    def test_contract_imports_do_not_load_scientific_runtime(self):
        root = str(Path(__file__).resolve().parents[1])
        code = (f'import sys; sys.path.insert(0, {root!r}); '
                'import neuro_rt.contracts, neuro_rt.study_types; '
                'assert not ({"numpy", "SimpleITK", "torch", "onnxruntime", '
                '"raidionicsseg"} & set(sys.modules))')
        subprocess.run([sys.executable, '-c', code], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
