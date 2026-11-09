"""CerebrA symmetric2009c atlas propagated template->subject with ANTs SyN."""
from pathlib import Path
from ..scientific_io import native_file_path
from ._scientific import ScientificAdapter, ScientificPrediction, verified_assets, label_masks


class CerebraANTsAdapter(ScientificAdapter):
    roles = ('T1',)
    cpu_only = True

    def predict(self, prepared, context):
        import ants
        import nibabel as nib
        import numpy as np
        context.checkpoint('running', 0.)
        folder, hashes = verified_assets(context)
        def read(path):
            with native_file_path(path) as local: return ants.image_read(local)
        fixed = read(prepared.channel_paths[0])
        moving = read(folder / 'template_t1.nii')
        labels = read(folder / 'atlas_labels.nii')
        mask = read(folder / 'template_mask.nii')
        if (moving.shape != labels.shape or not np.allclose(moving.origin, labels.origin)
                or not np.allclose(moving.direction, labels.direction)
                or not np.allclose(moving.spacing, labels.spacing)):
            raise ValueError('Template e atlas não compartilham a mesma grade física.')
        for image in (fixed, moving, labels, mask):
            if not np.isfinite(image.numpy()).all():
                raise ValueError('Imagem de registro contém valores não finitos.')
        directory = Path(context.job_dir) / 'ants_transforms'
        directory.mkdir(parents=True, exist_ok=True)
        # SyN performs affine initialization followed by deformable registration.
        with native_file_path(directory / 'template_to_subject_') as prefix:
            registration = ants.registration(fixed=fixed, moving=moving, type_of_transform='SyN',
                moving_mask=mask, mask_all_stages=True, random_seed=1729,
                reg_iterations=(40, 20, 0), aff_iterations=(2100, 1200, 1200, 10),
                outprefix=prefix, verbose=False)
            # ANTs returns relative filenames with a relative outprefix. Freeze
            # their absolute identity before restoring this child's cwd.
            for key in ('fwdtransforms', 'invtransforms'):
                registration[key] = [str(Path(p).resolve()) for p in registration[key]]
        if not registration['fwdtransforms'] or not registration['invtransforms']:
            raise ValueError('Registro não produziu transformações forward/inverse.')
        for path in set(registration['fwdtransforms'] + registration['invtransforms']):
            if not Path(path).is_file() or not Path(path).resolve().is_relative_to(directory.resolve()):
                raise ValueError('Transformação ausente ou fora da pasta privada de registro.')
            if path.endswith(('.nii.gz', '.nii')) and not np.isfinite(read(path).numpy()).all():
                raise ValueError('Transformação deformável não finita.')
            if path.endswith('.mat'):
                with native_file_path(path) as local: transform = ants.read_transform(local)
                if not (np.isfinite(transform.parameters).all() and
                        np.isfinite(transform.fixed_parameters).all()):
                    raise ValueError('Transformação afim não finita.')
        with native_file_path(directory / 'template_to_subject_') as prefix:
            propagated = ants.apply_transforms(fixed=fixed, moving=labels,
                transformlist=[Path(p).name if not Path(prefix).is_absolute() else p
                               for p in registration['fwdtransforms']], interpolator='genericLabel')
        output = directory / 'labels_subject.nii.gz'
        with native_file_path(output) as local: ants.image_write(propagated, local)
        image = nib.load(output)
        artifacts = label_masks(image.get_fdata(), image.affine, context)
        context.checkpoint('running', 1.)
        return ScientificPrediction(prepared, artifacts, [{
            'operation': 'ANTs_SyN', 'fixed': 'prepared_subject_T1', 'moving': 'MNI_sym2009c',
            'direction': 'template_to_subject', 'label_interpolation': 'genericLabel',
            'fwdtransforms': registration['fwdtransforms'], 'invtransforms': registration['invtransforms'],
            'reg_iterations': [40, 20, 0], 'aff_iterations': [2100, 1200, 1200, 10],
            'random_seed': 1729}],
            {'engine': 'antspyx/' + ants.__version__}, hashes)
