import tempfile
import unittest
from pathlib import Path

from neuro_rt.study_types import InputBinding, MaskArtifact, ModelResult, SeriesDescriptor, StudyItem
from test_pipeline import TEMP_ROOT


class OrchestrationTests(unittest.TestCase):
    def scenario(self, root):
        from neuro_rt.orchestrator import StudyRunContext, build_study_plan
        reference = SeriesDescriptor('reference', '1.2.3', 'subject', 'visit', 'MR')
        model_ids = ['model_a', 'model_b', 'model_c', 'model_d']
        specs = {mid: {'id': mid, 'catalog_state': 'distributed',
                      'channels': [{'role': 'T1c'}], 'classes': [{'class_id': 'tumor'}]}
                 for mid in model_ids}
        item = StudyItem('study', reference.ticket, model_ids,
                         {mid: [InputBinding('T1c', reference.ticket)] for mid in model_ids})
        context = StudyRunContext(reference, {reference.ticket: reference},
                                  {reference.ticket: root / 'input.nii.gz'},
                                  root / 'job', root / 'models', 'cpu', 'auto', '0.3.0', 'request')
        return build_study_plan(item, specs), context

    def test_individual_failure_and_empty_result_preserve_other_models(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            calls = []
            def runner(spec, model_context):
                mid = spec['id']; calls.append(mid)
                if mid == 'model_b':
                    raise RuntimeError('private path must not reach public manifest')
                if mid == 'model_c':
                    return ModelResult(mid, 'empty')
                return ModelResult(mid, 'completed', [MaskArtifact(mid, 'tumor', str(Path(tmp) / mid))])
            result = run_study(plan, context, runner)
            self.assertEqual(calls, ['model_a', 'model_b', 'model_c', 'model_d'])
            self.assertEqual(result.status, 'partial')
            self.assertEqual([r.status for r in result.results], ['completed', 'failed', 'empty', 'completed'])
            self.assertNotIn('private path', str(result.to_dict()))
            self.assertEqual(result.export_status, 'pending')

    def test_cancel_stops_remaining_models_and_keeps_finished_outputs(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            cancelled = [False]; calls = []
            context.cancel_requested = lambda: cancelled[0]
            def runner(spec, model_context):
                calls.append(spec['id']); cancelled[0] = True
                return ModelResult(spec['id'], 'completed', [MaskArtifact(spec['id'], 'tumor', 'mask.nii.gz')])
            result = run_study(plan, context, runner)
            self.assertEqual(calls, ['model_a'])
            self.assertEqual(result.status, 'cancelled')
            self.assertEqual(result.results[0].status, 'completed')
            self.assertEqual([r.status for r in result.results[1:]], ['cancelled'] * 3)

    def test_all_empty_and_all_failed_have_distinct_states(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            empty = run_study(plan, context, lambda spec, ctx: ModelResult(spec['id'], 'empty'))
            self.assertEqual((empty.status, empty.export_status), ('empty', 'empty'))
            def failed(spec, ctx):
                raise ValueError('synthetic')
            result = run_study(plan, context, failed)
            self.assertEqual((result.status, result.export_status), ('failed', 'failed'))

    def test_unknown_candidates_and_wrong_reference_cannot_run(self):
        from neuro_rt.orchestrator import build_study_plan, run_study
        with self.assertRaises(ValueError):
            build_study_plan(StudyItem('x', 'r', ['unknown'], {}), {})
        with self.assertRaises(ValueError):
            build_study_plan(StudyItem('x', 'r', ['candidate'], {}), {
                'candidate': {'id': 'candidate', 'catalog_state': 'candidate'}})
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            context.reference = SeriesDescriptor('other', '1.2.4', 'subject', 'visit', 'MR')
            with self.assertRaises(ValueError):
                run_study(plan, context, lambda *_: self.fail('runner must not start'))

    def test_nonterminal_runner_result_is_not_a_completed_empty_study(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            result = run_study(plan, context, lambda spec, ctx: ModelResult(spec['id'], 'running'))
            self.assertEqual(result.status, 'failed')
            self.assertTrue(all(r.status == 'failed' for r in result.results))

    def test_retry_reuses_only_matching_completed_model_fingerprint(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            context.execution_keys = {'model_a': 'same', 'model_b': 'new'}
            context.previous_results = {
                'model_a': {'execution_key': 'same', 'result': ModelResult('model_a', 'empty')},
                'model_b': {'execution_key': 'old', 'result': ModelResult('model_b', 'empty')}}
            calls = []
            result = run_study(plan, context, lambda spec, ctx: (
                calls.append(spec['id']) or ModelResult(spec['id'], 'empty')))
            self.assertEqual(calls, ['model_b', 'model_c', 'model_d'])
            self.assertEqual(len(result.results), 4)
            self.assertEqual(result.status, 'empty')

    def test_runner_cancel_state_stops_remaining_models(self):
        from neuro_rt.orchestrator import run_study
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            plan, context = self.scenario(Path(tmp))
            calls = []
            def runner(spec, ctx):
                calls.append(spec['id'])
                return ModelResult(spec['id'], 'cancelled')
            result = run_study(plan, context, runner)
            self.assertEqual(calls, ['model_a'])
            self.assertEqual(result.status, 'cancelled')
