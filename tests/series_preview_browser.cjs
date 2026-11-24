/* Exercise the native folder, series cards and full-size viewer without running a model. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(process.argv[3] || path.join(__dirname, '..'));
const work = process.argv[2];
const rows = JSON.parse(fs.readFileSync(path.join(work, 'phantom.json'), 'utf8'));
const screenshotDir = process.env.NEURO_PREVIEW_SCREENSHOTS;

function mockSelection(tickets, category) {
  const series = tickets.map(ticket => {
    const row = rows.find(r => r.bilhete === ticket);
    assert(row, 'Selection must contain tickets returned by the scan');
    return {ticket, modality:row.modalidade, group_key:'phantom', source_format:'dicom',
      slice_count:row.cortes, description:row.desc, sequence_candidates:[{role:row.role, certainty:'certain'}]};
  });
  const models = ['alpha', 'beta'].map(id => ({
    id, label:'Modelo ' + id, groups:[category], channels:[{role:'T1'}],
    classes:[{class_id:'target', label:'Alvo de teste'}], license:{code:'MIT'},
    eligibility:{selectable:true, technical_reasons:[], warnings:[]},
    bindings:series.length ? [{role:'T1', series_ticket:series[0].ticket,
      certainty:'certain', association_source:'suggested'}] : [],
  }));
  return {series, models};
}

async function check(browser, category) {
  const page = await browser.newPage({viewport:{width:1320, height:900}, locale:'pt-BR', reducedMotion:'reduce'});
  await page.addInitScript(()=>localStorage.setItem('radai_idioma','pt-BR'));
  page.setDefaultTimeout(8000);
  const errors = [], submissions = [], slices = [];
  page.on('pageerror', e => errors.push(e.message));
  const folder = '/phantom/' + category;
  const examRows = rows.filter(row => row.modalidade === 'MR' || category === 'metastasis');
  const [first, second, third] = examRows.map(r => r.bilhete);
  const thumbnail = '/api/lote/miniatura';
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname;
    if (url.hostname !== 'neuro.test') return route.abort();
    if (p === '/neuro/' + category) return route.fulfill({contentType:'text/html',
      path:path.join(work, category+'.html')});
    if (['/neuro/study.js', '/neuro/study.css'].includes(p)) return route.fulfill({
      contentType:p.endsWith('.js')?'application/javascript':'text/css',path:path.join(root,'web',path.basename(p))});
    if (p === '/neuro/api/status') return route.fulfill({json:{token:'synthetic-token'}});
    if (p === '/api/varrer/iniciar') {
      const data = req.postDataJSON();
      assert.equal(data.pasta, folder);
      assert.deepEqual(data.opcoes.modalidades, ['MR','CT']);
      return route.fulfill({json:{v:'synthetic-scan',fim:true,final:true,series:examRows.length,linhas:examRows}});
    }
    if (p === '/neuro/api/selection') {
      const data = req.postDataJSON();
      assert.equal(data.category, category);
      assert.equal(req.headers()['x-neuro-token'], 'synthetic-token');
      const contract = mockSelection(data.tickets, category);
      return route.fulfill({json:data.identify_only ? {series:contract.series,unreadable:[]} : contract});
    }
    if (p === thumbnail || p === '/api/lote/corte') {
      const ticket = url.searchParams.get('b'), slice = url.searchParams.get('corte');
      assert(rows.some(r=>r.bilhete===ticket));
      if (category === 'meningioma' && ticket === third && p === thumbnail) return route.fulfill({status:404});
      if (p !== thumbnail) {
        assert.equal(url.searchParams.get('janela'),'auto', 'MR uses its automatic window');
        assert(slice !== null && Number(slice)>=0 && Number(slice)<7);
        slices.push([ticket, Number(slice)]);
      }
      return route.fulfill({contentType:'image/png', headers:{'X-RadAI-Cortes':'7'},
        path:path.join(work, ticket+(p===thumbnail?'':'-'+slice)+'.png')});
    }
    if (p === '/neuro/api/studies' && req.method() === 'POST') submissions.push(req.postDataJSON());
    if (p === '/neuro/api/studies') return route.fulfill({json:{studies:[],results:[]}});
    return route.fulfill({json:{}});
  });
  try {
    await page.goto('http://neuro.test/neuro/'+category);
    const picker = page.locator('#nr-series-picker');
    await picker.waitFor({state:'visible'});
    await page.locator('#nr-series-picker_pasta').fill(folder);
    await page.locator('#nr-series-picker_pasta').press('Enter');
    const cards = page.locator('#series-list [data-preview]');
    await cards.nth(examRows.length-1).waitFor();
    assert.equal(await cards.count(), examRows.length);
    await picker.waitFor({state:'hidden'});
    const card = page.locator('[data-preview="'+first+'"]');
    assert.match(await card.innerText(), /Fantoma T1/);
    await card.scrollIntoViewIfNeeded();
    await card.locator('img').evaluate(img=>img.decode());
    const expected = category === 'anatomia' ? first : second;
    assert.equal(await page.locator('#reference').inputValue(), expected);
    const alpha = page.locator('[data-binding-model=alpha][data-role=T1]');
    const beta = page.locator('[data-binding-model=beta][data-role=T1]');
    await alpha.selectOption(second);
    assert.equal(await beta.inputValue(), first);
    if (screenshotDir && category==='glioma') {
      fs.mkdirSync(screenshotDir, {recursive:true});
      await page.locator('#series-list img').evaluateAll(images=>Promise.all(images.map(img=>img.decode())));
      await page.locator('#series-title').evaluate(el=>{el.scrollIntoView({block:'start'}); window.scrollBy(0,-95);});
      await page.screenshot({path:path.join(screenshotDir,'01-series-glioma.png')});
    }
    if (category === 'metastasis') {
      const ctTicket = examRows.find(row=>row.modalidade==='CT').bilhete;
      await page.locator('[data-preview="'+ctTicket+'"]').waitFor();
      assert.equal(await alpha.locator('option[value="'+ctTicket+'"]').count(),0);
      await page.locator('#reference').selectOption(ctTicket);
      assert(await page.locator('[data-model=alpha]').isDisabled(), 'A CT reference cannot bind a MR model');
      await page.locator('#reference').selectOption(expected);
      await page.setViewportSize({width:390,height:760});
    }
    if (category === 'meningioma') {
      await page.locator('[data-preview="'+third+'"] .nr-thumb-error').waitFor();
      assert.equal(await cards.count(), examRows.length);
    }
    if (category === 'glioma') {
      const buttonStyle = () => page.evaluate(() => {
        return ['start','refresh','cancel'].map(id => {
          const current = document.getElementById(id);
          const expected = document.createElement('button');
          expected.className = {start:'ui-bt pri', refresh:'ui-bt', cancel:'ui-bt perigo'}[id];
          expected.disabled = current.disabled;
          expected.hidden = current.hidden;
          document.body.appendChild(expected);
          const props = ['color','backgroundColor','borderTopColor','transitionProperty','transitionDuration'];
          const actual = getComputedStyle(current), shared = getComputedStyle(expected);
          const differences = props.filter(prop=>actual[prop]!==shared[prop]);
          expected.remove();
          return {id, differences};
        });
      });
      await page.emulateMedia({reducedMotion:'no-preference'});
      assert((await buttonStyle()).every(result=>!result.differences.length));
      await page.locator('[data-model=alpha]').check();
      assert(await page.locator('#start').isEnabled());
      assert((await buttonStyle()).every(result=>!result.differences.length));
      await page.emulateMedia({reducedMotion:'reduce'});
      await card.click();
    } else {
      await card.press('Space');

    }
    const viewer = page.locator('.ui-visor');
    await viewer.waitFor();
    const image = viewer.locator('.ui-visor-img img');
    await image.evaluate(img=>img.decode());
    assert.equal(Number(await viewer.locator('input[type=range]').inputValue()), 3);
    await page.keyboard.press('End');
    await page.waitForFunction(()=>document.querySelector('.ui-visor-rol').value === '6');
    await image.evaluate(img=>img.decode());
    assert(slices.some(([ticket,index])=>ticket===first && index===6));
    if (screenshotDir && category==='glioma') {
      await viewer.locator('.ui-organico').waitFor({state:'detached'});
      assert(await image.isVisible());
      await page.screenshot({path:path.join(screenshotDir,'02-serie-ampliada.png')});
    }
    await page.keyboard.press('Escape');
    await viewer.waitFor({state:'hidden'});
    assert(await card.evaluate(el=>el===document.activeElement),'Restore focus to the series opened');
    assert.equal(await alpha.inputValue(),second);
    assert.equal(await beta.inputValue(),first);
    await page.locator('[data-remove="'+third+'"]').click();
    await page.locator('[data-preview="'+third+'"]').waitFor({state:'detached'});
    assert.equal(await cards.count(), examRows.length-1);
    assert.equal(await alpha.inputValue(),second);
    assert.equal(await page.locator('#reference').inputValue(),expected);
    await card.focus();
    await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab');
    assert(await card.evaluate(el=>el.matches(':focus-visible') && getComputedStyle(el).outlineStyle !== 'none'));
    assert.deepEqual(submissions, []);
    assert.deepEqual(errors, []);
    console.log('PASS:', category, 'folder gallery, preview, slices, bindings and removal');
  } finally { await page.close(); }
}
(async()=>{
  const browser = await chromium.launch({headless:true,executablePath:process.env.NEURO_BROWSER_EXECUTABLE});
  try { for (const category of ['anatomia','glioma','metastasis','meningioma']) await check(browser, category); }
  finally { await browser.close(); }
})().catch(e=>{ console.error(e); process.exitCode=1; });

