// Real browser navigation through all five synthetic, local test-phase entries.
const fs=require('fs'),assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE||'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.env.NEURO_TESTING_FIXTURE,'utf8'));
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage();let posts=0,failNext=true;
  await page.route('http://neuro.test/**',async route=>{
   const request=route.request(),url=new URL(request.url()),path=url.pathname;
   if(path==='/neuro/')return route.fulfill({contentType:'text/html',body:fixture.landing});
   if(path.startsWith('/neuro/testing/'))return route.fulfill({contentType:'text/html',body:fixture.pages[path.split('/').pop()]});
   if(path.startsWith('/neuro/api/testing/')){
    const tool=path.split('/').pop(),policy=fixture.policies[tool];
    if(request.method()==='GET')return route.fulfill({json:{policy,token:'synthetic'}});
    assert.deepEqual(request.postDataJSON(),{accepted:true,version:policy.version,digest:policy.digest});
    assert.equal(request.headers()['x-neuro-token'],'synthetic');posts++;
    if(failNext){failNext=false;return route.fulfill({status:503,json:{detail:'Synthetic failure'}});}
    return route.fulfill({json:{route:'/neuro/'+tool}});
   }
   if(fixture.policies[path.split('/').pop()])return route.fulfill({contentType:'text/html',body:'<h1>Ferramenta aberta</h1><a href="/neuro/">Voltar</a>'});
   return route.fulfill({json:{state:'ready',release_check:{state:'current'},update:{state:'idle'}}});
  });
  await page.goto('http://neuro.test/neuro/');
  assert.equal(await page.locator('.md-grade > a.md-fer').count(),5);
  assert.equal(await page.locator('.md-grade > [aria-disabled="true"]').count(),0);
  for(const tool of Object.keys(fixture.pages)){
   const card=page.locator('a.md-fer[href="/neuro/testing/'+tool+'"]');
   assert((await card.textContent()).includes('[fase de testes]'));await card.focus();assert(await card.evaluate(e=>e===document.activeElement));
   await card.click();await page.locator('#testing-dialog').waitFor({state:'visible'});
   assert.equal(await page.locator('#testing-check').isChecked(),false);
   assert.equal(await page.locator('#testing-accept').isDisabled(),true);
   await page.locator('#testing-cancel').click();await page.waitForURL('**/neuro/');
   await page.locator('a[href="/neuro/testing/'+tool+'"]').click();
   await page.locator('#testing-check').check();await page.locator('#testing-accept').click();
   if(tool===Object.keys(fixture.pages)[0]){
    await page.locator('#testing-message').filter({hasText:'Não foi possível'}).waitFor();
    assert.equal(await page.locator('#testing-check').isDisabled(),false);await page.locator('#testing-accept').click();
   }
   await page.waitForURL('**/neuro/'+tool);assert.equal(await page.locator('h1').textContent(),'Ferramenta aberta');
   await page.goto('http://neuro.test/neuro/testing/'+tool);
   assert.equal(await page.locator('#testing-check').isChecked(),false,'Every card entry presents a fresh choice');
   await page.keyboard.press('Escape');await page.waitForURL('**/neuro/');
  }
  assert.equal(posts,6);console.log('PASS: five active native cards, focus, fresh modal per entry, cancel/Escape, explicit acceptance, failure retry and exact protected payloads.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
