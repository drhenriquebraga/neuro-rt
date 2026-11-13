/* Shared toolbar, physical brush contract, revision-safe STL and folder flow. */
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require(process.env.NEURO_PLAYWRIGHT_MODULE);
const image='<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#102433"/><circle cx="128" cy="128" r="80" fill="#54768a"/></svg>';
const geometry={centro:[50,50,50],da_caixa:[0,0,100,0,0,100,0,0,100,0,0,0,0,0,0,1],para_caixa:[0,0,.01,0,0,.01,0,0,.01,0,0,0,0,0,0,1]};
function stl(){
 const points=[[40,40,40],[60,40,40],[60,60,40],[40,60,40],[40,40,60],[60,40,60],[60,60,60],[40,60,60]];
 const triangles=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];
 const b=Buffer.alloc(84+50*triangles.length);b.writeUInt32LE(triangles.length,80);
 triangles.forEach((indices,t)=>{
  const p=indices.map(i=>points[i]),a=p[1].map((v,i)=>v-p[0][i]),c=p[2].map((v,i)=>v-p[0][i]);
  const n=[a[1]*c[2]-a[2]*c[1],a[2]*c[0]-a[0]*c[2],a[0]*c[1]-a[1]*c[0]],length=Math.hypot(...n);
  [...n.map(v=>v/length),...p.flat()].forEach((value,i)=>b.writeFloatLE(value,84+t*50+i*4));
 });return b;
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000},reducedMotion:'reduce'}),errors=[],calls=[];
  let revision=1,undo=0,rejectBrush=false,openCount=0,holdMesh=false,releaseMesh=null;
  const rows=[{bilhete:'tof-source',desc:'Synthetic original TOF',modalidade:'MR',cortes:101},
   {bilhete:'cine-source',desc:'Synthetic acquired TWIST',modalidade:'MR',cortes:30},
   {bilhete:'mip-derived',desc:'Synthetic TOF MIP',modalidade:'MR',cortes:30}];
  const metadata={itens:[{bilhete:'tof-source',preferida:true,original:true,tridimensional:true,possivel_tof:true},
   {bilhete:'cine-source',preferida:false},{bilhete:'mip-derived',preferida:false,derivada:true}]};
  const group={id:'folder-temporal',kind:'volume3d',count:3,can_rotate:true,timing_known:true,label:'CINE 1',series_tickets:[{bilhete:'cine-source',origem:'pasta'}]};
  page.on('pageerror',e=>errors.push(e.stack||e.message));
  await page.addInitScript(()=>window.addEventListener('DOMContentLoaded',()=>{window.ndAbrirEscolha=function(){ND.escolhendo=true}},{capture:true,once:true}));
  await page.route('**/*',async route=>{
   const request=route.request(),url=new URL(request.url()),body=request.method()==='POST'?request.postDataJSON():null;
   if(url.pathname==='/nidus/projecao')return route.fulfill({contentType:'text/html',body:fs.readFileSync(process.argv[2],'utf8')});
   calls.push({path:url.pathname,body});
   if(url.pathname==='/neuro/api/status')return route.fulfill({json:{token:'synthetic-token'}});
   if(url.pathname==='/api/nidus/consenso')return route.fulfill({json:{candidate:'candidate-A',revision,undo_available:false,empty:false}});
   if(url.pathname==='/api/nidus/consenso/pincel'){
    assert.equal(body.candidate,'candidate-A');assert.equal(body.revision,revision);
    if(rejectBrush)return route.fulfill({status:409,json:{detail:'Synthetic revision conflict'}});
    revision++;undo++;return route.fulfill({json:{candidate:'candidate-A',revision,undo_available:true,brush:{changed_voxels:10}}});
   }
   if(url.pathname==='/api/nidus/consenso/pincel/desfazer'){
    assert.equal(body.revision,revision);revision++;undo--;
    return route.fulfill({json:{candidate:'candidate-A',revision,undo_available:undo>0}});
   }
   if(url.pathname==='/api/nidus/consenso/malha')return route.fulfill({json:{candidate:'candidate-A',revision,empty:false,triangles:12,
    coordinate_system:'LPS_mm',bounds_lps:[[40,40,40],[60,60,60]],url:'/api/nidus/consenso/malha/download?revision='+revision}});
   if(url.pathname==='/api/nidus/consenso/malha/download'){
    if(holdMesh){holdMesh=false;await new Promise(resolve=>releaseMesh=resolve)}
    return route.fulfill({contentType:'application/octet-stream',body:stl()});
   }
   if(url.pathname==='/api/nidus/linhas')return route.fulfill({json:{largura:256,altura:256,indice:Math.round(Number(url.searchParams.get('pos'))*100),camadas:[]}});
   if(url.pathname==='/api/nidus/malhas')return route.fulfill({json:{malhas:[]}});
   if(url.pathname==='/api/nidus/series-metadata'){assert(!body.ancora,'new folder must not be scoped to the old patient');return route.fulfill({json:metadata})}
   if(url.pathname==='/api/nidus/temporal/folder-discover'){
    assert.equal(body.ancora.bilhete,'tof-source');assert.equal(body.itens.length,3);
    return route.fulfill({json:{groups:[group],auto_select:group.id,selection_required:false,scope:'patient-study'}});
   }
   if(url.pathname==='/api/nidus/temporal/prepare'){assert.equal(body.group,group.id);return route.fulfill({json:{job:'folder-job'}})}
   if(url.pathname==='/api/nidus/temporal/status/folder-job')return route.fulfill({json:{state:'ready',completed:3,total:3,frames:[0,1,2].map(index=>({index,time_seconds:index*.1}))}});
   if(url.pathname==='/api/nidus/abrir'){openCount++;return route.fulfill({json:{chave:'new-source',forma:[101,101,101],modalidade:'MR',hu:false,geometria:geometry,telas:{0:[256,256],1:[256,256],2:[256,256]},osso:{tem:false}}})}
   if(/\/api\/nidus\/(projecao|corte)$/.test(url.pathname)||url.pathname.startsWith('/api/nidus/temporal/frame/'))return route.fulfill({contentType:'image/svg+xml',body:image});
   return route.fulfill({json:{}});
  });
  await page.goto('http://127.0.0.1:18799/nidus/projecao');
  await page.waitForSelector('#nd_dicom_tools');
  await page.evaluate(async geo=>{
   ND.b='static';ND.ultima={bilhete:'static',origem:'pasta'};ND.aberta=true;ND.abrindo=false;ND.sessao='session-A';
   ND.forma=[101,101,101];ND.geo=geo;ND.telas={0:[256,256],1:[256,256],2:[256,256]};ND.caixa=null;
   ndModalidade('MR');ndTravas();ndConsControles();await Promise.all([ndProjetar(),ndCorte(0),ndCorte(1),ndCorte(2)]);
  },geometry);
  assert.equal(await page.locator('#nd_angio_max').count(),0);
  await page.locator('[data-dicom-tool="zoomIn"]').dblclick();assert(await page.locator('#nd_colB').isVisible());
  await page.locator('[data-dicom-tool="brush"]').click();
  await page.waitForFunction(()=>ND.consensoEditavel&&!ND.consensoBusy&&ND.consCandidate==='candidate-A'&&ND.consIndices[0]===50);
  assert.equal(await page.evaluate(()=>ND.consRevision),1);
  await page.locator('#nd_pp0').hover();
  const before=await page.evaluate(()=>({diam:ND.brushDiameter,slice:ND.planos[0],zoom:ND.zoom.k}));
  await page.locator('#nd_pp0').dispatchEvent('wheel',{deltaY:-120,ctrlKey:true,cancelable:true});
  assert.deepEqual(await page.evaluate(()=>({diam:ND.brushDiameter,slice:ND.planos[0],zoom:ND.zoom.k})),{...before,diam:before.diam+.5});
  await page.keyboard.press('.');assert.equal(await page.evaluate(()=>ND.brushDiameter),before.diam+1);
  await page.keyboard.press(',');assert.equal(await page.evaluate(()=>ND.brushDiameter),before.diam+.5);
  await page.locator('[data-dicom-tool="zoomIn"]').click();
  assert.equal(await page.evaluate(()=>NidusBrush.views[0].scale),1.25);
  assert.equal(await page.evaluate(()=>ND.zoom.k),before.zoom,'MPR zoom must not change angiography');
  await page.locator('[data-dicom-tool="pan"]').click();
  const pane=await page.locator('#nd_pp0').boundingBox();
  await page.mouse.move(pane.x+pane.width/2,pane.y+pane.height/2);await page.mouse.down();
  await page.mouse.move(pane.x+pane.width/2+18,pane.y+pane.height/2+12,{steps:3});await page.mouse.up();
  assert.deepEqual(await page.evaluate(()=>({x:NidusBrush.views[0].x,y:NidusBrush.views[0].y})),{x:18,y:12});
  await page.locator('[data-dicom-tool="brush"]').click();
  const brushCalls=calls.filter(c=>c.path==='/api/nidus/consenso/pincel').length;
  await page.mouse.move(pane.x+pane.width/2,pane.y+pane.height/2);await page.mouse.down();
  await page.locator('#nd_ed0').dispatchEvent('pointercancel',{pointerId:1,button:0});await page.mouse.up();
  assert.equal(await page.evaluate(()=>ND.consTrace),null,'cancelled pointer strokes must not remain active');
  assert.equal(calls.filter(c=>c.path==='/api/nidus/consenso/pincel').length,brushCalls);
  async function stroke(){
   const points=await page.evaluate(()=>[.45,.55].map(x=>{const svg=ndEl('nd_ed0'),p=svg.createSVGPoint();p.x=x*256;p.y=128;const c=p.matrixTransform(svg.getScreenCTM());return {x:c.x,y:c.y}}));
   await page.mouse.move(points[0].x,points[0].y);await page.mouse.down();
   assert.deepEqual(await page.evaluate(()=>{const old=ND.planos[0],slider=ndEl('nd_pos0');slider.value='60';slider.dispatchEvent(new Event('input',{bubbles:true}));return {unchanged:ND.planos[0]===old,slider:Number(slider.value)};}),{unchanged:true,slider:50},'a slider change cannot replace the image during a brush stroke');
   await page.mouse.move(points[1].x,points[1].y,{steps:5});await page.mouse.up();
  }
  await stroke();await page.waitForFunction(()=>ND.consRevision===2&&!ND.consensoBusy);
  const add=calls.filter(c=>c.path==='/api/nidus/consenso/pincel').at(-1).body;
  assert.equal(add.raio_mm,(before.diam+.5)/2);assert.equal(add.operacao,'add');assert.equal(add.indice,50);assert.equal(add.eixo,0);
  assert(add.pontos.length>=2);assert(add.pontos.every(p=>p.every(v=>v>=0&&v<=1)));
  assert(Math.abs(add.pontos[0][0]-.45)<.005&&Math.abs(add.pontos[0][1]-.5)<.005,'MPR brush keeps source coordinates after pan and zoom');
  await page.locator('[data-dicom-tool="fit"]').click();
  assert.deepEqual(await page.evaluate(()=>({scale:NidusBrush.views[0].scale,x:NidusBrush.views[0].x,y:NidusBrush.views[0].y})),{scale:1,x:0,y:0});
  await page.waitForFunction(()=>ND3.consensusObj&&ND3.consensusRevision===2);
  assert((await page.evaluate(()=>ND3.consensusBox)).every((value,index)=>Math.abs(value-([.3,.7,.3,.7,.3,.7][index]))<1e-8));
  assert.equal(await page.evaluate(()=>ND.caixa),null,'automatic 3D framing must never change the projection crop');
  assert.equal(await page.evaluate(()=>{const candidate=ND.consCandidate;ND.consCandidate='different-candidate';const crop=nd3RecorteLocal();ND.consCandidate=candidate;return crop}),null,'a different candidate cannot reuse the prior automatic 3D bounds');
  await page.evaluate(()=>nd3Vista('3d'));
  await page.waitForFunction(()=>!!nd3Caixa());
  assert(await page.evaluate(()=>{
   nd3Pintar();const gl=ND3.gl,pixels=new Uint8Array(ND3.canvas.width*ND3.canvas.height*4);
   gl.readPixels(0,0,ND3.canvas.width,ND3.canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
   let red=0;for(let i=0;i<pixels.length;i+=4)if(pixels[i]>70&&pixels[i]>pixels[i+1]*2&&pixels[i]>pixels[i+2]*2)red++;
   return red>100;
  }),'the revision-bound consensus volume must render visible red pixels in 3D');
  await page.waitForFunction(()=>!ND.projetando);
  await page.locator('#nd_pane0 .nd-mpr-title').hover();
  if(process.argv[3]){fs.mkdirSync(process.argv[3],{recursive:true});await page.screenshot({path:path.join(process.argv[3],'nidus-brush-mesh.png'),fullPage:true})}
  await page.locator('[data-dicom-tool="eraser"]').click();await stroke();await page.waitForFunction(()=>ND.consRevision===3&&!ND.consensoBusy);
  assert.equal(calls.filter(c=>c.path==='/api/nidus/consenso/pincel').at(-1).body.operacao,'remove');
  await page.locator('[data-dicom-tool="undo"]').click();await page.waitForFunction(()=>ND.consRevision===4&&!ND.consensoBusy);
  rejectBrush=true;await stroke();await page.waitForFunction(()=>!ND.consensoBusy&&document.getElementById('nd_msg').textContent.includes('Synthetic revision conflict'));
  assert.equal(await page.evaluate(()=>ND.consRevision),4);
  const editorCalls=await page.evaluate(async()=>{
   const calls=[];window.RadaiContourEditor.open=async options=>calls.push(options);
   for(const key of ['measure','window','editor']){document.querySelector('[data-dicom-tool="'+key+'"]').click();await Promise.resolve();await Promise.resolve()}
   return calls;
  });
  assert.deepEqual(editorCalls.map(c=>c.tool),['measure','window','brush']);assert(editorCalls.every(c=>c.b==='static'&&c.source==='thumbnail'));
  const oldMeshRequest=page.waitForRequest(request=>new URL(request.url()).pathname==='/api/nidus/consenso/malha/download');
  holdMesh=true;await page.evaluate(()=>{void NidusBrush.mesh()});await oldMeshRequest;
  await page.evaluate(data=>{
   window.uiVarrerLista=options=>{document.getElementById('nd_series').innerHTML=data.map(options.linha).join('');options.aoFim(data,{final:true})};
   ND.escolhendo=true;ndEl('nd_pasta').value='C:\\SYNTHETIC';ndCarregarPasta();
  },rows);
  await page.waitForFunction(()=>ND.b==='tof-source'&&ND.aberta&&!ND.abrindo&&NidusTemporal.state.folderOffers&&NidusTemporal.state.folderOffers.groups.length===1);
  assert.equal(openCount,1);assert.equal(await page.evaluate(()=>ND3.consensusObj),null,'new source clears the old consensus mesh');
  assert(releaseMesh);releaseMesh();await page.waitForTimeout(80);
  assert.equal(await page.evaluate(()=>ND3.consensusObj),null,'late STL from the previous series must never be reapplied');
  assert.equal(await page.evaluate(()=>ND_IMAGE_CACHE.stats().decoded<=8),true);
  assert.equal(await page.evaluate(()=>ND_IMAGE_CACHE.stats().entries>=72),true);
  await page.locator('#nd_cine_open').click();await page.waitForSelector('.nd-cine-group-list');
  assert.match(await page.locator('.nd-cine-group-list').innerText(),/Synthetic acquired TWIST/);
  await page.locator('.nd-cine-group-list button').click();await page.waitForFunction(()=>NidusTemporal.state.ready);
  assert.equal(await page.locator('#nd_cine_source').textContent(),'Synthetic acquired TWIST');
  assert(!calls.some(c=>c.path==='/api/nidus/temporal/discover'),'folder selection must reuse its detected temporal group');
  assert.equal(await page.evaluate(()=>ND.b),'tof-source');
  await page.evaluate(()=>NidusTemporal.leave());
  const previous=openCount;
  await page.evaluate(()=>{ND.escolhendo=true;NidusFolder.discovered([{bilhete:'a'},{bilhete:'b'}],{itens:['a','b'].map(b=>({bilhete:b,preferida:true,original:true,tridimensional:true,possivel_tof:true}))},'C:\\SYNTHETIC',true)});
  assert.equal(openCount,previous,'ambiguous TOF choices require explicit selection');
  await page.evaluate(()=>NidusFolder.discovered([{bilhete:'a'},{bilhete:'uninspected'}],{itens:[{bilhete:'a',preferida:true,original:true,tridimensional:true,possivel_tof:true}]},'C:\\SYNTHETIC',true));
  assert.equal(openCount,previous,'partial metadata must not auto-select a potentially ambiguous source');
  assert.deepEqual(errors,[]);
  console.log('PASS: shared NIDUS tools, brush/erase/undo revisions, physical diameter shortcuts, LPS mesh, unchanged crop, complete rotation cache and anchored folder TOF/CINE.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
