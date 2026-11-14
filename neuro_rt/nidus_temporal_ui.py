"""Acquired-phase angiography viewer, deliberately separate from NIDUS contours."""

NIDUS_TEMPORAL_JS = r"""
(function(){
 'use strict';
 var C={rows:new Map(),picking:false,active:false,generation:0,job:null,group:null,
        frames:[],ready:false,playing:false,index:0,timer:null,angleTimer:null,
        lao:0,cra:0,cache:null,dialog:null,hidden:[],speed:1,zoom:1};
 var el=function(id){return document.getElementById(id)};
 var text=function(node,value){ndTexto(node,value)};
 var label=function(tag,value){var n=document.createElement(tag);n.setAttribute('data-radai-frase','');n.textContent=value;return n};
 function button(value,action){var b=label('button',value);b.type='button';b.className='nd-bt';b.onclick=action;return b}
 function cancelJob(job){if(job)fetch('/api/nidus/temporal/cancel/'+encodeURIComponent(job),{method:'POST',keepalive:true}).catch(function(){})}
 async function api(path,body){
  var response=await fetch('/api/nidus/temporal/'+path,body===undefined?{cache:'no-store'}:
   {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  var data=await response.json();
  if(!response.ok || data.error)throw Error(data.error&&data.error.message||'Não foi possível preparar o CINE.');
  return data;
 }
 function status(message){text(el('nd_cine_status'),message)}
 function pause(){C.playing=false;clearTimeout(C.timer);C.timer=null;if(el('nd_cine_play'))text(el('nd_cine_play'),'Reproduzir')}
 function invalidate(){pause();clearTimeout(C.angleTimer);C.generation++;if(!C.ready)cancelJob(C.job);C.job=null;C.ready=false;C.frames=[];
  if(C.dialog){var dialog=C.dialog;C.dialog=null;dialog.finish()}
  if(C.cache)C.cache.reset();controls();return C.generation;
 }
 function controls(){
  if(!el('nd_cine_play'))return;
  el('nd_cine_play').disabled=!C.ready;el('nd_cine_slider').disabled=!C.ready;
  var rotate=!!(C.group&&C.group.can_rotate);
  el('nd_cine_angles').hidden=!rotate;
  el('nd_cine_presets').hidden=!rotate;
 }
 function enter(){
  if(C.active)return;C.active=true;ND.cineActive=true;
  C.hidden=['nd_trabalho','nd_actionbar','nd_cmd','nd_msg','nd_serie_cx'].map(function(id){var node=el(id);if(!node)return null;
   var record={node:node,hidden:node.hidden};node.hidden=true;return record}).filter(Boolean);
  el('nd_cine_panel').hidden=false;C.lao=ND.lao||0;C.cra=ND.cra||0;C.zoom=1;el('nd_cine_canvas').style.transform='';
  if(!C.cache)C.cache=new NidusImageCache({maxBytes:512*1024*1024,maxEntries:64});
  el('nd_cine_lao').value=C.lao;el('nd_cine_cra').value=C.cra;
  status('Escolher série temporal');controls();
 }
 function leave(){
  invalidate();C.active=false;ND.cineActive=false;C.group=null;
  el('nd_cine_panel').hidden=true;C.hidden.forEach(function(s){s.node.hidden=s.hidden});C.hidden=[];
  ndTravas();ndConsControles();ndAjustarTela();el('nd_cine_open').focus();
 }
 function display(index){
  if(!C.ready || !C.frames[index])return false;
  var entry=C.cache.get(C.frames[index].url);if(!entry){pause();C.ready=false;controls();status('Não foi possível preparar o CINE.');return false}
  C.index=index;var canvas=el('nd_cine_canvas');
  if(canvas.width!==entry.width)canvas.width=entry.width;if(canvas.height!==entry.height)canvas.height=entry.height;
  canvas.getContext('2d').drawImage(entry.image,0,0);el('nd_cine_slider').value=String(index);
  text(el('nd_cine_phase'),'Fase');el('nd_cine_index').textContent=(index+1)+' / '+C.frames.length;
  var seconds=C.frames[index].time_seconds;
  el('nd_cine_time').textContent=seconds==null?'':new Intl.NumberFormat(document.documentElement.lang||'pt-BR',{maximumFractionDigits:3}).format(seconds)+' s';
  return true;
 }
 function delay(index){
  var frames=C.frames, current=frames[index], next=frames[index+1], dt=null;
  if(current && next && current.time_seconds!=null && next.time_seconds!=null)dt=next.time_seconds-current.time_seconds;
  if(!(dt>0) && frames.length>1){var last=frames[frames.length-1], prior=frames[frames.length-2];
   if(last.time_seconds!=null && prior.time_seconds!=null)dt=last.time_seconds-prior.time_seconds}
  return Math.max(20,(dt>0?dt*1000:200)/C.speed);
 }
 function schedule(){
  if(!C.playing)return;
  C.timer=setTimeout(function(){
   if(!C.playing||!C.active||!C.ready)return;
   var next=C.index+1;if(next>=C.frames.length){if(!el('nd_cine_loop').checked){pause();return}next=0}
   if(display(next))schedule();
  },delay(C.index));
 }
 function play(){if(C.playing){pause();return}if(!C.ready)return;
  if(C.index===C.frames.length-1)display(0);C.playing=true;text(el('nd_cine_play'),'Pausar');schedule()}
 function angle(axis,value){
  if(!C.active||!C.group||!C.group.can_rotate)return;
  C[axis]=Math.max(axis==='lao'?-180:-90,Math.min(axis==='lao'?180:90,Number(value)||0));
  el('nd_cine_'+axis).value=C[axis];pause();clearTimeout(C.angleTimer);
  C.angleTimer=setTimeout(prepare,180);
 }
 function wheel(event){
  if(!C.active || !C.group || !event.deltaY)return;
  if(event.ctrlKey){event.preventDefault();C.zoom=Math.max(1,Math.min(8,C.zoom*(event.deltaY<0?1.15:1/1.15)));
   el('nd_cine_canvas').style.transform='scale('+C.zoom+')';return}
  if(!C.group.can_rotate)return;
  event.preventDefault();var axis=event.shiftKey?'cra':'lao';angle(axis,C[axis]+(event.deltaY>0?5:-5));
 }
 async function prepare(){
  if(!C.group||!C.active)return;
  var group=C.group, generation=invalidate(), current=function(){return C.active&&C.generation===generation};
  var dialog=new NidusOpeningDialog({roots:[el('nd_wrap')],title:'CINE de enchimento',
   onCancel:function(){if(current()){invalidate();status('Preparo cancelado.')}}});
  C.dialog=dialog;dialog.step('Preparando fases…');status('Preparando fases…');
  try{
   var canvas=el('nd_cine_canvas');canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
   var started=await api('prepare',{group:group.id,lao:group.can_rotate?C.lao:0,cra:group.can_rotate?C.cra:0,modo:'mip',janela:'angio',lado:1024,laje:null,caixa:null});
   if(!current()){cancelJob(started.job);return}C.job=started.job;
   var result;
   while(current()){
    result=await api('status/'+encodeURIComponent(C.job));if(!current())return;
    if(result.state==='failed')throw Error(result.error&&result.error.message||'Não foi possível preparar o CINE.');
    if(result.state==='cancelled')throw Error('Preparo cancelado.');
    dialog.step('Preparando fases…',result.completed,result.total);
    if(result.state==='ready')break;
    await new Promise(function(resolve){setTimeout(resolve,450)});
   }
   if(!current())return;
   var frames=result.frames.map(function(frame){return {index:frame.index,time_seconds:frame.time_seconds,
    url:'/api/nidus/temporal/frame/'+encodeURIComponent(C.job)+'/'+frame.index}});
   if(frames.length<2||frames.length>64)throw Error('Não foi possível preparar o CINE.');
   await C.cache.warm(frames.map(function(frame){return frame.url}),{signal:dialog.signal,
    onProgress:function(done,total){if(current())dialog.step('Preparando a reprodução…',done,total)}});
   if(!current())return;
   if(frames.some(function(frame){return !C.cache.get(frame.url)}))throw Error('Não foi possível preparar o CINE.');
   C.frames=frames;C.ready=true;el('nd_cine_slider').max=String(frames.length-1);controls();display(0);
   text(el('nd_cine_timing'),group.timing_known?'Intervalos adquiridos':'Intervalo temporal não informado');
   status(group.can_rotate?'Todas as fases prontas.':'CINE de projeções 2D — rotação indisponível.');
   C.dialog=null;dialog.finish();el('nd_cine_play').focus();
  }catch(error){
   if(!current())return;
   cancelJob(C.job);C.job=null;C.ready=false;controls();status(error.message||'Não foi possível preparar o CINE.');
   C.dialog=null;dialog.finish();
  }
 }
 function groupList(groups,sourceFor){
  var box=document.createElement('div');box.className='nd-cine-group-list';
  var modal=uiModal({titulo:'Fases adquiridas',no:box,origem:el(C.active?'nd_cine_choose':'nd_cine_open'),largura:560});
  groups.forEach(function(group,index){
   var row=document.createElement('div');row.style.cssText='display:flex;gap:12px;align-items:center;margin:12px 0';
   var desc=document.createElement('span');desc.textContent=(sourceFor?sourceFor(group):(index+1))+' · '+group.count+' · '+(group.kind==='volume3d'?'3D':'2D');
   desc.setAttribute('translate','no');desc.style.flex='1';
   row.append(desc,button('Abrir CINE',function(){
    modal.fechar();if(sourceFor){C.source=sourceFor(group);enter();el('nd_cine_source').textContent=C.source}
    C.group=group;prepare();
   }));box.appendChild(row);
  });if(window.radaiRetraduzir)window.radaiRetraduzir();
 }
 async function discover(anchor){
  enter();el('nd_cine_source').textContent=C.source||'';var generation=invalidate(),current=function(){return C.active&&C.generation===generation};
  var dialog=new NidusOpeningDialog({roots:[el('nd_wrap')],title:'CINE de enchimento',onCancel:function(){if(current()){invalidate();status('Preparo cancelado.')}}});
  C.dialog=dialog;dialog.step('Procurando fases adquiridas…');
  try{
   var rows=Array.from(C.rows.values()).filter(function(row){return row.origem===anchor.origem&&row.bilhete!==anchor.bilhete});rows.unshift(anchor);
   var result=await api('discover',{itens:rows.slice(0,128),ancora:anchor});if(!current())return;
   C.dialog=null;dialog.finish();
   if(!result.groups.length){status('Nenhuma sequência temporal compatível foi encontrada.');
    var note=label('p','TOF e 3SLAB são aquisições estáticas. Selecione uma sequência temporal adquirida, como TRICKS ou TWIST.');
    uiModal({titulo:'CINE de enchimento',no:note,largura:540});return}
   if(result.groups.length===1){C.group=result.groups[0];prepare()}else groupList(result.groups);
  }catch(error){if(!current())return;C.dialog=null;dialog.finish();status(error.message||'Não foi possível preparar o CINE.')}
 }
 var oldSeries=ndSeries;
 ndSeries=function(rows,origin){Array.from(C.rows.keys()).forEach(function(key){if(key.indexOf(origin+':')===0)C.rows.delete(key)});(rows||[]).forEach(function(row){if(row&&row.bilhete&&!row.carregando){
  C.rows.set(origin+':'+row.bilhete,{bilhete:row.bilhete,origem:origin});
  if(C.rows.size>512)C.rows.delete(C.rows.keys().next().value)}});return oldSeries.apply(this,arguments)};
 var originalMin=ND_MIN_CORTES, oldPopup=ndPopup;
 ndPopup=function(){var popup=oldPopup();uiPopupSerie('nd_escolha',{aoFechar:function(){ND.escolhendo=false;C.picking=false;ND_MIN_CORTES=originalMin}});return popup};
 var oldOpen=ndAbrirSerie;
 ndAbrirSerie=function(series){
  if(C.picking){var anchor={bilhete:series.bilhete,origem:series.origem||'pasta'};C.source=String(series.rotulo||series.desc||'');ndPopup().fechar();discover(anchor);return}
  if(C.active)leave();return oldOpen.apply(this,arguments);
 };
 function sourceLabel(offer,group){
  var labels=(group.series_tickets||[]).map(function(ticket){var row=offer.rows.find(function(r){return r.bilhete===ticket.bilhete});
   return row&&(row.desc||row.curto||row.rotulo)}).filter(Boolean);
  return Array.from(new Set(labels)).join(' · ')||group.label||'CINE';
 }
 async function choose(force){
  var offer=C.folderOffers;
  if(force!==true&&ND.b&&ND.ultima){
   var anchor={bilhete:ND.b,origem:ND.ultima.origem||'pasta'},reference=ND.b,load=ND.carga;
   enter();var generation=invalidate(),dialog=new NidusOpeningDialog({roots:[el('nd_wrap')],title:'CINE de enchimento',
    onCancel:function(){if(C.generation===generation){invalidate();status('Preparo cancelado.')}}});C.dialog=dialog;
   dialog.step('Procurando fases adquiridas…');
   try{
    if(!offer||offer.anchor.bilhete!==reference||offer.anchor.origem!==anchor.origem||!offer.groups.length){
     var rows=Array.from(C.rows.values()).concat(Object.values(ND.porB||{}));
     offer=await window.NidusFolder.ensure(anchor,rows);
    }
    if(!C.active||C.generation!==generation||ND.b!==reference||ND.carga!==load)return;
    C.dialog=null;dialog.finish();
    if(offer.groups.length===1){C.group=offer.groups[0];C.source=sourceLabel(offer,C.group);el('nd_cine_source').textContent=C.source;prepare()}
    else if(offer.groups.length>1)groupList(offer.groups,function(group){return sourceLabel(offer,group)});
    else status('Nenhuma sequência temporal compatível foi encontrada.');
   }catch(error){if(C.generation===generation){C.dialog=null;dialog.finish();status(error.message||'Não foi possível preparar este grupo temporal.')}}
   return;
  }
  C.picking=true;ND_MIN_CORTES=1;ndAbrirEscolha();
 }
 var oldLocks=ndTravas;
 ndTravas=function(){oldLocks.apply(this,arguments);var b=el('nd_cine_open');if(b)b.disabled=!!ND.abrindo};
 window.NidusTemporal={choose:choose,leave:leave,play:play,wheel:wheel,state:C,
  offerGroups:function(groups,rows,anchor){C.folderOffers={groups:groups,rows:rows,anchor:anchor};
   var open=el('nd_cine_open');if(open){open.dataset.availableGroups=String(groups.length);
    open.title=(window.radaiFrase?window.radaiFrase('Fases adquiridas'):'Fases adquiridas')+' · '+groups.length;}
  }};
 window.addEventListener('pagehide',function(){cancelJob(C.job)});
 window.addEventListener('keydown',function(event){
  if(!C.active || event.key!=='Escape' || document.querySelector('.ui-modal:not(.saindo)'))return;
  event.preventDefault();event.stopImmediatePropagation();leave();
 },true);
 document.addEventListener('visibilitychange',function(){if(document.hidden)pause()});
 window.addEventListener('DOMContentLoaded',function(){
  var open=button('CINE de enchimento',choose);open.id='nd_cine_open';
  el('nd_jan').insertBefore(open,el('nd_jan').querySelector('[data-j="osso"]'));
  var panel=document.createElement('section');panel.id='nd_cine_panel';panel.className='nd-cx';panel.hidden=true;
  panel.innerHTML='<div class="nd-cine-head"><strong data-radai-frase>CINE de enchimento</strong><span id="nd_cine_status" role="status"></span><span class="nd-cine-flex"></span></div>'+
   '<div id="nd_cine_source" class="sub" translate="no" style="padding:0 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0"></div><div id="nd_cine_presets" class="nd-cine-controls"></div><div class="nd-cine-stage"><canvas id="nd_cine_canvas" width="1024" height="1024" role="img" aria-label="CINE"></canvas></div>'+
   '<div class="nd-cine-controls" id="nd_cine_controls"><span id="nd_cine_phase" data-radai-frase>Fase</span><b id="nd_cine_index"></b><span id="nd_cine_time"></span>'+
   '<input id="nd_cine_slider" type="range" min="0" max="1" step="1" value="0" aria-label="Fase" disabled>'+
   '<label><input id="nd_cine_loop" type="checkbox" checked> <span data-radai-frase>Loop</span></label>'+
   '<label><span data-radai-frase>Velocidade</span> <select id="nd_cine_speed"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option><option value="4">4×</option></select></label></div>'+
   '<div id="nd_cine_angles" class="nd-cine-controls"><label>LAO/RAO <input id="nd_cine_lao" type="number" min="-180" max="180" step="5" value="0"></label><label>CRA/CAU <input id="nd_cine_cra" type="number" min="-90" max="90" step="5" value="0"></label><span id="nd_cine_timing"></span></div>'+
   '<details><summary class="nd-bt">?</summary><p data-radai-frase>A velocidade de reprodução não altera os tempos adquiridos. Sem fases interpoladas.</p><p data-radai-frase>Referência do NIDUS preservada. O CINE não modifica nem exporta os contornos.</p></details>';
  el('nd_trabalho').before(panel);
  var head=panel.querySelector('.nd-cine-head'),pick=button('Escolher outra série',function(){choose(true)});pick.id='nd_cine_choose';head.append(pick,button('Voltar à referência',leave));
  var pb=button('Reproduzir',play);pb.id='nd_cine_play';el('nd_cine_controls').prepend(pb);
  ND_INCIDENCIAS.forEach(function(preset){el('nd_cine_presets').appendChild(button(preset[0],function(){C.lao=preset[1];C.cra=preset[2];el('nd_cine_lao').value=C.lao;el('nd_cine_cra').value=C.cra;prepare()}))});
  el('nd_cine_slider').oninput=function(){pause();display(Number(this.value))};
  el('nd_cine_speed').onchange=function(){C.speed=Number(this.value);if(C.playing){clearTimeout(C.timer);schedule()}};
  ['lao','cra'].forEach(function(axis){el('nd_cine_'+axis).onchange=function(){angle(axis,this.value)}});
  el('nd_cine_canvas').addEventListener('wheel',wheel,{passive:false});
  var style=document.createElement('style');style.textContent='#nd_cine_panel[hidden],.nd-cine-controls[hidden]{display:none!important}#nd_cmd[hidden],#nd_trabalho[hidden],#nd_actionbar[hidden],#nd_serie_cx[hidden]{display:none!important}.nd-cine-head,.nd-cine-controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:8px}.nd-cine-flex{flex:1}.nd-cine-stage{height:clamp(320px,62vh,950px);background:#000;display:flex;justify-content:center;overflow:hidden;border-radius:8px;margin:8px}.nd-cine-stage canvas{max-width:100%;max-height:100%;object-fit:contain;touch-action:none}.nd-cine-controls input[type=range]{flex:1;min-width:150px;accent-color:var(--accent)}.nd-cine-controls input[type=number]{width:88px}.nd-cine-controls select,.nd-cine-controls input[type=number]{background:var(--panel,#111827);color:inherit;border:1px solid var(--border,#334155);border-radius:6px;padding:6px}#nd_cine_status{font-size:.85em;color:var(--muted,#94a3b8)}#nd_cine_panel details{padding:4px 10px}';document.head.appendChild(style);
  controls();ndTravas();if(window.radaiRetraduzir)window.radaiRetraduzir();
 });
})();
"""
