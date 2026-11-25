/* Real host controls with synthetic DICOM tickets and model eligibility. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE || 'playwright');
const web = path.resolve(__dirname, '../web');
const html = path.resolve(process.argv[2]);
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==','base64');
const rows = [
  {bilhete:'t1c',modalidade:'MR',role:'T1c',desc:'Fantoma coronal pós',cortes:7,numero:1},
  {bilhete:'flair',modalidade:'MR',role:'FLAIR',desc:'Fantoma FLAIR',cortes:7,numero:2},
  {bilhete:'head',modalidade:'CT',role:'CT',desc:'Fantoma TC',cortes:7,numero:3},
  {bilhete:'pre',modalidade:'MR',role:'T1',desc:'Fantoma T1 pré',cortes:7,numero:4},
  {bilhete:'other-frame',modalidade:'MR',role:'T1',desc:'Fantoma quadro diferente',cortes:7,numero:5},
];
function selection(data) {
  const series = data.tickets.map(id => {
    const r = rows.find(r=>r.bilhete===id);
    return {ticket:id,modality:r.modalidade,group_key:'phantom',description:r.desc,series_number:r.numero,
      patient_name:'Demo Patient',patient_id:'PHANTOM-01',study_date:'20260105',slice_thickness:2,
      slice_count:r.cortes,preview_header:[['Protocolo','Fantoma'],['Matriz','224 × 224']],
      sequence_candidates:[{role:r.role,certainty:'certain'}]};
  });
  if(data.identify_only)return {series,unreadable:[]};
  assert(series.every(s=>s.modality===series.find(t=>t.ticket===data.reference).modality));
  const model = (id,role,available,ticket=data.reference) => ({id,label:id,channels:[{role}],reference_role:role,
    bindings:available?[{role,series_ticket:ticket,association_source:'suggested',certainty:'certain'}]:[],
    eligibility:{selectable:available,missing_roles:available?[]:[role],technical_reasons:[]}});
  const output=(id,label=id)=>({class_id:id,label,roi_name:label});
  const outputs={snc_rm_simples:[output('oar_stem','Brainstem_ai')],snc_rm_avancado:[output('stem','Brainstem_ai'),output('vent','Ventricle_ai')],
    anatomy_cerebra_ants:[output('cstem','CBrainstem_ai')],MRI_GBM:[output('tumour','GBM_ai')],MRI_Meningioma:[output('men','Meningioma_ai')],MRI_LGGlioma:[output('lgg','LGG_ai')]};
  if(data.reference==='head')return {series,protocols:[{id:'cranio_buti',model_id:'cranio_buti'}],outputs:{cranio_buti:[output('optic','Optic_ai')]},models:[model('cranio_buti','CT',true)]};
  const t1=data.reference==='t1c';
  return {series,outputs,protocols:[{id:'snc_rm_simples',model_id:'anatomy_synthseg'},{id:'snc_rm_avancado',model_id:'anatomy_synthseg'},
    {id:'anatomy_cerebra_ants',model_id:'anatomy_cerebra_ants'}],models:[model('anatomy_synthseg','T1',t1),model('MRI_GBM','T1c',t1),
      model('MRI_Meningioma','T1c',t1),model('MRI_LGGlioma','FLAIR',!t1),
      {...model('anatomy_cerebra_ants','T1',true,'pre'),binding_options:{T1:['pre','t1c']}}]};
}
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE});
  try {
    const page=await browser.newPage({viewport:{width:1280,height:900},reducedMotion:'reduce'});
    page.setDefaultTimeout(9500);
    const errors=[],sent=[],requests=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>localStorage.setItem('radai_idioma','en'));
    await page.route('**/*',async route=>{
      const req=route.request(), url=new URL(req.url()), p=url.pathname;
      if(url.host!=='neuro.test')return route.abort();
      if(p==='/neuro/anatomia')return route.fulfill({contentType:'text/html',path:html});
      if(['/neuro/process.js','/neuro/process.css','/neuro/study.css'].includes(p))return route.fulfill({path:path.join(web,path.basename(p)),contentType:p.endsWith('.js')?'text/javascript':'text/css'});
      if(p==='/neuro/api/status')return route.fulfill({json:{token:'test'}});
      if(p==='/api/varrer/iniciar'){
        const d=req.postDataJSON(), modality=d.opcoes.modalidades[0];
        requests.push(d.pasta);
        assert.deepEqual(d.opcoes.modalidades,[modality]);
        assert.equal(d.pasta,'/fantoma/'+modality);
        return route.fulfill({json:{v:'sample',fim:true,final:true,linhas:rows.filter(r=>r.modalidade===modality)}});
      }
      if(p==='/neuro/api/selection'){
        const d=req.postDataJSON();assert.equal(d.category,'unified');assert.equal(req.headers()['x-neuro-token'],'test');
        return route.fulfill({json:selection(d)});
      }
      if(p==='/neuro/api/studies'){const request=req.postDataJSON();sent.push(request);return route.fulfill({status:202,json:{request_id:request.request_id,studies:request.studies.map(s=>({id:s.study_id,status:'queued'}))}});}
      if(p==='/neuro/api/protocols'){
        const {name,modality,plan}=req.postDataJSON();
        assert.deepEqual(plan.findings,['MRI_GBM','MRI_Meningioma']);
        assert.equal(JSON.stringify(plan).includes('PHANTOM'),false);
        return route.fulfill({json:{protocols:[{id:'local-1',name,modality,plan}]}});
      }
      if(p==='/api/lote/miniatura'||p==='/api/lote/corte')return route.fulfill({contentType:'image/png',body:png});
      return route.fulfill({json:{}});
    });
    await page.goto('http://neuro.test/neuro/anatomia');
    assert.equal(await page.locator('.nr-process .ps-num').count(),2);
    assert.equal(await page.locator('#viewer').count(),0);
    for(const modality of ['MR','CT']){
      const open=page.locator('#nr-add-'+modality+'-open');
      await open.click();
      await page.locator('.ui-modal-veu.vis #nr-add-'+modality).waitFor();
      const input=page.locator('#nr-add-'+modality+'_pasta');
      await input.fill('/fantoma/'+modality);await input.press('Enter');
      await page.locator('[data-select="'+(modality==='MR'?'t1c':'head')+'"]').waitFor().catch(async err=>{
        throw Error(err.message+' | '+(await page.locator('#nr-add-'+modality+'_mensagem').textContent())+' | '+
          JSON.stringify({errors,requests,state:await page.evaluate(()=>[document.activeElement.id,document.getElementById('nr-add-CT').outerHTML.slice(0,330)])}));
      });
      await page.locator('#nr-add-'+modality).waitFor({state:'hidden'});
    }
    assert.equal(await page.locator('[data-select]').count(),rows.length);
    await page.locator('[data-preview=t1c]').click();
    await page.locator('.ui-visor').waitFor();
    assert.match(await page.locator('.ui-visor dl').innerText(),/224 × 224/);
    assert.match(await page.locator('.ui-visor dl').innerText(),/Demo Patient/);
    assert.match(await page.locator('.ui-visor dl').innerText(),/PHANTOM-01/);
    assert.match(await page.locator('.ui-visor dl').innerText(),/2026/);
    await page.keyboard.press('Escape');
    await page.locator('.ui-visor').waitFor({state:'hidden'});
    assert.equal(await page.locator('.nr-plan').count(),0);
    await page.locator('[data-select=t1c]').click();
    const m=page.locator('tr.nr-plan[data-ticket=t1c]');
    await m.locator('[data-protocol=snc_rm_simples]').waitFor();
    assert(await m.locator('[data-protocol=snc_rm_simples]').isChecked());
    assert.equal(await m.locator('[data-finding]:checked').count(),0);
    assert(await m.locator('[data-finding=MRI_LGGlioma]').isDisabled());
    assert.match(await m.innerText(),/Basic CNS MRI/);
    assert.match(await page.locator('.nr-table').innerText(),/Thickness \(mm\)/);
    assert.match(await page.locator('.nr-summary').innerText(),/Demo Patient/);
    await m.locator('[data-protocol=snc_rm_avancado]').check();
    assert.equal(await m.locator('[data-protocol]:checked').count(),1);
    await m.locator('[data-exclude=vent]').click();
    assert.equal(await m.locator('[data-exclude=vent]').count(),0);
    await m.locator('.nr-removed summary').click();
    await m.locator('[data-restore=vent]').click();
    assert(await m.locator('[data-exclude=vent]').isVisible());
    await m.locator('[data-protocol=anatomy_cerebra_ants]').check();
    assert.equal(await m.locator('[data-protocol]:checked').count(),1);
    const atlasInput=m.locator('[data-bind-model=anatomy_cerebra_ants]');
    assert.equal(await atlasInput.inputValue(),'pre');
    assert.deepEqual(await atlasInput.locator('option').evaluateAll(ns=>ns.map(n=>n.value).sort()),['pre','t1c']);
    await atlasInput.selectOption('t1c');
    await page.locator('[data-remove="other-frame"]').click();
    await atlasInput.waitFor();
    assert.equal(await atlasInput.inputValue(),'t1c');
    await m.locator('[data-help=snc_rm_simples]').click();
    await page.getByRole('dialog').filter({hasText:'Basic CNS MRI'}).waitFor();
    await page.keyboard.press('Escape');
    await m.locator('[data-finding=MRI_GBM]').check();
    await m.locator('[data-finding=MRI_Meningioma]').check();
    await m.locator('[data-exclude=men]').click();
    await m.locator('[data-save]').click();
    await page.locator('.nr-preset-form input').fill('Somente teste');
    await page.locator('.nr-preset-form button').click();
    await m.locator('[data-saved=local-1]').waitFor();
    assert(await m.locator('[data-saved=local-1]').isChecked());
    await m.locator('[data-saved=local-1]').uncheck();
    assert.equal(await m.locator('[data-exclude]').count(),0);
    await m.locator('[data-saved=local-1]').check();
    assert.equal(await m.locator('[data-exclude=men]').count(),0);
    await page.locator('tr.nr-summary[data-ticket=t1c] [data-expand]').click();
    assert(await m.isHidden());
    await page.locator('[data-select=head]').click();
    const c=page.locator('tr.nr-plan[data-ticket=head]');
    await c.locator('[data-protocol=cranio_buti]').waitFor();
    assert.deepEqual(await c.locator('[data-protocol]').evaluateAll(ns=>ns.map(n=>n.dataset.protocol)),['cranio_buti']);
    assert.equal(await c.locator('[data-finding]').count(),0);
    await c.locator('[data-protocol=cranio_buti]').uncheck();
    assert(await page.locator('#start').isDisabled());
    await c.locator('[data-protocol=cranio_buti]').check();
    await page.locator('#start').click();
    await page.locator('#radai_rev').waitFor();
    assert.equal(sent.length,0);
    const review=await page.locator('#radai_rev_corpo').innerText();
    assert(review.includes('Fantoma coronal pós') && review.includes('Fantoma TC') && review.includes('CerebrA / ANTs'));
    await page.locator('#radai_rev_ok').click();
    await page.waitForFunction(()=>document.querySelectorAll('.nr-plan').length===0);
    assert.equal(sent.length,1);
    assert.deepEqual(sent[0].studies.map(s=>[s.reference,s.plan.anatomy,s.model_ids]),[
      ['t1c','anatomy_cerebra_ants',['anatomy_cerebra_ants','MRI_GBM']],['head','cranio_buti',['cranio_buti']]]);
    const mr=sent[0].studies[0];
    assert.deepEqual(mr.plan.findings,['MRI_GBM','MRI_Meningioma']);
    assert.deepEqual(mr.plan.rois.MRI_Meningioma,[]);
    assert.equal(mr.bindings_by_model.anatomy_cerebra_ants[0].series_ticket,'t1c');
    assert(!JSON.stringify(sent[0]).includes('Demo Patient'));
    await page.locator('[data-select=flair]').click();
    const f=page.locator('tr.nr-plan[data-ticket=flair]');
    await f.locator('[data-finding=MRI_LGGlioma]').check();
    assert.equal(await f.locator('[data-protocol]:checked').count(),0);
    assert(await page.locator('#start').isEnabled());
    await page.locator('[data-remove=flair]').click();
    assert.equal(await page.locator('.nr-plan').count(),0);
    assert.deepEqual(errors,[]);
    const translations=require('../web/process-i18n.json');
    for (const [locale, phrases] of Object.entries(translations)) {
      const localized = await browser.newPage();
      await localized.addInitScript(lang=>localStorage.setItem('radai_idioma',lang),locale);
      await localized.route('**/*',r=>r.request().resourceType()==='document'
        ? r.fulfill({contentType:'text/html',path:html}) : r.fulfill({json:{}}));
      await localized.goto('http://neuro.test/neuro/anatomia');
      const source=await localized.locator('#nr-add-CT-open .ui-cartao-tit').innerText();
      assert.equal(source,phrases['Adicionar novas séries de Tomografia'],locale);
      const name=await localized.evaluate(()=>window.radaiFrase('Estudo neuroanatômico completo'));
      assert.equal(name,phrases['Estudo neuroanatômico completo'],locale);
      await localized.close();
    }
    console.log('PASS: CT/MR pickers, preview metadata, per-reference eligibility, presets, atlas, task selection and single queue confirmation.');
  } finally {await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;});
