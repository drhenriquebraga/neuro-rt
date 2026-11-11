const fs = require('fs');
const path = require('path');
const assert = require('assert').strict;
const { chromium } = require(process.env.NEURO_PLAYWRIGHT_MODULE || 'playwright');
const ui = process.env.LOCAL_SUITE_UI_SOURCE || path.resolve(__dirname, '../../AUTO_CONTORNO/app/radai_ui.py');
const source = fs.readFileSync(ui, 'utf8').replace(/\r\n/g, '\n');
const begin = source.indexOf(" var HIST = 'radai_hist'");
const end = source.indexOf(" document.addEventListener('DOMContentLoaded', function(){\n  try{ window.uiAbasTodas()", begin);
assert(begin > 0 && end > begin);
const script = '(function(){\n' + source.slice(begin, end) + '\n})();';

(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.NEURO_BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('http://neuro.test/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/neuro') return route.fulfill({status: 307, headers: {location: '/neuro/'}});
      if (url.pathname === '/neuro/glioma') return route.fulfill({status: 307, headers: {location: '/neuro/?category=glioma'}});
      const tool = url.searchParams.get('category') === 'glioma';
      const title = tool ? 'Glioma RT' : url.pathname === '/' ? 'Local Suite' : 'NEURO RT';
      const parent = tool ? '/neuro' : '/';
      const html = '<!doctype html><meta charset="utf-8"><header class="rc-topo" data-radai-tela="' + title + '">' +
        '<a id="back" href="' + parent + '" data-radai-voltar data-radai-pai="' + parent + '">Voltar</a></header>' +
        '<a id="tool" href="/neuro/glioma">Glioma</a><script>' + script + '</script>';
      return route.fulfill({contentType: 'text/html', body: html});
    });
    await page.addInitScript(() => {
      if (location.origin !== 'http://neuro.test') return;
      if (!sessionStorage.getItem('history-test-seeded')) {
        sessionStorage.setItem('history-test-seeded', '1');
        sessionStorage.setItem('radai_hist', JSON.stringify([
          {u:'/',t:'Local Suite'}, {u:'/neuro',t:'NEURO RT'}, {u:'/neuro/',t:'NEURO RT'}]));
      }
    });
    await page.goto('http://neuro.test/neuro/');
    assert.equal(await page.locator('#back').getAttribute('href'), '/', 'Old slash aliases must not point back to the same mini page');
    await page.locator('#tool').click();
    await page.waitForURL('**/neuro/?category=glioma');
    assert.equal(await page.locator('#back').getAttribute('href'), '/neuro', 'A tool query must be distinct from the mini page');
    await page.locator('#back').click();
    await page.waitForURL('http://neuro.test/neuro/');
    assert.equal(await page.locator('#back').getAttribute('href'), '/');
    await page.locator('#back').click();
    await page.waitForURL('http://neuro.test/');
    assert.deepEqual(await page.evaluate(() => window.uiHistorico().map(row => row.u)), ['/']);
    assert.deepEqual(errors, []);
    console.log('PASS: stale alias stack, mini → tool query → mini → home; no back loop or JS error.');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
