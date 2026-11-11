const fs = require('fs');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE);
const assert = require('assert').strict;
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.NEURO_BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport: {width: 1600, height: 1000}});
    const errors = [], calls = [], projectionSides = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.addInitScript(() => window.addEventListener('DOMContentLoaded', () => {
      window.ndAbrirEscolha = function(){};
    }, {capture: true, once: true}));
    const html = fs.readFileSync(process.argv[2], 'utf8');
    const sample = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><defs><radialGradient id="g"><stop stop-color="#b8c8d8"/><stop offset="1" stop-color="#101a2b"/></radialGradient></defs><rect width="256" height="256" fill="url(#g)"/><text x="128" y="128" text-anchor="middle" fill="white" font-size="12">Synthetic fixture</text></svg>';
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/nidus/projecao') return route.fulfill({contentType:'text/html',body:html});
      if (/\/api\/nidus\/(projecao|corte)$/.test(url.pathname)) {
        if(url.pathname.endsWith('/projecao'))projectionSides.push(Number(url.searchParams.get('lado')));
        return route.fulfill({contentType:'image/svg+xml',body:sample});
      }
      if (url.pathname === '/api/nidus/linhas') return route.fulfill({json:{largura:256,altura:256,indice:20,
        camadas:[{qual:'inc',i:0,segmentos:[[[30,30],[200,200]]]},{qual:'consenso',segmentos:[[[100,100],[160,100]],[[160,100],[160,160]]]}]}});
      if (url.pathname === '/api/nidus/centro') return route.fulfill({json:{vazio:false,posicoes:[.25,.4,.75]}});
      calls.push(url.pathname);
      return route.fulfill({json:{}});
    });
    await page.goto('http://127.0.0.1:18799/nidus/projecao');
    await page.waitForSelector('#nd_aux_grid');
    await page.evaluate(() => {
      ND.b='synthetic'; ND.aberta=true; ND.forma=[40,60,80]; ND.sessao='synthetic-session';
      ND.planos={0:.5,1:.5,2:.5};ND.guardadas=[{lao:0,cra:0,pontos:[[0,0],[1,0],[1,1]]}];
      ndConsControles();ndPintarPlanos();ndAjustarTela();ndProjetar();
    });
    assert.equal(await page.locator('#nd_resolucao').count(),0);
    const pointRoundTrip=()=>page.evaluate(()=>{
      const svg=ndEl('nd_svg'),point=svg.createSVGPoint();point.x=123;point.y=765;
      const client=point.matrixTransform(svg.getScreenCTM());
      return ndPonto({clientX:client.x,clientY:client.y});
    });
    const samePoint=actual=>{assert(Math.abs(actual[0]-123)<.01);assert(Math.abs(actual[1]-765)<.01);};
    samePoint(await pointRoundTrip());
    await page.evaluate(()=>ndAplicar({resolucao:256},false));
    assert.equal(await page.evaluate(()=>ND.resolucao),1024);
    await page.evaluate(()=>ndProjetar(true));
    await page.waitForFunction(()=>!ND.previaNoAr);
    await page.evaluate(()=>ndAngulo(10,5));
    await page.waitForFunction(()=>!ND.projetando);
    assert(projectionSides.includes(256));assert.equal(projectionSides.at(-1),1024);
    for (const id of ['nd_3d_cx','nd_pane0','nd_pane1','nd_pane2']) assert(await page.locator('#'+id).isVisible(),id);
    const room=await page.locator('#nd_3d_cx').boundingBox(), axial=await page.locator('#nd_pane0').boundingBox();
    const coronal=await page.locator('#nd_pane1').boundingBox(), sagittal=await page.locator('#nd_pane2').boundingBox();
    assert(Math.abs(room.y-axial.y)<2 && Math.abs(coronal.y-sagittal.y)<2 && coronal.y>room.y+room.height-1);
    assert(Math.abs(room.x-coronal.x)<2 && Math.abs(axial.x-sagittal.x)<2);
    await page.locator('#nd_pp0').dblclick();
    assert.equal(await page.evaluate(()=>ND.principal),0);
    assert.equal(await page.locator('#nd_pane0').evaluate(el=>el.parentElement.id),'nd_mpr_main');
    assert.equal(await page.locator('#nd_palco').evaluate(el=>el.parentElement.id),'nd_proj_aux');
    samePoint(await pointRoundTrip());
    const before=await page.evaluate(()=>({pos:ND.planos[0],zoom:ND.zoom.k}));
    await page.locator('#nd_pp0').dispatchEvent('wheel',{deltaY:120,cancelable:true});
    const after=await page.evaluate(()=>({pos:ND.planos[0],zoom:ND.zoom.k}));
    assert(after.pos>before.pos);assert.equal(after.zoom,before.zoom);
    await page.locator('#nd_pp0').dispatchEvent('wheel',{deltaY:0,deltaX:120,cancelable:true});
    assert.equal(await page.evaluate(()=>ND.planos[0]),after.pos);
    await page.locator('#nd_pp1').dblclick();assert.equal(await page.evaluate(()=>ND.principal),1);
    await page.locator('#nd_pp2').dblclick();assert.equal(await page.evaluate(()=>ND.principal),2);
    await page.locator('#nd_angio_max').click();
    assert.equal(await page.evaluate(()=>ND.principal),null);assert(await page.locator('#nd_colB').isHidden());
    samePoint(await pointRoundTrip());
    await page.locator('#nd_angio_max').click();assert(await page.locator('#nd_colB').isVisible());
    await page.locator('#nd_cons_centrar').click();
    await page.waitForFunction(()=>ND.planos[0]===.25&&ND.planos[1]===.4&&ND.planos[2]===.75);
    await page.route('**/api/nidus/centro?**',route=>route.fulfill({json:{vazio:true,voxels:0}}));
    await page.locator('#nd_cons_centrar').click();
    assert.deepEqual(await page.evaluate(()=>Object.values(ND.planos)),[.25,.4,.75]);
    await page.evaluate(()=>{ND.hu=false;ndModalidade('MR')});
    assert(await page.locator('.nd-osso').isHidden());
    const names=await page.evaluate(()=>['Anatomia','Tecidos'].map(text=>window.radaiFrase?window.radaiFrase(text):text));
    await page.waitForFunction(expected=>document.querySelector('#nd_jan [data-j="osso"]').textContent===expected,names[0]);
    assert.equal(await page.locator('#nd_jan [data-j="parenquima"]').innerText(),names[1]);
    await page.waitForFunction(()=>document.querySelector('.nd-consenso-linha')&&getComputedStyle(document.querySelector('.nd-consenso-linha')).stroke==='rgb(255, 36, 59)');
    const color=await page.evaluate(()=>getComputedStyle(document.querySelector('.nd-consenso-linha')).stroke);
    assert.equal(color,'rgb(255, 36, 59)');
    await page.locator('#nd_inc_details > summary').click();assert(await page.locator('#nd_guardadas').isVisible());
    await page.locator('#nd_inc_details > summary').click();
    await page.screenshot({path:process.argv[3] || process.argv[2]+'.png',fullPage:true});
    assert.deepEqual(errors,[]);
    process.stdout.write('PASS: A grid, three MPR swaps, angio maximize/restore, slice wheel, center and incidence access.\n');
  } finally {await browser.close();}
})().catch(error=>{process.stderr.write(String(error.stack||error));process.exitCode=1;});
