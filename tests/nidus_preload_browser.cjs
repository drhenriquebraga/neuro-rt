/* Real host UI and synthetic HTTP images: no clinical exam is opened. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE);
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const hold = () => {let release; const promise=new Promise(resolve=>{release=resolve});return {promise,release}};

(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000},reducedMotion:'reduce'});
  const html=fs.readFileSync(process.argv[2],'utf8'), output=process.argv[3];
  const errors=[],calls=[],lastMpr=hold(),warm=hold(),oldOpen=hold();
  let mprWaiting=false,warmWaiting=false,oldWaiting=false,reopenCalls=0;
  const sample='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><defs><radialGradient id="g"><stop stop-color="#586b80"/><stop offset="1" stop-color="#101a2b"/></radialGradient></defs><rect width="256" height="256" fill="url(#g)"/><path d="M128 230V150L86 100V48M128 150L176 94V35M128 168L49 130M128 183L205 130" fill="none" stroke="#d7e8f4" stroke-width="5"/><text x="128" y="244" text-anchor="middle" fill="white" font-size="10">Synthetic fixture</text></svg>';
  const opened={forma:[40,60,80],chave:'synthetic',modalidade:'MR',hu:false,osso:{tem:false},passos:{},geometria:null};
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>window.addEventListener('DOMContentLoaded',()=>{window.ndAbrirEscolha=function(){}},{capture:true,once:true}));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.pathname==='/nidus/projecao')return route.fulfill({contentType:'text/html',body:html});
   calls.push(url);
   if(url.pathname==='/api/nidus/abrir'){
    const data=request.postDataJSON();
    if(data.b==='same-ticket' && ++reopenCalls===1){oldWaiting=true;await oldOpen.promise;return route.fulfill({json:{...opened,forma:[11,11,11]}}).catch(()=>{})}
    return route.fulfill({json:opened});
   }
   if(/\/api\/nidus\/(projecao|corte)$/.test(url.pathname)){
    if(url.searchParams.get('b')==='first' && url.pathname.endsWith('/corte') && url.searchParams.get('eixo')==='2' && !mprWaiting){mprWaiting=true;await lastMpr.promise}
    if(url.searchParams.get('b')==='first' && url.pathname.endsWith('/projecao') && (url.searchParams.get('t')||'').includes('-preparo-') && !warmWaiting){warmWaiting=true;await warm.promise}
    if(url.searchParams.get('b')==='bad-image')return route.fulfill({status:500,body:'Synthetic failure'});
    return route.fulfill({contentType:'image/svg+xml',body:sample}).catch(()=>{});
   }
   if(url.pathname==='/api/nidus/linhas')return route.fulfill({json:{largura:256,altura:256,indice:20,camadas:[]}});
   return route.fulfill({json:{}});
  });
  await page.goto('http://127.0.0.1:18799/nidus/projecao');
  await page.evaluate(()=>ndAbrirSerie({bilhete:'first',modalidade:'MR',desc:'Synthetic TOF',rotulo:'Synthetic TOF'}));
  while(!mprWaiting)await delay(20);
  assert.equal(await page.evaluate(()=>ND.aberta),true,'volume is available');
  assert.equal(await page.evaluate(()=>ND.abrindo),true,'one missing MPR must hold readiness');
  assert.equal(await page.locator('#nd_wrap').evaluate(e=>e.inert),true);
  assert(await page.locator('#nd_lao').isDisabled());
  const frozen=await page.evaluate(()=>{const before=ND.lao;ndRoda({deltaY:120,preventDefault(){}});return ND.lao===before&&!ndPodeDesenhar()});
  assert(frozen);
  assert.equal(await page.locator('.ui-modal[role="dialog"]').count(),1);
  if(output){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'nidus-initial-loading.png'),fullPage:true})}
  lastMpr.release();while(!warmWaiting)await delay(20);
  assert.equal(await page.evaluate(()=>ND.abrindo),true,'preset preparation also holds readiness');
  const art=page.locator('.nd-thinking');
  assert.equal(await art.count(),1);
  const firstState=await art.innerText();
  assert.notEqual(firstState,await page.locator('.ui-modal p[role="status"]').innerText(),'art and progress status must not duplicate the same sentence');
  await page.waitForFunction(previous=>document.querySelector('.nd-thinking').innerText!==previous,firstState);
  assert.equal(await page.locator('.nd-thinking .t-think-text').evaluate(e=>getComputedStyle(e).transitionDuration),'0s');
  warm.release();await page.waitForFunction(()=>ND.aberta&&!ND.abrindo&&!ND.projetando);
  assert.equal(await page.locator('#nd_wrap').evaluate(e=>e.inert),false);
  assert.deepEqual(await page.evaluate(()=>['nd_proj','nd_pl0','nd_pl1','nd_pl2'].map(id=>document.getElementById(id).naturalWidth)),[256,256,256,256]);
  await page.waitForSelector('.ui-modal',{state:'detached'});
  const before=calls.filter(u=>u.pathname.endsWith('/projecao')&&!(u.searchParams.get('t')||'').includes('-preparo-')).length;
  await page.evaluate(()=>ndAngulo(90,0));await page.waitForFunction(()=>!ND.projetando);
  const after=calls.filter(u=>u.pathname.endsWith('/projecao')&&!(u.searchParams.get('t')||'').includes('-preparo-')).length;
  assert.equal(before,after,'a warmed preset must use the decoded image cache');
  await page.locator('#nd_palco').dispatchEvent('wheel',{deltaY:120,cancelable:true});
  assert.equal(await page.evaluate(()=>ND.lao),95);
  await page.locator('#nd_palco').dispatchEvent('wheel',{deltaY:-120,shiftKey:true,cancelable:true});
  assert.equal(await page.evaluate(()=>ND.cra),-5);
  const zoom=await page.evaluate(()=>ND.zoom.k);
  await page.locator('#nd_palco').dispatchEvent('wheel',{deltaY:-120,ctrlKey:true,cancelable:true});
  assert((await page.evaluate(()=>ND.zoom.k))>zoom);assert.equal(await page.evaluate(()=>ND.lao),95);
  const slice=await page.evaluate(()=>ND.planos[0]);
  await page.locator('#nd_pp0').dispatchEvent('wheel',{deltaY:120,cancelable:true});
  assert(Math.abs((await page.evaluate(()=>ND.planos[0]))-slice-1/39)<1e-9);
  await page.evaluate(()=>ndRoda({deltaY:0,preventDefault(){}}));
  assert.equal(await page.evaluate(()=>ND.lao),95);
  await page.waitForFunction(()=>!ND.projetando);
  if(output)await page.screenshot({path:path.join(output,'nidus-prepared.png'),fullPage:true});

  await page.evaluate(()=>ndAbrirSerie({bilhete:'same-ticket',modalidade:'MR',rotulo:'Synthetic repeat'}));
  while(!oldWaiting)await delay(20);
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!ND.aberta&&!ND.abrindo&&ND.recuperavel);
  assert.equal(await page.locator('#nd_wrap').evaluate(e=>e.inert),false);
  await page.evaluate(()=>ndAbrirSerie({bilhete:'same-ticket',modalidade:'MR',rotulo:'Synthetic repeat'}));
  await page.waitForFunction(()=>ND.aberta&&!ND.abrindo&&!ND.projetando);
  oldOpen.release();await delay(100);
  assert.deepEqual(await page.evaluate(()=>ND.forma),[40,60,80],'late same-ticket response must be ignored');
  assert(await page.evaluate(()=>ND_IMAGE_CACHE.stats().bytes<=ND_IMAGE_CACHE.maxBytes));

  await page.evaluate(()=>ndAbrirSerie({bilhete:'bad-image',modalidade:'MR',rotulo:'Synthetic failure'}));
  await page.waitForFunction(()=>!ND.aberta&&!ND.abrindo&&ND.recuperavel);
  assert.equal(await page.locator('#nd_wrap').evaluate(e=>e.inert),false);
  assert.equal(await page.evaluate(()=>ndPodeDesenhar()),false);
  assert.equal(await page.locator('#nd_msg').innerText(),await page.evaluate(()=>radaiFrase('Não foi possível preparar todas as imagens. Tente novamente.')));
  assert.deepEqual(errors,[]);
  console.log('PASS: blocking preparation, complete image decode, cached presets, angiography/MPR wheel, cancelled same-ticket reopening and failed preparation.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
