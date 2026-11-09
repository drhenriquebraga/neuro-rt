'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

async function checkFormat(format, expected) {
  const elements = new Map();
  const metadata = {planes: {}};
  for (const plane of ['axial', 'coronal', 'sagittal']) {
    metadata.planes[plane] = {count: 5, center: 2, ...(format ? {format} : {})};
  }
  const context = vm.createContext({
    URL, activeJob: 'synthetic', base: 'http://localhost/neuro/',
    fetch: async () => ({ok: true, json: async () => metadata}),
    document: {
      querySelectorAll: () => [],
      getElementById: id => {
        if (!elements.has(id)) elements.set(id, {});
        return elements.get(id);
      },
    },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/viewer.js'), 'utf8'), context);
  await vm.runInContext("showViewer({id:'synthetic'})", context);
  for (const plane of ['axial', 'coronal', 'sagittal']) {
    assert.equal(elements.get(`${plane}-image`).src,
      `http://localhost/neuro/api/jobs/synthetic/views/${plane}_002.${expected}`);
    const slider = elements.get(`${plane}-slice`);
    slider.value = 4;
    slider.oninput();
    assert.equal(elements.get(`${plane}-image`).src,
      `http://localhost/neuro/api/jobs/synthetic/views/${plane}_004.${expected}`);
  }
  assert.equal(elements.get('visualization').hidden, false);
}

(async () => {
  await checkFormat('svg', 'svg');
  await checkFormat(undefined, 'png');
  await checkFormat('png', 'png');
  await checkFormat('../unexpected', 'png');
})().catch(error => { console.error(error); process.exitCode = 1; });
