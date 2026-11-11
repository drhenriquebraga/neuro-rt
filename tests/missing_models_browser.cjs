const fs = require('fs');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE);
(async () => {
  const browser = await chromium.launch({headless: true,
    executablePath: process.env.NEURO_BROWSER_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.route('**/*', route => route.fulfill({contentType: 'text/html',
      body: fs.readFileSync(process.env.NEURO_MISSING_FIXTURE, 'utf8')}));
    await page.goto('http://127.0.0.1:18799/neuro/');
    await page.evaluate(() => {window.uiConfirmar = options => {window.missingPopup = options;};});
    const nidus = page.locator('a[href="/neuro/testing/nidus"]');
    if (await nidus.count() !== 1) throw Error('Nidus is not available');
    const cards = page.locator('[data-neuro-models-missing]');
    if (await cards.count() !== 4) throw Error('Missing model cards are incorrect');
    await cards.first().click();
    if (!await page.evaluate(() => window.missingPopup?.corpo.includes('modelos adicionais'))) throw Error('Popup absent');
    if (!page.url().endsWith('/neuro/')) throw Error('Navigated before confirmation');
    await page.evaluate(() => window.missingPopup.aoNao());
    if (!page.url().endsWith('/neuro/')) throw Error('Cancellation changed the page');
    await page.evaluate(() => window.missingPopup.aoSim());
    await page.waitForURL('**/config#ps_neuro');
    if (errors.length) throw Error(errors.join('\n'));
    process.stdout.write('PASS: Nidus open, missing models popup, cancel and settings navigation.\n');
  } finally {await browser.close();}
})().catch(error => {process.stderr.write(String(error)); process.exitCode = 1;});
