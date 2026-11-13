"""Synthetic raster painting keeps holes/islands and original physical geometry."""
import base64
from types import SimpleNamespace
import unittest
import numpy as np
import SimpleITK as sitk
import radai_projection as N
from neuro_rt.nidus_projection_paint import incidence_mask, painted_tube, projection_consensus


def inc(mask, lao=0, cra=0):
    return {'lao':lao,'cra':cra,'pontos':[[0,0],[63,0],[63,63],[0,63]],
            'mascara':base64.b64encode(np.packbits(mask).tobytes()).decode()}


class ProjectionPainting(unittest.TestCase):
    def setUp(self):
        self.image=sitk.Image([41,37,33],sitk.sitkUInt8)
        self.image.SetSpacing((.8,1.1,1.3));self.image.SetOrigin((-12.,31.,-24.))
        a=np.deg2rad(23);self.image.SetDirection((np.cos(a),-np.sin(a),0.,np.sin(a),np.cos(a),0.,0.,0.,1.))
        self.series=SimpleNamespace(img=self.image,eixos=N.eixos_lps(self.image))
        self.mask=np.zeros((64,64),bool);self.mask[18:46,18:46]=1
        self.mask[27:37,27:37]=0 # Erased central hole.
        self.mask[20:24,48:52]=1 # Disconnected painted island.

    def test_packed_roundtrip_and_hole_remains_empty(self):
        row=inc(self.mask);np.testing.assert_array_equal(incidence_mask(row,64),self.mask)
        core=projection_consensus(self.image,[row],64)
        packed=painted_tube(self.series,row,64)
        tube=np.unpackbits(packed.bits,axis=-1,count=packed.shape[-1]).astype(bool)
        expected=N.para_lps(core.mask(50),self.series.eixos)
        np.testing.assert_array_equal(tube,expected)
        full=self.mask.copy();full[27:37,27:37]=1
        solid=projection_consensus(self.image,[inc(full)],64)
        self.assertGreater(np.count_nonzero(solid.mask(50)&~core.mask(50)),0)
        self.assertNotEqual(core.incidence_digest,solid.incidence_digest)

    def test_rotated_painted_consensus_endpoints_and_planes(self):
        rows=[inc(self.mask),inc(self.mask,63,17)]
        core=projection_consensus(self.image,rows,64)
        masks=[projection_consensus(self.image,[row],64).mask(50) for row in rows]
        np.testing.assert_array_equal(core.mask(0),masks[0]|masks[1])
        np.testing.assert_array_equal(core.mask(100),masks[0]&masks[1])
        view=N.para_lps(core.mask(50),self.series.eixos)
        for axis in range(3):
            i=view.shape[axis]//2
            np.testing.assert_array_equal(core.plane(50,axis,i),N.corte(view,axis,i))
        self.assertEqual(core.geometry['direction'],list(self.image.GetDirection()))

    def test_pencil_remains_identical_and_bad_rasters_rejected(self):
        row={'lao':45,'cra':12,'pontos':[[19,20],[43,20],[43,44],[19,44]]}
        np.testing.assert_array_equal(projection_consensus(self.image,[row],64).mask(50),N.consenso(self.image,[row],lado=64).mask(50))
        for value in ['!',inc(self.mask)['mascara'][:-4],None]:
            with self.subTest(value=str(value)[:8]),self.assertRaises(ValueError):
                incidence_mask({'mascara':value},64)

if __name__=='__main__':unittest.main()
