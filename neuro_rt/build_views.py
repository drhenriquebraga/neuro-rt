"""Artefatos de exibição; usa PNG, geometria e superfícies do Local Suite."""
import argparse
import json
import sys
from pathlib import Path


def center_slices(mask):
    if mask.any():
        return [int(mask.sum(axis=tuple(a for a in range(3) if a != axis)).argmax())
                for axis in range(3)]
    return [(count-1)//2 for count in mask.shape]


def build(job_dir,host_app):
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from integration.host_imports import prepare_host_imports
    prepare_host_imports(host_app)
    import SimpleITK as sitk
    import radai_recon3d as recon
    import radai_recon3d_screen as screen
    import radai_viewer as renderer
    from neuro_rt.imaging import validate_mask
    from neuro_rt.segmentation_views import StudyViews, mask_region, native_surface

    job=Path(job_dir).resolve();dest=job/'views';dest.mkdir(exist_ok=True)
    image=sitk.ReadImage(str(job/'inputs/input0.nii.gz'))
    mask=sitk.ReadImage(str(job/'masks/Tumor.nii.gz'));validate_mask(mask,image)
    views=StudyViews(image)
    region=mask_region(mask)
    if region is not None:
        views.add_roi(mask,region,'Tumor',(255,173,72))
    centers=views.centers()
    data={'schema':'neuro-rt/view/1','planes':{},'meshes':[],'window':[float(views.lo),float(views.hi)],
          'render_spacing_mm':float(min(views.spacing)),'render_spacing_xyz_mm':views.spacing.tolist(),
          'orientation':'LPS','engine':'Local Suite'}
    for axis,name in enumerate(('axial','coronal','sagittal')):
        data['planes'][name]={'count':views.shape[axis],'center':centers[axis],'format':'svg'}
        for index in range(views.shape[axis]):
            (dest/f'{name}_{index:03d}.svg').write_bytes(views.svg(axis,index))
    for name,file,color,opacity in [('Tumor',job/'masks/Tumor.nii.gz',[255,173,72],1.),
                                    ('Brain',job/'brain_predictions/labels_Brain.nii.gz',[145,179,211],.14)]:
        if not file.is_file():continue
        original=mask if name=='Tumor' else sitk.ReadImage(str(file))
        validate_mask(original,image)
        region=mask_region(original)
        if region is None:continue
        verts,faces=native_surface(original,region)
        path=f'{name}.stl';(dest/path).write_bytes(recon.stl_da_malha(verts,faces))
        data['meshes'].append({'name':name,'label':'Segmentação' if name=='Tumor' else 'Cérebro',
            'path':path,'color':color,'opacity':opacity,
            'bounds':[verts.min(0).tolist(),verts.max(0).tolist()],'triangles':len(faces)})
    # Reutilização literal do renderizador do host; nenhuma cópia entra no código do módulo.
    (dest/'renderer.js').write_text(renderer.JS_3D+'\n'+screen.JS_MALHA,encoding='utf-8')
    (dest/'view.json').write_text(json.dumps(data),encoding='utf-8')
    manifest=job/'manifest.json';result=json.loads(manifest.read_text(encoding='utf-8'))
    result['visualization']={'schema':data['schema'],'available':True,'path':'views/view.json'}
    manifest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Planos de segmentação e reconstruções montados pelo Local Suite.',flush=True)
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--job-dir',required=True,type=Path)
    parser.add_argument('--host-app',required=True,type=Path);args=parser.parse_args()
    build(args.job_dir,args.host_app)
