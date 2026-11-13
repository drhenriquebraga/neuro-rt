"""Explicit folder loading: unique original TOF plus same-study temporal inventory."""

NIDUS_FOLDER_JS = r"""
(function(){
 'use strict';
 var pending=null,request=0;
 function candidates(rows,metadata){
  var byTicket=new Map((rows||[]).map(function(row){return[row.bilhete,row]}));
  return (metadata&&metadata.itens||[]).filter(function(item){
   return item.preferida&&item.original&&item.tridimensional&&item.possivel_tof&&byTicket.has(item.bilhete);
  }).map(function(item){return byTicket.get(item.bilhete)});
 }
 async function inventory(series,selection){
  var generation=++request,load=ND.carga,anchor={bilhete:series.bilhete,origem:series.origem||'pasta'};
  if(window.NidusTemporal&&window.NidusTemporal.offerGroups)window.NidusTemporal.offerGroups([],[],anchor);
  try{
   var response=await fetch('/api/nidus/temporal/folder-discover',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({ancora:anchor,itens:selection.rows.slice(0,128).map(function(row){return{bilhete:row.bilhete,origem:'pasta'}})})});
   if(!response.ok)return;var data=await response.json();
   if(generation!==request||load!==ND.carga||anchor.bilhete!==ND.b)return;
   if(window.NidusTemporal&&window.NidusTemporal.offerGroups)
    window.NidusTemporal.offerGroups(data.groups||[],selection.rows,anchor);
  }catch(error){/* Series loading remains usable when temporal inventory fails. */}
 }
 var oldOpen=ndAbrirSerie;
 ndAbrirSerie=function(series){
  var result=oldOpen.apply(this,arguments),selection=pending;
  if(series&&selection&&series.origem==='pasta'&&selection.rows.some(function(row){return row.bilhete===series.bilhete}))
   inventory(series,selection);
  return result;
 };
 window.NidusFolder={candidates:candidates,discovered:function(rows,metadata,path,automatic){
  request++;pending={rows:(rows||[]).filter(function(row){return row&&row.bilhete&&!row.carregando}),path:path};
  if(!automatic||!ND.escolhendo)return;
  var eligible=candidates(pending.rows,metadata);
  var inspected=new Set((metadata&&metadata.itens||[]).map(function(item){return item.bilhete}));
  var complete=pending.rows.every(function(row){return inspected.has(row.bilhete)});
  if(eligible.length===1&&complete){
   var row=eligible[0];ndAbrirSerie({bilhete:row.bilhete,origem:'pasta',modalidade:row.modalidade||'MR',
    desc:row.desc||'',rotulo:ndRotuloDaLista(row)});return;
  }
  var note=ndEl('nd_tof_sugestao');
  if(note)ndFrases(note,[eligible.length>1?'Mais de uma série TOF original foi encontrada. Escolha a referência.':
    'Escolha a série de referência. As sequências temporais do mesmo exame serão identificadas.']);
 }};
})();
"""
