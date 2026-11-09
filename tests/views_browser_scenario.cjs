'use strict';
const assert = require('node:assert/strict');
const {chromium} = require(process.env.NEURO_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage();
    const responsePromise = page.waitForResponse(response => response.url().endsWith('axial_001.svg'));
    await page.goto(process.argv[2]);
    await page.waitForLoadState('networkidle');
    const response = await responsePromise;
    assert.equal(response.status(), 200);
    assert.equal(response.headers()['content-type'], 'image/svg+xml');
    assert.equal(response.headers()['cache-control'], 'no-store');
    const pixel = await page.locator('#sample').evaluate(image => {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0);
      return [...ctx.getImageData(2, 2, 1, 1).data];
    });
    assert.ok(pixel[0] > 50, `PNG embutido não visível: ${pixel}`);
    assert.equal(pixel[0], pixel[1]);
    assert.equal(pixel[1], pixel[2]);
    assert.equal(pixel[3], 255);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
