/* Browser-level synthetic contract check; no patient data or model inference. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
const browserPath=process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:browserPath});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],posted=[],retries=[],selections=[];let finished=false,failDetail=false,detailRequests=0,retryStage=0;const liveRequests=[],stoppedScans=[];
  let releaseStatus;
  const firstStatus = new Promise(resolve => { releaseStatus = resolve; });
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{if(!localStorage.getItem('radai_idioma'))localStorage.setItem('radai_idioma','pt-BR');});
  const series=[1,2,3,4,5].map(i=>({ticket:'ticket'+i,modality:'MR',group_key:i===5?'other-exam':'synthetic-exam',source_format:'nifti',sequence_candidates:[{role:['T1c','T1','T2','FLAIR','T1'][i-1],certainty:'uncertain'}]}));
  const template={id:'synthetic',label:'Modelo de quatro entradas',groups:['glioma'],channels:['T1c','T1','T2','FLAIR'].map(role=>({role})),classes:[{class_id:'tumor',label:'Tumor'}],revision:'test',license:{code:'MIT'},source_url:'https://example.invalid/model',eligibility:{selectable:true,technical_reasons:[],warnings:[{message:'Classificação incerta; confira as associações.'}]}};
  const restrictedReason='Modelo adiado; não distribuído nesta versão.';
  const result=(id,revision=1,status='completed')=>({id,status,result:{study_id:id,reference_ticket:'reference-'+id,status,revision,export_status:'completed',models:[{model_id:'synthetic',status:'completed',classes:['tumor'],warnings:[{code:'class_lost_on_reference_grid',class_id:'enhancing_tumor',working_voxels:2,reference_voxels:0}]}],artifacts:[{artifact_id:'scene',kind:'view',logical_name:'view.json'},{artifact_id:'mesh',kind:'mesh',logical_name:'roi_000.stl'},...['axial','coronal','sagittal'].map(name=>({artifact_id:name,kind:'slice',logical_name:name+'_000.svg'}))]}});
  function selection(tickets){const chosen=series.filter(s=>tickets.includes(s.ticket));return {series:chosen,models:[{...template,bindings:chosen.map(s=>({role:s.sequence_candidates[0].role,series_ticket:s.ticket,certainty:'uncertain',association_source:'suggested',warnings:[]}))},{...template,id:'missing-runtime',label:'Modelo sem ambiente',channels:[{role:'T1c'}],bindings:[{role:'T1c',series_ticket:'ticket1'}],eligibility:{selectable:false,missing_roles:[],warnings:[],technical_reasons:[{message:'Ambiente ausente.'}]}},{...template,id:'candidate-model',label:'Modelo candidato',eligibility:{selectable:false,technical_reasons:[{code:'model_not_distributed',message:restrictedReason}]}}]};}
  await page.route('http://neuro.test/**',async route=>{
   const url=new URL(route.request().url()),p=url.pathname;
   if(p==='/neuro/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.NEURO_STUDY_HTML,'utf8')});
   if(p==='/neuro/study.js'||p==='/neuro/study.css')return route.fulfill({contentType:p.endsWith('.js')?'text/javascript':'text/css',body:fs.readFileSync(path.join(root,'web',path.basename(p)),'utf8')});
   if(p==='/neuro/api/status'){await firstStatus;return route.fulfill({json:{token:'synthetic-token'}});}
   if(p==='/api/acervo/tabela')return route.fulfill({json:{series:[{bilhete:'ticket1',date:'20260101',pid:'synthetic',estado:'ok'}]}});
   if(p==='/api/acervo/tabela/detalhes')return route.fulfill({json:{itens:[{nome:'Synthetic archive row',modalidade:'MR',cortes:12,espessura_mm:1}]}});
   if(p==='/api/varrer/iniciar'){
    const request=route.request().postDataJSON();
    assert.deepEqual(request.opcoes,{modalidades:['MR','CT']});
    if(request.pasta==='synthetic-cancel')return route.fulfill({json:{v:'scan-to-cancel',fim:false,series:1,linhas:[{uid:'partial',desc:'Synthetic partial row',carregando:true}]}});
    const lines=series.map((s,i)=>({uid:'synthetic-'+i,bilhete:s.ticket,modalidade:s.modality,desc:'Synthetic series '+(i+1),cortes:12}));
    lines.push({uid:'still-scanning',desc:'Synthetic partial row',cortes:3,carregando:true});
    return route.fulfill({json:{v:'synthetic-scan',fim:true,final:true,series:lines.length,linhas:lines}});
   }
   if(p==='/api/varrer/parar'){stoppedScans.push(route.request().postDataJSON().v);return route.fulfill({json:{v:'scan-to-cancel'}});}
   if(p==='/api/varrer/estado')return route.fulfill({json:{v:'scan-to-cancel',fim:!!stoppedScans.length,final:!!stoppedScans.length,parado:!!stoppedScans.length,linhas:[]}});
   if(p==='/neuro/api/selection'){
    assert.equal(route.request().headers()['x-neuro-token'],'synthetic-token');
    const {tickets,category}=route.request().postDataJSON();
    assert.equal(category,'glioma');
    selections.push(tickets);
    const data=selection(tickets);data.models.push(...JSON.parse(fs.readFileSync(path.join(root,'catalog/models.json'),'utf8')).models.filter(m=>['anatomy_synthseg','anatomy_cerebra_ants','cranio_buti'].includes(m.id)).map(m=>({...m,bindings:[],eligibility:{selectable:false,technical_reasons:[{message:'Ambiente ausente.'}],warnings:[]}})));return route.fulfill({json:data});
   }
   if(p==='/neuro/api/studies'&&route.request().method()==='POST'){posted.push(route.request().postDataJSON());return route.fulfill({status:202,json:{studies:[{id:'study1',status:'queued'}]}});}
   if(p==='/neuro/api/studies')return route.fulfill({json:{studies:finished?[result('study2',retryStage>=4?3:2,retryStage>=4?'completed':'partial'),result('study3')]:(posted.length?[{id:'study1',status:'queued'}]:[]),results:finished?[result('study2').result,result('study2',2,'partial').result,...(retryStage>=4?[result('study2',3).result]:[]),result('study3').result]:[]}});
   if(p==='/neuro/api/studies/study1'){detailRequests++;if(failDetail){failDetail=false;return route.fulfill({status:503,json:{detail:'synthetic transient failure'}});}return route.fulfill({json:{id:'study1',status:'queued'}});}
   if(p==='/neuro/api/studies/study2/retry'){retries.push(route.request().postDataJSON());retryStage=1;return route.fulfill({status:202,json:{...result('study2',2,'partial'),status:'queued',progress:{model_id:'synthetic'}}});}
   if(p==='/neuro/api/studies/study2'&&retryStage&&!url.searchParams.has('revision')){liveRequests.push(url.search);const status=retryStage===1?'queued':retryStage===2?'running':'completed';retryStage++;return route.fulfill({json:status==='completed'?result('study2',3):{...result('study2',2,'partial'),status,progress:{model_id:'synthetic'}}});}
   if(/^\/neuro\/api\/studies\/study[23]$/.test(p)){const revision=+(url.searchParams.get('revision')||1);return route.fulfill({json:result(p.split('/').pop(),revision,revision===2?'partial':'completed')});}
   if(p.includes('/artifacts/')){
    const id=p.split('/')[4],name=p.split('/').pop();
    if(name==='scene')return route.fulfill({json:{schema:'neuro-rt/view/2',bounds:[[0,0,0],[10,10,10]],rois:[{id:'roi_000',label:id+' lesão',color:[255,100,90],visible:true,opacity:.7,mesh:'roi_000.stl'},{id:'roi_001',label:id+' anatomia',color:[90,170,255],visible:true,opacity:.4}],planes:Object.fromEntries(['axial','coronal','sagittal'].map(name=>[name,{count:3,center:0,slices:[name+'_000.svg',name+'_000.svg',name+'_000.svg']}]))}});
    if(name==='mesh'){const bytes=Buffer.alloc(134);bytes.writeUInt32LE(1,80);[0,0,1,0,0,0,5,0,0,0,5,0].forEach((v,i)=>bytes.writeFloatLE(v,84+i*4));return route.fulfill({contentType:'model/stl',body:bytes});}
    if(id==='study2')await new Promise(resolve=>setTimeout(resolve,250));
    return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><title>'+id+'</title><rect width="100" height="100" fill="#222"/><g data-roi="roi_000"><path d="M10 10L50 10L50 50Z" fill="none" stroke="red"/></g><g data-roi="roi_001"><path d="M30 30L80 30L80 80Z" fill="none" stroke="blue"/></g></svg>'});
   }
   return route.fulfill({json:{}});
  });
  await page.goto('http://neuro.test/neuro/');
  const picker=page.locator('#nr-series-picker'), trigger=page.locator('#nr-picker-open');
  assert(await trigger.isDisabled(),'Series picker must wait for the status token');
  assert(await picker.isHidden());
  assert.deepEqual(selections,[]);
  releaseStatus();
  await picker.waitFor({state:'visible'});
  await page.waitForLoadState('networkidle');
  assert(await page.locator('.nr-wrap > .ui-fn .ui-ajuda').isVisible());
  assert.equal(await page.locator('.nr-wrap > .ps-cx').count(),3);
  const archiveRow=page.locator('#nr-picker-archive [data-ua-abrir]').first();
  await page.locator('#nr-picker-source-t-archive').click();
  assert(await picker.locator('.ui-ajuda').isVisible());
  await archiveRow.click();
  await picker.waitFor({state:'hidden'});
  assert.deepEqual(selections,[['ticket1']]);
  assert.equal(await trigger.evaluate(e=>document.activeElement===e),true);
  await trigger.click();
  await page.locator('#nr-picker-source-t-folder').click();
  const folder=page.locator('#nr-series-picker_pasta'), scan=page.locator('#nr-series-picker_form button[type="submit"]');
  await folder.fill('synthetic-cancel');
  await scan.click();
  await page.locator('#nr-series-picker_leitura .ui-ler-lista li').waitFor();
  assert.equal(await page.locator('#nr-picker-results [data-b]').count(),0);
  await page.locator('#nr-series-picker_parar').click();
  await folder.waitFor();
  assert.deepEqual(stoppedScans,['scan-to-cancel']);
  assert.deepEqual(await page.evaluate(()=>NeuroStudy.state.series.map(s=>s.ticket)),['ticket1']);
  assert(await picker.isVisible());
  await folder.fill('synthetic-folder');
  await scan.click();
  await page.locator('#nr-picker-results [data-b="ticket5"]').waitFor();
  assert.deepEqual(selections,[['ticket1']],'Listing a folder must not choose a series');
  assert.equal(await page.getByRole('button',{name:'Synthetic partial row'}).count(),0);
  const addFolderTicket=async ticket=>{
    if(await picker.isHidden()) await trigger.click();
    await page.locator('#nr-picker-results [data-b="'+ticket+'"]').click();
    await picker.waitFor({state:'hidden'});
  };
  await page.locator('#nr-picker-results [data-b="ticket5"]').click();
  await page.locator('#nr-picker-status').waitFor({state:'visible'});
  assert.deepEqual(await page.evaluate(()=>NeuroStudy.state.series.map(s=>s.ticket)),['ticket1']);
  await page.locator('#nr-picker-results [data-b="ticket1"]').click();
  assert.deepEqual(selections,[['ticket1'],['ticket1','ticket5']],'A duplicate ticket must not start another selection');
  for(const ticket of ['ticket2','ticket3','ticket4']) await addFolderTicket(ticket);
  assert.deepEqual(selections.at(-1),['ticket1','ticket2','ticket3','ticket4']);
  assert.equal(await page.locator('#nr-picker-count').innerText(),'Séries selecionadas · 4');
  if(process.env.NEURO_STUDY_HTML){
    await page.evaluate(()=>{window.translationIdle={passes:0,mutations:0};const translate=window.radaiRetraduzir;window.radaiRetraduzir=function(){translationIdle.passes++;return translate();};window.idleProbe=new MutationObserver(records=>{translationIdle.mutations+=records.length;});idleProbe.observe(document.querySelector('.nr-wrap'),{childList:true,subtree:true,characterData:true});});
    await page.waitForTimeout(200);const settled=await page.evaluate(()=>({...translationIdle}));await page.waitForTimeout(400);const afterIdle=await page.evaluate(()=>({...translationIdle}));assert.deepEqual(afterIdle,settled,'pt-BR translation must become idle with select options present');console.log('Idle pt-BR:',JSON.stringify({settled,afterIdle}));
    await page.evaluate(()=>{const probe=document.createElement('p');probe.id='external-translation-probe';probe.textContent='O que segmenta';document.querySelector('.nr-wrap').append(probe);});await page.waitForFunction(()=>translationIdle.passes>0);await page.waitForTimeout(200);const afterExternal=await page.evaluate(()=>({...translationIdle}));await page.waitForTimeout(400);assert.deepEqual(await page.evaluate(()=>({...translationIdle})),afterExternal,'An external update must translate once and settle again');console.log('External update pt-BR:',JSON.stringify(afterExternal));
  }
  assert.equal(posted.length,0,'Opening the page must never submit inference');
  await page.waitForSelector('[data-model="synthetic"]');
  assert.equal(await page.locator('[data-model="synthetic"]').isChecked(),false);
  assert.equal(await page.locator('[data-model="synthetic"]').isDisabled(),false,'Uncertainty must stay selectable');
  assert.equal(await page.locator('[data-model="missing-runtime"]').isDisabled(),true);
  const restricted = page.locator('.nr-model').filter({has:page.locator('[data-model="candidate-model"]')});
  assert(await restricted.getByText(restrictedReason,{exact:true}).isVisible());
  assert(await restricted.getByRole('switch').isDisabled());
  const compatibility=await page.evaluate(()=>{const s=NeuroStudy.state,m=s.models[0],ct={ticket:'ct',modality:'CT',group_key:'other'},old=s.reference;s.series.push(ct);s.reference='ct';const mrOnCt=NeuroStudy.modelAvailability(m).selectable;const ctModel={id:'ct-model',channels:[{role:'CT'}],eligibility:{technical_reasons:[]}};s.bindings['ct-model']=[{role:'CT',series_ticket:'ct'}];s.reference=old;const ctOnMr=NeuroStudy.modelAvailability(ctModel).selectable;s.series.forEach(x=>x.group_key=x.ticket==='ct'?'other':'group-a');s.series[1].group_key='group-b';const mismatch=NeuroStudy.modelAvailability(m).selectable;s.series[1].group_key='group-a';const same=NeuroStudy.modelAvailability(m).selectable;s.series.pop();return{mrOnCt,ctOnMr,mismatch,same};});assert.deepEqual(compatibility,{mrOnCt:false,ctOnMr:false,mismatch:false,same:true});
  await page.evaluate(()=>{NeuroStudy.state.series.push({ticket:'ct',modality:'CT'});document.getElementById('reference').add(new Option('Synthetic CT','ct'));});await page.locator('#reference').selectOption('ct');assert.equal(await page.locator('[data-model="synthetic"]').isDisabled(),true);assert.equal(await page.locator('[data-help="synthetic"]').isEnabled(),true);await page.locator('#reference').selectOption('ticket1');assert.equal(await page.locator('[data-model="synthetic"]').isDisabled(),false);await page.evaluate(()=>NeuroStudy.state.series.pop());
  await page.locator('[data-help="missing-runtime"]').click();assert(await page.locator('#model-help').isVisible());assert((await page.locator('#help-content').innerText()).includes('Ambiente ausente'));
  await page.keyboard.press('Escape');assert.equal(await page.locator('[data-help="missing-runtime"]').evaluate(e=>document.activeElement===e),true);
  assert(await page.locator('[data-help="anatomy_synthseg"]').count() === 0);
  await page.locator('label[for="include-anatomy"], #anatomy-option').click();
  assert(await page.locator('#include-anatomy').isChecked());
  await page.locator('[data-help="anatomy_synthseg"]').click();assert((await page.locator('#help-content').innerText()).includes('Somente CPU'));assert((await page.locator('#help-content').innerText()).includes('DIPY 1.12.0'));assert(await page.locator('[data-model="anatomy_synthseg"]').isDisabled());await page.keyboard.press('Escape');
  await page.locator('[data-model="synthetic"]').check();assert.equal(await page.locator('#start').isDisabled(),false);
  await page.locator('[data-remove="ticket4"]').click();await page.waitForFunction(()=>NeuroStudy.state.series.length===3);
  assert.equal(await page.locator('#nr-picker-count').innerText(),'Séries selecionadas · 3');
  assert.equal(await page.locator('[data-model="synthetic"]').isDisabled(),true);assert.equal(await page.locator('#start').isDisabled(),true);
  await addFolderTicket('ticket4');await page.waitForFunction(()=>NeuroStudy.state.series.length===4);
  await page.locator('[data-binding-model="synthetic"][data-role="T1"]').selectOption('ticket1');assert.equal(await page.locator('[data-model="synthetic"]').isDisabled(),true,'Duplicate channels must disable the model');
  await page.locator('[data-binding-model="synthetic"][data-role="T1"]').selectOption('ticket2');await page.locator('[data-model="synthetic"]').check();
  await page.locator('#start').click();assert.equal(posted.length,0,'The shared review must precede inference');
  await page.locator('#reference').selectOption('ticket2');await page.locator('#radai_rev_ok').click();await page.waitForFunction(()=>document.getElementById('selection-status').textContent.includes('enviado'));
  assert.equal(posted.length,1);assert.equal(posted[0].studies[0].reference,'ticket1','Submitted request must remain frozen while review is open');
  assert.equal(posted[0].schema,'neuro-rt/request/2');assert.deepEqual(posted[0].studies[0].model_ids,['synthetic']);assert.equal(new Set(posted[0].studies[0].bindings_by_model.synthetic.map(b=>b.series_ticket)).size,4);
  assert.equal(JSON.stringify(posted[0]).includes('synthetic-folder'),false);
  failDetail=true;await page.waitForFunction(()=>document.getElementById('job-status').textContent.includes('Acompanhamento interrompido'));const beforeRefresh=detailRequests;await page.locator('#refresh').click();await page.waitForFunction(()=>document.getElementById('job-status').textContent==='Na fila comum');await page.waitForTimeout(1650);assert(detailRequests>=beforeRefresh+2,'Refresh must fetch detail and resume polling');
  finished=true;await page.locator('#refresh').click();await page.waitForSelector('#result-series option[value="study2:1"]',{state:'attached'});
  for(const key of ['study2:1','study2:2','study3:1'])assert.equal(await page.locator('#result-series option[value="'+key+'"]').count(),1,'Merge historical results and jobs without repeating a revision');
  await page.locator('#result-series').selectOption('study2:1');await page.waitForSelector('#slice-axial svg');
  if(process.env.NEURO_STUDY_HTML){await page.waitForFunction(()=>window.R3G&&R3G.gl&&R3G.objs.roi_000);await page.evaluate(()=>{window.deletedBuffers=0;const remove=R3G.gl.deleteBuffer.bind(R3G.gl);R3G.gl.deleteBuffer=buffer=>{window.deletedBuffers++;remove(buffer);};});}
  await page.locator('[data-roi-visible="roi_000"]').uncheck();assert.equal(await page.locator('#slice-axial [data-roi="roi_000"]').evaluate(e=>e.style.display),'none');assert.equal(await page.locator('#slice-axial [data-roi="roi_001"]').evaluate(e=>e.style.display),'');
  await page.locator('[data-roi-opacity="roi_001"]').evaluate(e=>{e.value=25;e.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await page.locator('#slice-axial [data-roi="roi_001"]').evaluate(e=>e.style.opacity),'0.25');
  if(process.env.NEURO_STUDY_HTML){assert.deepEqual(await page.evaluate(()=>[R3M.lig.roi_000,R3M.alfa.roi_001]),[false,.25]);}
  assert((await page.locator('#result-warnings').innerText()).includes('enhancing_tumor'));assert((await page.locator('#result-warnings').innerText()).includes('2 → 0'));
  const beforeViewerPosts=posted.length;
  await page.locator('[data-primary-plane="coronal"]').click();assert.equal(await page.locator('[data-plane="coronal"]').getAttribute('data-primary'),'true');
  await page.locator('[data-enlarge="axial"]').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('[data-plane="axial"]').getAttribute('role'),'dialog');
  await page.locator('#range-axial').evaluate(e=>{e.value=2;e.dispatchEvent(new Event('input',{bubbles:true}));});await page.waitForTimeout(350);
  assert.equal(await page.locator('#slice-axial [data-roi="roi_000"]').evaluate(e=>e.style.display),'none');
  assert.equal(await page.locator('#slice-axial [data-roi="roi_001"]').evaluate(e=>e.style.opacity),'0.25');
  const color=await page.locator('#slice-axial [data-roi="roi_001"] path').getAttribute('stroke');
  await page.keyboard.press('Escape');assert.equal(await page.locator('#range-axial').inputValue(),'2');assert.equal(await page.locator('[data-enlarge="axial"]').evaluate(e=>document.activeElement===e),true);
  await page.locator('#slice-coronal').dblclick();assert(await page.locator('[data-plane="coronal"]').evaluate(e=>e.classList.contains('nr-expanded')));await page.locator('[data-enlarge="coronal"]').click();
  assert.equal(await page.locator('#slice-axial [data-roi="roi_001"] path').getAttribute('stroke'),color);assert.equal(posted.length,beforeViewerPosts);
  await page.locator('#structure-search').fill('lesão');await page.locator('#show-filtered').click();assert.equal(await page.locator('[data-roi-visible="roi_000"]').isChecked(),true);assert.equal(await page.locator('[data-roi-visible="roi_001"]').isChecked(),true);
  await page.locator('#result-series').selectOption('study3:1');await page.waitForFunction(()=>document.querySelector('#slice-axial title')?.textContent==='study3');
  if(process.env.NEURO_STUDY_HTML){assert((await page.evaluate(()=>window.deletedBuffers))>=3,'Switching series must release old GPU buffers');}
  assert((await page.locator('#structures').innerText()).includes('study3'));assert.equal(await page.locator('#slice-axial title').textContent(),'study3');
  await page.evaluate(async()=>{NeuroStudy.selectResultSeries('study2:1');await new Promise(resolve=>setTimeout(resolve,35));NeuroStudy.selectResultSeries('study3:1');});await page.waitForFunction(()=>document.querySelector('#slice-axial title')?.textContent==='study3');await page.waitForTimeout(300);assert.equal(await page.locator('#slice-axial title').textContent(),'study3','A late slice must never replace the active reference');
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(root,'runtime/test-tmp/study-ui.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(root,'runtime/test-tmp/study-ui-mobile.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('#result-series').selectOption('study2:2');await page.waitForFunction(()=>document.getElementById('retry').hidden===false);await page.locator('#retry').click();assert.equal(retries.length,0,'Retry needs explicit review');await page.locator('#radai_rev_ok').click();await page.waitForFunction(()=>document.getElementById('radai_rev').style.display==='none');assert.deepEqual(retries,[{explicit_request:true}]);await page.waitForFunction(()=>NeuroStudy.state.job.status==='queued'&&!document.getElementById('cancel').hidden);assert.equal(await page.locator('#result-series option[value="study2:1"]').count(),1);await page.waitForFunction(()=>NeuroStudy.state.job.status==='running'&&!document.getElementById('cancel').hidden);await page.waitForFunction(()=>NeuroStudy.state.job.result?.revision===3);assert(await page.locator('#cancel').isHidden());assert(liveRequests.length>=3);assert(liveRequests.every(q=>q===''));await page.locator('#result-series').selectOption('study2:1');await page.waitForFunction(()=>NeuroStudy.state.job.result?.revision===1);assert((await page.locator('#result-warnings').innerText()).includes('2 → 0'));
  const catalog=JSON.parse(fs.readFileSync(path.join(root,'web/study-i18n.json'),'utf8'));
  const footer='Material de estudo — 100% local. Nenhuma imagem sai desta rede';
  const helpExamples={
   'candidate-model':restrictedReason,
   anatomy_synthseg:'Somente CPU neste adaptador. A preferência global GPU estrita impede a execução.',
   anatomy_cerebra_ants:'Depende da qualidade do registro. Lesões e cavidades podem deslocar estruturas; convergência não valida a anatomia.',
   cranio_buti:'Evidência específica em TC sem contraste ainda não validada nesta instalação; não há bloqueio automático por contraste.',
  };
  assert.equal(catalog.en[footer],'Study material — 100% local. No image leaves this network');
  for(const [code, phrases] of Object.entries(catalog)){
   await page.evaluate(code=>localStorage.setItem('radai_idioma',code),code);
   await page.reload();
   await page.waitForFunction(expected=>document.getElementById('series-title').textContent===expected,phrases['Séries do exame']);
   assert.equal(await page.locator('.nr-footer').innerText(),phrases[footer]);
   assert.equal(await page.locator('.nr-wrap > .ui-alerta').innerText(),phrases['Resultados exigem revisão no TPS.']);
   assert.equal(await page.locator('html').getAttribute('dir'),code==='ar'?'rtl':'ltr');
   await page.locator('#nr-picker-source-t-archive').click();
   await archiveRow.click();
   await picker.waitFor({state:'hidden'});
   await page.waitForSelector('[data-help="synthetic"]');
   const selected=await page.evaluate(()=>window.radaiFrase('Séries selecionadas'));
   assert.equal(await page.locator('#nr-picker-count').innerText(),selected+' · 1');
   await page.locator('[data-help="synthetic"]').click();
   await page.waitForFunction(expected=>document.querySelector('#help-content h3').textContent===expected,phrases['O que segmenta']);
   assert((await page.locator('#help-content').innerText()).includes(phrases['Objetivo do modelo não é diagnóstico. WT: tumor total; TC: núcleo tumoral; ET: componente com realce. Licença não comprova validação clínica. Tempo e precisão não medidos nesta instalação.']));
   await page.keyboard.press('Escape');
   await page.locator('#anatomy-option').click();
   for(const [id, text] of Object.entries(helpExamples)){
    assert(phrases[text],`Missing ${id} help in ${code}`);
    await page.locator(`[data-help="${id}"]`).click();
    await page.waitForFunction(expected=>document.getElementById('help-content').textContent.includes(expected),phrases[text]);
    if(id==='candidate-model')assert(await page.locator('#help-content').getByText(phrases[text],{exact:true}).isVisible());
    await page.keyboard.press('Escape');
   }
  }
  assert.deepEqual(errors,[]);console.log('PASS: real retry with previous result queued-running-revision3 and history1, loss warning in history, keyboard/double-click enlargement and main plane preserving slice/ROI, per-model CPU/atlas/Buti help in 12 languages, selection, uncertainty, missing runtime, help keyboard/focus, removal, duplicate channels, explicit review, frozen v2 payload, no paths, independent MPR visibility/opacity, filter, series change, responsive layout.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
