import json
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

from neuro_rt.study_types import MaskArtifact, ModelResult, SeriesDescriptor, StudyManifest

TEMP_ROOT = Path(__file__).resolve().parents[1] / '.research/test_tmp'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


def sample_manifest(status='completed'):
    return StudyManifest('request-1', 'study-1', '0.3', 1,
                         SeriesDescriptor('ticket-1', '1.2.3', 'private-subject',
                                          'private-study', 'MR',
                                          frame_of_reference_uid='1.2.4',
                                          sop_instance_uids=['1.2.5']),
                         ['MRI_GBM'], [ModelResult('MRI_GBM', status,
                         [MaskArtifact('MRI_GBM', 'tumor', 'masks/tumor.nii.gz')]
                         if status == 'completed' else [])], status, 'cpu', 'cpu')


class RecoveryTests(unittest.TestCase):
    def test_manifest_refuses_windows_alias_identifiers(self):
        from neuro_rt.result_store import validate_manifest
        reserved = ['CON', 'PRN', 'AUX', 'NUL'] + [f'{kind}{n}' for kind in ('COM', 'LPT') for n in range(1, 10)]
        values = ['study.', 'study..', 'study '] + reserved + [name.lower() + '.txt' for name in reserved]
        for field in ('request_id', 'study_id'):
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        validate_manifest(replace(sample_manifest(), **{field: value}))

    def test_manifest_preserves_internal_dots_and_uuid_identifiers(self):
        from neuro_rt.result_store import validate_manifest
        import uuid
        for request_id, study_id in (('request.1', 'study.1'), (str(uuid.uuid4()), str(uuid.uuid4()))):
            with self.subTest(request_id=request_id, study_id=study_id):
                manifest = validate_manifest(replace(sample_manifest(), request_id=request_id, study_id=study_id))
                self.assertEqual((manifest.request_id, manifest.study_id), (request_id, study_id))

    def store(self, folder):
        from neuro_rt.result_store import ResultStore
        return ResultStore(folder)

    def prepare(self, folder):
        job = Path(folder) / 'jobs/study-1'
        (job / 'masks').mkdir(parents=True)
        (job / 'masks/tumor.nii.gz').write_bytes(b'synthetic-mask')
        return job

    def test_revisions_survive_restart_and_keep_old_artifact(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = self.prepare(tmp)
            store = self.store(tmp)
            self.assertEqual(store.save_manifest(sample_manifest()), 1)
            first = store.load_manifest('study-1', 1)
            old_id = store.public_view(first).to_dict()['artifacts'][0]['artifact_id']
            (job / 'masks/tumor.nii.gz').write_bytes(b'new-mask')
            self.assertEqual(store.save_manifest(sample_manifest()), 2)
            restarted = self.store(tmp)
            self.assertEqual(restarted.load_manifest('study-1').revision, 2)
            self.assertEqual(restarted.resolve_artifact('study-1', old_id).path.read_bytes(),
                             b'synthetic-mask')
            self.assertEqual(len(restarted.list_results('ticket-1')), 1)
            self.assertEqual(restarted.list_results('other'), [])

    def test_recovery_ignores_uncommitted_and_corrupt_revisions(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            store.save_manifest(sample_manifest('running'))
            revisions = Path(tmp) / 'studies/study-1/revisions'
            (revisions / '.pending-abandoned').mkdir()
            (revisions / '2').mkdir()
            (revisions / '2/manifest.json').write_text('{broken')
            restarted = self.store(tmp)
            result = restarted.load_manifest('study-1')
            self.assertEqual(result.status, 'interrupted')
            self.assertEqual(result.results[0].status, 'interrupted')
            self.assertNotEqual(restarted.list_results()[0]['status'], 'running')

    def test_public_view_and_artifact_resolution_are_allowlisted(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            store.save_manifest(sample_manifest())
            public = json.dumps(store.public_view(store.load_manifest('study-1')).to_dict())
            for private in (tmp, 'private-subject', 'private-study', '1.2.3',
                            '1.2.4', '1.2.5', 'tumor.nii.gz', 'path'):
                self.assertNotIn(private, public)
            for artifact in ('../source.json', 'source.json', '%2e%2e', 'manifest.json'):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    store.resolve_artifact('study-1', artifact)
            with self.assertRaises(ValueError):
                store.load_manifest('../study-1')
            bad = replace(sample_manifest(), artifacts=[
                {'artifact_id': 'secret', 'path': 'source.json', 'kind': 'view'}])
            with self.assertRaises(ValueError):
                store.save_manifest(bad)

    def test_mask_escape_unknown_class_and_unknown_schema_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            for mask in (MaskArtifact('MRI_GBM', 'tumor', '../secret.nii.gz'),
                         MaskArtifact('MRI_GBM', 'unknown', 'masks/tumor.nii.gz')):
                with self.assertRaises(ValueError):
                    store.save_manifest(replace(sample_manifest(), results=[
                        ModelResult('MRI_GBM', 'completed', [mask])]))
            bad = sample_manifest().to_dict()
            bad['schema'] = 'neuro-rt/result/999'
            with self.assertRaises(ValueError):
                store.save_manifest(bad)

    def test_interrupted_write_keeps_last_commit_and_index_is_rebuildable(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            store.save_manifest(sample_manifest())
            with patch('neuro_rt.result_store.os.rename', side_effect=OSError('power loss')):
                with self.assertRaises(OSError):
                    store.save_manifest(sample_manifest())
            (Path(tmp) / 'studies/study-1/latest.json').write_text('broken')
            restarted = self.store(tmp)
            self.assertEqual(restarted.load_manifest('study-1').revision, 1)
            self.assertEqual(restarted.save_manifest(sample_manifest()), 2)

    def test_missing_artifact_does_not_leave_interrupted_study_running(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            store.save_manifest(replace(sample_manifest(), status='exporting'))
            manifest = store.load_manifest('study-1')
            Path(manifest.results[0].masks[0].path).unlink()
            restarted = self.store(tmp)
            self.assertEqual(restarted.load_manifest('study-1').status, 'interrupted')
            self.assertEqual(restarted.load_manifest('study-1').results[0].status, 'failed')

    def test_modified_allowlisted_artifact_is_refused(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.prepare(tmp)
            store = self.store(tmp)
            store.save_manifest(sample_manifest())
            manifest = store.load_manifest('study-1')
            artifact = manifest.artifacts[0]
            Path(artifact['path']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                store.resolve_artifact('study-1', artifact['artifact_id'])

    def test_synthetic_view_names_map_to_opaque_artifact_ids(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            job = self.prepare(tmp)
            (job / 'views').mkdir()
            entries = [('view.json', 'view', '{}'), ('axial_000.svg', 'slice', '<svg/>'),
                       ('roi_000.stl', 'mesh', 'solid synthetic\nendsolid'),
                       ('renderer.js', 'view', '/* synthetic renderer */')]
            artifacts = []
            for name, kind, content in entries:
                (job / 'views' / name).write_text(content)
                artifacts.append({'kind': kind, 'logical_name': name, 'path': 'views/' + name})
            store = self.store(tmp)
            store.save_manifest(replace(sample_manifest(), artifacts=artifacts))
            public = store.public_view(store.load_manifest('study-1')).to_dict()
            logical = {a['logical_name']: a for a in public['artifacts'] if 'logical_name' in a}
            self.assertEqual(set(logical), {entry[0] for entry in entries})
            artifact = store.resolve_artifact('study-1', logical['axial_000.svg']['artifact_id'])
            self.assertEqual(artifact.media_type, 'image/svg+xml')
            self.assertNotIn('views/', json.dumps(public))
            for name in ('../view.json', 'patient.json', 'C:/secret', 'axial_000.svg/secret'):
                with self.assertRaises(ValueError):
                    store.save_manifest(replace(sample_manifest(), artifacts=[{
                        'kind': 'view', 'logical_name': name, 'path': 'views/view.json'}]))


if __name__ == '__main__':
    unittest.main()
