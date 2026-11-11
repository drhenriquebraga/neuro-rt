const fs=require('fs'),assert=require('assert');
const {chromium}=require(process.argv[3]);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.argv[4]});
 try{
  const page=await browser.newPage();
  const rows=[{bilhete:'mip',desc:'TOF MIP',modalidade:'MR',cortes:20},{bilhete:'source',desc:'AXI3DTOF3SLABFSMTASSET',modalidade:'MR',cortes:100},{bilhete:'other',desc:'Other study',modalidade:'MR',cortes:30}];
  await page.route('http://nidus.test/**',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/picker')return route.fulfill({contentType:'text/html',body:'<div id="nd_escolha"><div id="nd_tof_sugestao"></div><div id="nd_series"></div><div id="nd_acervo"></div></div><div id="nd_busca"></div><input id="nd_pasta"><button id="nd_escolher"></button>'});
   assert.equal(url.pathname,'/api/nidus/series-metadata','unexpected import or image request');
   const request=route.request().postDataJSON();
   assert.equal(request.ancora.bilhete,'explicit-reference');
   return route.fulfill({json:{itens:rows.map(row=>({bilhete:row.bilhete,preferida:row.bilhete==='source',tridimensional:true}))}});
  });
  await page.goto('http://nidus.test/picker');
  await page.evaluate(rows=>{
   window.rows=rows;window.ND={porB:{},ultima:{bilhete:'explicit-reference',origem:'pasta'},escolhendo:true};
   window.ND_MODALIDADES=['CT','MR'];window.ND_MIN_CORTES=20;window.opened=[];
   window.ndEl=id=>document.getElementById(id);window.ndEsc=text=>String(text||'').replace(/</g,'&lt;');
   window.ndAbrirSerie=series=>opened.push(series);window.radaiRetraduzir=()=>{};
   window.ndFrases=(target,texts)=>target.textContent=texts.join(' ');
   window.uiVarrerLista=options=>{document.getElementById(options.alvo).innerHTML=rows.map(options.linha).join('');options.aoFim(rows);};
   window.uiTabelaAcervo=(id,options)=>{document.getElementById(id).innerHTML='<table><tbody>'+rows.map((row,i)=>'<tr data-i="'+i+'"><td>'+row.desc+'</td></tr>').join('')+'</tbody></table>';options.aoCarregar(rows);return{linhas:()=>rows};};
   window.uiPopupSerie=()=>({abrir(){},fechar(){}});
  },rows);
  await page.addScriptTag({content:fs.readFileSync(process.argv[2]+'/picker.js','utf8')});
  await page.evaluate(()=>ndListar('SYNTHETIC_FOLDER'));
  await page.locator('#nd_series [data-nd-tof]').waitFor();
  assert.equal(await page.locator('#nd_series [data-nd-tof]').count(),1);
  assert.equal(await page.locator('#nd_series [data-b="mip"] [data-nd-tof]').count(),0);
  assert.equal(await page.evaluate(()=>ND.ultima.bilhete),'explicit-reference');
  assert.equal(await page.evaluate(()=>opened.length),0);
  await page.evaluate(()=>ndAbrirEscolha());
  await page.locator('#nd_acervo [data-nd-tof]').waitFor();
  assert.equal(await page.locator('#nd_acervo tr[data-i="1"] [data-nd-tof]').count(),1);
  assert.equal(await page.evaluate(()=>opened.length),0);
  await page.evaluate(()=>ndEscolher('mip'));
  assert.equal(await page.evaluate(()=>opened.length),1);
  assert.equal(await page.evaluate(()=>opened[0].bilhete),'mip','explicit selection changed by suggestion');
  console.log('PASS TOF hints prefer source, do not import, keep explicit choice and keep archive rows aligned');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
