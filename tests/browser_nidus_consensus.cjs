/* Full generated Nidus page, mocked synthetic HTTP data, no clinical inputs. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const htmlPath = path.join(root, 'runtime/test-tmp/nidus-browser.html');
  const python = process.env.NEURO_HOST_PYTHON || 'C:/RADIOTERAPIA_AI/LOCAL_SUITE/_montagem/LOCAL_SUITE/python/python.exe';
  const host = process.env.NEURO_HOST_ROOT || path.resolve(root,'../AUTO_CONTORNO');
  const source = "import sys,pathlib;sys.path.insert(0,sys.argv[1]+'/tools');import _componentes;_componentes.ligar_caminho(sys.argv[1],extras=(sys.argv[2]+'/app',));import radai_nidus_screen as s;p=pathlib.Path(sys.argv[3]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s.radai_menu.aplicar(s.pagina(),'nidus_projecao'),encoding='utf-8')";
  const generated=spawnSync(python,['-I','-B','-c',source,host,root,htmlPath],{encoding:'utf8',timeout:30000});
  assert.equal(generated.status,0,generated.stderr||String(generated.error));
  const html = fs.readFileSync(htmlPath, 'utf8');
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:800}, acceptDownloads:true});
  const errors = [], calls = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.hostname !== '127.0.0.1') return route.abort();
    if (url.pathname === '/nidus/projecao') return route.fulfill({contentType:'text/html',body:html});
    let data = {};
    if (url.pathname === '/neuro/api/status') data = {token:'synthetic-token'};
    if (url.pathname === '/api/nidus/linhas') {
      const axis = +url.searchParams.get('eixo'), pos = +url.searchParams.get('pos');
      data = {largura:210,altura:170,indice:Math.round(pos*([21,17,13][axis]-1)),
        camadas:[{qual:'consenso',segmentos:[[[30,30],[170,130]]]}],consenso_vazio:url.searchParams.get('temperatura')==='100'};
      calls.push({path:url.pathname,temperature:+url.searchParams.get('temperatura')});
    } else if (url.pathname.startsWith('/api/nidus/consenso')) {
      const body = request.postDataJSON();
      calls.push({path:url.pathname,body,token:request.headers()['x-neuro-token']});
      data = {candidate:'synthetic',revision:2,edited:true,empty:false,approval_status:'UNAPPROVED'};
    } else if (url.pathname === '/api/nidus/corte') {
      return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="210" height="170"><rect width="210" height="170" fill="#171e2a"/><path d="M0 85H210M105 0V170" stroke="#46536b"/></svg>'});
    }
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  try {
    await page.goto('http://127.0.0.1/nidus/projecao');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => {
      ndFecharEscolha(); ND.b='synthetic';ND.chave='synthetic';ND.aberta=true;ND.forma=[21,17,13];
      ND.sessao=null;ndConsControles();
    });
    assert.equal(await page.locator('#nd_max0').isDisabled(),true);
    await page.evaluate(() => {
      ND.sessao='synthetic-session';ND.guardadas=[{lao:0,cra:0,pontos:[[10,10],[20,10],[20,20]]}];
      ND.seguir=false;ND.zoom={k:2,x:-30,y:-40};ND3.cam={yaw:120,pitch:16,dist:3050};
      ndConsControles();ndPintarGuardadas();[0,1,2].forEach(ndCorte);
      window.originalPanes=[0,1,2].map(a=>ndEl('nd_pane'+a));window.original3D=ND3.canvas;
    });
    for (const axis of [0,1,2]) {
      await page.locator('#nd_max'+axis).click();
      assert.equal(await page.evaluate(a => ndEl('nd_mpr_main').firstElementChild===window.originalPanes[a],axis),true);
      assert.equal(await page.locator('#nd_palco').isVisible(),false);
      assert.equal(await page.evaluate(() => ND3.canvas===window.original3D),true);
      const box = await page.locator('#nd_pp'+axis).boundingBox();
      assert.ok(box.width>200 && box.height>200,JSON.stringify(box));
    }
    await page.locator('#nd_layout_original').click();
    assert.equal(await page.locator('#nd_palco').isVisible(),true);
    assert.equal(await page.evaluate(() => [0,1,2].every(a=>ndEl('nd_pane'+a)===originalPanes[a] && ndEl('nd_home'+a).previousElementSibling===originalPanes[a])),true);
    assert.equal(await page.evaluate(() => ND.zoom.k),2);
    assert.deepEqual(await page.evaluate(() => ND.zoom),{k:2,x:-30,y:-40});
    await page.evaluate(() => ndTemperatura(0));
    await page.waitForFunction(() => ndEl('nd_temperatura_v').textContent==='0');
    await page.waitForTimeout(220);
    await page.evaluate(() => ndTemperatura(100));
    await page.waitForTimeout(220);
    assert.ok(calls.some(c=>c.temperature===0));assert.ok(calls.some(c=>c.temperature===100));
    assert.equal(await page.locator('#nd_cons_vazio').isVisible(),true);
    await page.evaluate(() => ndTemperatura(50));await page.waitForTimeout(220);
    await page.locator('#nd_cons_editar').click();
    await page.waitForFunction(() => ND.consensoEditavel && !ND.consensoBusy);
    assert.equal(await page.locator('#nd_temperatura').isDisabled(),true);
    await page.locator('#nd_max1').click();
    await page.waitForFunction(() => Number.isInteger(ND.consIndices[1]));
    await page.locator('#nd_pp1 .ui-organico').waitFor({state:'detached'});
    const bounds = await page.locator('#nd_ed1').boundingBox();
    const x=bounds.x+bounds.width*.3,y=bounds.y+bounds.height*.3;
    await page.mouse.move(x,y);await page.mouse.down();
    const traceStart=await page.evaluate(({x,y})=>({trace:ND.consTrace,index:ND.consIndices[1],position:ND.planos[1],classes:ndEl('nd_pp1').className,viewbox:ndEl('nd_ed1').getAttribute('viewBox'),hit:document.elementFromPoint(x,y)?.outerHTML.slice(0,200)}),{x,y});
    await page.mouse.move(x+40,y);await page.mouse.move(x+40,y+40);await page.mouse.move(x,y+40);await page.mouse.up();
    await page.waitForFunction(() => !ND.consensoBusy);
    await page.waitForTimeout(100);
    const edit = calls.find(c=>c.path.endsWith('/editar'));
    assert.ok(edit,'manual pointer edit did not call the API: '+JSON.stringify(traceStart));
    assert.equal(edit.token,'synthetic-token');assert.equal(edit.body.eixo,1);assert.equal(edit.body.indice,8);
    assert.ok(edit.body.pontos.length>=3 && edit.body.pontos.every(p=>p.every(v=>Number.isFinite(v)&&v>=0&&v<=1)));
    await page.locator('#nd_cons_undo').click();
    await page.waitForFunction(() => !ND.consensoBusy);
    assert.ok(calls.some(c=>c.path.endsWith('/desfazer')));
    const layout=await page.evaluate(()=>({top:document.querySelector('.nd-cima').getBoundingClientRect().bottom,
      bottom:ndEl('nd_mpr').getBoundingClientRect().top}));
    assert.ok(layout.top<=layout.bottom,JSON.stringify(layout));
    await page.screenshot({path:path.join(root,'runtime/test-tmp/nidus-consensus-chrome.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    await page.setViewportSize({width:1024,height:768});
    await page.waitForTimeout(180);
    const compact=await page.evaluate(()=>({top:document.querySelector('.nd-cima').getBoundingClientRect().bottom,
      bottom:ndEl('nd_mpr').getBoundingClientRect().top}));
    assert.ok(compact.top<=compact.bottom,JSON.stringify(compact));
    console.log(JSON.stringify({ok:true,checks:['disabled_before_incidence','maximize_3_axes','restore_pane_identity','retain_3D_and_zoom','temperature_endpoints','empty_feedback','edit_native_index','fresh_token','undo'],pageErrors:errors.length},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
