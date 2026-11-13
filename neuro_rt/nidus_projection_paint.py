"""Projection-space painting, preserving holes and islands in one incidence.

The raster is in the exact projection pixel grid. Existing pencil polygons keep
their original path. No depth is inferred from a single painted projection.
"""
import base64
import hashlib
import json


def incidence_mask(incidence, side):
    import numpy as np
    value = incidence.get('mascara')
    if not isinstance(value, str) or not 16 <= side <= 1024:
        raise ValueError('Máscara de incidência inválida.')
    expected = (side * side + 7) // 8
    if len(value) != 4 * ((expected + 2) // 3):
        raise ValueError('Máscara de incidência inválida.')
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ValueError('Máscara de incidência inválida.') from None
    if len(raw) != expected:
        raise ValueError('Máscara de incidência inválida.')
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8), count=side*side).reshape(side, side).astype(bool)


def painted_tube(series, incidence, side):
    import numpy as np
    import SimpleITK as sitk
    import radai_projection as N
    mask = incidence_mask(incidence, side)
    transform = N._transformada(series.img, float(incidence.get('lao', 0)), float(incidence.get('cra', 0)))
    diagonal, step, _, _ = N._medidas_da_grade(series.img, side)
    center = transform.GetCenter()
    image = sitk.GetImageFromArray(np.ascontiguousarray(np.broadcast_to(mask[::-1, None, :].astype('uint8'), (side, 2, side))))
    image.SetSpacing((step, diagonal, step))
    image.SetOrigin(tuple(v-diagonal/2 for v in center))
    native = sitk.GetArrayFromImage(sitk.Resample(image, series.img, transform, sitk.sitkNearestNeighbor, 0)).view(np.bool_)
    return N.compactar(N.para_lps(native, series.eixos))


def projection_consensus(image, incidences, side):
    """Reuse the host's physical sampler with signed fields from painted pixels."""
    import numpy as np
    from scipy import ndimage
    import radai_projection as N
    core = N.consenso(image, incidences, lado=side)
    for index, incidence in enumerate(incidences):
        if not incidence.get('mascara'):
            continue
        mask = incidence_mask(incidence, side)
        if not mask.any():
            field = np.full(mask.shape, core.outside, dtype=np.float32)
        elif mask.all():
            field = np.full(mask.shape, -core.outside, dtype=np.float32)
        else:
            field = (ndimage.distance_transform_edt(mask, sampling=(core.step, core.step))
                     - ndimage.distance_transform_edt(~mask, sampling=(core.step, core.step))).astype(np.float32)
        core.fields[index] = field
        core.incidences[index]['mascara'] = incidence['mascara']
    core.incidence_digest = hashlib.sha256(json.dumps(core.incidences, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return core


NIDUS_PROJECTION_PAINT_JS = r"""
(function(){
 'use strict';
 var canvas=null,context=null,serialized=null,trace=null;
 function painting(){return ND.tool==='brush'||ND.tool==='eraser'}
 function prepare(){
  if(!canvas||canvas.width!==ND.lado){canvas=document.createElement('canvas');canvas.width=canvas.height=ND.lado;context=canvas.getContext('2d',{willReadFrequently:true});serialized=null}
  if(serialized===ND.projectionMask&&ND.projectionMask)return;
  context.clearRect(0,0,ND.lado,ND.lado);context.fillStyle='#e9a148';
  if(ND.projectionMask){
   var raw=atob(ND.projectionMask),pixels=context.createImageData(ND.lado,ND.lado);
   for(var i=0;i<ND.lado*ND.lado;i++)if(raw.charCodeAt(i>>3)&(1<<(7-(i&7)))){
    pixels.data[i*4]=233;pixels.data[i*4+1]=161;pixels.data[i*4+2]=72;pixels.data[i*4+3]=255;
   }context.putImageData(pixels,0,0);
  }else if(ND.pontos.length>=3){context.beginPath();ND.pontos.forEach(function(p,i){if(i)context.lineTo(p[0],p[1]);else context.moveTo(p[0],p[1])});context.closePath();context.fill('evenodd')}
  serialized=ND.projectionMask;
 }
 function overlay(){
  var group=ndEl('nd_marca');if(!group)return;
  if(canvas.parentNode&&canvas.parentNode.parentNode===group)return;
  group.replaceChildren();var foreign=document.createElementNS('http://www.w3.org/2000/svg','foreignObject');
  foreign.setAttribute('width',ND.lado);foreign.setAttribute('height',ND.lado);foreign.style.pointerEvents='none';foreign.style.opacity='.48';
  canvas.style.width=canvas.style.height='100%';foreign.appendChild(canvas);group.appendChild(foreign);
 }
 function radius(){
  var step=ND.passos&&Number(ND.passos[String(ND.lado)]);
  if(!(step>0)&&ND.geo){var q=ND.geo.da_caixa;step=Math.hypot(q[0]+q[1]+q[2],q[4]+q[5]+q[6],q[8]+q[9]+q[10])/ND.lado}
  return Math.max(.5,ND.brushDiameter/(2*Math.max(step||1,.001)));
 }
 function dab(point){
  context.globalCompositeOperation=trace.tool==='eraser'?'destination-out':'source-over';
  context.strokeStyle=context.fillStyle='#e9a148';context.lineWidth=trace.radius*2;context.lineCap=context.lineJoin='round';
  if(trace.last){context.beginPath();context.moveTo(trace.last[0],trace.last[1]);context.lineTo(point[0],point[1]);context.stroke()}
  context.beginPath();context.arc(point[0],point[1],trace.radius,0,Math.PI*2);context.fill();trace.last=point;overlay();
 }
 function commit(){
  var data=context.getImageData(0,0,ND.lado,ND.lado).data,bytes=new Uint8Array(Math.ceil(ND.lado*ND.lado/8));
  var x0=ND.lado,y0=ND.lado,x1=-1,y1=-1;
  for(var i=0;i<ND.lado*ND.lado;i++)if(data[i*4+3]>=128){
   bytes[i>>3]|=1<<(7-(i&7));var x=i%ND.lado,y=Math.floor(i/ND.lado);x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
  }
  if(x1<0){ND.projectionMask=null;ND.pontos=[];serialized=null;ndPintarMarca();ndRegistrar('pintar');ndAtualizarGuardar();return}
  var chunks=[];for(var offset=0;offset<bytes.length;offset+=8192)chunks.push(String.fromCharCode.apply(null,bytes.subarray(offset,offset+8192)));
  ND.projectionMask=btoa(chunks.join(''));serialized=ND.projectionMask;
  // Bounds satisfy the legacy save/angle guards; the backend uses the exact mask.
  ND.pontos=[[x0,y0],[x1+1,y0],[x1+1,y1+1],[x0,y1+1]];
  ndPintarMarca();ndRegistrar('pintar');ndAtualizarGuardar();
 }
 var oldPaint=ndPintarMarca;
 ndPintarMarca=function(){
  if(ND.projectionMask&&ND.pontos.length>=3){prepare();overlay();return}
  if(!ND.pontos.length){ND.projectionMask=null;serialized=null}
  return oldPaint.apply(this,arguments);
 };
 var oldStart=ndPressionar,oldMove=ndArrastar,oldEnd=ndSoltar;
 ndPressionar=function(event){
  if(!painting()){if(ND.tool==='pencil'){ND.projectionMask=null;serialized=null}return oldStart.apply(this,arguments)}
  if(event.button!==0||ndQuerMover(event)||!ndPodeDesenhar())return;
  event.preventDefault();ND.saveConfirmed=false;clearTimeout(ND.saveConfirmTimer);ndAtualizarGuardar();prepare();trace={b:ND.b,carga:ND.carga,lao:ND.lao,cra:ND.cra,tool:ND.tool,radius:radius(),before:ND.projectionMask,points:ND.pontos.slice()};
  ND.tracando=true;dab(ndPonto(event));
 };
 ndArrastar=function(event){if(!trace)return oldMove.apply(this,arguments);event.preventDefault();dab(ndPonto(event))};
 ndSoltar=function(){
  if(!trace)return oldEnd.apply(this,arguments);
  var snapshot=trace;trace=null;ND.tracando=false;
  if(snapshot.b!==ND.b||snapshot.carga!==ND.carga||snapshot.lao!==ND.lao||snapshot.cra!==ND.cra){serialized=null;return}
  context.globalCompositeOperation='source-over';commit();ndTravas();
 };
 var oldFoto=ndFoto,oldApply=ndAplicar;
 ndFoto=function(){var result=oldFoto();result.projectionMask=ND.projectionMask||null;return result};
 ndAplicar=function(f,draw){oldApply.apply(this,arguments);if(draw){ND.projectionMask=f&&f.projectionMask||null;serialized=null;ndPintarMarca()}};
 var oldSave=ndGuardar;
 ndGuardar=function(){
  var mask=ND.projectionMask,count=ND.guardadas.length;
  // ndGuardar calls ndCalcular synchronously; publish the mask into its snapshot.
  ND.savingProjectionMask=mask;
  try{return oldSave.apply(this,arguments)}finally{ND.savingProjectionMask=null;if(ND.guardadas.length>count){ND.projectionMask=null;serialized=null}}
 };
 var oldOpen=ndAbrirSerie;
 ndAbrirSerie=function(){trace=null;serialized=null;ND.projectionMask=null;return oldOpen.apply(this,arguments)};
 window.NidusProjectionPaint={active:function(){return !!trace}};
})();
"""
