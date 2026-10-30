const fs=require('fs'),assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const page=await browser.newPage(),posted=[],tokens=[],unexpected=[];
  const data={state:'absent',mounted:false,active_version:null,token:'stale-page-token',release_check:{state:'available',version:'1.0.0'},update:{state:'idle'}};
  data.consent={installation_accepted:true,first_use_accepted:false,policy:{schema:'neuro-rt/consent-policy/1',plugin_id:'neuro-rt',version:'1.0',digest:'a'.repeat(64),title:'Termo sintético',clauses:[{id:'scope',text:'Synthetic scope'}]}};
  let gap=false;
  await page.route('http://neuro.test/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname;
   if(path==='/neuro')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.NEURO_INSTALL_HTML,'utf8')});
   if(path==='/neuro/')return route.fulfill({contentType:'text/html',body:'<h1 id="installed">Installed synthetic plugin</h1>'});
   if(path==='/api/plugins/neuro-rt/install'){
    assert.deepEqual(req.postDataJSON(),{confirm:true});assert.equal(req.headers()['x-neuro-plugin-token'],'first-session');posted.push(path);
    data.update={state:'downloading',downloaded_bytes:32,total_bytes:100};return route.fulfill({status:202,json:data.update});
   }
   if(path==='/api/plugins/neuro-rt'){
    if(gap){gap=false;return route.fulfill({status:503,body:'restarting'});}
    tokens.push(data.token);return route.fulfill({json:data});
   }
   unexpected.push(path);return route.fulfill({json:{}});
  });
  await page.goto('http://neuro.test/neuro');
  await page.locator('[data-neuro-action="comecar"]').waitFor();
  data.token='first-session';
  await page.locator('[data-neuro-action="comecar"]').click();
  await page.waitForFunction(()=>document.getElementById('neuro-update-progress').value===32);
  data.update={state:'preparing'};await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-update-message').textContent()).includes('Preparando'));
  data.update={state:'restarting'};await page.evaluate(()=>NeuroPluginUpdate.read());
  gap=true;await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-update-message').textContent()).includes('Reabrindo'));
  data.token='new-session';data.state='checking';data.update={state:'idle'};await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-update-message').textContent()).includes('Verificando'));
  data.state='ready';data.mounted=true;data.active_version='1.0.0';
  await page.evaluate(()=>NeuroPluginUpdate.read());await page.locator('#installed').waitFor();
  assert.equal(posted.length,1);assert(tokens.includes('new-session'));assert(!unexpected.some(p=>/\.js$/.test(p)),'No payload JavaScript before verification');
  console.log('PASS: trusted absent-page consumer, explicit install POST/fresh token, download/preparation/restart, temporary outage, new-session checking, mounted redirect; no downloaded payload JavaScript.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
