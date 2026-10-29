"""Artefatos de exibição; usa PNG, geometria e superfícies do Local Suite."""
import argparse
import itertools
import json
import sys
from pathlib import Path
from types import SimpleNamespace


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
    import numpy as np
    import SimpleITK as sitk
    import radai_recon3d as recon
    import radai_recon3d_screen as screen
    import radai_viewer as renderer
    from neuro_rt.imaging import validate_mask

    job=Path(job_dir).resolve();dest=job/'views';dest.mkdir(exist_ok=True)
    image=sitk.ReadImage(str(job/'inputs/input0.nii.gz'))
    mask=sitk.ReadImage(str(job/'masks/Tumor.nii.gz'));validate_mask(mask,image)
    corners=np.array([image.TransformIndexToPhysicalPoint(tuple(int(v) for v in index))
                      for index in itertools.product(*[(0,n-1) for n in image.GetSize()])])
    low=corners.min(0);high=corners.max(0)
    spacing=max(1.,float(np.max(high-low))/319)
    size=[int(np.ceil(v/spacing))+1 for v in high-low]
    grid=sitk.Image(size,sitk.sitkFloat32);grid.SetOrigin(tuple(low));grid.SetSpacing((spacing,)*3)
    native=sitk.Resample(image,grid,sitk.Transform(),sitk.sitkLinear,0.,sitk.sitkFloat32)
    labels=sitk.Resample(mask,grid,sitk.Transform(),sitk.sitkNearestNeighbor,0,sitk.sitkUInt8)
    volume=sitk.GetArrayFromImage(native);bits=sitk.GetArrayFromImage(labels)>0
    values=volume[volume>0]
    lo,hi=(np.percentile(values,[.5,99.5]) if values.size else (0.,1.))
    if hi<=lo:hi=lo+1
    centers=center_slices(bits)
    # Contrato de mapa de rótulos já consumido pelo MPR do host. A máscara
    # está na mesma grade LPS isotrópica da imagem de exibição.
    geometry={'esp_zyx':grid.GetSpacing()[::-1],'origem':grid.GetOrigin(),
              'direcao':grid.GetDirection()}
    conjunto={'tipo':'rotulos','rois':[{'nome':'Tumor','cor':[255,173,72]}],
              'mapa':SimpleNamespace(_vol={'Tumor':bits},
                  tabela=[{'nome':'Tumor','chave':'Tumor','indice':1}]),**geometry}
    data={'schema':'neuro-rt/view/1','planes':{},'meshes':[],'window':[float(lo),float(hi)],
          'render_spacing_mm':spacing,'orientation':'LPS','engine':'Local Suite'}
    for axis,name in enumerate(('axial','coronal','sagittal')):
        data['planes'][name]={'count':volume.shape[axis],'center':centers[axis],'format':'svg'}
        for index in range(volume.shape[axis]):
            gray=np.take(volume,index,axis=axis)
            # A função do host preserva milímetros e põe o crânio em cima.
            gray=recon.plano_para_a_tela(gray,axis,geometry['esp_zyx'],('sup','post','esq'))
            png=recon.para_png(gray,float(lo+hi)/2,float(hi-lo))
            svg=screen._png_com_contornos(png,conjunto,volume.shape,
                geometry['esp_zyx'],geometry['origem'],geometry['direcao'],
                ('sup','post','esq'),axis,index,None)
            (dest/f'{name}_{index:03d}.svg').write_bytes(svg)
    for name,file,color,opacity in [('Tumor',job/'masks/Tumor.nii.gz',[255,173,72],1.),
                                    ('Brain',job/'brain_predictions/labels_Brain.nii.gz',[145,179,211],.14)]:
        if not file.is_file():continue
        original=sitk.ReadImage(str(file));validate_mask(original,image)
        if name=='Brain':
            factors=[max(1,int(round(2./s))) for s in original.GetSpacing()]
            original=sitk.Shrink(original,factors)
        array=sitk.GetArrayFromImage(original)>0
        if not array.any():continue
        verts,faces=recon.malha_de_mascara(array,original.GetSpacing()[::-1],
            original.GetOrigin(),original.GetDirection(),suavizar_mm=0.)
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
