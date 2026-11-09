"""Selection fixtures contain invented metadata only; no images or runtimes."""
import copy
import subprocess
import sys
import unittest

from neuro_rt import series_selection as selection
from neuro_rt.contracts import validate_study_request
from neuro_rt.model_registry import get_model_spec
from neuro_rt.study_types import InputBinding, SeriesDescriptor


MULTI = {'id': 'synthetic-multi', 'catalog_state': 'distributed',
         'runtime_id': 'synthetic-runtime',
         'channels': [{'role': r} for r in ('T1', 'T1c', 'T2', 'FLAIR')]}


def series(ticket, role=None, *, certainty='certain', subject='subject-a',
           study='20261001-pre', modality='MR', uid=None, geometry=None):
    candidates = [] if role is None else [
        {'role': role, 'certainty': certainty,
         'evidence': [{'field': 'ProtocolName', 'signal': role}]}]
    return SeriesDescriptor(ticket, uid or '1.2.synthetic.' + ticket, subject,
                            study, modality, geometry or {}, candidates)


def complete():
    return [series('t1', 'T1'), series('ce', 'T1c'), series('t2', 'T2'),
            series('flair', 'FLAIR')]


def capabilities(items=(), **changes):
    return {'runtimes': {'synthetic-runtime': {'available': True}},
            'models': {'synthetic-multi': {'status': 'ready'}},
            'series': {s.ticket: s for s in items}, **changes}


class SelectionTests(unittest.TestCase):
    # Breaks caught: empty/missing associations, channel cloning, uncertainty
    # treated as absence, greedy role assignment, and cross-study mixing.
    def test_complete_four_series_bind_exact_order_and_server_contract_agrees(self):
        items = complete()
        bindings = selection.suggest_bindings(items, MULTI)
        self.assertEqual([(b.role, b.series_ticket) for b in bindings],
                         [('T1', 't1'), ('T1c', 'ce'), ('T2', 't2'), ('FLAIR', 'flair')])
        eligible = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertTrue(eligible.selectable)
        self.assertEqual(eligible.missing_roles, [])
        payload = {'schema': 'neuro-rt/request/2', 'request_id': 'synthetic-request',
                   'explicit_request': True, 'studies': [{
                       'study_id': 'synthetic-study', 'reference': 'ce',
                       'model_ids': [MULTI['id']], 'bindings_by_model': {
                           MULTI['id']: [b.to_dict() for b in bindings]}}]}
        valid = validate_study_request(payload, {MULTI['id']: MULTI},
                                       capabilities(items)['series'])
        self.assertEqual(valid.studies[0].bindings_by_model[MULTI['id']], bindings)

    def test_three_series_report_absent_channel_without_cloning(self):
        items = complete()[:-1]
        bindings = selection.suggest_bindings(items, MULTI)
        result = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertFalse(result.selectable)
        self.assertEqual(result.missing_roles, ['FLAIR'])
        self.assertEqual(len({b.series_ticket for b in bindings}), 3)
        self.assertEqual(result.technical_reasons, [])

    def test_present_unknown_fourth_series_is_selectable_without_acceptance(self):
        items = complete()[:-1] + [series('unknown')]
        bindings = selection.suggest_bindings(items, MULTI)
        result = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertTrue(result.selectable)
        self.assertEqual(result.missing_roles, [])
        self.assertEqual((bindings[-1].series_ticket, bindings[-1].certainty),
                         ('unknown', 'unknown'))
        self.assertTrue(result.warnings)
        self.assertEqual(result.to_dict()['selectable'], True)

    def test_explicit_uncertain_channel_remains_selectable(self):
        items = complete()[:-1] + [series('uncertain', 'FLAIR', certainty='uncertain')]
        bindings = selection.suggest_bindings(items, MULTI)
        result = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertTrue(result.selectable)
        self.assertEqual(bindings[-1].certainty, 'uncertain')
        self.assertTrue(result.warnings)

    def test_duplicate_candidates_are_deterministic_and_can_be_swapped(self):
        items = complete() + [series('ce-alternate', 'T1c')]
        first = selection.suggest_bindings(items, MULTI)
        self.assertEqual(first, selection.suggest_bindings(list(reversed(items)), MULTI))
        ce = next(b for b in first if b.role == 'T1c')
        self.assertEqual(ce.series_ticket, 'ce')
        alternatives = [w.details.get('alternative_tickets', []) for w in ce.warnings]
        self.assertIn(['ce-alternate'], alternatives)
        swapped = [InputBinding('T1c', 'ce-alternate') if b.role == 'T1c' else b
                   for b in first]
        self.assertTrue(selection.evaluate_eligibility(
            MULTI, swapped, capabilities(items)).selectable)

    def test_duplicate_alias_uid_cannot_manufacture_channel(self):
        items = complete()[:-1] + [series('alias', uid='1.2.synthetic.t1')]
        bindings = selection.suggest_bindings(items, MULTI)
        self.assertEqual(len(bindings), 3)
        self.assertFalse(selection.evaluate_eligibility(
            MULTI, bindings, capabilities(items)).selectable)

    def test_grouping_never_completes_channels_with_other_subject_or_date(self):
        for extra in (series('other', 'FLAIR', subject='subject-b'),
                      series('other', 'FLAIR', study='20261020-post')):
            with self.subTest(extra=extra.ticket, study=extra.study_key):
                items = complete()[:-1] + [extra]
                result = selection.evaluate_eligibility(
                    MULTI, selection.suggest_bindings(items, MULTI), capabilities(items))
                self.assertFalse(result.selectable)
                self.assertEqual(result.missing_roles, ['FLAIR'])

    def test_ambiguous_candidate_does_not_steal_only_available_role(self):
        ambiguous = series('ambiguous', 'T1')
        ambiguous.sequence_candidates.append({'role': 'T2', 'certainty': 'uncertain'})
        spec = {**MULTI, 'channels': [{'role': 'T1'}, {'role': 'T2'}]}
        chosen = selection.suggest_bindings([ambiguous, series('only-t1', 'T1')], spec)
        self.assertEqual([(b.role, b.series_ticket) for b in chosen],
                         [('T1', 'only-t1'), ('T2', 'ambiguous')])

    def test_known_incompatible_sequence_does_not_fill_missing_role(self):
        items = complete()[:-1] + [series('second-t1', 'T1')]
        result = selection.evaluate_eligibility(
            MULTI, selection.suggest_bindings(items, MULTI), capabilities(items))
        self.assertEqual(result.missing_roles, ['FLAIR'])

    def test_catalog_channels_include_ct_and_bind_per_model(self):
        t1c = get_model_spec('MRI_GBM')
        flair = get_model_spec('MRI_LGGlioma')
        ct = get_model_spec('cranio_buti')
        items = complete() + [series('ct', 'CT', modality='CT')]
        self.assertEqual(selection.suggest_bindings(items, t1c)[0].series_ticket, 'ce')
        self.assertEqual(selection.suggest_bindings(items, flair)[0].series_ticket, 'flair')
        self.assertEqual(selection.suggest_bindings(items, ct)[0].series_ticket, 'ct')

    def test_ct_modality_suffices_without_mr_classification_and_pet_is_not_mr(self):
        ct = get_model_spec('cranio_buti')
        self.assertEqual(selection.suggest_bindings([series('ct', modality='CT')], ct)[0].series_ticket,
                         'ct')
        t1 = {**MULTI, 'channels': [{'role': 'T1'}]}
        self.assertEqual(selection.suggest_bindings([series('pet', 'T1', modality='PT')], t1), [])

    def test_evaluator_catches_aliases_and_mr_ct_transfer_even_with_manual_bindings(self):
        items = complete()[:-1] + [series('alias', 'FLAIR', uid='1.2.synthetic.t1')]
        bindings = [InputBinding(role, ticket) for role, ticket in
                    [('T1', 't1'), ('T1c', 'ce'), ('T2', 't2'), ('FLAIR', 'alias')]]
        result = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertFalse(result.selectable)
        self.assertEqual(result.missing_roles, [])
        self.assertIn('duplicate_input', [r.code for r in result.technical_reasons])
        ct = series('ct', 'CT', modality='CT')
        result = selection.evaluate_eligibility(
            {**MULTI, 'channels': [{'role': 'T1'}]}, [InputBinding('T1', 'ct')], capabilities([ct]))
        self.assertFalse(result.selectable)
        self.assertIn('inconsistent_modality', [r.code for r in result.technical_reasons])

    def test_candidate_and_runtime_unavailability_have_technical_reasons_not_absence(self):
        items = complete()
        bindings = selection.suggest_bindings(items, MULTI)
        for spec, caps, code in [
                ({**MULTI, 'catalog_state': 'candidate'}, capabilities(items), 'model_not_distributed'),
                (MULTI, capabilities(items, runtimes={}), 'runtime_unavailable'),
                (MULTI, capabilities(items, models={MULTI['id']: {'status': 'corrupt'}}),
                 'model_artifacts_unavailable')]:
            result = selection.evaluate_eligibility(spec, bindings, caps)
            self.assertFalse(result.selectable)
            self.assertEqual(result.missing_roles, [])
            self.assertIn(code, [r.code for r in result.technical_reasons])

    def test_manual_duplicates_cross_subject_and_invalid_geometry_remain_technical_errors(self):
        items = complete()
        bindings = selection.suggest_bindings(items, MULTI)
        duplicate = [InputBinding('FLAIR', 't1') if b.role == 'FLAIR' else b for b in bindings]
        result = selection.evaluate_eligibility(MULTI, duplicate, capabilities(items))
        self.assertFalse(result.selectable)
        self.assertIn('duplicate_input', [r.code for r in result.technical_reasons])
        for bad, code in [(series('flair', 'FLAIR', subject='subject-b'), 'inconsistent_subject'),
                          (series('flair', 'FLAIR', study='other-date'), 'inconsistent_study'),
                          (series('flair', 'FLAIR', geometry={'valid': False}), 'invalid_geometry'),
                          (series('flair', 'FLAIR', geometry={'readable': False}), 'unreadable_series')]:
            caps = capabilities(items[:-1] + [bad])
            result = selection.evaluate_eligibility(MULTI, bindings, caps)
            self.assertFalse(result.selectable)
            self.assertEqual(result.missing_roles, [])
            self.assertIn(code, [r.code for r in result.technical_reasons])

    def test_unknown_manual_binding_is_present_but_unknown_ticket_is_technical_failure(self):
        bindings = [InputBinding('T1', 'not-authorized', certainty='unknown')]
        spec = {**MULTI, 'channels': [{'role': 'T1'}]}
        result = selection.evaluate_eligibility(spec, bindings, capabilities(complete()))
        self.assertEqual(result.missing_roles, [])
        self.assertFalse(result.selectable)
        self.assertIn('unknown_series', [r.code for r in result.technical_reasons])


class DescribeTests(unittest.TestCase):
    # Breaks caught: classification by MR alone or filenames, discarded evidence,
    # loss of resolver errors, and imports of a scientific/image runtime.
    def describe(self, metadata, modality='MR'):
        record = series('host-ticket', modality=modality).to_dict()
        record['metadata'] = metadata

        class Host:
            def resolve_series_ticket(self, ticket):
                if ticket != 'host-ticket':
                    raise ValueError('Unknown ticket')
                return record

        return selection.describe_series('host-ticket', Host())

    def test_metadata_description_protocol_and_acquisition_evidence_are_retained(self):
        for metadata, role in [({'SeriesDescription': 'AX T1 POST',
                                 'ContrastBolusAgent': 'synthetic-agent'}, 'T1c'),
                               ({'ProtocolName': '3D FLAIR'}, 'FLAIR'),
                               ({'SeriesDescription': 'T2 TSE'}, 'T2'),
                               ({'ProtocolName': 'T1 PRECONTRAST'}, 'T1'),
                               ({'RepetitionTime': 500, 'EchoTime': 10}, 'T1')]:
            with self.subTest(role=role):
                descriptor = self.describe(metadata)
                self.assertEqual(descriptor.ticket, 'host-ticket')
                candidate = descriptor.sequence_candidates[0]
                self.assertEqual(candidate['role'], role)
                self.assertTrue(candidate['evidence'])
                self.assertEqual(descriptor.subject_key, 'subject-a')

    def test_modality_and_filename_alone_never_prove_mr_sequence(self):
        descriptor = self.describe({'filename': 'T1_POST.dcm', 'folder': 'FLAIR'})
        self.assertEqual(descriptor.sequence_candidates, [])
        self.assertEqual(self.describe({}, modality='CT').sequence_candidates[0]['role'], 'CT')

    def test_conflicting_metadata_is_uncertain_with_recorded_conflict(self):
        descriptor = self.describe({'SeriesDescription': 'T1', 'ProtocolName': 'FLAIR'})
        self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1', 'T1c', 'FLAIR'})
        self.assertTrue(all(c['certainty'] == 'uncertain' for c in descriptor.sequence_candidates))
        self.assertTrue(all(c['conflicts'] for c in descriptor.sequence_candidates))

    def test_t1_name_without_contrast_metadata_remains_selectable_for_t1c(self):
        descriptor = self.describe({'ProtocolName': 'T1'})
        spec = {**MULTI, 'channels': [{'role': 'T1c'}]}
        bindings = selection.suggest_bindings([descriptor], spec)
        result = selection.evaluate_eligibility(spec, bindings, capabilities([descriptor]))
        self.assertTrue(result.selectable)
        self.assertEqual(result.missing_roles, [])
        self.assertEqual([(b.role, b.series_ticket, b.certainty) for b in bindings],
                         [('T1c', 'host-ticket', 'uncertain')])
        self.assertTrue(result.warnings)

    def test_explicit_precontrast_does_not_manufacture_t1c_candidate(self):
        for protocol in ('T1 PRECONTRAST', 'T1 NONCONTRAST', 'T1 SEM CONTRASTE', 'T1 NATIVE'):
            with self.subTest(protocol=protocol):
                descriptor = self.describe({'ProtocolName': protocol})
                spec = {**MULTI, 'channels': [{'role': 'T1c'}]}
                bindings = selection.suggest_bindings([descriptor], spec)
                result = selection.evaluate_eligibility(spec, bindings, capabilities([descriptor]))
                self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1'})
                self.assertEqual(bindings, [])
                self.assertFalse(result.selectable)
                self.assertEqual(result.missing_roles, ['T1c'])

    def test_post_name_alone_is_not_certain_contrast_evidence(self):
        descriptor = self.describe({'ProtocolName': 'T1 POST'})
        self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1', 'T1c'})
        self.assertTrue(all(c['certainty'] == 'uncertain' for c in descriptor.sequence_candidates))

    def test_null_blank_and_nonstring_agent_values_do_not_establish_contrast(self):
        for value in (None, '', '  ', False, True, 0, 42, [], {}):
            with self.subTest(agent=value):
                descriptor = self.describe({'ProtocolName': 'T1', 'ContrastBolusAgent': value})
                self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1', 'T1c'})
                self.assertTrue(all(c['certainty'] == 'uncertain'
                                    for c in descriptor.sequence_candidates))

    def test_preoperative_or_isolated_pre_does_not_establish_absent_contrast(self):
        for name in ('T1 PRE OP', 'T1 PRE'):
            with self.subTest(protocol=name):
                descriptor = self.describe({'ProtocolName': name})
                self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1', 'T1c'})
                self.assertTrue(all(c['certainty'] == 'uncertain'
                                    for c in descriptor.sequence_candidates))

    def test_ambiguous_t1_volume_cannot_supply_two_of_four_required_channels(self):
        descriptor = self.describe({'ProtocolName': 'T1'})
        items = [descriptor, series('t2', 'T2'), series('flair', 'FLAIR')]
        bindings = selection.suggest_bindings(items, MULTI)
        result = selection.evaluate_eligibility(MULTI, bindings, capabilities(items))
        self.assertFalse(result.selectable)
        self.assertEqual(len(bindings), 3)
        self.assertEqual(len({b.series_ticket for b in bindings}), 3)
        self.assertEqual(result.missing_roles, ['T1c'])

    def test_precontrast_protocol_and_contrast_agent_are_a_conflict_not_certain_t1c(self):
        descriptor = self.describe({'ProtocolName': 'T1 PRECONTRAST',
                                    'ContrastBolusAgent': 'synthetic-agent'})
        self.assertTrue(all(c['certainty'] == 'uncertain' for c in descriptor.sequence_candidates))
        self.assertTrue(all(c['conflicts'] for c in descriptor.sequence_candidates))

    def test_conflicting_precontrast_and_agent_preserve_both_concrete_role_options(self):
        descriptor = self.describe({'ProtocolName': 'T1 PRECONTRAST',
                                    'ContrastBolusAgent': 'synthetic-agent'})
        self.assertEqual({c['role'] for c in descriptor.sequence_candidates}, {'T1', 'T1c'})
        for role in ('T1', 'T1c'):
            with self.subTest(role=role):
                spec = {**MULTI, 'channels': [{'role': role}]}
                bindings = selection.suggest_bindings([descriptor], spec)
                result = selection.evaluate_eligibility(spec, bindings, capabilities([descriptor]))
                self.assertTrue(result.selectable)
                self.assertEqual(result.missing_roles, [])
                self.assertEqual([(b.role, b.series_ticket, b.certainty) for b in bindings],
                                 [(role, 'host-ticket', 'uncertain')])
                self.assertTrue(result.warnings)

    def test_resolver_failure_and_ticket_mismatch_are_not_sequence_ambiguity(self):
        class BrokenHost:
            def resolve_series_ticket(self, ticket):
                raise OSError('Synthetic unreadable series')

        with self.assertRaises(OSError):
            selection.describe_series('host-ticket', BrokenHost())

        class WrongHost:
            def resolve_series_ticket(self, ticket):
                return series('different')

        with self.assertRaises(ValueError):
            selection.describe_series('host-ticket', WrongHost())

    def test_metadata_processing_never_mutates_host_record(self):
        original = series('host-ticket').to_dict()
        original['metadata'] = {'ProtocolName': 'T1'}
        snapshot = copy.deepcopy(original)

        class Host:
            def resolve_series_ticket(self, ticket):
                return original

        selection.describe_series('host-ticket', Host())
        self.assertEqual(original, snapshot)

    def test_module_import_is_lightweight(self):
        subprocess.run([sys.executable, '-c',
                        'import neuro_rt.series_selection; import sys; '
                        'assert not ({"numpy", "pydicom", "SimpleITK", "torch", '
                        '"onnxruntime", "raidionicsseg"} & set(sys.modules))'],
                       check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
