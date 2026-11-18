"""Registered MPRs and native-resolution surfaces for NEURO model results."""
import itertools
import xml.etree.ElementTree as ET

import numpy as np
import SimpleITK as sitk
from scipy import ndimage


def _corners(image, first, last):
    return np.array([image.TransformContinuousIndexToPhysicalPoint(tuple(map(float, xyz)))
                     for xyz in itertools.product(*zip(first, last))])


def native_surface(original, region):
    """A clipped scalar field keeps every native sample on its original side of the surface."""
    import radai_bolus
    import radai_recon3d as recon

    bits = sitk.GetArrayViewFromImage(original)[region] != 0
    padded = np.pad(bits, 1)
    spacing = np.asarray(original.GetSpacing()[::-1])
    # Subvoxel displacement only. Marching tetrahedra sees the same sign pattern,
    # hence the same intersected edges, connected components and holes.
    smooth = ndimage.gaussian_filter(padded.astype(np.float32),
                                    sigma=.75*spacing.min()/spacing, mode='constant')
    np.maximum(smooth, np.float32(.72), out=smooth, where=padded)
    np.minimum(smooth, np.float32(.28), out=smooth, where=~padded)
    # Keep the native outer extent on all six sides, including single-slice ROIs.
    for axis in range(3):
        for index in {0,1,padded.shape[axis]-2,padded.shape[axis]-1}:
            cut=[slice(None)]*3
            cut[axis]=index
            smooth[tuple(cut)] = padded[tuple(cut)]
    smooth *= -1
    smooth += .5
    vertices, faces = radai_bolus.superficie(smooth)
    offset = np.asarray([s.start for s in region])*spacing
    return recon._mascara_em_lps(vertices, faces, spacing, original.GetOrigin(),
                                 original.GetDirection(), offset)


def mask_region(original):
    # Model masks are integer (typically uint8, sometimes multiples of 1).
    objects = ndimage.find_objects(sitk.GetArrayViewFromImage(original) != 0, max_label=1)
    return objects[0] if objects else None


class StudyViews:
    def __init__(self, image):
        self.image = image
        native = np.asarray(image.GetSpacing())
        directions = np.abs(np.asarray(image.GetDirection()).reshape(3,3))
        # The nearest display sample to any native voxel centre stays inside
        # that voxel, also in oblique acquisitions with anisotropic spacing.
        if np.allclose(directions, np.rint(directions), atol=1e-7):
            self.spacing = np.rint(directions) @ native
        else:
            axis_pitch = 1 / np.linalg.norm(directions/native, axis=1)
            self.spacing = axis_pitch * min(native/(directions.T @ axis_pitch)) * .999
        corners = _corners(image, (0,0,0), np.asarray(image.GetSize())-1)
        self.low = corners.min(0)
        self.high = corners.max(0)
        self.size = np.ceil((self.high-self.low)/self.spacing-1e-7).astype(int)+1
        self.shape = tuple(int(d) for d in self.size[::-1])
        self.overlays = [dict() for _ in self.shape]
        self.union = np.zeros((*self.shape[:2], (self.shape[2]+7)//8), dtype=np.uint8)
        self.identity = sitk.Transform()
        samples = sitk.GetArrayViewFromImage(image)
        # Bound the temporary percentile sample independently of scan size.
        stride = max(1, int(np.ceil((samples.size/1_000_000)**(1/3))))
        samples = samples[::stride,::stride,::stride]
        values = samples[samples > 0]
        self.lo, self.hi = np.percentile(values,[.5,99.5]) if values.size else (0.,1.)
        if self.hi <= self.lo:
            self.hi=self.lo+1.

    def _sample(self, image, first, size, interp, pixel):
        return sitk.Resample(image, list(map(int,size)), self.identity, interp,
                             tuple(self.low+self.spacing*first), tuple(self.spacing),
                             (1.,0.,0.,0.,1.,0.,0.,0.,1.), 0., pixel)

    def add_roi(self, original, region, name, color):
        import engine
        import radai_recon3d as recon

        first_native = np.array([s.start for s in region][::-1])-.5
        last_native = np.array([s.stop for s in region][::-1])-.5
        corners = _corners(original, first_native, last_native)
        first = np.maximum(0,np.floor((corners.min(0)-self.low)/self.spacing).astype(int))
        last = np.minimum(self.size-1,np.ceil((corners.max(0)-self.low)/self.spacing).astype(int))
        cut = self._sample(original, first, last-first+1, sitk.sitkNearestNeighbor, sitk.sitkUInt8)
        bits = sitk.GetArrayViewFromImage(cut) != 0
        z,y,x = map(int,first[::-1])
        aligned = np.pad(bits,((0,0),(0,0),(x%8,0)))
        packed = np.packbits(aligned,axis=2)
        self.union[z:z+bits.shape[0], y:y+bits.shape[1], x//8:x//8+packed.shape[2]] |= packed
        for axis in range(3):
            rows,cols=[a for a in range(3) if a!=axis]
            y0,x0=first[::-1][[rows,cols]]
            fl,fc=recon.grade_da_tela((self.shape[rows],self.shape[cols]),
                                     self.spacing[::-1][rows],self.spacing[::-1][cols])[2:]
            flip=rows==0
            ty=(self.shape[rows]-y0-.5 if flip else y0+.5)*fl
            transform='matrix(%.10g 0 0 %.10g %.10g %.10g)' % (fc,-fl if flip else fl,(x0+.5)*fc,ty)
            for index, plane in enumerate(np.moveaxis(bits,axis,0)):
                if not plane.any():
                    continue
                paths=[]
                for xy in engine.aneis_subpixel_plano(plane):
                    paths.append('M'+' '.join('%.4f,%.4f'%(a,b) for a,b in xy)+'Z')
                if paths:
                    group=ET.Element('{http://www.w3.org/2000/svg}g',{'data-roi':name,'fill':'none',
                                     'stroke':'rgb(%d,%d,%d)'%tuple(color),'stroke-width':'1.2',
                                     'stroke-linejoin':'round'})
                    ET.SubElement(group,'{http://www.w3.org/2000/svg}path',
                                  {'d':' '.join(paths),'transform':transform,'vector-effect':'non-scaling-stroke'})
                    self.overlays[axis].setdefault(int(first[::-1][axis])+index,[]).append(group)

    def centers(self):
        counts=[np.zeros(n,dtype=np.int64) for n in self.shape]
        for z, packed in enumerate(self.union):
            plane=np.unpackbits(packed,axis=1,count=self.shape[2])
            counts[0][z]=plane.sum()
            counts[1]+=plane.sum(axis=1,dtype=np.int64)
            counts[2]+=plane.sum(axis=0,dtype=np.int64)
        return [int(c.argmax()) if c.any() else (len(c)-1)//2 for c in counts]

    def svg(self, axis, index):
        import radai_recon3d as recon
        import radai_recon3d_screen as screen
        from types import SimpleNamespace

        first=np.zeros(3,dtype=int);first[2-axis]=index
        size=self.size.copy();size[2-axis]=1
        section=self._sample(self.image, first, size, sitk.sitkLinear, sitk.sitkFloat32)
        pixels=np.squeeze(sitk.GetArrayViewFromImage(section),axis=axis)
        pitch=tuple(self.spacing[::-1])
        sense=('sup','post','esq')
        plane=recon.plano_para_a_tela(pixels,axis,pitch,sense)
        png=recon.para_png(plane,float(self.lo+self.hi)/2,float(self.hi-self.lo))
        empty={'tipo':'rotulos','rois':[],'mapa':SimpleNamespace(_vol={},tabela=[]),
               'esp_zyx':pitch,'origem':self.low,'direcao':section.GetDirection()}
        svg=screen._png_com_contornos(png,empty,self.shape,pitch,self.low,section.GetDirection(),sense,axis,index,[])
        groups=self.overlays[axis].pop(index,())
        if not groups:
            return svg
        root=ET.fromstring(svg)
        root.extend(groups)
        return ET.tostring(root, encoding='utf-8')
