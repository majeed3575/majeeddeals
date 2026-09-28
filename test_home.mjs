import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';

const read = name => readFileSync(new URL(name, import.meta.url), 'utf8');
const html = read('index.html'), source = read('home.js');
function element() {
  const listeners = {}, attrs = {};
  return {listeners, attrs, hidden:false, inert:false, firstElementChild:{},
    addEventListener:(name, fn) => {listeners[name] = fn;},
    setAttribute:(name, value) => {attrs[name] = value;},
    removeAttribute:name => {delete attrs[name];}};
}
function home({reduced=false, search='', hash='', dir='rtl'}={}) {
  const elements = new Map(), slides = Array.from({length:3}, element), tabs = Array.from({length:3}, element);
  const el = name => {if (!elements.has(name)) elements.set(name, element()); return elements.get(name);};
  const timers = new Map(); let sequence = 0, redirected;
  const motion = {...element(), matches:reduced};
  const document = {...element(), documentElement:{dir}, hidden:false, activeElement:null,
    getElementById:el, querySelectorAll:s => s === '[data-home-slide]' ? slides : tabs};
  const region = el('howItWorks'); region.contains = node => !!node;
  const context = vm.createContext({document, URLSearchParams,
    location:{search, hash, replace:url => {redirected=url;}},
    matchMedia:() => motion,
    setTimeout:(fn, delay) => {timers.set(++sequence, {fn, delay}); return sequence;},
    clearTimeout:id => timers.delete(id)});
  vm.runInContext(source, context);
  function tick() {
    const first = timers.entries().next().value;
    assert.ok(first, 'a timer is scheduled'); timers.delete(first[0]); first[1].fn();
  }
  return {el, slides, tabs, timers, motion, document, region, context, tick,
    get redirected(){return redirected;}, index:() => slides.findIndex(s => !s.hidden)};
}
test('home is an explanatory carousel followed by category icons, never a product feed', () => {
  assert.equal((html.match(/data-home-slide role=/g)||[]).length, 3);
  assert.ok(html.indexOf('id="categories"') > html.indexOf('id="howItWorks"'));
  assert.doesNotMatch(html, /product-card|dealsGrid|deals-initial\.json|<dialog|loading="eager"/);
  assert.doesNotMatch(source, /fetch\(|XMLHttpRequest|localStorage|sessionStorage/);
  const images = [...html.matchAll(/<img[^>]+src="([^"]+)"/g)].map(m => m[1]);
  assert.equal(images.length, 2);
  assert.ok(images.every(src => src === 'assets/overly-dark-logo-trimmed.webp'));
  assert.match(html, /إفصاح العمولة/);
});
test('all generated category cards have actual destinations and valid native icons', () => {
  const links = [...html.matchAll(/class="home-category-card" href="([^"]+)"/g)].map(m => m[1]);
  assert.ok(links.length >= 10); assert.equal(new Set(links).size, links.length);
  for (const href of links) {
    assert.ok(existsSync(new URL(href+'index.html', import.meta.url)), href);
    assert.match(read(href+'index.html'), /class="product-card"/);
  }
  for (const [,id] of html.matchAll(/home-icons\.svg#([\w-]+)/g)) assert.ok(read('assets/home-icons.svg').includes(`id="${id}"`), id);
});
test('autoplay advances every seven seconds and hides/inerts noncurrent content', () => {
  const h = home(); assert.equal(h.index(), 0);
  assert.equal([...h.timers.values()][0].delay, 7000);
  h.tick(); assert.equal(h.index(), 1);
  assert.deepEqual(h.slides.map(s => s.inert), [true,false,true]);
  assert.equal(h.tabs[1].attrs['aria-current'], 'step');
  assert.equal(h.el('homeSlideStatus').attrs['aria-live'], 'off');
  h.tick(); h.tick(); assert.equal(h.index(), 0);
});
test('manual navigation wraps, announces changes and pauses rotation', () => {
  const h = home(); h.el('homePrevious').listeners.click();
  assert.equal(h.index(), 2); assert.equal(h.timers.size, 0);
  assert.equal(h.el('homeSlideStatus').attrs['aria-live'], 'polite');
  assert.equal(h.el('homePlay').attrs['aria-pressed'], 'true');
  h.el('homeNext').listeners.click(); assert.equal(h.index(), 0);
  h.tabs[1].listeners.click(); assert.equal(h.index(), 1);
  h.el('homePlay').listeners.click(); h.tick(); assert.equal(h.index(), 2);
});
test('autoplay respects hover, keyboard focus and background tabs', () => {
  const h = home(); h.region.listeners.mouseenter(); assert.equal(h.timers.size, 0);
  h.region.listeners.mouseleave(); assert.equal(h.timers.size, 1);
  h.document.activeElement = h.tabs[0]; h.region.listeners.focusin(); assert.equal(h.timers.size, 0);
  h.document.listeners.visibilitychange(); assert.equal(h.timers.size, 0);
  h.document.activeElement = null; h.region.listeners.focusout(); h.tick(); assert.equal(h.timers.size, 1);
  h.document.hidden = true; h.document.listeners.visibilitychange(); assert.equal(h.timers.size, 0);
  h.document.hidden = false; h.document.listeners.visibilitychange(); assert.equal(h.timers.size, 1);
});
test('reduced motion starts paused and stops autoplay if the preference changes', () => {
  const h = home({reduced:true}); assert.equal(h.timers.size, 0);
  assert.equal(h.el('homePlay').attrs['aria-pressed'], 'true');
  const active = home(); active.motion.matches = true; active.motion.listeners.change();
  assert.equal(active.timers.size, 0);
});
test('explicit play works while its own button retains focus or hover', () => {
  const h = home({reduced:true});
  h.region.listeners.mouseenter(); h.document.activeElement = h.el('homePlay');
  h.region.listeners.focusin(); h.el('homePlay').listeners.click();
  h.tick(); assert.equal(h.index(), 1);
  h.document.activeElement = h.tabs[1]; h.region.listeners.focusin();
  assert.equal(h.timers.size, 0);
});
test('keyboard direction follows Arabic and English', () => {
  for (const [dir,key] of [['rtl','ArrowLeft'],['ltr','ArrowRight']]) {
    const h = home({dir}); let prevented = false;
    h.region.listeners.keydown({key,preventDefault(){prevented=true;}});
    assert.equal(h.index(), 1); assert.equal(prevented, true);
  }
});
test('touch navigation distinguishes horizontal swipes from page scrolling', () => {
  for (const [dir,x] of [['rtl',190],['ltr',10]]) {
    const h = home({dir});
    h.region.listeners.touchstart({touches:[{clientX:100,clientY:100}]});
    h.region.listeners.touchend({changedTouches:[{clientX:x,clientY:110}]});
    assert.equal(h.index(), 1);
  }
  const h = home();
  h.region.listeners.touchstart({touches:[{clientX:100,clientY:100}]});
  h.region.listeners.touchend({changedTouches:[{clientX:105,clientY:210}]});
  assert.equal(h.index(), 0); assert.equal(h.timers.size, 1);
});
test('old product/search bookmarks redirect without losing language or intent', () => {
  for (const [search, hash] of [['?deal=AMAZON1&lang=en',''],['?q=charger&lang=en',''],['?lang=ar','#dealsTitle'],['','#aliSearchSection'],['','#mobileSearchHub']]) {
    const h = home({search, hash}); assert.equal(h.redirected, 'browse.html'+search+hash);
    assert.equal(h.timers.size, 0);
  }
  assert.equal(home({search:'?lang=en', hash:'#categories'}).redirected, undefined);
});
test('all homepage copy has English translations, including dynamic controls', () => {
  const ctx = vm.createContext({});
  for (const file of ['site-copy-en.js','legal-copy-en.js','site-extra-en.js','site-angles-en.js','home-copy-en.js','site-phrases.js','locale.js']) vm.runInContext(read(file), ctx);
  const api = ctx.createOverlyI18n(); api.setLanguage('en');
  for (const phrase of ['كل اهتماماتك.','وش يهمّك اليوم؟','تشغيل الحركة التلقائية','إيقاف الحركة التلقائية','الخطوة {count} من {total}']) assert.doesNotMatch(api.t(phrase), /[\u0600-\u06ff]/);
  const h = home(); h.context.OverlyI18n = api; h.document.listeners['overly:languagechange']();
  assert.equal(h.el('homePlay').attrs['aria-label'], 'Pause automatic slides');
});
