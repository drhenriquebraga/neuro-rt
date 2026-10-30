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
    assert.equal(await disabled.count(), 4);
    for (let i = 0; i < 4; i++) {
      assert(await disabled.nth(i).textContent().then(value => value.includes('[em construção]')));
      const values = await disabled.nth(i).evaluate(el => ({
        tag: el.tagName, link: el.getAttribute('href'), tab: el.tabIndex,
        focusable: el.querySelectorAll('a,button,input,[tabindex]').length,
        opacity: Number(getComputedStyle(el).opacity)
      }));
      assert.equal(values.tag, 'DIV');
      assert.equal(values.link, null);
      assert.equal(values.tab, -1);
      assert.equal(values.focusable, 0);
      assert(values.opacity >= 0.6 && values.opacity < 1);
    }
    const nidus = page.locator('.md-grade > a.md-fer');
    assert.equal(await nidus.count(), 1);
    assert.equal(await nidus.getAttribute('href'), '/neuro/nidus');
    await nidus.focus();
    assert(await nidus.evaluate(el => el === document.activeElement));
    console.log('PASS: Nidus active, four inert construction cards, host styling and keyboard focus.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
