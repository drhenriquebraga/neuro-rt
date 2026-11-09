"""All eight Buti CT labels, using the host's unchanged nnU-Net inference.

Executed only in the host Python scientific worker. The coordinator owns the
worker process tree, including nnU-Net's multiprocessing children. No nested
Popen, download, FULL filtering, ROI renaming or connected-component pruning.
"""
from ..scientific_io import read_image, write_image
from pathlib import Path
import shutil
import sys
import tempfile

from ._scientific import ScientificAdapter, ScientificPrediction
from ..study_types import MaskArtifact


def _run_host_script(engine, trainer, input_path, directory, device):
    import torch
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA solicitada, mas indisponível no Python do host.')
    if device not in ('cpu', 'cuda'):
        raise ValueError('Dispositivo precisa estar resolvido em cpu ou cuda.')
    output = directory / 'output'; output.mkdir()
    # Reuse exactly the engine's published _SCRIPT, including its predictor
    # settings and fold_all. Invoke inside the already isolated host worker.
    namespace = {'__name__': '_neuro_private_buti_inference'}
    exec(compile(engine._SCRIPT, engine.__file__ + ':_SCRIPT', 'exec'), namespace)
    previous_argv = sys.argv
    try:
        sys.argv = [engine.__file__, str(trainer), str(input_path), str(output),
                    str(directory), device]
        namespace['_principal']()
    finally:
        sys.argv = previous_argv
    generated = list(output.glob('*.nii.gz'))
    if len(generated) != 1:
        raise RuntimeError('Buti não produziu exatamente um mapa de rótulos.')
    return generated[0], str(torch.__version__)


class ButiCTAdapter(ScientificAdapter):
    roles = ('CT',)

    def prepare(self, context):
        if context.reference.modality != 'CT':
            raise ValueError('Buti exige referência TC (CT).')
        from integration.buti_host import LABELS
        if [c['class_id'] for c in context.model_spec['classes']] != list(LABELS.values()):
            raise ValueError('O contrato Buti deve preservar as oito classes/rótulos originais.')
        return super().prepare(context)

    def predict(self, prepared, context):
        import numpy as np
        import SimpleITK as sitk
        from integration.buti_host import LABELS, host_assets, load_host_module
        from ..geometry_pipeline import verify_reference_geometry
        from ..imaging import check_volume, geometry
        context.checkpoint('running', 0.)
        python = getattr(context, 'host_python', None)
        if not python or str(python).strip() == '?' or Path(python).resolve() != Path(sys.executable).resolve():
            raise RuntimeError('Buti deve executar no Python científico do host configurado.')
        host_app = getattr(context, 'host_app', None)
        _, trainer, table, metadata, hashes = host_assets(host_app, verify_hashes=True)
        if context.model_spec['revision'] != metadata.get('revisao'):
            raise ValueError('Revisão dos pesos Buti diverge do catálogo autorizado.')
        engine = load_host_module(host_app, 'radai_cranio_engine')
        if engine.ROTULOS_CONFERIDOS != LABELS:
            raise ValueError('As classes/rótulos conferidos do host foram alterados.')
        engine.conferir_rotulos(table)
        directory = Path(tempfile.mkdtemp(prefix='buti_', dir=context.job_dir))
        # nnU-Net derives the case ID from the channel suffix _0000.
        input_path = directory / 'case_0000.nii.gz'
        shutil.copyfile(prepared.channel_paths[0], input_path)
        output, torch_version = _run_host_script(engine, trainer, input_path, directory, context.device)
        context.checkpoint('running', 1.)
        image = read_image(str(output)); check_volume(image)
        if not verify_reference_geometry(image, prepared.working_geometry).valid:
            raise ValueError('Geometria do mapa Buti diverge da entrada preparada.')
        labels = sitk.GetArrayFromImage(image)
        if not np.isfinite(labels).all() or not np.isin(labels, [0, *LABELS]).all():
            raise ValueError('Buti retornou rótulos inválidos ou não finitos.')
        masks = []
        for index, name in LABELS.items():
            mask = sitk.GetImageFromArray((labels == index).astype(np.uint8))
            mask.CopyInformation(image)
            path = directory / (name + '.nii.gz'); write_image(mask, str(path))
            masks.append(MaskArtifact(context.model_spec['id'], name, str(path), geometry(mask),
                'working', {'adapter': 'buti_host', 'label_value': index, 'host_managed': True}))
        return ScientificPrediction(prepared, masks,
            [{'operation': 'host_nnunet_buti', 'input': 'whole_prepared_CT',
              'folds': ['all'], 'use_mirroring': False, 'device': context.device,
              'checkpoint': 'checkpoint_final.pth'}],
            {'engine': 'host-nnunet', 'torch': torch_version}, hashes)
