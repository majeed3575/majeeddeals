/* Browser regression check for the real CSS cascade, not just palette values.
   Run after build_public_site.py with Playwright installed, or provide its module
   path via PLAYWRIGHT_MODULE. OVERLY_THEME_LIVE=1 checks the published site. */
import assert from 'node:assert/strict';
import {readFile, stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(fileURLToPath(new URL('./dist-site/', import.meta.url)));
const live = process.env.OVERLY_THEME_LIVE === '1';
const home = await readFile(path.join(root, 'index.html'), 'utf8');
const categoryPaths = [...home.matchAll(/class="home-category-card" href="([^"]+)"/g)].map(m => '/'+m[1]);
const pages = ['/categories/kids/', ...categoryPaths.filter(p => p !== '/categories/kids/'),
  '/stores/amazon/', '/stores/aliexpress/', '/products/aliexpress-1005010561069073/',
  '/guides/car-accessories-checklist/'];
const browser = await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_CHANNEL ? {channel:process.env.PLAYWRIGHT_CHANNEL} : {})});
const context = await browser.newContext({reducedMotion:'reduce'});
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.json':'application/json','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg'};
if (!live) await context.route('https://overly.live/**', async route => {
  const pathname = decodeURIComponent(new URL(route.request().url()).pathname);
  let file = path.resolve(root, '.'+pathname);
  if (file !== root && !file.startsWith(root+path.sep)) return route.fulfill({status:403,body:'Forbidden'});
  try { if ((await stat(file)).isDirectory()) file=path.join(file, 'index.html'); }
  catch { if (!path.extname(file)) file += '.html'; }
  try { await route.fulfill({status:200,contentType:mime[path.extname(file)] || 'application/octet-stream',body:await readFile(file)}); }
  catch { await route.fulfill({status:404,body:'Not found'}); }
});
// No analytics or merchant/API actions in this read-only check.
await context.route('https://*.workers.dev/**', route => route.abort());
// External product photos do not affect the computed card-copy background.
await context.route(/https:\/\/.*(?:aliexpress-media|alicdn|media-amazon|ssl-images-amazon)\.com\//, route => route.abort());
const page = await context.newPage(), errors = [];
page.on('pageerror', error => errors.push(error.message));
let checks = 0, samples = 0, minimum = 100;
try {
  for (const width of [390,1280]) for (const language of ['ar','en']) for (const pathname of pages) {
    await page.setViewportSize({width,height:844});
    const response = await page.goto(`https://overly.live${pathname}?theme=light&lang=${language}&v=theme-contrast-2`, {waitUntil:'domcontentloaded'});
    assert.equal(response.status(), 200, pathname);
    await page.waitForSelector('#themeToggle');
    for (const theme of ['light','dark','light']) {
      if (await page.locator('html').getAttribute('data-theme') !== theme) await page.locator('#themeToggle').click();
      const result = await page.evaluate(() => {
        const rgba = value => {const p=value.match(/[\d.]+/g).map(Number); return [p[0],p[1],p[2],p[3] ?? 1];};
        const over = (front,back) => [0,1,2].map(i=>front[i]*front[3]+back[i]*(1-front[3]));
        const luminance = rgb => rgb.map(c=>c/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4).reduce((n,c,i)=>n+c*[.2126,.7152,.0722][i],0);
        const ratio = (a,b) => {const x=luminance(a), y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
        function background(node) {
          const ancestors=[];
          for(let el=node;el;el=el.parentElement) ancestors.unshift(el);
          return ancestors.reduce((color,el)=>over(rgba(getComputedStyle(el).backgroundColor),color),[255,255,255]);
        }
        const selectors=['.card-copy h2 a','.card-copy p','.card-copy .badge','.card-copy .text-link'];
        const values=selectors.flatMap(selector=>Array.from(document.querySelectorAll(selector)).map(el=>({
          selector,ratio:ratio(over(rgba(getComputedStyle(el).color),background(el)),background(el))
        })));
        const card=document.querySelector('.product-card');
        return {values,cardBackground:card?getComputedStyle(card).backgroundColor:null,
          headerBackground:getComputedStyle(document.querySelector('.site-header')).backgroundColor,
          overflow:document.documentElement.scrollWidth>innerWidth+1};
      });
      assert.ok(result.values.length, `${pathname}: must actually check product copy`);
      for (const value of result.values) {
        assert.ok(value.ratio>=4.5, `${pathname} ${theme}/${language}/${width} ${value.selector}: contrast ${value.ratio.toFixed(2)}:1`);
        minimum=Math.min(minimum,value.ratio); samples++;
      }
      const expected = theme==='light'?'rgb(254, 253, 251)':'rgb(27, 31, 37)';
      assert.equal(result.cardBackground,expected,`${pathname}: opaque theme-aware cards`);
      assert.equal(result.headerBackground,expected,`${pathname}: header matches its navigation`);
      assert.equal(result.overflow,false,`${pathname}: no horizontal overflow`);
      checks++;
    }
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({status:'PASS',mode:live?'live':'local',pages:pages.length,checks,textSamples:samples,minimumContrast:Number(minimum.toFixed(2)),errors:errors.length},null,2));
} finally {await browser.close();}
