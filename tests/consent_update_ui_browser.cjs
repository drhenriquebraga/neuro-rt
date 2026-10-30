const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try {
  const page=await browser.newPage(),posted=[];
  const policy=JSON.parse(fs.readFileSync(process.env.NEURO_CONSENT_POLICY,'utf8'));
  const data={state:'absent',mounted:false,token:'fresh-token',release_check:{state:'available',version:'1.0.1'},update:{state:'idle'}};
  const script=fs.readFileSync(path.resolve(__dirname,'../web/plugin-update.js'),'utf8');
  const catalog=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../web/plugin-update-i18n.json'),'utf8'));
  const html='<html lang="pt-BR"><body><section id="neuro-update" data-neuro-install="1"><p id="neuro-update-message"></p><progress id="neuro-update-progress" hidden></progress><div id="neuro-update-actions"></div></section><script>window.NEURO_INSTALL_CATALOG='+JSON.stringify(catalog)+';</script><script>'+script+'</script></body></html>';
  await page.route('http://neuro.test/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.pathname==='/neuro')return route.fulfill({contentType:'text/html',body:html});
   if(req.method()==='POST'){
    posted.push({path:url.pathname,body:req.postDataJSON(),token:req.headers()['x-neuro-plugin-token']});
    return route.fulfill({status:202,json:{state:'busy'}});
   }
   return route.fulfill({json:data});
  });
  await page.goto('http://neuro.test/neuro');
  await page.waitForFunction(()=>window.NeuroPluginUpdate&&NeuroPluginUpdate.state.last);
  assert.equal(await page.locator('[data-neuro-action="comecar"]:enabled').count(),0,'Missing host consent must fail closed during installation');
  await page.evaluate(()=>NeuroPluginUpdate.request('comecar'));
  assert.equal(posted.length,0);
  data.consent={policy,installation_accepted:false,first_use_accepted:false};
  await page.evaluate(()=>NeuroPluginUpdate.read());
  const checkbox=page.locator('#neuro-install-consent-check');
  assert.equal(await checkbox.isChecked(),false);
  assert.equal(await page.locator('[data-neuro-action="comecar"]').isDisabled(),true);
  assert((await page.locator('#neuro-install-consent-document').textContent()).includes(policy.clauses[0].text));
  await checkbox.check();
  await page.evaluate(()=>NeuroPluginUpdate.read());
  assert.equal(await checkbox.isChecked(),true,'Polling must preserve the acknowledgement of the same policy');
  assert.equal(await page.locator('[data-neuro-action="comecar"]').isEnabled(),true);
  await page.evaluate(()=>document.documentElement.lang='en');
  await page.evaluate(()=>NeuroPluginUpdate.read());
  assert((await page.locator('#neuro-install-consent label').textContent()).includes('I have read and accept'));
  assert((await page.locator('#neuro-install-consent-document').textContent()).includes(policy.clauses[0].text),'The original Portuguese document remains unchanged');
  // A policy changed after the click must never be accepted from a stale checkbox.
  data.consent.policy={...policy,version:'1.1',digest:'b'.repeat(64)};
  await page.evaluate(()=>NeuroPluginUpdate.request('comecar'));
  assert.equal(posted.length,0);
  assert.equal(await checkbox.isChecked(),false);
  await checkbox.check();
  await page.evaluate(()=>NeuroPluginUpdate.request('comecar'));
  assert.deepEqual(posted[0],{path:'/api/plugins/neuro-rt/install',token:'fresh-token',body:{confirm:true,consent:{accepted:true,version:'1.1',digest:'b'.repeat(64)}}});
  await page.locator('[data-neuro-action="confirm-interrupt"]').click();
  assert.equal(posted.length,1,'Interrupt retains a separate confirmation');
  await page.locator('[data-neuro-action="interromper"]').click();
  await page.waitForFunction(()=>NeuroPluginUpdate.state.posting===false);
  assert.equal(posted[1].body.action,'interromper');
  assert.deepEqual(posted[1].body.consent,posted[0].body.consent);
  data.consent.installation_accepted=true;data.update={state:'idle'};
  await page.evaluate(()=>NeuroPluginUpdate.read());
  await page.evaluate(()=>NeuroPluginUpdate.request('comecar'));
  assert.deepEqual(posted[2].body,{confirm:true},'No new consent payload once the host has a current receipt');
  data.consent={...data.consent,installation_accepted:false,policy:{...policy,digest:'invalid'}};
  await page.evaluate(()=>NeuroPluginUpdate.read());
  await page.evaluate(()=>NeuroPluginUpdate.request('esperar'));
  assert.equal(posted.length,3,'Invalid policy cannot authorize wait/install/update');
  console.log('PASS: absent-base guard, explicit unchecked consent, polling, fresh-policy reset, exact consent payload, interrupt confirmation, receipt reuse and invalid-policy refusal.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
