import base64
import json
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import SimpleITK as sitk
from test_pipeline import TEMP_ROOT
from neuro_rt.service import Service, Settings
from neuro_rt.server import make_server


class ViewsTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('NEURO_PLAYWRIGHT_MODULE') and shutil.which('node'),
                         'Defina NEURO_PLAYWRIGHT_MODULE para a verificação real no Chrome.')
    def test_svg_embedded_png_renders_under_server_csp(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root=Path(tmp);folder=root/'runtime/jobs/synthetic';folder.mkdir(parents=True)
            image=sitk.GetImageFromArray(np.arange(120,dtype=np.float32).reshape((4,5,6)))
            self.build_views(folder,image,np.zeros((4,5,6),dtype=np.uint8))
            (root/'web').mkdir()
            (root/'web/index.html').write_text('<img id="sample" src="/neuro/api/jobs/synthetic/views/axial_001.svg">')
            service=Service(Settings(root));service._jobs['synthetic']={'id':'synthetic'}
            server=make_server(service,port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                script=Path(__file__).with_name('views_browser_scenario.cjs')
                proc=subprocess.run([shutil.which('node'),str(script),f'http://127.0.0.1:{server.server_port}/neuro/'],
                                    capture_output=True,timeout=60)
                self.assertEqual(proc.returncode,0,proc.stderr.decode(errors='replace'))
            finally:
                server.shutdown();server.server_close();service.close();thread.join(timeout=2)

    @unittest.skipUnless(shutil.which('node'),'Node é necessário para exercitar o viewer.')
    def test_viewer_uses_svg_and_keeps_legacy_png_navigation(self):
        script=Path(__file__).with_name('viewer_format_scenario.cjs')
        proc=subprocess.run([shutil.which('node'),str(script)],capture_output=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stderr.decode(errors='replace'))

    def build_views(self, folder, image, labels):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'neuro_rt.local.json').read_text())
        (folder/'inputs').mkdir();(folder/'masks').mkdir()
        sitk.WriteImage(image,str(folder/'inputs/input0.nii.gz'))
        mask=sitk.GetImageFromArray(labels);mask.CopyInformation(image)
        sitk.WriteImage(mask,str(folder/'masks/Tumor.nii.gz'))
        (folder/'manifest.json').write_text(json.dumps({'schema':'neuro-rt/result/1','masks':[{'path':'masks/Tumor.nii.gz'}]}))
        proc=subprocess.run([config['host_python'],str(root/'neuro_rt/build_views.py'),'--job-dir',str(folder),'--host-app',config['host_app']],capture_output=True,timeout=90)
        self.assertEqual(proc.returncode,0,proc.stderr.decode(errors='replace')[-1500:])
        return json.loads((folder/'views/view.json').read_text())

    def test_host_builds_planes_and_mesh_with_physical_geometry(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder=Path(tmp)
            array=np.arange(12*16*18,dtype=np.float32).reshape((12,16,18))
            image=sitk.GetImageFromArray(array);image.SetSpacing((.8,1.25,2.));image.SetOrigin((20.,30.,40.))
            view=self.build_views(folder,image,(array>700).astype(np.uint8))
            self.assertEqual(set(view['planes']),{'axial','coronal','sagittal'})
            self.assertEqual(len(view['meshes']),1)
            self.assertTrue((folder/'views'/view['meshes'][0]['path']).stat().st_size>84)
            for name,plane in view['planes'].items():
                self.assertEqual(plane['format'],'svg')
                frame=folder/'views'/f'{name}_{plane["center"]:03d}.svg'
                svg=ET.fromstring(frame.read_bytes())
                embedded=svg.find('{http://www.w3.org/2000/svg}image')
                png=base64.b64decode(embedded.attrib['{http://www.w3.org/1999/xlink}href'].split(',')[1])
                self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
                expected={'axial':(15,20),'coronal':(15,23),'sagittal':(20,23)}[name]
                self.assertEqual(struct.unpack('>II',png[16:24]),expected)
                self.assertTrue(svg.findall('.//{http://www.w3.org/2000/svg}path'))
            receipt=json.loads((folder/'manifest.json').read_text())['visualization']
            self.assertTrue(receipt['available'])
            self.assertTrue((folder/'views/renderer.js').stat().st_size>1000)

    def test_host_contours_and_mesh_stay_in_rotated_image_space(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder=Path(tmp)
            image=sitk.GetImageFromArray(np.ones((4,5,6),dtype=np.float32))
            image.SetOrigin((10.,20.,30.))
            image.SetDirection((0.,-1.,0.,1.,0.,0.,0.,0.,1.))
            labels=np.zeros((4,5,6),dtype=np.uint8);labels[1,1:3,2:4]=1
            view=self.build_views(folder,image,labels)
            svg=ET.fromstring((folder/'views/axial_001.svg').read_bytes())
            path=svg.find('.//{http://www.w3.org/2000/svg}path')
            self.assertEqual(path.attrib['d'],'M2 2h2M2 4h2M2 2v2M4 2v2')
            self.assertEqual(view['meshes'][0]['bounds'],[[7.5,21.5,30.5],[9.5,23.5,31.5]])

    def test_empty_mask_has_planes_without_contours_or_mesh(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            folder=Path(tmp)
            image=sitk.GetImageFromArray(np.zeros((4,5,6),dtype=np.float32))
            view=self.build_views(folder,image,np.zeros((4,5,6),dtype=np.uint8))
            self.assertEqual(view['meshes'],[])
            self.assertEqual(view['window'],[0.,1.])
            for name,plane in view['planes'].items():
                svg=ET.fromstring((folder/'views'/f'{name}_{plane["center"]:03d}.svg').read_bytes())
                self.assertFalse(svg.findall('.//{http://www.w3.org/2000/svg}path'))

    def test_view_file_accepts_svg_and_legacy_png_with_same_path_guard(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root=Path(tmp);folder=root/'jobs'/'synthetic'/'views';folder.mkdir(parents=True)
            service=Service.__new__(Service)
            service.settings=SimpleNamespace(data_dir=root)
            service.job=lambda job_id: {'id':job_id}
            for name in ('axial_001.svg','coronal_002.png'):
                path=folder/name;path.write_bytes(b'synthetic')
                self.assertEqual(service.view_file('synthetic',name),path)
            for name in ('../axial_001.svg','axial_001.svg.js','anything.svg'):
                with self.assertRaises(ValueError):service.view_file('synthetic',name)


if __name__=='__main__':unittest.main()
