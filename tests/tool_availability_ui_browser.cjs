// Synthetic browser check: card links, keyboard access and existing host styling.
const fs = require('fs'), assert = require('assert');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE || 'C:/Users/henri/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.NEURO_BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage();
    await page.addInitScript(() => localStorage.setItem('radai_idioma', 'pt-BR'));
    await page.route('http://neuro.test/**', route => {
      if (new URL(route.request().url()).pathname === '/neuro/') {
        return route.fulfill({contentType: 'text/html', body: fs.readFileSync(process.env.NEURO_AVAILABILITY_HTML, 'utf8')});
      }
      return route.fulfill({json: {state: 'ready', release_check: {state: 'current'}, update: {state: 'idle'}}});
    });
    await page.goto('http://neuro.test/neuro/');
    const cards = page.locator('.md-grade > .md-fer');
    assert.equal(await cards.count(), 5);
    const disabled = page.locator('.md-grade > .md-fer[aria-disabled="true"]');
    assert.equal(await disabled.count(), 0);
    for (const tool of ['nidus','glioma','metastasis','meningioma','anatomia']) {
      const card=page.locator('.md-grade > a.md-fer[href="/neuro/testing/'+tool+'"]');
      assert.equal(await card.count(),1);
      assert((await card.textContent()).includes('[fase de testes]'));
      await card.focus();assert(await card.evaluate(el=>el===document.activeElement));
    }
    console.log('PASS: five active test-phase cards, acknowledgement links, host styling and keyboard focus.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
