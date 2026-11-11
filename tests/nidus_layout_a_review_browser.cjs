const fs=require('fs'),assert=require('assert').strict;
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE);
const expected=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const findings=[];
 const locales=Object.keys(expected).filter(code=>!process.env.NIDUS_REVIEW_LOCALE||code===process.env.NIDUS_REVIEW_LOCALE);
 try{
  for(const locale of locales){
   const page=await browser.newPage({viewport:{width:1366,height:768},reducedMotion:'reduce'}),errors=[];
   let centerMode='normal';
   page.on('pageerror',e=>errors.push(String(e)));
   await page.addInitScript(code=>{localStorage.setItem('radai_idioma',code);window.addEventListener('DOMContentLoaded',()=>{window.ndAbrirEscolha=function(){}},{capture:true,once:true});},locale);
   const sample='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#183040"/><circle cx="128" cy="128" r="70" fill="#7fa6bb"/><text x="128" y="128" text-anchor="middle">Synthetic only</text></svg>';
   await page.route('**/*',route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/nidus/projecao')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.argv[2],'utf8')});
    if(/\/api\/nidus\/(projecao|corte)$/.test(url.pathname))return route.fulfill({contentType:'image/svg+xml',body:sample});
    if(url.pathname==='/api/nidus/linhas')return route.fulfill({json:{largura:256,altura:256,indice:20,camadas:[{qual:'consenso',segmentos:[[[100,100],[160,100]],[[160,100],[160,160]]]}]}});
    if(url.pathname==='/api/nidus/centro')return route.fulfill(centerMode==='failed'?{status:400,json:{erro:'Não foi possível centrar o consenso.'}}:{json:centerMode==='empty'?{vazio:true}:{vazio:false,posicoes:[.25,.4,.75]}});
    return route.fulfill({json:{}});
   });
   await page.goto('http://127.0.0.1:18799/nidus/projecao');
   await page.waitForSelector('#nd_aux_grid');
   await page.waitForFunction(()=>typeof window.radaiFrase==='function');
   const translations=await page.evaluate(keys=>Object.fromEntries(keys.map(key=>[key,radaiFrase(key)])),Object.keys(expected[locale]));
   assert.deepEqual(translations,expected[locale],'translation mismatch in '+locale);
   await page.evaluate(()=>{ND.b='synthetic';ND.aberta=true;ND.forma=[40,60,80];ND.sessao='synthetic-session';ND.planos={0:.5,1:.5,2:.5};ND.hu=false;ndModalidade('MR');ND.guardadas=[{lao:0,cra:0,pontos:[[0,0],[1,0],[1,1]]}];ndConsControles();ndPintarPlanos();ndAjustarTela();radaiRetraduzir();});
   for(const width of [1366,390]){
    console.log('Review '+locale+' '+width);
    await page.setViewportSize({width,height:width===1366?768:844});
    await page.evaluate(()=>{ndMaximizar(null);if(ND.angioMax)ndMaximizarAngio();ndAjustarTela()});
    for(const axis of [0,1,2]){
     await page.locator('#nd_pp'+axis).dblclick();
     assert.equal(await page.evaluate(()=>ND.principal),axis,'MPR swap');
     const before=await page.evaluate(axis=>({pos:ND.planos[axis],zoom:ND.zoom.k,n:ND.forma[axis]}),axis);
     await page.locator('#nd_pp'+axis).dispatchEvent('wheel',{deltaY:120,cancelable:true});
     const after=await page.evaluate(axis=>({pos:ND.planos[axis],zoom:ND.zoom.k}),axis);
     assert(Math.abs(after.pos-before.pos-1/(before.n-1))<1e-9,'wheel moved more than one slice');
     assert.equal(after.zoom,before.zoom,'MPR wheel changed angio zoom');
    }
    try{await page.locator('#nd_angio_max').click({timeout:5000});}
    catch(error){
     await page.screenshot({path:process.argv[4]+'/nidus-a-blocked-'+locale+'-'+width+'.png',fullPage:true});
     console.log(await page.evaluate(()=>{const b=document.getElementById('nd_angio_max'),r=b.getBoundingClientRect();return {button:{x:r.x,y:r.y,width:r.width,height:r.height},interceptor:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.outerHTML.slice(0,180)}}));
     throw error;
    }
    assert.equal(await page.evaluate(()=>ND.principal),null);
    assert(await page.locator('#nd_colB').isHidden());
    await page.locator('#nd_angio_max').click();
    assert(await page.locator('#nd_colB').isVisible());
    await page.evaluate(()=>ndZoomRepor());
    await page.locator('#nd_palco').dispatchEvent('wheel',{deltaY:-120,clientX:200,clientY:200,cancelable:true});
    assert(Math.abs(await page.evaluate(()=>ND.zoom.k)-1.15)<1e-9,'angio wheel zoomed more than once');
    await page.locator('#nd_cons_centrar').click();
    await page.waitForFunction(()=>ND.planos[0]===.25&&ND.planos[1]===.4&&ND.planos[2]===.75);
    for(const [mode,message] of [['empty','Consenso vazio: ajuste a temperatura ou revise as incidências.'],['failed','Não foi possível centrar o consenso.']]){
     centerMode=mode;
     const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/nidus/centro');
     await page.locator('#nd_cons_centrar').click();await response;
     await page.waitForFunction(()=>document.getElementById('nd_cons_centrar').disabled===false);
     assert.equal(await page.locator('#nd_msg').innerText(),expected[locale][message],'immediate center state translation in '+locale);
    }
    centerMode='normal';await page.evaluate(()=>ndMsg('',''));
    for(const selector of ['#nd_inc_details','.nd-anatomia-popover']){
     const summary=page.locator(selector+' > summary');await summary.focus();await page.keyboard.press('Enter');
     assert(await page.locator(selector).evaluate(e=>e.open),'popover Enter');
     if(!(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)))findings.push({locale,width,issue:'popover overflow',selector});
     await page.keyboard.press('Escape');
     if(await page.locator(selector).evaluate(e=>e.open))findings.push({locale,width,issue:'Escape did not close popover',selector});
     await page.locator(selector).evaluate(e=>e.open=false);
     await summary.focus();await page.keyboard.press('Space');assert(await page.locator(selector).evaluate(e=>e.open),'popover Space');
     await page.locator(selector).evaluate(e=>e.open=false);
    }
    if(!(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)))findings.push({locale,width,issue:'page overflow'});
    assert.equal(await page.locator('#nd_cons_exportar').innerText(),expected[locale]['Exportar sugestão'],'dynamic export label in '+locale);
    assert.equal(await page.locator('#nd_jan [data-j="osso"]').innerText(),expected[locale]['Anatomia'],'MR anatomy label in '+locale);
    assert.equal(await page.locator('#nd_jan [data-j="parenquima"]').innerText(),expected[locale]['Tecidos'],'MR tissues label in '+locale);
    if(locale==='en')await page.screenshot({path:process.argv[4]+'/nidus-a-review-'+width+'.png',fullPage:true});
   }
   assert(await page.locator('.nd-osso').isHidden(),'MR showed bone controls');
   assert.deepEqual(errors,[],'JavaScript errors');
   await page.close();
  }
 }finally{await browser.close()}
 fs.writeFileSync(process.argv[4]+'/nidus-a-review.json',JSON.stringify(findings,null,2));
 if(findings.length)throw Error(JSON.stringify(findings.slice(0,8))+'; total findings='+findings.length);
 console.log('PASS '+locales.length+' locales, laptop/mobile, three MPR swaps, one-slice wheel, angio maximize/restore, consensus center/error states, keyboard popovers');
})().catch(error=>{console.error(error);process.exitCode=1});
