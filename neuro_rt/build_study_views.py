"""Build v2 MPR and independent ROI surfaces with Local Suite renderers.

Only generated logical names enter view.json. The ResultStore publishes each
artifact with an opaque ID; neither the scene nor the client receives paths.
"""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuro_rt.scientific_io import read_image


def _inside(job, path):
    target = Path(path).resolve()
    if not target.is_relative_to(job) or not target.is_file():
        raise ValueError('Máscara fora da pasta privada do estudo ou indisponível.')
    return target


def build_study_views(job_dir, host_app):
    from integration.host_imports import prepare_host_imports
    prepare_host_imports(host_app)
    import numpy as np
    import SimpleITK as sitk
    import radai_recon3d as recon
    from neuro_rt.imaging import validate_mask
    from neuro_rt.segmentation_views import StudyViews, mask_region, native_surface
    from neuro_rt.result_store import atomic_json
    from neuro_rt.roi_registry import make_roi_identity
    from neuro_rt.model_registry import get_model_spec

    job = Path(job_dir).resolve()
    manifest_path = job / 'study-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'neuro-rt/result/2':
        raise ValueError('A visualização exige manifesto de estudo v2.')
    image = read_image(str(_inside(job, job / 'inputs' / 'reference.nii.gz')))
    source_rois = []
    for result in manifest.get('results', []):
        for mask in result.get('masks', []):
            source = Path(mask['path'])
            if not source.is_absolute():
                raise ValueError('Máscara deve apontar para um caminho privado absoluto.')
            source = _inside(job, source)
            identity = 'roi_%03d' % len(source_rois)
            roi_identity = make_roi_identity(result['model_id'], mask['class_id'], manifest['revision'])
            spec = get_model_spec(result['model_id'])
            class_label = next(c.get('label',str(c['class_id'])) for c in spec['classes']
                               if c['class_id'] == mask['class_id'])
            source_rois.append(({
                'id': identity, 'model_id': result['model_id'], 'class_id': mask['class_id'],
                'label': spec['label'] + ' / ' + class_label,
                'roi_name': roi_identity.roi_name,
                'color': list(roi_identity.color),
                'opacity': .7, 'visible': True, 'mesh': None,
            }, source))
    views = StudyViews(image)
    dest = (job / 'views').resolve()
    if not dest.is_relative_to(job):
        raise ValueError('Pasta de visualização fora da área privada do estudo.')
    dest.mkdir(exist_ok=True)
    artifacts = []
    scene = {'schema':'neuro-rt/view/2','orientation':'LPS','engine':'Local Suite',
             'planes':{},'rois':[],'bounds':[views.low.tolist(),views.high.tolist()],
             'render_spacing_xyz_mm':views.spacing.tolist()}
    large_anatomy = len(source_rois) > 24
    for roi, source in source_rois:
        original = read_image(str(source)); validate_mask(original,image)
        roi['visible'] = not large_anatomy
        roi['volume_cm3'] = float(np.count_nonzero(sitk.GetArrayViewFromImage(original)) * np.prod(original.GetSpacing()) / 1000.)
        region = mask_region(original)
        if region is not None:
            views.add_roi(original,region,roi['id'],roi['color'])
            verts, faces = native_surface(original,region)
            if len(faces):
                name = roi['id'] + '.stl'; (dest/name).write_bytes(recon.stl_da_malha(verts,faces))
                roi['mesh'] = name
                artifacts.append({'kind':'mesh','path':'views/'+name,'logical_name':name})
        scene['rois'].append(roi)
    centers = views.centers()
    for axis, name in enumerate(('axial','coronal','sagittal')):
        plane = {'count':views.shape[axis],'center':centers[axis],'slices':[]}
        scene['planes'][name] = plane
        for index in range(views.shape[axis]):
            filename = '%s_%03d.svg' % (name,index)
            (dest/filename).write_bytes(views.svg(axis,index))
            plane['slices'].append(filename)
            artifacts.append({'kind':'slice','path':'views/'+filename,'logical_name':filename})
    atomic_json(dest/'view.json',scene)
    artifacts.append({'kind':'view','path':'views/view.json','logical_name':'view.json'})
    # Rebuilding replaces generated artifacts, preserving masks and export receipts.
    manifest['artifacts'] = [a for a in manifest.get('artifacts',[]) if a.get('kind') not in ('view','mesh','slice')] + artifacts
    atomic_json(manifest_path,manifest)
    return scene


build = build_study_views

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-dir',required=True,type=Path)
    parser.add_argument('--host-app',required=True,type=Path)
    args = parser.parse_args()
    build_study_views(args.job_dir,args.host_app)
