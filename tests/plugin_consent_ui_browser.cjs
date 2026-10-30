const fs=require('fs'), assert=require('assert');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE || 'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage(), posts=[];
  let fail=true;
  await page.route('http://neuro.test/**',route=>{
   const request=route.request(), path=new URL(request.url()).pathname;
   if(path==='/neuro/onboarding')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.NEURO_CONSENT_HTML,'utf8')});
   if(path==='/neuro/api/consent' && request.method()==='POST'){
    posts.push(request.postDataJSON());assert.equal(request.headers()['x-neuro-token'],'synthetic-token');
    return route.fulfill({status:fail?400:200,json:{accepted:!fail}});
   }
   return route.fulfill({json:{token:'synthetic-token'}});
  });
  await page.goto('http://neuro.test/neuro/onboarding');
  const check=page.locator('#neuro-consent-check'), button=page.locator('#neuro-consent-continue');
  assert.equal(await check.isChecked(),false); assert.equal(await button.isDisabled(),true); assert.equal(posts.length,0);
  await check.check();assert.equal(await button.isEnabled(),true);
  await button.click();await page.locator('#neuro-consent-message').filter({hasText:'Não foi possível'}).waitFor();
  assert.equal(posts.length,1);assert.equal(posts[0].accepted,true);assert.equal(posts[0].version,'1.0');assert.match(posts[0].digest,/^[a-f0-9]{64}$/);
  assert((await page.textContent('main')).includes(posts[0].digest));
  assert.equal(await button.isEnabled(),true);
  fail=false;await button.click();await page.waitForURL('http://neuro.test/neuro/');assert.equal(posts.length,2);
  console.log('PASS: unchecked first use, explicit click, policy digest, protected post, failure retry and landing navigation.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
