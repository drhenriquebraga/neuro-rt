/* Full generated Nidus page, mocked synthetic HTTP data, no clinical inputs. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

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
  const defaultCamera = {yaw:120,pitch:16,dist:3050};
  const crop = [.1,.9,.1,.9,.1,.9];
  const meshCalls = () => calls.filter(call => call.path === '/api/nidus/malhas' || call.path === '/api/nidus/malha');
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
      if (url.pathname.endsWith('/anatomia')) data = {selection:'synthetic-selection',reference:'synthetic',models:[
        {id:'cranio_buti',label:'Buti',channels:[{role:'CT'}],help:{summary:'Estruturas na TC'},
         bindings:[{role:'CT',series_ticket:'synthetic'}],eligibility:{selectable:true,missing_roles:[]}},
        {id:'anatomy_synthseg',label:'SynthSeg',channels:[{role:'T1'}],bindings:[],
         eligibility:{selectable:false,missing_roles:['T1']}}]};
      if (url.pathname.endsWith('/exportar-com-anatomia')) data = {study_id:'synthetic-study',approval_status:'UNAPPROVED'};
    } else if (url.pathname === '/neuro/api/studies/synthetic-study') {
      data = {status:'completed',result:{artifacts:[{kind:'rtstruct',artifact_id:'synthetic-rtstruct'}]}};
    } else if (url.pathname === '/api/nidus/tubos') {
      const body = request.postDataJSON();
      calls.push({path:url.pathname,body});
      data = {sessao:'synthetic-session',incidencias:body.incidencias.length,teto:12};
    } else if (url.pathname === '/api/nidus/abrir') {
      calls.push({path:url.pathname,body:request.postDataJSON()});
      data = {chave:'synthetic',forma:[21,17,13],espacamento:[1,1,1],modalidade:'CT',
        passos:{256:30/256,512:30/512,768:30/768,1024:30/1024},lado_util:512,
        telas:{0:[17,13],1:[21,13],2:[21,17]},
        geometria:{diag:30,centro:[10.5,8.5,6.5],
          da_caixa:[21,0,0,0,0,17,0,0,0,0,13,0,0,0,0,1],
          para_caixa:[1/21,0,0,0,0,1/17,0,0,0,0,1/13,0,0,0,0,1]}};
    } else if (url.pathname === '/api/nidus/malhas' || url.pathname === '/api/nidus/malha') {
      calls.push({path:url.pathname,body:request.method()==='POST'?request.postDataJSON():null});
      data = {erro:'',malhas:[]};
    } else if (url.pathname === '/api/nidus/eixos') {
      data = {L:[1,0,0],P:[0,1,0],S:[0,0,1]};
    } else if (url.pathname === '/api/nidus/projecao') {
      const side = +url.searchParams.get('lado');
      calls.push({path:url.pathname,side});
      return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="${side}" height="${side}"><rect width="100%" height="100%" fill="#171e2a"/></svg>`});
    } else if (url.pathname === '/api/nidus/corte') {
      return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="210" height="170"><rect width="210" height="170" fill="#171e2a"/><path d="M0 85H210M105 0V170" stroke="#46536b"/></svg>'});
    }
    return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
  });
  try {
    await page.goto('http://127.0.0.1/nidus/projecao');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => ndFecharEscolha());
    const assertSala = async () => {
      assert.equal(await page.evaluate(() => ND3.emSala),true);
      assert.equal(await page.locator('#nd_vista').inputValue(),'sala');
      assert.equal(await page.locator('#nd_3d_cx .ui-seg [data-v="sala"]').getAttribute('aria-checked'),'true');
      assert.equal(await page.locator('#nd_3d_t').textContent(),'Sala');
      assert.equal(await page.locator('#nd_ctl_sala').isVisible(),true);
      assert.equal(await page.locator('#nd_ctl_3d').isVisible(),false);
      assert.deepEqual(await page.evaluate(() => ND3.cam),defaultCamera);
    };
    await assertSala();
    const concept = /a mesma lesão em duas incidências, e onde as duas se cruzam/i;
    assert.match(await page.locator('.nd-cabeca .ui-balao').textContent(),concept);
    assert.doesNotMatch(await page.locator('.nd-cabeca .ui-fn-frase').textContent(),concept);
    assert.equal(await page.locator('.nd-wrap > footer .nd-privacidade').textContent(),'Material de estudo · 100% local. Nenhuma imagem sai desta rede.');
    const resolution = page.getByRole('combobox',{name:'Resolução da projeção'});
    assert.equal(await resolution.isDisabled(),true);
    assert.equal(await page.evaluate(() => ND3.gl?'':ND3.motivo),'','WebGL is required to exercise on-demand meshes');
    const originalAngles = await page.evaluate(() => ND.ver);
    await page.evaluate(() => { ND3.cam={yaw:65,pitch:32,dist:4200}; });
    await page.locator('#nd_sala_padrao').click();
    assert.deepEqual(await page.evaluate(() => ND3.cam),defaultCamera);
    assert.deepEqual(await page.evaluate(() => ND.ver),originalAngles);
    const existing = [{lao:0,cra:0,pontos:[[180,180],[290,190],[260,300]]}];
    await page.evaluate(({savedCrop, incidences}) => {
      sessionStorage.setItem('radai_nidus_v2_synthetic',JSON.stringify({caixa:savedCrop,guardadas:incidences,pontos:[]}));
      ndAbrirSerie({bilhete:'synthetic',modalidade:'CT',origem:'acervo',rotulo:'Fantoma sintético'});
    },{savedCrop:crop,incidences:existing});
    await page.waitForFunction(() => ND.aberta && !ND.abrindo && !ND.projetando && !ND.cruzando);
    await assertSala();
    assert.deepEqual(await page.evaluate(() => ND.caixa),crop);
    assert.equal(await resolution.inputValue(),'1024');
    assert.deepEqual(await resolution.locator('option').evaluateAll(options=>options.map(o=>+o.value)),[256,512,768,1024]);
    const tubeCalls = () => calls.filter(c=>c.path==='/api/nidus/tubos');
    assert.deepEqual(tubeCalls().map(c=>c.body),[{b:'synthetic',lado:1024,incidencias:existing}]);
    const switchResolution = async side => {
      const projection = page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.pathname==='/api/nidus/projecao' && +url.searchParams.get('lado')===side;
      });
      await resolution.selectOption(String(side));
      await projection;
      await page.waitForFunction(() => !ND.projetando);
      assert.equal(await page.locator('#nd_svg').getAttribute('viewBox'),'0 0 1024 1024');
      const alignment = await page.evaluate(side => {
        const img = ndEl('nd_proj').getBoundingClientRect(), svg = ndEl('nd_svg').getBoundingClientRect();
        return [img.left+img.width*.5/side-svg.left-svg.width*.5/1024,
          img.bottom-img.height*.5/side-svg.bottom+svg.height*.5/1024];
      },side);
      assert.ok(alignment.every(error=>Math.abs(error)<.001),JSON.stringify(alignment));
    };
    await switchResolution(256);
    assert.match(await page.locator('#nd_passo').textContent(),/0,12 mm/);
    const low = await page.evaluate(() => {
      const r = ndEl('nd_svg').getBoundingClientRect();
      function at(x,y){ return {clientX:r.left+x*r.width/1024,clientY:r.top+y*r.height/1024,preventDefault(){}}; }
      ndPressionar(at(380,380)); ndArrastar(at(480,395)); ndArrastar(at(445,500)); ndSoltar();
      return JSON.parse(JSON.stringify(ND.pontos));
    });
    assert.deepEqual(low.map(p=>p.map(Math.round)),[[380,380],[480,395],[445,500]]);
    await switchResolution(512);
    await switchResolution(768);
    assert.match(await page.locator('#nd_passo').textContent(),/interpolação/);
    assert.deepEqual(await page.evaluate(() => ND.pontos),low);
    assert.deepEqual(await page.evaluate(() => ND.guardadas.map(({lao,cra,pontos})=>({lao,cra,pontos}))),existing);
    assert.equal(tubeCalls().length,1,'resolution must not invalidate the consensus');
    const mixed = [...existing,{lao:22,cra:12,pontos:low}];
    const mixedCalculation = page.waitForResponse(response=>new URL(response.url()).pathname==='/api/nidus/tubos');
    await page.evaluate(saved => { ND.guardadas=saved; ndCalcular(); },mixed);
    await mixedCalculation;
    await page.waitForFunction(() => !ND.cruzando);
    assert.deepEqual(tubeCalls().at(-1).body,{b:'synthetic',lado:1024,incidencias:mixed});
    await page.evaluate(() => ndAbrirSerie({bilhete:'synthetic',modalidade:'CT',origem:'acervo',rotulo:'Fantoma sintético'}));
    await page.waitForFunction(() => ND.aberta && !ND.abrindo && !ND.projetando && !ND.cruzando);
    assert.equal(await resolution.inputValue(),'768');
    assert.deepEqual(tubeCalls().at(-1).body,{b:'synthetic',lado:1024,incidencias:mixed});
    await switchResolution(1024);
    await page.evaluate(() => { ND.guardadas=[]; ND.pontos=[]; ND.sessao=null; ndRegistrar('synthetic-reset'); ndPintarMarca(); ndPintarGuardadas(); });
    assert.equal(meshCalls().length,0,'opening a saved crop in Sala must not request meshes');
    const meshReply = page.waitForResponse(response => new URL(response.url()).pathname==='/api/nidus/malhas');
    await page.locator('#nd_3d_cx .ui-seg [data-v="3d"]').click();
    await meshReply;
    assert.equal(await page.evaluate(() => ND3.emSala),false);
    assert.equal(await page.locator('#nd_vista').inputValue(),'3d');
    assert.equal(await page.locator('#nd_ctl_3d').isVisible(),true);
    assert.equal(await page.locator('#nd_ctl_sala').isVisible(),false);
    assert.equal(meshCalls().length,1);
    assert.equal(meshCalls()[0].body.b,'synthetic');
    await page.evaluate(() => {
      ND3.cam={yaw:65,pitch:32,dist:4200};
      ndAbrirSerie({bilhete:'synthetic',modalidade:'CT',origem:'acervo',rotulo:'Fantoma sintético'});
    });
    await page.waitForFunction(() => ND.aberta && !ND.abrindo && !ND.projetando);
    await assertSala();
    await page.evaluate(() => { ND_CX={}; ndCaixaSoltar(); });
    await page.waitForFunction(() => !ND.projetando);
    assert.equal(meshCalls().length,1,'reopening or releasing the crop in Sala must not request meshes');
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
    const layouts = [];
    const assertLayout = async name => {
      await page.waitForFunction(() => !document.querySelector('#nd_palco .ui-organico, #nd_mpr .ui-organico'));
      const layout = await page.evaluate(() => {
        const bounds = selector => {
          const r=document.querySelector(selector).getBoundingClientRect();
          return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};
        };
        const panel=ndEl('nd_mpr'), lateral=document.querySelector('.nd-mpr-lateral');
        return {viewport:innerWidth,viewportHeight:innerHeight,colB:bounds('#nd_colB'),top:bounds('.nd-cima'),mpr:bounds('#nd_mpr'),
          panes:bounds('.nd-planos'),legend:bounds('#nd_legenda'),consensus:bounds('.nd-consenso'),
          slider:bounds('#nd_temperatura'),lateral:bounds('.nd-mpr-lateral'),
          edit:bounds('#nd_cons_editar'),export:bounds('#nd_cons_exportar'),
          overflow:panel.scrollWidth-panel.clientWidth,lateralOverflow:lateral.scrollWidth-lateral.clientWidth};
      });
      const detail=JSON.stringify(layout);
      assert.ok(layout.top.bottom<=layout.mpr.top,detail);
      assert.ok(layout.consensus.top>=layout.legend.bottom-1,detail);
      assert.ok(layout.lateral.left>=layout.panes.left+layout.panes.width/2,detail);
      assert.ok(layout.consensus.left>=layout.mpr.left && layout.consensus.right<=layout.mpr.right+1,detail);
      assert.ok(layout.consensus.bottom<=layout.mpr.bottom+1,detail);
      assert.ok(layout.slider.width>0 && layout.slider.width<=150,detail);
      assert.ok(layout.overflow<=1 && layout.lateralOverflow<=1,detail);
      if(layout.viewport>=1100){
        for(const button of [layout.edit,layout.export]){
          assert.ok(button.top>=Math.max(0,layout.colB.top) && button.bottom<=Math.min(layout.viewportHeight,layout.colB.bottom)+1,detail);
          assert.ok(button.left>=layout.colB.left && button.right<=layout.colB.right+1,detail);
        }
      }
      layouts.push({name,...layout});
      await page.screenshot({path:path.join(root,'runtime/test-tmp/nidus-consensus-'+name+'.png'),fullPage:true});
    };
    await assertLayout('desktop');
    await page.setViewportSize({width:1280,height:720});
    await page.waitForTimeout(180);
    await assertLayout('compact720');
    await page.setViewportSize({width:1024,height:768});
    await page.waitForTimeout(180);
    await assertLayout('tablet');
    await page.setViewportSize({width:1280,height:800});
    await page.waitForTimeout(180);
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
    await page.locator('#nd_cons_anatomia').evaluate(input => input.click());
    await page.locator('#nd_cons_anatomia_painel input[value="cranio_buti"]').waitFor();
    assert.equal(await page.locator('#nd_cons_anatomia_painel input[value="anatomy_synthseg"]').isDisabled(),true);
    assert.equal(await page.locator('#nd_cons_exportar').isDisabled(),true);
    await page.locator('#nd_cons_anatomia_painel input[value="cranio_buti"]').evaluate(input => input.click());
    await page.locator('#nd_cons_exportar').click();
    await page.locator('#nd_cons_entrega_link').waitFor();
    const joint = calls.find(c=>c.path.endsWith('/exportar-com-anatomia'));
    assert.deepEqual(joint.body,{s:'synthetic-session',temperatura:50,editado:true,selection:'synthetic-selection',modelos:['cranio_buti']});
    assert.equal(await page.locator('#nd_cons_entrega_link').getAttribute('href'),'/neuro/api/studies/synthetic-study/artifacts/synthetic-rtstruct');
    await page.screenshot({path:path.join(root,'runtime/test-tmp/nidus-consensus-chrome.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({ok:true,checks:['initial_sala','default_camera_reset','concept_in_help','privacy_footer','four_raster_resolutions','physical_raster_alignment','legacy_and_mixed_drawings','restore_resolution_and_consensus','saved_crop_without_meshes','explicit_3D_requests_meshes','reopen_restores_sala','crop_release_without_meshes','disabled_before_incidence','maximize_3_axes','restore_pane_identity','retain_3D_and_zoom','compact_consensus_desktop_tablet','temperature_endpoints','empty_feedback','edit_native_index','fresh_token','undo','joint_nidus_anatomy_delivery'],layouts,pageErrors:errors.length},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
