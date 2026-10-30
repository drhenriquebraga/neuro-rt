const fs=require('fs'), assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const page=await browser.newPage();
  await page.addInitScript(()=>localStorage.setItem('radai_idioma','pt-BR'));
  const data={state:'ready',mounted:true,active_version:'1.0.0',token:'synthetic-token',release_check:{state:'available',version:'1.1.0'},update:{state:'idle'}};
  const posted=[];
  await page.route('http://neuro.test/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path==='/neuro/')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.NEURO_UPDATE_HTML,'utf8')});
   if(path==='/api/plugins/neuro-rt/update'){
    const body=route.request().postDataJSON();assert.equal(route.request().headers()['x-neuro-plugin-token'],'synthetic-token');posted.push(body.action);
    data.update=body.action==='comecar'?{state:'busy'}:body.action==='esperar'?{state:'waiting'}:{state:'downloading',downloaded_bytes:25,total_bytes:100};
    return route.fulfill({status:202,json:data.update});
   }
   if(path==='/api/plugins/neuro-rt')return route.fulfill({json:data});
   return route.fulfill({json:{}});
  });
  await page.goto('http://neuro.test/neuro/');await page.waitForLoadState('networkidle');
  await page.locator('[data-neuro-action="comecar"]').click();
  await page.locator('[data-neuro-action="esperar"]').waitFor();
  await page.locator('[data-neuro-action="esperar"]').click();
  await page.waitForFunction(()=>NeuroPluginUpdate.state.last.update.state==='waiting');
  assert.equal(await page.locator('#neuro-update-message').textContent(),await page.evaluate(()=>radaiFrase('Esperando terminar para atualizar…')));
  assert.equal(await page.locator('[data-neuro-action="confirm-interrupt"]').count(),0,'Do not offer escalation while a worker is already waiting');
  data.update={state:'busy'};await page.evaluate(()=>NeuroPluginUpdate.read());
  await page.locator('[data-neuro-action="confirm-interrupt"]').click();
  assert.deepEqual(posted,['comecar','esperar'],'Interrupt needs the host confirmation step');
  await page.locator('[data-neuro-action="interromper"]').click();
  await page.waitForFunction(()=>document.getElementById('neuro-update-progress').value===25);
  assert.deepEqual(posted,['comecar','esperar','interromper']);
  data.update={state:'preparing'};await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-update-message').textContent()).includes('Preparando'));
  data.update={state:'idle'};data.release_check={state:'unavailable'};await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-update-message').textContent()).includes('continua disponível'));
  assert.equal(await page.locator('.md-grade a[aria-disabled="true"]').count(),0,'Network failure must not disable tools');
  data.release_check={state:'available',version:'1.1.0'};
  await page.evaluate(()=>{localStorage.setItem('radai_idioma','en');if(window.radaiRetraduzir)radaiRetraduzir();});
  await page.evaluate(()=>NeuroPluginUpdate.read());
  await page.waitForFunction(()=>document.querySelector('[data-neuro-action="comecar"]').textContent==='Update NEURO RT');
  console.log('PASS: release offer, shared action token, wait, explicit interrupt confirmation, progress, offline tools, translated update control.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
