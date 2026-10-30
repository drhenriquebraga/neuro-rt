const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage();page.setDefaultTimeout(5000);
  const policy=JSON.parse(fs.readFileSync(process.env.NEURO_CONSENT_POLICY,'utf8'));
  const data={state:'ready',mounted:true,token:'token1',host_pid:101,active_version:'1.1.0',
   release_check:{state:'current',version:'1.1.0'},update:{state:'idle'},
   consent:{policy,installation_accepted:false,first_use_accepted:true}};
  const posts=[];let inspected=0;
  const script=fs.readFileSync(path.resolve(__dirname,'../web/plugin-update.js'),'utf8');
  const catalog=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../web/plugin-update-i18n.json'),'utf8'));
  const html='<html lang="pt-BR"><style>input{width:100%}</style><body><section id="neuro-update" data-neuro-install="1" data-neuro-settings="1"><p id="neuro-update-message"></p><progress id="neuro-update-progress" hidden></progress><div id="neuro-update-actions"></div><details id="neuro-local-source" open><summary>Fonte local</summary><input id="neuro-local-folder"><button id="neuro-local-browse">Escolher pasta</button><button id="neuro-local-inspect">Conferir</button><p id="neuro-local-message"></p></details><button id="neuro-release-refresh">Verificar versão</button></section><script>window.NEURO_INSTALL_CATALOG='+JSON.stringify(catalog)+';</script><script>'+script+'</script></body></html>';
  await page.route('http://neuro.test/**',async route=>{
   const request=route.request(),url=new URL(request.url());
   if(url.pathname==='/settings'){
    let body=html;
    if(url.searchParams.has('host'))body=body.replace('id="neuro-local-browse"','id="neuro-local-browse" data-neuro-host-browse="1"').replace('<script>'+script,'<script>document.getElementById("neuro-local-browse").addEventListener("click",()=>{const field=document.getElementById("neuro-local-folder");field.value="NativeHostFolder";field.dispatchEvent(new Event("input"));});</script><script>'+script);
    return route.fulfill({contentType:'text/html',body});
   }
   if(request.method()==='POST'){
    posts.push({path:url.pathname,body:request.postDataJSON(),token:request.headers()['x-neuro-plugin-token']});
    if(url.pathname.endsWith('/local/browse'))return route.fulfill({json:{folder:'C:\\Transport\\Neuro'}});
    if(url.pathname.endsWith('/local/inspect')){
     if(request.postDataJSON().folder.endsWith('ParentOnly'))return route.fulfill({status:400,json:{detail:'Source invalid'}});
     return route.fulfill({json:{source_id:'opaque-source-'+(++inspected),version:'1.1.0',trust:'host-pinned-code'}});
    }
    if(url.pathname.endsWith('/refresh')){data.release_check={state:'available',version:'1.1.1'};return route.fulfill({json:data.release_check});}
    return route.fulfill({status:202,json:{state:'restarting',version:'1.1.0'}});
   }
   return route.fulfill({json:data});
  });
  await page.goto('http://neuro.test/settings');
  await page.waitForFunction(()=>window.NeuroPluginUpdate&&NeuroPluginUpdate.state.last);
  assert.equal(await page.locator('#neuro-update').isVisible(),true,'Current plugin must keep maintenance controls visible in Settings');
  const checkboxBox=await page.locator('#neuro-install-consent-check').boundingBox();
  assert(checkboxBox&&checkboxBox.width<30,'Consent checkbox must resist the host input width:100% rule');
  data.consent.installation_accepted=true;await page.evaluate(()=>NeuroPluginUpdate.read());
  await page.evaluate(()=>document.documentElement.lang='en');
  await page.locator('#neuro-local-browse').click();
  await page.waitForFunction(()=>document.getElementById('neuro-local-folder').value==='C:\\Transport\\Neuro');
  await page.locator('#neuro-local-inspect').click();
  await page.waitForFunction(()=>document.getElementById('neuro-local-message').textContent.includes('1.1.0'));
  assert((await page.locator('#neuro-local-message').textContent()).includes('Local source verified.'));
  assert.equal(await page.locator('[data-neuro-action="comecar"]').isEnabled(),true);
  await page.locator('#neuro-local-folder').fill('C:\\Transport\\Changed');
  assert.equal(await page.locator('[data-neuro-action="comecar"]').isDisabled(),true,'Changing the folder invalidates the opaque source selection');
  await page.evaluate(()=>NeuroPluginUpdate.request('comecar'));
  assert.equal(posts.filter(p=>p.path.endsWith('/update')||p.path.endsWith('/install')).length,0,'Uninspected folder must never fall back to online');
  await page.locator('#neuro-local-inspect').click();
  await page.waitForFunction(()=>document.getElementById('neuro-local-message').textContent.includes('1.1.0'));
  await page.locator('[data-neuro-action="comecar"]').click();
  await page.waitForFunction(()=>NeuroPluginUpdate.state.posting===false);
  const operation=posts.find(p=>p.path.endsWith('/update'));
  assert.deepEqual(operation,{path:'/api/plugins/neuro-rt/update',token:'token1',body:{action:'comecar',source_id:'opaque-source-2'}});
  data.token='token2';data.host_pid=202;data.update={state:'ready',version:'1.1.0'};
  await page.evaluate(()=>NeuroPluginUpdate.read());
  assert.equal(new URL(page.url()).pathname,'/settings','Confirmed restart must keep Settings open');
  await page.locator('#neuro-release-refresh').click();
  await page.waitForFunction(()=>document.getElementById('neuro-update-message').textContent.includes('1.1.1'));
  const refresh=posts.find(p=>p.path.endsWith('/refresh'));
  assert(refresh&&refresh.token==='token2','Refresh uses a POST and the new host token');
  await page.locator('#neuro-local-source').evaluate(element=>element.open=false);
  data.release_check={state:'unavailable'};
  await page.evaluate(()=>NeuroPluginUpdate.read());
  assert.equal(await page.locator('#neuro-local-source').evaluate(element=>element.open),true,'Network failure offers local guidance');
  await page.locator('#neuro-local-folder').fill('C:\\Transport\\ParentOnly');
  await page.locator('#neuro-local-inspect').click();
  await page.waitForFunction(()=>document.getElementById('neuro-local-message').textContent.includes('release-manifest.json'));
  assert((await page.locator('#neuro-local-message').textContent()).includes('START_HERE.cmd'));
  assert(!(await page.locator('body').innerText()).includes('undefined'));
  const beforeNative=posts.filter(p=>p.path.endsWith('/local/browse')).length;
  await page.goto('http://neuro.test/settings?host=1');
  await page.waitForFunction(()=>window.NeuroPluginUpdate&&NeuroPluginUpdate.state.last);
  await page.locator('#neuro-local-browse').click();
  await page.waitForFunction(()=>document.getElementById('neuro-local-folder').value==='NativeHostFolder');
  await page.waitForTimeout(50);
  assert.equal(posts.filter(p=>p.path.endsWith('/local/browse')).length,beforeNative,'Host native Explorer marker must suppress the fallback POST listener');
  console.log('PASS: Settings remains visible; native browse/inspect; folder change invalidates source; opaque source_id only; no online fallback; restart stays Settings; explicit fresh metadata POST.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
