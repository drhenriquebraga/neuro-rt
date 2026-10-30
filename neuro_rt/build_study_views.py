"""Build v2 MPR and independent ROI surfaces with Local Suite renderers.

Only generated logical names enter view.json. The ResultStore publishes each
artifact with an opaque ID; neither the scene nor the client receives paths.
"""
import argparse
import itertools
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

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
    import radai_recon3d_screen as screen
    from neuro_rt.imaging import validate_mask
    from neuro_rt.build_views import center_slices
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
    corners = np.array([image.TransformIndexToPhysicalPoint(tuple(int(v) for v in index))
                        for index in itertools.product(*[(0,n-1) for n in image.GetSize()])])
    low, high = corners.min(0), corners.max(0)
    spacing = max(1., float(np.max(high-low))/319)
    grid = sitk.Image([int(np.ceil(v/spacing))+1 for v in high-low], sitk.sitkFloat32)
    grid.SetOrigin(tuple(low)); grid.SetSpacing((spacing,)*3)
    native = sitk.Resample(image, grid, sitk.Transform(), sitk.sitkLinear, 0., sitk.sitkFloat32)
    volume = sitk.GetArrayFromImage(native)
    values = volume[volume > 0]
    lo, hi = np.percentile(values,[.5,99.5]) if values.size else (0.,1.)
    if hi <= lo: hi = lo + 1
    geometry = {'esp_zyx':grid.GetSpacing()[::-1], 'origem':grid.GetOrigin(), 'direcao':grid.GetDirection()}
    dest = (job / 'views').resolve()
    if not dest.is_relative_to(job):
        raise ValueError('Pasta de visualização fora da área privada do estudo.')
    dest.mkdir(exist_ok=True)
    union = np.zeros(volume.shape,dtype=bool)
    artifacts = []
    scene = {'schema':'neuro-rt/view/2','orientation':'LPS','engine':'Local Suite',
             'planes':{},'rois':[],'bounds':[low.tolist(),high.tolist()]}
    large_anatomy = len(source_rois) > 24
    # Keep one resampled ROI at a time. An atlas with many classes must not
    # multiply a full 320-cubed label volume by the number of structures.
    pngs, overlays = {}, {}
    for axis in range(3):
        pngs[axis], overlays[axis] = [], []
        for index in range(volume.shape[axis]):
            gray = recon.plano_para_a_tela(np.take(volume,index,axis=axis),axis,geometry['esp_zyx'],('sup','post','esq'))
            pngs[axis].append(recon.para_png(gray,float(lo+hi)/2,float(hi-lo)))
            overlays[axis].append([])
    for roi, source in source_rois:
        original = read_image(str(source)); validate_mask(original,image)
        bits = sitk.GetArrayFromImage(sitk.Resample(original,grid,sitk.Transform(),sitk.sitkNearestNeighbor,0,sitk.sitkUInt8)) > 0
        union |= bits
        roi['visible'] = not large_anatomy
        native_bits = sitk.GetArrayFromImage(original) > 0
        if native_bits.any():
            verts, faces = recon.malha_de_mascara(native_bits,original.GetSpacing()[::-1],
                original.GetOrigin(),original.GetDirection(),suavizar_mm=0.)
            if len(faces):
                name = roi['id'] + '.stl'; (dest/name).write_bytes(recon.stl_da_malha(verts,faces))
                roi['mesh'] = name
                artifacts.append({'kind':'mesh','path':'views/'+name,'logical_name':name})
        scene['rois'].append(roi)
        conjunto = {'tipo':'rotulos','rois':[{'nome':roi['id'],'cor':roi['color']}],
                    'mapa':SimpleNamespace(_vol={roi['id']:bits},
                        tabela=[{'nome':roi['id'],'chave':roi['id'],'indice':1}]), **geometry}
        for axis in range(3):
            for index in range(volume.shape[axis]):
                if not np.take(bits,index,axis=axis).any(): continue
                layer = ET.fromstring(screen._png_com_contornos(pngs[axis][index],conjunto,volume.shape,
                    geometry['esp_zyx'],geometry['origem'],geometry['direcao'],('sup','post','esq'),axis,index,[roi['id']]))
                group = layer.find('{http://www.w3.org/2000/svg}g')
                if group is not None:
                    group.set('data-roi',roi['id']); overlays[axis][index].append(group)
    centers = center_slices(union)
    conjunto = {'tipo':'rotulos','rois':[],'mapa':SimpleNamespace(_vol={},tabela=[]),**geometry}
    for axis, name in enumerate(('axial','coronal','sagittal')):
        plane = {'count':volume.shape[axis],'center':centers[axis],'slices':[]}
        scene['planes'][name] = plane
        for index in range(volume.shape[axis]):
            png = pngs[axis][index]
            svg = screen._png_com_contornos(png,conjunto,volume.shape,geometry['esp_zyx'],geometry['origem'],geometry['direcao'],('sup','post','esq'),axis,index,[])
            root = ET.fromstring(svg)
            for group in overlays[axis][index]: root.append(group)
            filename = '%s_%03d.svg' % (name,index)
            (dest/filename).write_bytes(ET.tostring(root,encoding='utf-8'))
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
