// Offline browser integration check: no analytics, merchant or GitHub traffic
// reaches the network. Build dist-site first. Supply PLAYWRIGHT_MODULE if needed.
import assert from 'node:assert/strict';
import {readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=fileURLToPath(new URL('.',import.meta.url)), bundle=path.join(root,'dist-site');
const csp=(await readFile(path.join(bundle,'_headers'),'utf8')).match(/Content-Security-Policy: (.*)/)[1];
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png'};
const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
const tiny=Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7','base64');
const errors=[];let views=0,clicks=0;
try {
  for(const language of ['ar','en']) for(const width of [320,1280]) {
    const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
    const events=[];
    await context.route('**/*',async route=>{
      const req=route.request(),url=new URL(req.url());
      if(url.origin==='https://overly-aliexpress-search.overly-sa.workers.dev'&&url.pathname==='/events') {
        if(req.method()==='POST')events.push(req.postDataJSON());
        return route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'https://overly.live','Access-Control-Allow-Methods':'POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type'}});
      }
      if(url.origin!=='https://overly.live')return route.fulfill({status:200,contentType:req.resourceType()==='image'?'image/gif':'text/css',body:req.resourceType()==='image'?tiny:''});
      let file=path.resolve(bundle,'.'+decodeURIComponent(url.pathname));
      assert.ok(file===bundle||file.startsWith(bundle+path.sep));
      try{if((await stat(file)).isDirectory())file=path.join(file,'index.html')}catch{if(!path.extname(file))file+='.html'}
      try{return route.fulfill({status:200,body:await readFile(file),contentType:mime[path.extname(file)]||'application/octet-stream',headers:{'Content-Security-Policy':csp}})}catch{return route.fulfill({status:404,body:'Not found'})}
    });
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{globalThis.cspViolations=[];document.addEventListener('securitypolicyviolation',e=>globalThis.cspViolations.push({directive:e.violatedDirective,blocked:e.blockedURI}));});
    for(const routePath of ['/','/categories/kids/','/products/aliexpress-1005010561069073/','/browse','/privacy.html']) {
      const start=events.length;
      const request=page.waitForResponse(r=>r.url().endsWith('/events')&&r.request().method()==='POST');
      assert.equal((await page.goto(`https://overly.live${routePath}?lang=${language}&theme=light&secret=not-tracked#private-fragment`)).status(),200);
      await request;
      await page.evaluate(()=>{OverlyAnalytics.pageView();OverlyAnalytics.pageView()});
      assert.equal(events.slice(start).filter(e=>e.event_type==='page_view').length,1);views++;
      assert.equal(events[start].page_path,routePath);
      assert.ok(!JSON.stringify(events.slice(start)).includes('not-tracked'));
      assert.deepEqual(await page.evaluate(()=>cspViolations.filter(v=>v.blocked.includes('/events')||v.blocked.includes('analytics.js'))),[]);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,routePath);
      if(routePath.includes('/products/')) {
        const link=page.locator('a[data-overly-product]'),href=await link.getAttribute('href');
        await page.evaluate(()=>document.addEventListener('click',e=>e.preventDefault(),{capture:true,once:true}));
        const sent=page.waitForResponse(r=>r.url().endsWith('/events')&&r.request().method()==='POST');
        await link.click();await sent;
        const event=events.at(-1);assert.equal(event.event_type,'product_click');assert.equal(event.product_key,'aliexpress:1005010561069073');clicks++;
        assert.equal(await link.getAttribute('href'),href);
      }
    }
    await context.close();
  }

  // Exercise the actual extension popup, with Chrome APIs and GitHub mocked.
  const context=await browser.newContext({viewport:{width:640,height:1000}});
  let catalog={deals:[{store:'amazon',asin:'B0DL5FT193',title:'منتج محلي لاختبار المزامنة',image:'https://m.media-amazon.com/test.jpg',category:'الإلكترونيات',original_price:0,discount_percent:0,rating:4.8,title_en:'A fixture product',owner_pinned:true}],count:1};
  let puts=0;
  await context.addInitScript(()=>{
    const data={overly_github_token_v5:'test-only'};
    globalThis.chrome={storage:{local:{get(keys,cb){cb(Object.fromEntries(keys.map(k=>[k,data[k]])))},set(value,cb){Object.assign(data,value);cb?.()},remove(key,cb){delete data[key];cb?.()}}},tabs:{query(_q,cb){cb([])},create(){}},runtime:{}};
  });
  await context.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.origin==='https://api.github.com') {
      if(req.method()==='PUT'){puts++;catalog=JSON.parse(Buffer.from(req.postDataJSON().content,'base64').toString('utf8'));return route.fulfill({json:{commit:{html_url:'https://github.com/fixture/fixture'}}})}
      return route.fulfill({body:JSON.stringify(catalog),contentType:'application/json'});
    }
    if(url.origin!=='https://extension.example')return route.fulfill({contentType:'image/gif',body:tiny});
    const file=path.join(root,'browser-extension',path.basename(url.pathname));
    return route.fulfill({body:await readFile(file),contentType:mime[path.extname(file)]});
  });
  const popup=await context.newPage();popup.on('pageerror',e=>errors.push(e.message));
  await popup.goto('https://extension.example/popup.html');
  await popup.locator('#syncGithub').click();await popup.locator('.item').first().waitFor();
  assert.equal(await popup.locator('#count').textContent(),'1');
  await popup.locator('button[data-action="edit"]').click();
  await popup.locator('#title').fill('اسم معدل بالواجهة لا يضيع تقييم المنتج');
  await popup.locator('#saveProduct').click();
  await popup.locator('#publishDirect').click();
  await popup.waitForFunction(()=>!document.querySelector('#publishDirect').disabled);
  assert.equal(puts,1);assert.equal(catalog.deals[0].rating,4.8);assert.equal(catalog.deals[0].title_en,undefined);
  await popup.locator('button[data-action="edit"]').click();
  await popup.locator('#title').fill('مسودة محلية قديمة');await popup.locator('#saveProduct').click();
  catalog.deals[0].title='تعديل بعيد أحدث';
  await popup.locator('#publishDirect').click();await popup.waitForFunction(()=>!document.querySelector('#publishDirect').disabled);
  assert.equal(puts,1);assert.match(await popup.locator('#status').textContent(),/تعارض/);
  await context.close();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'PASS',pageViews:views,merchantClicks:clicks,extension:'sync/edit/publish/conflict passed with mock APIs',javascriptErrors:errors.length,externalNetworkRequests:0}));
}finally{await browser.close()}
