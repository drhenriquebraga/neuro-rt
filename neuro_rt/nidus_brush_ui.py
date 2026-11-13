"""NIDUS adapter for the shared DICOM tools and revision-bound consensus mesh."""

NIDUS_BRUSH_JS = r"""
(function(){
 'use strict';
 var toolbar=null, meshSequence=0, meshTimer=null, lastPoint=null, activeAxis=null, mprViews=[], pan=null, editorRoot=null, editorHidden=[];
 ND.tool='pencil';ND.brushDiameter=5;ND.consCandidate=null;ND.consRevision=null;ND.consSession=null;ND.consUndo=false;
 function paintView(axis){
  var view=mprViews[axis];if(!view)return;
  view.layer.style.transform='translate('+view.x+'px,'+view.y+'px) scale('+view.scale+')';
 }
 function resetViews(){mprViews.forEach(function(view,axis){view.scale=1;view.x=0;view.y=0;paintView(axis)});activeAxis=null;pan=null}
 function zoomView(axis,factor,point){
  var view=mprViews[axis];if(!view||!ndDisponivel()||ND.consTrace)return;
  var old=view.scale,next=Math.max(1,Math.min(8,old*factor)),ratio=next/old;
  var box=view.pane.getBoundingClientRect(),x=point?point.clientX-box.left-box.width/2:0,y=point?point.clientY-box.top-box.height/2:0;
  view.x=x-(x-view.x)*ratio;view.y=y-(y-view.y)*ratio;view.scale=next;
  if(next===1){view.x=0;view.y=0}paintView(axis);
 }
 function installMprView(axis){
  var pane=ndEl('nd_pp'+axis),layer=document.createElement('div');layer.className='nd-mpr-transform';
  layer.style.cssText='position:absolute;inset:0;transform-origin:50% 50%';
  ['nd_pl','nd_lin','nd_cx','nd_ed'].forEach(function(prefix){layer.appendChild(ndEl(prefix+axis))});pane.prepend(layer);
  mprViews[axis]={pane:pane,layer:layer,scale:1,x:0,y:0};pane.tabIndex=0;
  pane.addEventListener('pointerenter',function(){activeAxis=axis});pane.addEventListener('focusin',function(){activeAxis=axis});
  pane.addEventListener('pointerdown',function(event){
   activeAxis=axis;
   if(!ndDisponivel()||ND.consTrace||ND.consensoBusy||!(ND.tool==='pan'&&event.button===0||event.button===1||event.shiftKey&&event.button===0))return;
   event.preventDefault();event.stopImmediatePropagation();pane.focus({preventScroll:true});pane.setPointerCapture(event.pointerId);
   var view=mprViews[axis];pan={axis:axis,pointer:event.pointerId,x:event.clientX,y:event.clientY,dx:view.x,dy:view.y};pane.style.cursor='grabbing';
  },true);
  pane.addEventListener('pointermove',function(event){
   if(!pan||pan.axis!==axis||pan.pointer!==event.pointerId)return;
   event.preventDefault();event.stopImmediatePropagation();var view=mprViews[axis];view.x=pan.dx+event.clientX-pan.x;view.y=pan.dy+event.clientY-pan.y;paintView(axis);
  },true);
  function finish(event){if(!pan||pan.axis!==axis||pan.pointer!==event.pointerId)return;event.stopImmediatePropagation();pan=null;pane.style.cursor='';if(pane.hasPointerCapture(event.pointerId))pane.releasePointerCapture(event.pointerId)}
  pane.addEventListener('pointerup',finish,true);pane.addEventListener('pointercancel',finish,true);
  pane.addEventListener('pointercancel',function(){
   if(ND.consTrace&&ND.consTrace.axis===axis){ND.consTrace=null;ndEl('nd_ed'+axis).innerHTML='<rect width="100%" height="100%" fill="transparent"/>';ndConsControles()}
  });
  pane.addEventListener('wheel',function(event){
   activeAxis=axis;if(!event.ctrlKey||brush()||!ndDisponivel())return;
   event.preventDefault();event.stopImmediatePropagation();zoomView(axis,event.deltaY<0?1.15:1/1.15,event);
  },{capture:true,passive:false});
 }
 function clearMesh(){
  meshSequence++;clearTimeout(meshTimer);
  if(ND3.consensusObj&&ND3.gl)r3gSoltarObj(ND3,ND3.consensusObj);
  ND3.consensusObj=null;ND3.consensusBox=null;ND3.consensusSession=null;
  nd3Pedir();
 }
 function same(session,candidate,revision){
  return session===ND.sessao&&candidate===ND.consCandidate&&revision===ND.consRevision&&ND.consensoEditavel;
 }
 function localBox(bounds){
  if(!ND.geo||!bounds||bounds.length!==2)return null;
  var low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
  for(var i=0;i<8;i++){
   var point=[bounds[i&1?1:0][0]+(i&1?10:-10),bounds[i&2?1:0][1]+(i&2?10:-10),bounds[i&4?1:0][2]+(i&4?10:-10)];
   var normalized=ndM4(ND.geo.para_caixa,point);
   normalized.forEach(function(v,axis){low[axis]=Math.min(low[axis],v);high[axis]=Math.max(high[axis],v)});
  }
  return [0,1,2].reduce(function(result,axis){return result.concat([Math.max(0,low[axis]),Math.min(1,high[axis])])},[]);
 }
 async function mesh(){
  if(!ND.consensoEditavel||!ND.consCandidate||!ND.sessao||!ND3.gl)return;
  var session=ND.sessao,candidate=ND.consCandidate,revision=ND.consRevision,sequence=++meshSequence;
  try{
   var data=await ndConsPost('/malha',{s:session,candidate:candidate,revision:revision});
   if(sequence!==meshSequence||!same(session,candidate,revision))return;
   if(data.empty){clearMesh();return}
   if(data.coordinate_system!=='LPS_mm'||!data.url)throw Error('Não foi possível montar a visualização 3D dentro do limite.');
   var response=await fetch(data.url,{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
   var bytes=await response.arrayBuffer();
   if(sequence!==meshSequence||!same(session,candidate,revision))return;
   var object=r3gSubirEm(ND3,r3gLerStl(bytes),[255,36,59]);
   if(ND3.consensusObj)r3gSoltarObj(ND3,ND3.consensusObj);
   ND3.consensusObj=object;ND3.consensusSession=session;ND3.consensusCandidate=candidate;ND3.consensusRevision=revision;
   ND3.consensusBox=localBox(data.bounds_lps);nd3Malhas();nd3Pedir();
  }catch(error){
   if(sequence!==meshSequence||!same(session,candidate,revision))return;
   clearMesh();ndMsg(String(error.message||error),'erro');
  }
 }
 function scheduleMesh(){
  clearTimeout(meshTimer);meshTimer=setTimeout(mesh,40);
 }
 var oldPost=ndConsPost;
 ndConsPost=async function(path,payload){
  var response=await oldPost.apply(this,arguments);
  if(payload&&payload.s===ND.sessao&&response&&response.candidate!=null&&response.revision!=null&&path!=='/malha'){
   ND.consSession=payload.s;ND.consCandidate=response.candidate;ND.consRevision=response.revision;
   ND.consUndo=!!response.undo_available;scheduleMesh();
  }
  return response;
 };
 function refresh(){
  if(ND.consSession&&ND.consSession!==ND.sessao){
   ND.consSession=null;ND.consCandidate=null;ND.consRevision=null;ND.consUndo=false;clearMesh();
  }
  if(!ND.consensoEditavel&&ND3.consensusObj)clearMesh();
  if(toolbar)toolbar.refresh();
 }
 var oldLocks=ndTravas,oldControls=ndConsControles;
 ndTravas=function(){oldLocks.apply(this,arguments);refresh()};
 ndConsControles=function(){oldControls.apply(this,arguments);refresh()};
 var oldAvailable=ndPodeDesenhar;
 ndPodeDesenhar=function(){return oldAvailable()&&(!toolbar||ND.tool==='pencil'||ND.tool==='brush'||ND.tool==='eraser')};
 var oldMove=ndQuerMover;
 ndQuerMover=function(event){return oldMove(event)||!!(toolbar&&ND.tool==='pan'&&event.button===0)};
 var oldOpen=ndAbrirSerie;
 ndAbrirSerie=function(){clearMesh();clearEditorMeshes();resetViews();ND.consSession=null;ND.consCandidate=null;ND.consRevision=null;ND.consUndo=false;return oldOpen.apply(this,arguments)};
 var oldUndo=ndConsDesfazer;
 ndConsDesfazer=async function(){
  if(!ND.consCandidate||!ND.consSession)return oldUndo.apply(this,arguments);
  if(!ND.consensoEditavel||ND.consensoBusy)return;
  var session=ND.sessao;ND.consensoBusy=true;ndConsControles();
  try{await ndConsPost('/pincel/desfazer',{s:session,candidate:ND.consCandidate,revision:ND.consRevision});
   if(session===ND.sessao)[0,1,2].forEach(ndLinhas);
  }catch(error){if(session===ND.sessao)ndMsg(String(error.message||error),'erro')}
  finally{ND.consensoBusy=false;ndConsControles()}
 };
 function brush(){return ND.tool==='brush'||ND.tool==='eraser'}
 function radii(axis,svg){
  var axes=axis===0?[2,1]:axis===1?[2,0]:[1,0],matrix=ND.geo&&ND.geo.da_caixa,vb=svg.viewBox.baseVal;
  if(!matrix)return [4,4];
  return axes.map(function(d,index){var mm=Math.hypot(matrix[d],matrix[4+d],matrix[8+d]);
   return ND.brushDiameter*.5*(index===0?vb.width:vb.height)/Math.max(mm,.001)});
 }
 function cursor(axis,point){
  var svg=ndEl('nd_ed'+axis),vb=svg.viewBox.baseVal,r=radii(axis,svg);
  var old=svg.querySelector('.nd-brush-cursor');if(old)old.remove();
  var circle=document.createElementNS('http://www.w3.org/2000/svg','ellipse');circle.classList.add('nd-brush-cursor');
  circle.setAttribute('cx',point[0]*vb.width);circle.setAttribute('cy',point[1]*vb.height);
  circle.setAttribute('rx',r[0]);circle.setAttribute('ry',r[1]);circle.setAttribute('fill','none');
  circle.setAttribute('stroke',ND.tool==='eraser'?'#f4b861':'#ff243b');circle.setAttribute('stroke-width','1.5');
  circle.setAttribute('vector-effect','non-scaling-stroke');circle.style.pointerEvents='none';svg.appendChild(circle);
 }
 var oldStart=ndEditStart,oldMotion=ndEditMove,oldEnd=ndEditEnd;
 ndEditStart=function(axis,event){
  if(!toolbar||ND.tool==='pencil')return oldStart.apply(this,arguments);
  if(!brush()||!ndDisponivel()||ND.corteBusy[axis]||ND.consensoBusy||!ND.consensoEditavel||event.button!==0||!ND.consCandidate)return;
  var index=Math.round(ND.planos[axis]*(ND.forma[axis]-1));if(ND.consIndices[axis]!==index)return;
  var svg=ndEl('nd_ed'+axis);event.preventDefault();if(svg.setPointerCapture)svg.setPointerCapture(event.pointerId);
  ND.consTrace={axis:axis,index:index,points:[ndEditPoint(svg,event)],session:ND.sessao,
   brush:true,operation:ND.tool==='eraser'?'remove':'add',radius:ND.brushDiameter/2,candidate:ND.consCandidate,revision:ND.consRevision};
  ndEditPaint(ND.consTrace);cursor(axis,ND.consTrace.points[0]);
 };
 ndEditMove=function(axis,event){
  if(!brush())return oldMotion.apply(this,arguments);
  var point=ndEditPoint(ndEl('nd_ed'+axis),event);lastPoint={axis:axis,point:point};
  var trace=ND.consTrace;
  if(trace&&trace.brush&&trace.axis===axis){
   var last=trace.points[trace.points.length-1];
   if(Math.hypot(point[0]-last[0],point[1]-last[1])>.001){
    if(trace.points.length===256)trace.points=trace.points.filter(function(_,i){return i%2===0});
    trace.points.push(point);ndEditPaint(trace);
   }
  }
  if(ND.consensoEditavel)cursor(axis,point);
 };
 ndEditEnd=async function(axis,event){
  var trace=ND.consTrace;if(!trace||!trace.brush)return oldEnd.apply(this,arguments);
  if(trace.axis!==axis)return;ND.consTrace=null;
  ndEl('nd_ed'+axis).innerHTML='<rect width="100%" height="100%" fill="transparent"/>';
  if(!same(trace.session,trace.candidate,trace.revision))return;
  ND.consensoBusy=true;ndConsControles();
  try{await ndConsPost('/pincel',{s:trace.session,candidate:trace.candidate,revision:trace.revision,
   eixo:trace.axis,indice:trace.index,pontos:trace.points,operacao:trace.operation,raio_mm:trace.radius});
   if(trace.session===ND.sessao)[0,1,2].forEach(ndLinhas);
  }catch(error){if(trace.session===ND.sessao)ndMsg(String(error.message||error),'erro')}
  finally{ND.consensoBusy=false;ndConsControles()}
 };
 function clearEditorMeshes(){
  (ND3.editorObjs||[]).forEach(function(object){r3gSoltarObj(ND3,object)});
  ND3.editorObjs=[];ND3.editorCache=new Map();ND3.editorBox=null;ND3.editorReference=null;ND3.editorSession=null;ND3.editorRevision=null;ND3.editorCenter=null;
 }
 function editorMesh(mesh){
  if(mesh.coordinate_system!=='LPS_mm'||!Array.isArray(mesh.vertices)||!Array.isArray(mesh.faces))throw Error('Geometria 3D inválida.');
  var p=new Float32Array(mesh.vertices.flat()),idx=new Uint32Array(mesh.faces.flat()),normals=new Float32Array(p.length),low=[Infinity,Infinity,Infinity],high=[-Infinity,-Infinity,-Infinity];
  if(p.length>1500000||idx.length>1500000||p.length%3||idx.length%3)throw Error('Geometria 3D inválida.');
  for(var i=0;i<p.length;i++){if(!Number.isFinite(p[i]))throw Error('Geometria 3D inválida.');var axis=i%3;low[axis]=Math.min(low[axis],p[i]);high[axis]=Math.max(high[axis],p[i])}
  for(var i=0;i<idx.length;i+=3){
   var a=idx[i]*3,b=idx[i+1]*3,c=idx[i+2]*3;if(Math.max(a,b,c)>=p.length)throw Error('Geometria 3D inválida.');
   var u=[p[b]-p[a],p[b+1]-p[a+1],p[b+2]-p[a+2]],v=[p[c]-p[a],p[c+1]-p[a+1],p[c+2]-p[a+2]],n=nd3Cruz(u,v);
   [a,b,c].forEach(function(offset){for(var k=0;k<3;k++)normals[offset+k]+=n[k]});
  }
  for(var i=0;i<normals.length;i+=3){var length=Math.hypot(normals[i],normals[i+1],normals[i+2])||1;normals[i]/=length;normals[i+1]/=length;normals[i+2]/=length}
  return {mesh:{pos:p,nrm:normals,idx:idx,nv:p.length/3,T:idx.length/3,centro:low.map(function(v,i){return(v+high[i])/2})},bounds:[low,high]};
 }
 function editorPreview(data,b,source,load){
  if(b!==ND.b||load!==ND.carga||!data.reference||data.reference.b!==b||data.reference.source!==source||!ND3.gl)return;
  if(!ND.identity||!ND.identity.uid||!ND.identity.frame_uid||data.reference.uid!==ND.identity.uid||data.reference.frame_uid!==ND.identity.frame_uid)return;
  if(ND3.editorSession===data.session&&Number(data.revision)<ND3.editorRevision)return;
  var previous=ND3.editorSession===data.session?(ND3.editorCache||new Map()):new Map(),next=new Map(),objects=[],created=[],bounds=null;
  try{(data.meshes||[]).forEach(function(row){
   if(!(row.faces||[]).length)return;
   var key=String(row.roi),revision=row.geometry_revision===undefined?data.revision:row.geometry_revision,cached=previous.get(key);
   if(!cached||cached.revision!==revision){
    var built=editorMesh(row),object=r3gSubirEm(ND3,built.mesh,row.color||[255,36,59]);
    cached={revision:revision,object:object,bounds:built.bounds};created.push(object);
   }
   next.set(key,cached);objects.push(cached.object);cached.object.cor=row.color||[255,36,59];
   if(!bounds)bounds=cached.bounds.map(function(v){return v.slice()});else [0,1,2].forEach(function(i){bounds[0][i]=Math.min(bounds[0][i],cached.bounds[0][i]);bounds[1][i]=Math.max(bounds[1][i],cached.bounds[1][i])});
  })}catch(error){created.forEach(function(object){r3gSoltarObj(ND3,object)});throw error}
  (ND3.editorObjs||[]).forEach(function(object){if(objects.indexOf(object)<0)r3gSoltarObj(ND3,object)});
  if(ND3.editorReference!==b)ND3.editorCenter=null;
  ND3.editorCache=next;ND3.editorObjs=objects;ND3.editorBox=localBox(bounds);ND3.editorReference=b;ND3.editorSession=data.session;ND3.editorRevision=Number(data.revision);
  nd3Malhas();nd3Pedir();
 }
 var oldCrop=nd3RecorteLocal;
 nd3RecorteLocal=function(){
  var current=oldCrop();
  var extra=ND3.editorReference===ND.b&&ND3.editorBox;if(!extra)return current;if(!current)return extra;
  return current.map(function(value,index){return index%2?Math.max(value,extra[index]):Math.min(value,extra[index])});
 };
 var oldBox=nd3Caixa;
 nd3Caixa=function(){var result=oldBox();if(result&&ND3.editorReference===ND.b&&ND3.editorCenter)result.centro=ND3.editorCenter.slice();return result};
 function restoreEditor(){
  ND.inlineEditorActive=false;
  editorHidden.forEach(function(state){state.node.hidden=state.hidden});editorHidden=[];if(editorRoot)editorRoot.hidden=true;
  ndAjustarTela();nd3Pedir();
 }
 async function editor(tool){
  if(!window.RadaiContourEditor||!ND.b)return;
  var b=ND.b,load=ND.carga,source=ND.ultima&&ND.ultima.origem==='acervo'?'archive':'thumbnail';
  if(!editorRoot){editorRoot=document.createElement('section');editorRoot.id='nd_inline_editor';ndEl('nd_trabalho').after(editorRoot)}
  editorRoot.hidden=false;ND.inlineEditorActive=true;
  editorHidden=['nd_trabalho','nd_actionbar','nd_cmd','nd_msg','nd_serie_cx'].map(function(id){var node=ndEl(id);if(!node)return null;var state={node:node,hidden:node.hidden};node.hidden=true;return state}).filter(Boolean);
  nd3Vista('3d');
  try{await window.RadaiContourEditor.open({b:b,source:source,
   rs:'',inlineRoot:editorRoot,returnLabel:'NIDUS RT',tool:tool||'brush',
   externalScene:{element:ndEl('nd_palco3d'),request:nd3Pedir,resize:nd3Pedir,center:function(point){
    if(b!==ND.b||load!==ND.carga||!Array.isArray(point)||point.length!==3)return;
    ND3.editorCenter=point.slice();var normalized=ndM4(ND.geo.para_caixa,point);
    [0,1,2].forEach(function(axis){var n=ND.forma[axis];ND.planos[axis]=n>1?Math.max(0,Math.min(1,(normalized[axis]*n-.5)/(n-1))):0;ndEl('nd_pos'+axis).value=String(ND.planos[axis]*100);ndCorte(axis);ndLinhas(axis)});nd3Pedir();
   }},onPreview:function(data){editorPreview(data,b,source,load)},onClose:function(){restoreEditor()}});
  }catch(error){restoreEditor();ndMsg(String(error.message||error),'erro')}
 }
 window.NidusBrush={refresh:refresh,clear:clearMesh,mesh:mesh,localBox:localBox,editorPreview:editorPreview,getToolbar:function(){return toolbar},views:mprViews,activeAxis:function(){return activeAxis}};
 window.addEventListener('DOMContentLoaded',function(){
  if(!window.RadaiDicomToolbar)return;
  [0,1,2].forEach(installMprView);
  ndEl('nd_palco').addEventListener('pointerenter',function(){activeAxis=null});ndEl('nd_palco').addEventListener('focusin',function(){activeAxis=null});
  var host=document.createElement('div');host.id='nd_dicom_tools';host.style.flex='1 1 100%';ndEl('nd_actionbar').prepend(host);
  toolbar=window.RadaiDicomToolbar.mount(host,{scope:ndEl('nd_trabalho'),tool:'pencil',diameter:5,
   tools:['pointer','pencil','brush','eraser','pan','measure','window','zoomIn','zoomOut','fit','undo','editor'],
   enabled:function(key){
    if(!ndDisponivel()||ND.consensoBusy||ND.consTrace)return false;
    if(key==='measure'||key==='window'||key==='editor')return !!window.RadaiContourEditor;
    if(key==='brush'||key==='eraser')return true;
    if(key==='undo')return ND.consensoEditavel&&ND.consUndo;
    return true;
   },
   onTool:async function(key){
    ND.tool=key;
    if(key==='measure'||key==='window'){await editor(key);ND.tool='pointer';toolbar.setTool('pointer');return}
    if((key==='brush'||key==='eraser')&&activeAxis!==null&&ND.sessao&&!ND.consensoEditavel)await ndEditarConsenso();
    ndTravas();ndConsControles();
   },
   onAction:function(key){
    if(key==='zoomIn'||key==='zoomOut'){
     if(activeAxis===null)ndZoomPasso(key==='zoomIn'?1:-1);else zoomView(activeAxis,key==='zoomIn'?1.25:1/1.25);
    }else if(key==='fit'){
     if(activeAxis===null)ndZoomAjustar();else{var view=mprViews[activeAxis];view.scale=1;view.x=0;view.y=0;paintView(activeAxis)}
    }else if(key==='undo')ndConsDesfazer();else if(key==='editor')editor('brush');
   },
   onDiameter:function(mm){ND.brushDiameter=mm;if(lastPoint&&ND.consensoEditavel)cursor(lastPoint.axis,lastPoint.point)}
  });
  ['nd_cons_add','nd_cons_remove','nd_cons_undo','nd_zoom_mais','nd_zoom_menos','nd_zoom_ajustar'].forEach(function(id){var old=ndEl(id);if(old)old.style.display='none'});
  ndAjustarTela();refresh();
 });
})();
"""
