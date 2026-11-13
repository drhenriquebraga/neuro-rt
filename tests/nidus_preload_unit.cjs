/* Synthetic image/network tests; no patient data, browser or model required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../neuro_rt/nidus_preload.py'), 'utf8')
  .split('NIDUS_PRELOAD_JS = r"""')[1].split('"""')[0];

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => {resolve = yes; reject = no});
  return {promise, resolve, reject};
}
function harness() {
  let active = 0, maximum = 0, nextUrl = 0;
  const requested = [], revoked = [], blobs = new Map(), gates = new Map();
  class LocalURL extends URL {}
  LocalURL.createObjectURL = blob => {const id = 'blob:fake/' + ++nextUrl; blobs.set(id, blob); return id};
  LocalURL.revokeObjectURL = url => {revoked.push(url); blobs.delete(url)};
  class FakeImage {
    async decode() {
      const blob = blobs.get(this.src);
      if (!blob || blob.bad) throw new Error('bad image');
      this.naturalWidth = blob.width; this.naturalHeight = blob.height;
    }
  }
  class Element {
    constructor() {this.attrs = new Map(); this.style = {}; this.children = []; this.inert = false; this.textContent = ''; this.events = {}}
    setAttribute(k, v) {this.attrs.set(k, String(v))}
    getAttribute(k) {return this.attrs.has(k) ? this.attrs.get(k) : null}
    removeAttribute(k) {this.attrs.delete(k)}
    appendChild(child) {this.children.push(child)}
    addEventListener(name, fn) {this.events[name] = fn}
  }
  const context = {URL: LocalURL, Image: FakeImage, AbortController, DOMException,
    document: {createElement: () => new Element()}, location: {href: 'http://localhost/nidus/projecao'},
    fetch: async (url, options) => {
      requested.push(url); active++; maximum = Math.max(maximum, active);
      try {
        if (gates.has(url)) {
          await Promise.race([gates.get(url).promise, new Promise((_, reject) => {
            if (options.signal.aborted) reject(new DOMException('Cancelled', 'AbortError'));
            else options.signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')), {once: true});
          })]);
        }
        return {ok: !url.includes('http-error'), status: 500,
          blob: async () => ({size:url.includes('native')?1024*1024+4096:10,
            width:url.includes('native')?1024:url.includes('large')?100:4,
            height:url.includes('native')?1024:4,bad:url.includes('bad-image')})};
      } finally {active--}
    },
    uiTexto: (node, text) => {node.textContent = text}, uiCarregando: () => {},
    uiModal: options => ({options, fechar: options.aoFechar})};
  context.window = context;
  vm.runInNewContext(source, context, {filename: 'nidus_preload.js'});
  return {...context, requested, revoked, gates, Element, maximum: () => maximum};
}

(async () => {
  let h = harness(), c = new h.NidusImageCache({maxBytes: 300, maxEntries: 3});
  const first = await c.load('/p?b=one&lao=5&n=1&t=tab1');
  const alias = await c.load('/p?t=tab2&lao=5&b=one&n=99');
  assert.equal(first, alias); assert.equal(h.requested.length, 1);
  await Promise.all([c.load('/p?b=one&lao=10'), c.load('/p?b=one&lao=15')]);
  assert.equal(h.maximum(), 1, 'renders must be serial');
  assert.equal(c.stats().bytes, 222, 'include decoded RGBA');
  assert.equal(c.get('/p?b=other&lao=5'), null, 'never mix patient tickets');
  assert.equal(c.get('/p?b=one&lao=5&janela=osso'), null, 'window remains in cache key');
  assert.equal(c.get('/p?b=one&lao=5&caixa=0,1'), null, 'crop remains in cache key');
  assert.equal(c.get('/p?b=one&lao=5&phase=2'), null, 'time remains in cache key');

  const img = new h.Image();
  await c.paint(img, '/p?b=one&lao=5');
  await c.load('/p?b=one&lao=20');
  assert.equal(c.get('/p?b=one&lao=10'), null, 'evict oldest unpinned');
  assert(c.get('/p?b=one&lao=5'), 'displayed image must remain pinned');
  assert(!h.revoked.includes(img.src));
  c.release(img);
  await c.load('/p?b=one&lao=25');
  assert(c.stats().bytes <= 300); assert.equal(c.stats().entries, 3);
  await assert.rejects(c.load('/large'), /cache limit/);
  assert(c.stats().bytes <= 300);
  await assert.rejects(c.load('/bad-image'), /bad image/);
  await assert.rejects(c.load('/http-error'), /HTTP 500/);

  h = harness(); c = new h.NidusImageCache();
  h.gates.set('/slow', deferred());
  const slow = c.load('/slow'), queued = c.load('/queued');
  const rejectedSlow = assert.rejects(slow, {name: 'AbortError'});
  const rejectedQueue = assert.rejects(queued, {name: 'AbortError'});
  c.reset();
  await Promise.all([rejectedSlow, rejectedQueue]);
  const fresh = await c.load('/fresh'); assert(fresh); assert.equal(c.stats().entries, 1);
  assert(!h.requested.includes('/queued'));
  const target = new h.Image();
  await assert.rejects(c.paint(target, '/fresh', {current: () => false}), {name: 'AbortError'});
  assert.equal(target.src, undefined, 'stale callback must never change visible image');
  const controller = new AbortController(); controller.abort();
  await assert.rejects(c.load('/cancelled', {signal: controller.signal}), {name: 'AbortError'});
  assert(!h.requested.includes('/cancelled'));

  h = harness(); c = new h.NidusImageCache();
  h.gates.set('/first', deferred());
  const p1 = c.load('/first'), p2 = c.load('/background', {priority: -1}), p3 = c.load('/foreground', {priority: 1});
  h.gates.get('/first').resolve();await Promise.all([p1,p2,p3]);
  assert.deepEqual(h.requested, ['/first','/foreground','/background']);
  h = harness();c = new h.NidusImageCache();h.gates.set('/active',deferred());
  const active=c.load('/active');let wanted=1;
  const stale=c.paint(new h.Image(),'/superseded',{current:()=>wanted===1});
  const rejectedStale=assert.rejects(stale,{name:'AbortError'});
  wanted=2;
  const latest=c.paint(new h.Image(),'/latest',{current:()=>wanted===2});
  h.gates.get('/active').resolve();await Promise.all([active,rejectedStale,latest]);
  assert.deepEqual(h.requested,['/active','/latest'],'skip superseded queued wheel frames before rendering');
  const counts = [];
  await c.warm(['/a?n=1','/a?n=2','/b'], {onProgress: (done,total) => counts.push([done,total])});
  assert.deepEqual(counts, [[1,2],[2,2]], 'count only actual unique frames');
  const cancelled = new AbortController();let progress = 0;
  await assert.rejects(c.warm(['/c','/d'], {signal: cancelled.signal, onProgress: () => {progress++; cancelled.abort()}}), {name:'AbortError'});
  assert.equal(progress, 1); assert(!h.requested.includes('/d'));
  c.reset(); assert.equal(c.stats().bytes, 0);assert.equal(c.stats().entries, 0);

  h=harness();c=new h.NidusImageCache({maxBytes:128*1024*1024,maxEntries:96,maxDecodedEntries:8});
  const rotation=Array.from({length:72},(_,index)=>'/native?angle='+(-180+index*5));
  const fixed=new h.Image();await c.paint(fixed,rotation[36]);
  await c.warm(rotation);
  assert.equal(c.stats().entries,72,'retain every encoded 5-degree projection');
  assert.equal(c.stats().decoded,8,'decoded references obey their independent bound');
  assert(c.stats().bytes<=128*1024*1024);
  assert(rotation.every(url=>c.get(url)),'complete encoded rotation remains cached');
  assert.equal(c.get(rotation[10]).image,null,'old unpinned decoded buffer is released');
  const countBeforeDecode=h.requested.length;
  await c.load(rotation[10]);
  assert.equal(h.requested.length,countBeforeDecode,'encoded cache hit never downloads or renders again');
  assert(c.get(rotation[10]).image);assert(c.get(rotation[36]).image,'visible projection remains pinned');
  assert.equal(c.stats().decoded,8);c.reset();assert.equal(c.stats().decoded,0);

  h = harness();let cancelledCount = 0;
  const root = new h.Element();root.setAttribute('aria-busy','false');
  const dialog = new h.NidusOpeningDialog({roots:[root],onCancel:()=>cancelledCount++});
  assert(root.inert);assert.equal(root.getAttribute('aria-busy'),'true');
  assert.equal(dialog.modal.options.fecharFora,false);
  dialog.step('Preparing views',2,8);
  const bar = dialog.modal.options.no.children[2];assert.equal(bar.value,2);assert.equal(bar.max,8);
  dialog.modal.fechar();assert(dialog.signal.aborted);assert.equal(cancelledCount,1);
  assert.equal(root.inert,false);assert.equal(root.getAttribute('aria-busy'),'false');
  dialog.cancel();assert.equal(cancelledCount,1);
  root.inert=true;
  const success = new h.NidusOpeningDialog({roots:[root],onCancel:()=>cancelledCount++});
  success.finish();assert(!success.signal.aborted);assert.equal(cancelledCount,1);assert(root.inert);
  console.log('NIDUS preload: cache isolation, bounded memory, serial/priority loading, cancellation, stale guards and dialog lifecycle passed.');
})().catch(error => {console.error(error); process.exitCode=1});
