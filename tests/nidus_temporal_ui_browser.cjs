// Browser regression with synthetic API responses and the real UI/preload modules.
// Optional env: PLAYWRIGHT_MODULE, CHROME_EXECUTABLE, NIDUS_PROJECT_ROOT, NIDUS_TEST_OUTPUT.
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const os = require('node:os');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(process.argv[2] || process.env.NIDUS_PROJECT_ROOT || path.join(__dirname, '..'));
const output = path.resolve(process.env.NIDUS_TEST_OUTPUT || path.join(os.tmpdir(), 'nidus-temporal-browser-tests'));
fs.mkdirSync(output, {recursive:true});
function pythonJS(file, symbol) {
  const source = fs.readFileSync(path.join(root, 'neuro_rt', file), 'utf8');
  const marker = symbol + ' = r"""';
  const start = source.indexOf(marker) + marker.length;
  assert(start >= marker.length, 'JavaScript constant not found');
  return source.slice(start, source.indexOf('"""', start));
}
const mocks = `
window.ND={lao:45,cra:15,aberta:true,abrindo:false,escolhendo:false,
 guardadas:[{id:'reference-incidence'}],pontos:[[1,2],[3,4],[5,6]],chave:'reference',sessao:'static-session'};
window.ND_MIN_CORTES=8; window.ND_INCIDENCIAS=[['AP',0,0],['Perfil D',-90,0]];
window.__host={normalOpen:[],series:[],modals:[],errors:[],locks:0};
window.ndTexto=function(node,value){if(node)node.textContent=value};
window.uiTexto=window.ndTexto; window.radaiFrase=function(value){return value};
window.radaiRetraduzir=function(){};
window.ndSeries=function(rows,origin){__host.series.push({rows,origin})};
window.ndTravas=function(){__host.locks++}; window.ndConsControles=function(){};window.ndAjustarTela=function(){};
window.uiCarregando=function(art,active,label){art.dataset.active=String(active);art.textContent=label||''};
window.uiModal=function(options){
 const box=document.createElement('div');box.className='mock-modal';box.setAttribute('role','dialog');
 box.dataset.title=options.titulo||'';if(options.no)box.append(options.no);document.body.append(box);
 let closed=false;
 const modal={fechar(){if(closed)return;closed=true;box.remove();if(options.aoFechar)options.aoFechar()},box,options};
 __host.modals.push(modal);return modal;
};
window.__popupOptions={};window.__popupOpen=false;
window.uiPopupSerie=function(id,options){
 Object.assign(__popupOptions,options||{});
 return {abrir(){__popupOpen=true;if(__popupOptions.aoAbrir)__popupOptions.aoAbrir()},
 fechar(){if(!__popupOpen)return;__popupOpen=false;if(__popupOptions.aoFechar)__popupOptions.aoFechar()},
 aberto(){return __popupOpen}};
};
window.ndPopup=function(){return uiPopupSerie('nd_escolha',{aoAbrir(){ND.escolhendo=true},aoFechar(){ND.escolhendo=false}})};
window.ndAbrirEscolha=function(){ndPopup().abrir()};
window.ndAbrirSerie=function(series){__host.normalOpen.push(series);ndPopup().fechar()};
`;
function html() {
 return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><style>body{background:#09111e;color:white;font:14px Arial}#nd_wrap{width:1100px}.mock-modal{position:fixed;inset:20%;background:#14253b;z-index:100;padding:24px}</style></head><body><main id="nd_wrap"><div id="nd_cmd"><div id="nd_jan"><button data-j="osso">Anatomia</button></div></div><div id="nd_actionbar">actions</div><div id="nd_msg">static message</div><div id="nd_trabalho">static work area</div></main><script>${mocks}</script><script>${pythonJS('nidus_preload.py','NIDUS_PRELOAD_JS')}</script><script>${pythonJS('nidus_temporal_ui.py','NIDUS_TEMPORAL_JS')}</script></body></html>`;
}
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlZ8AAAAASUVORK5CYII=', 'base64');
function group(id='g1', kind='volume3d', timing=true) {
 return {id,kind,count:3,can_rotate:kind==='volume3d',timing_known:timing,
  frames:[0,.125,.375].map((t,index)=>({index,time_seconds:timing?t:null}))};
}
async function until(check){const limit=Date.now()+5000;while(!check()){if(Date.now()>limit)throw Error('Timed out waiting for harness state');await new Promise(r=>setTimeout(r,10))}}
async function fixture(browser, settings={}) {
 const page=await browser.newPage({viewport:{width:1280,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const calls=[];const releases=[];
 const state={groups:[group()],hold:null,holdCount:0,jobs:new Map(),nextJob:0,...settings};
 await page.route('http://nidus.test/**', async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.pathname==='/'){await route.fulfill({contentType:'text/html',body:html()});return}
  let body=null;try{body=request.postDataJSON()}catch{}
  calls.push({path:url.pathname,method:request.method(),body});
  const stage=url.pathname.split('/')[4];
  if(state.hold===stage && state.holdCount>0){state.holdCount--;await new Promise(resolve=>releases.push(resolve))}
  let data={},status=200;
  if(stage==='discover')data={groups:state.groups,rejected:[]};
  if(stage==='prepare'){
   const selected=state.groups.find(g=>g.id===body.group);
   if(!selected)data={error:{message:'Selecione novamente o grupo temporal.'}},status=422;
   else if(!selected.can_rotate&&(body.lao!==0||body.cra!==0))data={error:{message:'Parâmetros de reconstrução inválidos.'}},status=422;
   else {const job='job'+(++state.nextJob);state.jobs.set(job,selected);data={job,state:'queued'}}
  }
  if(stage==='status'){
   const job=url.pathname.split('/')[5],g=state.jobs.get(job);
   data={job,state:'ready',completed:6,total:6,frames:g.frames,can_rotate:g.can_rotate,timing_known:g.timing_known};
  }
  if(stage==='frame'){
   try{await route.fulfill({contentType:'image/png',body:png})}catch{}
   return;
  }
  if(stage==='cancel')data={state:'cancelled'};
  try{await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)})}catch{}
 });
 await page.goto('http://nidus.test/',{waitUntil:'networkidle'});
 await page.waitForSelector('#nd_cine_open');
 async function pick(ticket='chosen',origin='pasta',rows=[{bilhete:ticket}]) {
  await page.evaluate(({ticket,origin,rows})=>{ndSeries(rows,origin);NidusTemporal.choose();ndAbrirSerie({bilhete:ticket,origem:origin})},{ticket,origin,rows});
 }
 async function ready(){await page.waitForFunction(()=>NidusTemporal.state.ready,{},{timeout:5000})}
 return {page,state,calls,releases,errors,pick,ready,async close(){releases.splice(0).forEach(fn=>fn());await page.close()}};
}
const results=[];
async function test(browser,name,fn){
 let f;try{f=await fixture(browser);await fn(f);assert.deepEqual(f.errors,[]);results.push({name,status:'passed'})}
 catch(error){results.push({name,status:'failed',error:String(error.stack||error)})}
 finally{if(f)await f.close()}
}
(async()=>{
 const launch={headless:true};
 if(process.env.CHROME_EXECUTABLE)launch.executablePath=process.env.CHROME_EXECUTABLE;
 const browser=await chromium.launch(launch);
 try{
  await test(browser,'chooser cancellation restores normal selection and slice threshold',async f=>{
   await f.page.evaluate(()=>NidusTemporal.choose());
   assert.equal(await f.page.evaluate(()=>ND_MIN_CORTES),1);
   await f.page.evaluate(()=>ndPopup().fechar());
   assert.deepEqual(await f.page.evaluate(()=>[NidusTemporal.state.picking,ND_MIN_CORTES,ND.escolhendo]),[false,8,false]);
   await f.page.evaluate(()=>ndAbrirSerie({bilhete:'normal',origem:'pasta'}));
   assert.equal(await f.page.evaluate(()=>__host.normalOpen.length),1);
   assert.equal(f.calls.length,0);
   await f.pick();await f.ready();
   assert.equal(await f.page.evaluate(()=>__host.normalOpen.length),1);
  });
  await test(browser,'cine prepares all frames and preserves reference and restores workspace',async f=>{
   const before=await f.page.evaluate(()=>({guardadas:ND.guardadas,pontos:ND.pontos,chave:ND.chave,sessao:ND.sessao}));
   await f.pick();await f.ready();
   assert.equal(f.calls.filter(c=>c.path.includes('/frame/')).length,3);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_wrap').inert),false);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_trabalho').hidden),true);
   await f.page.evaluate(()=>NidusTemporal.leave());
   assert.deepEqual(await f.page.evaluate(()=>({guardadas:ND.guardadas,pontos:ND.pontos,chave:ND.chave,sessao:ND.sessao})),before);
   assert.deepEqual(await f.page.evaluate(()=>[document.getElementById('nd_trabalho').hidden,ND.cineActive,NidusTemporal.state.ready]),[false,false,false]);
  });
  await test(browser,'2D temporal projections send zero angles and disable rotation',async f=>{
   f.state.groups=[group('g2','projection2d')];await f.pick();await f.ready();
   const request=f.calls.find(c=>c.path.endsWith('/prepare')).body;
   assert.equal(request.lao,0);assert.equal(request.cra,0);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_cine_angles').hidden),true);
   const count=f.calls.length;await f.page.evaluate(()=>NidusTemporal.wheel({deltaY:1,preventDefault(){throw Error('2D rotation should be ignored')}}));
   assert.equal(f.calls.length,count);
  });
  await test(browser,'current chooser replaces stale rows and prioritizes selected anchor beyond128',async f=>{
   await f.page.evaluate(()=>ndSeries([{bilhete:'old'}],'pasta'));
   const rows=Array.from({length:200},(_,i)=>({bilhete:'row'+i}));
   await f.pick('row199','pasta',rows);await f.ready();
   const body=f.calls.find(c=>c.path.endsWith('/discover')).body;
   assert.equal(body.itens.length,128);assert.equal(body.itens[0].bilhete,'row199');
   assert(!body.itens.some(i=>i.bilhete==='old'));
  });
  await test(browser,'playback uses acquired intervals, loops cached frames and pauses at end',async f=>{
   await f.pick();await f.ready();const time=new Date('2026-11-12T12:00:00Z');await f.page.clock.install({time});await f.page.clock.pauseAt(time);
   const before=f.calls.length;await f.page.evaluate(()=>NidusTemporal.play());
   await f.page.clock.runFor(124);assert.equal(await f.page.evaluate(()=>NidusTemporal.state.index),0);
   await f.page.clock.runFor(1);assert.equal(await f.page.evaluate(()=>NidusTemporal.state.index),1);
   await f.page.clock.runFor(249);assert.equal(await f.page.evaluate(()=>NidusTemporal.state.index),1);
   await f.page.clock.runFor(1);assert.equal(await f.page.evaluate(()=>NidusTemporal.state.index),2);
   await f.page.clock.runFor(250);assert.equal(await f.page.evaluate(()=>NidusTemporal.state.index),0);
   await f.page.evaluate(()=>document.getElementById('nd_cine_loop').checked=false);
   await f.page.clock.runFor(625);
   assert.deepEqual(await f.page.evaluate(()=>[NidusTemporal.state.index,NidusTemporal.state.playing]),[2,false]);
   assert.equal(f.calls.length,before);
  });
  await test(browser,'cancel discovery ignores late response without recursive invalidation',async f=>{
   f.state.hold='discover';f.state.holdCount=1;await f.pick();
   await f.page.waitForFunction(()=>!!NidusTemporal.state.dialog);
   const before=await f.page.evaluate(()=>NidusTemporal.state.generation);
   await f.page.evaluate(()=>NidusTemporal.state.dialog.cancel());
   assert.equal(await f.page.evaluate(()=>NidusTemporal.state.generation),before+1);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_wrap').inert),false);
   f.releases.splice(0).forEach(fn=>fn());await f.page.waitForLoadState('networkidle');
   assert.equal(f.calls.filter(c=>c.path.endsWith('/prepare')).length,0);
   await f.pick();await f.ready();
  });
  await test(browser,'cancel pending prepare cancels late server job and never shows stale frames',async f=>{
   f.state.hold='prepare';f.state.holdCount=1;await f.pick();
   await f.page.waitForFunction(()=>NidusTemporal.state.dialog&&NidusTemporal.state.group);
   await until(()=>f.releases.length>0);
   const before=await f.page.evaluate(()=>NidusTemporal.state.generation);
   await f.page.evaluate(()=>NidusTemporal.state.dialog.cancel());
   assert.equal(await f.page.evaluate(()=>NidusTemporal.state.generation),before+1);
   f.releases.splice(0).forEach(fn=>fn());await until(()=>f.calls.some(c=>c.path==='/api/nidus/temporal/cancel/job1'));
   assert.equal(await f.page.evaluate(()=>NidusTemporal.state.ready),false);
   assert(f.calls.some(c=>c.path==='/api/nidus/temporal/cancel/job1'));
   assert.equal(f.calls.filter(c=>c.path.includes('/frame/')).length,0);
   await f.page.evaluate(()=>document.querySelector('#nd_cine_presets button').click());await f.ready();
   assert.equal(await f.page.evaluate(()=>NidusTemporal.state.job),'job2');
  });
  await test(browser,'leaving during status request prevents late decode and restores reference',async f=>{
   f.state.hold='status';f.state.holdCount=1;await f.pick();
   await f.page.waitForFunction(()=>!!NidusTemporal.state.job);
   await f.page.evaluate(()=>NidusTemporal.leave());
   f.releases.splice(0).forEach(fn=>fn());await f.page.waitForLoadState('networkidle');
   assert.equal(f.calls.filter(c=>c.path.includes('/frame/')).length,0);
   assert.equal(await f.page.evaluate(()=>NidusTemporal.state.active),false);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_wrap').inert),false);
  });
  await test(browser,'cancel frame preloading aborts cache and prevents partial playback',async f=>{
   f.state.hold='frame';f.state.holdCount=1;await f.pick();
   await f.page.waitForFunction(()=>NidusTemporal.state.cache&&NidusTemporal.state.cache.running);
   await f.page.evaluate(()=>NidusTemporal.state.dialog.cancel());
   f.releases.splice(0).forEach(fn=>fn());await f.page.waitForLoadState('networkidle');
   assert.deepEqual(await f.page.evaluate(()=>[NidusTemporal.state.ready,NidusTemporal.state.frames.length,NidusTemporal.state.cache.stats().entries]),[false,0,0]);
   assert.equal(await f.page.evaluate(()=>document.getElementById('nd_cine_play').disabled),true);
  });
 }finally{await browser.close()}
 fs.writeFileSync(path.join(output,'temporal-ui-results.json'),JSON.stringify({generated:new Date().toISOString(),tests:results},null,2));
 for(const r of results)console.log(`${r.status.toUpperCase()} ${r.name}${r.error?'\n'+r.error:''}`);
 console.log(`${results.filter(r=>r.status==='passed').length}/${results.length} passed`);
 process.exitCode=results.some(r=>r.status!=='passed')?1:0;
})().catch(e=>{console.error(e);process.exitCode=1});
