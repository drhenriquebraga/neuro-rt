import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
import SimpleITK as sitk
from neuro_rt.execution_errors import ProcessTreeUnconfirmed
from neuro_rt.study_types import ModelResult, MaskArtifact, SeriesDescriptor, StudyManifest, ContractMessage
from neuro_rt.imaging import geometry
from test_pipeline import TEMP_ROOT
import test_study_service as service_tests


class FinalFixTests(unittest.TestCase):
    def test_unconfirmed_tree_aborts_all_models_and_later_stages_until_confirmed(self):
        fixture = service_tests.StudyServiceTests()
        for failure in ('false', 'raise'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                service, bridge = fixture.make(Path(tmp))
                second = copy.deepcopy(service.catalog['model']); second['id'] = 'second'
                service.catalog['second'] = second
                payload = fixture.payload(); item = payload['studies'][0]
                item['model_ids'].append('second'); item['bindings_by_model']['second'] = item['bindings_by_model']['model']
                trees, stages = [], []
                class Process:
                    returncode = 0
                    confirmed = False
                    def __init__(self, *a, **kw): trees.append(self)
                    def poll(self): return 0
                    def close(self):
                        if self.confirmed: return True
                        if failure == 'false': return False
                        raise RuntimeError('unconfirmed')
                def run(spec, context, event):
                    stages.append(spec['id']); context.job_dir.mkdir(parents=True, exist_ok=True)
                    service._execute(['synthetic'], context.job_dir, 'test.log', event, 'study')
                    return ModelResult(spec['id'], 'empty')
                service.run_model = run
                service.build_views = lambda *args: stages.append('views')
                with patch('neuro_rt.process_tree.ManagedProcess', Process):
                    service.submit(payload); fixture.finished(service, 'study')
                    job = service._jobs['study']; old_directory = job['directory']
                    self.assertEqual(stages, ['model']); self.assertEqual(len(trees), 1)
                    self.assertIs(job['process'], trees[0]); self.assertIsNotNone(job['lease'])
                    self.assertEqual(bridge.finished, [])
                    with self.assertRaises(ProcessTreeUnconfirmed): service.retry('study', explicit_request=True)
                    with self.assertRaises(ProcessTreeUnconfirmed): service.submit(fixture.payload('new', 'new-study'))
                    with self.assertRaises(ProcessTreeUnconfirmed):
                        service._execute(['later'], old_directory, 'later.log', threading.Event(), 'study')
                    service.cancel('study')
                    with self.assertRaises(ProcessTreeUnconfirmed): service.confirm_process_exit('study')
                    self.assertIs(job['process'], trees[0]); self.assertEqual(job['directory'], old_directory)
                    recovered, _ = fixture.make(Path(tmp))
                    self.assertFalse(recovered._jobs['study']['release_safe'])
                    with self.assertRaises(ProcessTreeUnconfirmed): recovered.retry('study', explicit_request=True)
                    with self.assertRaises(ProcessTreeUnconfirmed): recovered.confirm_process_exit('study')
                    recovered.close()
                    trees[0].confirmed = True; service.confirm_process_exit('study')
                    self.assertTrue(job['release_safe']); self.assertIsNone(job['process'])
                    self.assertEqual(bridge.finished, ['failed'])
                service.close()

    def test_export_termination_failure_prevents_views_and_publication(self):
        fixture=service_tests.StudyServiceTests()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service,bridge=fixture.make(Path(tmp));stages=[]
            class Process:
                returncode=0
                def __init__(self,*a,**kw): stages.append('export')
                def poll(self): return 0
                def close(self): return False
            def run(spec,context,event):
                context.job_dir.mkdir(parents=True,exist_ok=True)
                path=context.job_dir/'mask.nii.gz';path.write_bytes(b'synthetic')
                return ModelResult('model','completed',[MaskArtifact('model','tumor',str(path))])
            service.run_model=run;service.build_views=lambda *a:stages.append('views')
            service.publish=lambda *a:stages.append('publish')
            payload=fixture.payload();payload['export_rtstruct']=True
            with patch('neuro_rt.process_tree.ManagedProcess',Process):
                service.submit(payload);fixture.finished(service,'study')
            self.assertEqual(stages,['export']);self.assertEqual(bridge.finished,[])
            self.assertIsNotNone(service._jobs['study']['process']);service.close()

    def test_constructor_retains_uncertain_owner_and_ordinary_failure_remains_isolated(self):
        fixture=service_tests.StudyServiceTests()
        for fatal in (False,True):
            with self.subTest(fatal=fatal),tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
                service,bridge=fixture.make(Path(tmp));stages=[];owner=object()
                second=copy.deepcopy(service.catalog['model']);second['id']='second';service.catalog['second']=second
                payload=fixture.payload();item=payload['studies'][0];item['model_ids'].append('second')
                item['bindings_by_model']['second']=item['bindings_by_model']['model']
                class Process:
                    def __init__(self,*a,**kw):
                        if fatal:raise ProcessTreeUnconfirmed('ownership',process=owner)
                        self.returncode=1 if len(stages)==1 else 0
                    def poll(self):return self.returncode
                    def close(self):return None
                def run(spec,ctx,event):
                    stages.append(spec['id']);ctx.job_dir.mkdir(parents=True,exist_ok=True)
                    service._execute(['synthetic'],ctx.job_dir,'run.log',event,'study')
                    return ModelResult(spec['id'],'empty')
                service.run_model=run;service.build_views=lambda *a:stages.append('views')
                with patch('neuro_rt.process_tree.ManagedProcess',Process):
                    service.submit(payload);fixture.finished(service,'study')
                if fatal:
                    self.assertEqual(stages,['model']);self.assertIs(service._jobs['study']['process'],owner)
                    self.assertFalse(service._jobs['study']['release_safe']);self.assertEqual(bridge.finished,[])
                else:
                    self.assertEqual(stages,['model','second','views']);self.assertEqual(bridge.finished,['partial'])
                service.close()

    def test_retry_live_state_has_no_stale_result_and_history_has_no_live_progress(self):
        fixture=service_tests.StudyServiceTests()
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            service,_=fixture.make(Path(tmp));service.submit(fixture.payload());fixture.finished(service,'study')
            old=service.store.load_manifest('study',1).to_dict()
            service._update('study',progress={'model_id':'model','fraction':1.})
            with patch('neuro_rt.study_service.threading.Thread'):
                queued=service.retry('study',explicit_request=True)
            self.assertEqual(queued['status'],'queued');self.assertIsNone(queued['result']);self.assertIsNone(queued['progress'])
            self.assertIn('model',service._jobs['study']['previous_results'])
            service._update('study',progress={'model_id':'active-model','fraction':.5})
            history=service.job('study',revision=1)
            self.assertEqual(history['result']['revision'],1);self.assertEqual(history['status'],'empty')
            self.assertIsNone(history['progress']);self.assertEqual(service.store.load_manifest('study',1).to_dict(),old)
            service.close()

    def test_reference_discretization_warns_only_for_lost_nonempty_class_and_survives_history(self):
        from neuro_rt.adapters.base import PreparedInputs
        from neuro_rt.adapters._scientific import ScientificAdapter, ScientificPrediction
        from neuro_rt.result_store import ResultStore, public_view
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root=Path(tmp); job=root/'jobs/study'; job.mkdir(parents=True)
            ref_image=sitk.Image([2,2,2],sitk.sitkUInt8); ref_image.SetSpacing((3.,3.,3.))
            ref_path=job/'reference.nii.gz'; sitk.WriteImage(ref_image,str(ref_path))
            ref=SeriesDescriptor('ref','','synthetic','study','MR',geometry(ref_image),source_format='nifti')
            classes=['survives','lost','originally_empty']; masks=[]
            for name in classes:
                array=np.zeros((4,4,4),np.uint8)
                if name=='survives': array[0,0,0]=1
                if name=='lost': array[1,1,1:3]=1
                image=sitk.GetImageFromArray(array); path=job/(name+'.nii.gz');sitk.WriteImage(image,str(path))
                masks.append(MaskArtifact('model',name,str(path),geometry(image),'working'))
            spec={'id':'model','classes':[{'class_id':c} for c in classes]}
            prepared=PreparedInputs([],[],{},ref,[],'synthetic',str(ref_path),str(job/'masks/model'))
            context=SimpleNamespace(model_spec=spec,reference=ref,checkpoint=lambda *a:None)
            result=ScientificAdapter().normalize_result(ScientificPrediction(prepared,masks,[],{},{}),context)
            self.assertEqual([m.class_id for m in result.masks],['survives'])
            self.assertEqual(len(result.warnings),1)
            self.assertEqual(result.warnings[0].details['working_voxels'],2)
            self.assertEqual(result.warnings[0].details['reference_voxels'],0)
            self.assertEqual(result.transformations[-1]['classes'][-1]['working_voxels'],0)
            # Deliberately taint private fields: the DTO must project a strict allowlist.
            result.warnings[0].details['path']='PRIVATE_PATH'; result.warnings.append(ContractMessage('private','PRIVATE_LOG'))
            manifest=StudyManifest('request','study','1.0',1,ref,['model'],[result],'completed','cpu','cpu')
            store=ResultStore(root,catalog={'model':spec});store.register_job('study',job)
            store.save_manifest(manifest);store.save_manifest(manifest)
            for revision in (1,2):
                view=store.public_view(store.load_manifest('study',revision)).to_dict()
                self.assertNotIn('PRIVATE',json.dumps(view)); warning=view['models'][0]['warnings'][0]
                self.assertEqual(warning['class_id'],'lost'); self.assertEqual(warning['model_id'],'model')
                self.assertEqual(warning['reference_voxels'],0)

    def test_model_help_is_complete_and_all_new_phrases_are_localized(self):
        from neuro_rt.model_registry import load_catalog
        root=Path(__file__).resolve().parents[1]
        translations=json.loads((root/'web/study-i18n.json').read_text(encoding='utf-8'))
        self.assertEqual(len(translations),12)
        for model in load_catalog():
            for key in ('summary','method','preparation','hardware','limitations'):
                self.assertTrue(model['help'].get(key), (model['id'],key))
            for phrase in model['help'].values():
                # Phrase fragments can be composed; scientific proper names remain unchanged.
                for lang in translations: self.assertIn(phrase,translations[lang])
        for mid in ('anatomy_synthseg','anatomy_cerebra_ants'):
            model=next(m for m in load_catalog() if m['id']==mid)
            self.assertIn('Somente CPU',model['help']['hardware'])
