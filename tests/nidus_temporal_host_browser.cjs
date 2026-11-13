/* Integrated host DOM, acquired-phase routes mocked with synthetic vessel art. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE);
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const hold=()=>{let release;const promise=new Promise(resolve=>{release=resolve});return {promise,release}};
const sample=index=>'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512"><rect width="512" height="512" fill="#080f18"/><path d="M256 465V310L172 200V96M256 310L352 188V70M256 336L98 260M256 366L410 260" fill="none" stroke="'+['#638eae','#adcadf','#d9edfa'][index]+'" stroke-width="'+[5,8,10][index]+'"/><text x="256" y="495" text-anchor="middle" fill="#b0c7d8" font-size="16">Synthetic acquired phase '+(index+1)+'</text></svg>';

(async()=>{
 const html=fs.readFileSync(process.argv[2],'utf8'),expected=JSON.parse(fs.readFileSync(process.argv[3],'utf8')),out=process.argv[4];
 if(out)fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const report=[];
 try{
  for(const locale of Object.keys(expected)){
   const page=await browser.newPage({viewport:{width:1600,height:1000},reducedMotion:'reduce'}),errors=[],calls=[];
   const blocked=hold(),cancelled=hold();let frameHeld=false,scenario='3d',serial=0,cancelHeld=false;
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(code=>localStorage.setItem('radai_idioma',code),locale);
   await page.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.pathname==='/nidus/projecao')return route.fulfill({contentType:'text/html',body:html});
    calls.push({url,path:url.pathname,body:req.method()==='POST'?req.postDataJSON():null});
    if(url.pathname==='/api/nidus/temporal/discover'){
     const data=req.postDataJSON();assert.equal(data.itens.length,3);assert.equal(data.ancora.bilhete,'temporal-0');
     return route.fulfill({json:{groups:scenario==='empty'?[]:[{id:scenario,kind:scenario==='2d'?'projection2d':'volume3d',can_rotate:scenario!=='2d',timing_known:true,count:3}]}});
    }
    if(url.pathname==='/api/nidus/temporal/prepare')return route.fulfill({json:{job:scenario+'-'+(++serial)}});
    if(url.pathname.startsWith('/api/nidus/temporal/status/')){
     if(scenario==='cancel'){cancelHeld=true;await cancelled.promise}
     return route.fulfill({json:{state:'ready',completed:3,total:3,frames:[0,1,2].map(index=>({index,time_seconds:index*.04}))}}).catch(()=>{});
    }
    if(url.pathname.startsWith('/api/nidus/temporal/frame/')){
     const index=Number(url.pathname.split('/').at(-1));
     if(scenario==='3d'&&index===2&&!frameHeld){frameHeld=true;await blocked.promise}
     return route.fulfill({contentType:'image/svg+xml',body:sample(index)}).catch(()=>{});
    }
    if(/\/api\/nidus\/(projecao|corte)$/.test(url.pathname))return route.fulfill({contentType:'image/svg+xml',body:sample(1)});
    if(url.pathname==='/api/nidus/linhas')return route.fulfill({json:{largura:512,altura:512,indice:20,camadas:[]}});
    if(url.pathname==='/api/nidus/tof')return route.fulfill({json:{itens:[]}});
    return route.fulfill({json:{}});
   });
   await page.goto('http://127.0.0.1:18799/nidus/projecao');
   await page.waitForSelector('#nd_cine_open');
   // The normal auto-open series picker is present; dismiss it before choosing CINE.
   await page.waitForSelector('.ui-modal-veu.vis');await page.keyboard.press('Escape');
   await page.waitForSelector('.ui-modal',{state:'detached'});
   await page.evaluate(async()=>{
    ND.b='static-reference';ND.chave='reference';ND.sessao='reference-consensus';ND.aberta=true;
    ND.forma=[40,60,80];ND.planos={0:.5,1:.5,2:.5};ND.hu=false;ND.temperatura=65;
    ND.guardadas=[{lao:0,cra:0,pontos:[[100,100],[200,100],[150,200]],pendente:false}];
    ND.pontos=[[110,110],[190,110],[150,180]];
    ndRotuloDaSerie('Synthetic static reference');
    ndModalidade('MR');ndConsControles();ndTravas();ndSincronizar();
    await Promise.all([ndProjetar(),ndCorte(0),ndCorte(1),ndCorte(2)]);
   });
   const reference=await page.evaluate(()=>JSON.stringify({b:ND.b,sessao:ND.sessao,photo:ndFoto()}));
   const staticLabel=await page.locator('#nd_serie_cx').innerText();
   assert.equal(await page.locator('#nd_cine_open').innerText(),expected[locale]['CINE de enchimento']);
   const cineBox=await page.locator('#nd_cine_open').boundingBox(),anatomyBox=await page.locator('#nd_jan [data-j="osso"]').boundingBox();
   assert.equal(await page.locator('#nd_cine_open').evaluate(e=>e.nextElementSibling.dataset.j),'osso');
   const rtl=await page.locator('#nd_jan').evaluate(e=>getComputedStyle(e).direction==='rtl');
   assert(rtl?cineBox.x>=anatomyBox.x+anatomyBox.width-1:cineBox.x+cineBox.width<=anatomyBox.x+1,'CINE must be immediately before Anatomy');
   async function choose(){
    await page.locator(await page.locator('#nd_cine_panel').isVisible()?'#nd_cine_choose':'#nd_cine_open').click();
    await page.waitForSelector('.ui-modal-veu.vis:not(.saindo) #nd_escolha');
    assert.equal(await page.evaluate(()=>NidusTemporal.state.picking),true);
    assert.equal(await page.evaluate(()=>ND_MIN_CORTES),1);
    await page.evaluate(mode=>{
     const rows=[0,1,2].map(index=>({bilhete:'temporal-'+index,modalidade:'MR',cortes:30,desc:'Synthetic temporal '+index}));
     ndSeries(rows,'pasta');ndAbrirSerie({...rows[0],origem:'pasta',rotulo:'Synthetic '+mode+' series'});
    },scenario);
   }
   await choose();
   while(!frameHeld)await sleep(15);
   await page.waitForSelector('.ui-modal-veu.vis:not(.saindo)');
   assert.equal(await page.locator('#nd_wrap').evaluate(e=>e.inert),true);
   assert(await page.locator('#nd_serie_cx').isHidden(),'static patient card must be hidden during CINE preparation');
   assert.equal(await page.locator('#nd_cine_source').textContent(),'Synthetic 3d series');
   assert.equal(await page.locator('#nd_cine_source').getAttribute('translate'),'no');
   assert(await page.locator('#nd_cine_play').isDisabled());
   const visibleModal=page.locator('.ui-modal-veu.vis:not(.saindo)');
   assert.equal(await visibleModal.locator('.ui-modal-tit').innerText(),expected[locale]['CINE de enchimento']);
   assert.equal(await visibleModal.locator('p[role="status"]').innerText(),expected[locale]['Preparando a reprodução…']);
   if(out&&['en','pt-BR'].includes(locale))await page.screenshot({path:path.join(out,'cine-loading-'+locale+'.png'),fullPage:true});
   blocked.release();await page.waitForFunction(()=>NidusTemporal.state.ready);
   await page.waitForSelector('.ui-modal',{state:'detached'});
   assert.equal(await page.locator('#nd_cine_status').innerText(),expected[locale]['Todas as fases prontas.']);
   assert.equal(await page.locator('#nd_cine_play').innerText(),expected[locale]['Reproduzir']);
   assert(await page.locator('#nd_trabalho').isHidden());assert(await page.locator('#nd_cmd').isHidden());
   assert(await page.locator('#nd_serie_cx').isHidden());
   assert.equal(await page.locator('#nd_cine_source').innerText(),'Synthetic 3d series');
   assert.equal(await page.evaluate(()=>JSON.stringify({b:ND.b,sessao:ND.sessao,photo:ndFoto()})),reference);
   assert.equal(await page.evaluate(()=>ND_MIN_CORTES),20);
   if(out&&['en','pt-BR','ar','ja'].includes(locale))await page.screenshot({path:path.join(out,'cine-ready-'+locale+'.png'),fullPage:true});

   if(locale==='en'){
    const frameCount=()=>calls.filter(c=>c.path.startsWith('/api/nidus/temporal/frame/')).length;
    const framesBefore=frameCount();
    await page.locator('#nd_cine_play').click();await page.waitForFunction(()=>NidusTemporal.state.index===2);
    await page.waitForFunction(()=>NidusTemporal.state.index===0);await sleep(200);
    assert.equal(frameCount(),framesBefore,'loop must play only decoded cached frames');
    await page.locator('#nd_cine_play').click();assert.equal(await page.evaluate(()=>NidusTemporal.state.playing),false);
    await page.locator('#nd_cine_loop').uncheck();
    await page.locator('#nd_cine_play').click();await page.waitForFunction(()=>!NidusTemporal.state.playing&&NidusTemporal.state.index===2);
    scenario='2d';await choose();await page.waitForFunction(()=>NidusTemporal.state.ready&&NidusTemporal.state.group.id==='2d');
    await page.waitForSelector('.ui-modal',{state:'detached'});
    assert.equal(await page.locator('#nd_cine_source').innerText(),'Synthetic 2d series','new temporal selection updates its own source label');
    assert(await page.locator('#nd_cine_angles').isHidden());assert(await page.locator('#nd_cine_presets').isHidden());
    assert.equal(await page.locator('#nd_cine_status').innerText(),expected[locale]['CINE de projeções 2D — rotação indisponível.']);
    const angle=await page.evaluate(()=>({lao:NidusTemporal.state.lao,cra:NidusTemporal.state.cra})),prepares=calls.filter(c=>c.path.endsWith('/prepare')).length;
    await page.locator('#nd_cine_canvas').dispatchEvent('wheel',{deltaY:120,cancelable:true});await sleep(210);
    assert.deepEqual(await page.evaluate(()=>({lao:NidusTemporal.state.lao,cra:NidusTemporal.state.cra})),angle);
    assert.equal(calls.filter(c=>c.path.endsWith('/prepare')).length,prepares);
    if(out)await page.screenshot({path:path.join(out,'cine-projection2d.png'),fullPage:true});
    scenario='cancel';await choose();while(!cancelHeld)await sleep(15);
    await page.keyboard.press('Escape');await page.waitForFunction(()=>!NidusTemporal.state.ready&&!document.getElementById('nd_wrap').inert);
    cancelled.release();await sleep(100);
    assert.equal(await page.evaluate(()=>JSON.stringify({b:ND.b,sessao:ND.sessao,photo:ndFoto()})),reference);
    assert(calls.some(c=>c.path.startsWith('/api/nidus/temporal/cancel/')));
   }

   if(locale==='en'){
    await page.waitForSelector('.ui-modal',{state:'detached'});await page.keyboard.press('Escape');
   }else await page.evaluate(()=>NidusTemporal.leave());
   assert(await page.locator('#nd_trabalho').isVisible());assert(await page.locator('#nd_colB').isVisible());
   assert(await page.locator('#nd_serie_cx').isVisible());
   assert.equal(await page.locator('#nd_serie_cx').innerText(),staticLabel,'return must restore the static reference card');
   assert.equal(await page.evaluate(()=>JSON.stringify({b:ND.b,sessao:ND.sessao,photo:ndFoto()})),reference);
   await page.locator('#nd_angio_max').click();assert(await page.locator('#nd_colB').isHidden());
   await page.locator('#nd_angio_max').click();assert(await page.locator('#nd_colB').isVisible());
   scenario='empty';await choose();
   await page.waitForFunction(()=>document.getElementById('nd_cine_status').textContent===radaiFrase('Nenhuma sequência temporal compatível foi encontrada.'));
   const noTemporal=page.locator('.ui-modal-veu.vis:not(.saindo)');await noTemporal.waitFor();
   assert.equal(await noTemporal.locator('.ui-modal-tit').innerText(),expected[locale]['CINE de enchimento']);
   assert.equal(await noTemporal.locator('.ui-modal-corpo p').innerText(),expected[locale]['TOF e 3SLAB são aquisições estáticas. Selecione uma sequência temporal adquirida, como TRICKS ou TWIST.']);
   assert.deepEqual(errors,[],'host JavaScript errors '+locale);
   report.push({locale,popup:true,ready:true,referencePreserved:true});await page.close();
   console.log('CINE host '+locale+' passed');
  }
 }finally{await browser.close()}
 if(out)fs.writeFileSync(path.join(out,'review.json'),JSON.stringify(report,null,2));
 console.log('PASS: CINE host DOM, normal series popup, 3D/2D, cache-only loop, cancellation, static reference/MPR restoration and '+report.length+' languages.');
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
