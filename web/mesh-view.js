'use strict';
const params=new URLSearchParams(location.search),jobId=params.get('job');
const route=new URL(`api/jobs/${encodeURIComponent(jobId)}/views/`,new URL('./',location.href));
function r3El(id){return document.getElementById(id)}
function r3mVisiveis(){return Object.entries(R3G.objs).filter(([name])=>R3M.lig[name]).map(([name,obj])=>[obj,R3M.alfa[name]])}
async function start(){
 try{
  const script=document.createElement('script');script.src=new URL('renderer.js',route).href;
  await new Promise((resolve,reject)=>{script.onload=resolve;script.onerror=reject;document.head.append(script)});
  // Overrides limitados à conexão da cena; matemática e desenho são do host.
  window.r3El=id=>document.getElementById(id);
  window.r3mVisiveis=()=>Object.entries(R3G.objs).filter(([name])=>R3M.lig[name]).map(([name,obj])=>[obj,R3M.alfa[name]]);
  window.r3mRecuo=reason=>{R3G.gl=null;R3M.modo='nuvem';r3El('cvGL').hidden=true;r3El('cv3Db').hidden=true;r3El('cv3D').hidden=false;r3El('status').textContent=`3D em nuvem de pontos · ${reason}`;window.neuroCloud()};
  window.r3mIniciar=()=>location.reload();
  const response=await fetch(new URL('view.json',route));if(!response.ok)throw Error('Reconstrução indisponível');const scene=await response.json();
  let bounds=null;const parsed=[];
  for(const item of scene.meshes){const bytes=await (await fetch(new URL(item.path,route))).arrayBuffer();const mesh=r3gLerStl(bytes);parsed.push({item,mesh});
   bounds=bounds?bounds.map((b,i)=>b.map((v,j)=>i===0?Math.min(v,item.bounds[i][j]):Math.max(v,item.bounds[i][j]))):item.bounds;
   R3M.lig[item.name]=true;R3M.alfa[item.name]=item.opacity;
   const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=true;check.addEventListener('change',()=>{R3M.lig[item.name]=check.checked;if(R3G.gl)r3gPedir();else window.neuroCloud()});label.append(check,document.createTextNode(item.label));r3El('layers').append(label);
  }
  window.neuroCloud=()=>{const all=parsed.filter(p=>R3M.lig[p.item.name]);const center=bounds?bounds[0].map((v,i)=>(v+bounds[1][i])/2):[0,0,0];const items=all.map(({item,mesh})=>{const step=Math.max(1,Math.ceil(mesh.nv/4000)),points=[],normals=[];for(let i=0;i<mesh.nv;i+=step){points.push([mesh.pos[i*3]-center[0],mesh.pos[i*3+1]-center[1],mesh.pos[i*3+2]-center[2]]);normals.push([mesh.nrm[i*3],mesh.nrm[i*3+1],mesh.nrm[i*3+2]])}return{nome:item.label,pontos:points,normais:normals,cor:item.color,centro_mm:[0,0,0]}});n3Mostrar({itens:items,eixos:['esq','post','sup']},'Arraste para girar')};
  const reason=r3gDetectar();if(reason){window.r3mRecuo(reason)}else{R3M.modo='gl';r3gLigar(r3El('cvGL'));for(const {item,mesh} of parsed)r3gSubir(item.name,mesh,item.color);r3gCena(bounds);r3gPedir();r3El('status').textContent=scene.meshes.length?'Arraste para girar · roda para aproximar':'Máscara vazia; nenhuma superfície prevista'}
  for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>{if(R3G.gl){R3G.M=button.dataset.view==='inicial'?n3MatrizInicial(R3_EIXOS):n3MatrizDaVista(button.dataset.view,R3_EIXOS);R3G.zoom=1;r3gPedir()}else n3Vista(button.dataset.view)});
 }catch(error){r3El('status').textContent='Não foi possível montar o 3D. Reabra o resultado.'}
}
start();
