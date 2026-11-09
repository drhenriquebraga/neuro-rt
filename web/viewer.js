'use strict';
let neuroViewJob='',neuroViewMetadata=null;
const planeNames={axial:'Axial',sagittal:'Sagital',coronal:'Coronal'};
function promotePlane(name){
 const chosen=document.querySelector(`.plane[data-plane="${name}"]`);
 const current=document.querySelector('.main-views .main-plane');
 if(!chosen || !current || chosen===current)return;
 const placeholder=document.createComment('troca de plano');
 chosen.replaceWith(placeholder);current.replaceWith(chosen);placeholder.replaceWith(current);
 chosen.classList.add('main-plane');current.classList.remove('main-plane');
 updatePlaneButtons();
}
function updatePlaneButtons(){
 for(const card of document.querySelectorAll('.plane[data-plane]')){
  const name=card.dataset.plane,isMain=card.classList.contains('main-plane'),button=card.querySelector('.promote-plane');
  card.querySelector('h3').textContent=planeNames[name]+(isMain?' · segmentação':'');
  button.disabled=isMain;button.textContent=isMain?'Principal':'Ampliar';
  button.setAttribute('aria-label',isMain?`Plano ${planeNames[name].toLowerCase()} no visor principal`:`Mostrar plano ${planeNames[name].toLowerCase()} no visor principal`);
 }
}
for(const button of document.querySelectorAll('.promote-plane'))button.addEventListener('click',()=>promotePlane(button.closest('[data-plane]').dataset.plane));
function clearViewer(){
 promotePlane('axial');
 neuroViewJob='';neuroViewMetadata=null;
 document.getElementById('visualization').hidden=true;
 document.getElementById('mesh-frame').removeAttribute('src');
 for(const plane of ['axial','coronal','sagittal'])document.getElementById(`${plane}-image`).removeAttribute('src');
}
async function showViewer(job){
 if(neuroViewJob===job.id)return;
 const section=document.getElementById('visualization');
 const response=await fetch(new URL(`api/jobs/${job.id}/views/view.json`,base));
 if(activeJob!==job.id)return;
 if(!response.ok)throw Error('Não foi possível abrir os cortes da segmentação.');
 const metadata=await response.json();
 if(activeJob!==job.id)return;
 neuroViewMetadata=metadata;
 neuroViewJob=job.id;
 for(const plane of ['axial','coronal','sagittal']){
  const metadata=neuroViewMetadata.planes[plane],slider=document.getElementById(`${plane}-slice`);
  slider.min=0;slider.max=metadata.count-1;slider.value=metadata.center;
  const format=metadata.format==='svg'?'svg':'png';
  const update=()=>{const n=Number(slider.value);document.getElementById(`${plane}-position`).textContent=`${n+1} / ${metadata.count}`;document.getElementById(`${plane}-image`).src=new URL(`api/jobs/${job.id}/views/${plane}_${String(n).padStart(3,'0')}.${format}`,base).href};
  slider.oninput=update;update();
  document.getElementById(`${plane}-image`).onwheel=event=>{event.preventDefault();slider.value=Math.max(0,Math.min(metadata.count-1,Number(slider.value)+(event.deltaY>0?1:-1)));update()};
 }
 document.getElementById('mesh-frame').src=new URL(`mesh-view.html?job=${encodeURIComponent(job.id)}`,base).href;
 section.hidden=false;
}
