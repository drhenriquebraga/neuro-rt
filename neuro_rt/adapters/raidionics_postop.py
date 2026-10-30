"""Three-channel Raidionics final stage, after explicit input registration.

The shared preparer requires source->reference transforms for distinct tickets.
Those registrations replace pipeline steps3/4/6/7; no header equality is treated
as registration. The official backend performs all final-stage preprocessing.
"""
from pathlib import Path
import shutil
from ._scientific import ScientificAdapter, ScientificPrediction, verified_assets, binary_masks


class RaidionicsPostopAdapter(ScientificAdapter):
    roles = ('T1c', 'T1', 'FLAIR')

    def predict(self, prepared, context):
        import importlib.metadata
        import nibabel as nib
        import numpy as np
        import onnxruntime as ort
        from raidionicsseg.fit import run_model
        from ..catalog import validate_model_folder, BRAIN, MODEL_LOCK
        from ..model_paths import resolve_model_folder
        from ..worker import write_runtime_config
        context.checkpoint('running', 0.)
        folder, hashes = verified_assets(context)
        if context.device == 'cuda':
            if 'CUDAExecutionProvider' not in ort.get_available_providers():
                raise ValueError('CUDA indisponível neste runtime.')
            session = ort.InferenceSession(str(folder / 'fold0/model.onnx'), providers=['CUDAExecutionProvider'])
            if 'CUDAExecutionProvider' not in session.get_providers():
                raise ValueError('CUDA não inicializou; fallback não permitido.')
            del session
        brain_folder = resolve_model_folder(context.models_dir, 'MRI_Brain', '1.2.0',
                                            allow_legacy=context.allow_legacy_models)
        validate_model_folder(brain_folder, BRAIN)
        hashes['MRI_Brain/fold0/model.onnx'] = MODEL_LOCK['MRI_Brain']['files']['fold0/model.onnx']
        directory = Path(context.job_dir) / 'raidionics_3p'
        inputs = directory / 'inputs'
        inputs.mkdir(parents=True, exist_ok=False)
        for i, path in enumerate(prepared.channel_paths):
            shutil.copyfile(path, inputs / f'input{i}.nii.gz')
        (directory / 'brain_predictions').mkdir()
        config = write_runtime_config(directory, brain_folder, context.device, 'brain_predictions')
        run_model(config_filename=str(config))
        brain = directory / 'brain_predictions/labels_Brain.nii.gz'
        if not brain.is_file() or not np.any(nib.load(brain).get_fdata()):
            raise ValueError('Máscara cerebral auxiliar ausente/vazia.')
        (directory / 'predictions').mkdir()
        config = write_runtime_config(directory, folder, context.device, brain_mask=brain)
        run_model(config_filename=str(config))
        paths = list((directory / 'predictions').glob('*_Tumor.nii.gz'))
        if len(paths) != 1:
            raise ValueError('O backend não produziu uma única máscara Tumor.')
        image = nib.load(paths[0])
        artifacts = binary_masks([image.get_fdata()], image.affine, ['tumor'], context)
        context.checkpoint('running', 1.)
        return ScientificPrediction(prepared, artifacts, [{
            'operation': 'Raidionics_3p_pipeline_stage8', 'input_order': list(self.roles),
            'registration': 'explicit_source_to_reference_transforms_in_prepare',
            'brain_crop': 'official_MRI_Brain_on_T1c', 'threshold': .4}],
            {'engine': 'raidionicsseg/' + importlib.metadata.version('raidionicsseg')}, hashes)
