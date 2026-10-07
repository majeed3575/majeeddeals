import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('browser-extension/popup.js', import.meta.url), 'utf8');
function extension(extra = {}) {
  const ctx = vm.createContext({ URL, URLSearchParams, TextEncoder, TextDecoder, Uint8Array,
    AbortSignal, Response, crypto: globalThis.crypto, console, ...extra });
  vm.runInContext(source.slice(0, source.indexOf('$("dealPrice").addEventListener')), ctx);
  return ctx;
}
const product = (extra = {}) => ({ store:'amazon', asin:'B0DL5FT193', title:'منتج تجربة آمن للمزامنة',
  image:'https://m.media-amazon.com/images/I/test.jpg', original_price:100, discount_percent:20,
  category:'الإلكترونيات', rating:4.8, title_en:'Original English title', owner_pinned:true,
  auto_discovered:false, sales_volume:2200, added_at:'2026-01-01', ...extra });
const plain = value => JSON.parse(JSON.stringify(value));

test('every current catalog item survives extension sync and an unchanged publish byte-for-byte', () => {
  const ctx=extension();
  ctx.catalog=JSON.parse(readFileSync(new URL('deals.json',import.meta.url),'utf8')).deals;
  const result=vm.runInContext('const hashes=remoteHashes(catalog); const synced=mergeForSync(catalog,[],{}); ({synced,merged:mergeForPublish(catalog,synced,hashes),issues:auditList(synced,{requireAffiliate:true}).filter(x=>x.errors.length)})',ctx);
  assert.equal(result.synced.length,ctx.catalog.length);
  assert.deepEqual(plain(result.issues),[]);
  assert.equal(JSON.stringify(result.merged),JSON.stringify(ctx.catalog));
});
function fixture() {
  const ctx = extension();
  ctx.original = product();
  vm.runInContext('local = normalizedItem(original); baseline = remoteHashes([original])', ctx);
  return ctx;
}
test('publishing an unchanged synchronized product preserves every metadata field', () => {
  const ctx = fixture();
  assert.deepEqual(plain(vm.runInContext('mergeForPublish([original], [local], baseline)', ctx)), [product()]);
});
test('a local edit preserves uneditable data and clears only stale title/discount fallbacks', () => {
  const ctx = fixture();
  const result = vm.runInContext('mergeForPublish([{...original,manual_discount_percent:25}], [{...local,title:"عنوان جديد للمنتج المعدل",discount_percent:0}], baseline)', ctx)[0];
  assert.equal(result.rating,4.8);assert.equal(result.sales_volume,2200);assert.equal(result.added_at,'2026-01-01');
  assert.equal(result.title_en,undefined);assert.ok(!result.manual_discount_percent);assert.equal(result.owner_pinned,true);
});
test('a stale unchanged local copy never overwrites remote changes or recreates removed items', () => {
  const ctx = fixture();
  const result = vm.runInContext('mergeForPublish([{...original,title:"عنوان أحدث من لوحة الإدارة"}], [local], baseline)', ctx);
  assert.equal(result[0].title,'عنوان أحدث من لوحة الإدارة');
  assert.equal(vm.runInContext('mergeForPublish([], [local], baseline)',ctx).length,0);
});
test('concurrent changes to the same product stop publishing before any write', () => {
  const ctx = fixture();
  assert.throws(()=>vm.runInContext('mergeForPublish([{...original,title:"عنوان أحدث بعيد"}], [{...local,title:"عنوان محلي مختلف"}], baseline)',ctx),/تعارض/);
  assert.throws(()=>vm.runInContext('mergeForPublish([], [{...local,title:"مسودة لمنتج حذف بعيداً"}], baseline)',ctx),/تعارض/);
});
test('missing or different-repository baselines do not authorize overwriting existing items', () => {
  const ctx = fixture();
  assert.throws(()=>vm.runInContext('mergeForPublish([original], [{...local,title:"نسخة لا نعرف مصدرها"}], {})',ctx),/تعارض/);
});
test('new manual products are pinned and unrelated remote products remain unchanged', () => {
  const ctx = fixture();
  const result=vm.runInContext('mergeForPublish([original], [{...local,asin:"B08D22WD2W"}], {})',ctx);
  assert.equal(result.length,2);assert.deepEqual(plain(result[0]),product());
  assert.equal(result[1].owner_pinned,true);assert.equal(result[1].auto_discovered,false);
});
test('sync refreshes untouched local copies while preserving nonconflicting drafts', () => {
  const ctx = fixture();
  assert.equal(vm.runInContext('mergeForSync([{...original,title:"تحديث بعيد آمن"}], [local], baseline)[0].title',ctx),'تحديث بعيد آمن');
  assert.equal(vm.runInContext('mergeForSync([original], [{...local,title:"مسودة محلية آمنة"}], baseline)[0].title',ctx),'مسودة محلية آمنة');
  assert.throws(()=>vm.runInContext('mergeForSync([{...original,title:"تحديث بعيد مختلف"}], [{...local,title:"مسودة محلية مختلفة"}], baseline)',ctx),/تعارض/);
});
test('catalog products without reported prices or discounts remain editable and synchronizable', () => {
  const ctx=fixture();
  assert.equal(vm.runInContext('validateItem(normalizedItem({...original,original_price:0,discount_percent:0})).length',ctx),0);
  assert.equal(vm.runInContext('normalizedValidList([{...original,original_price:0,discount_percent:0}]).length',ctx),1);
});

test('editing another field preserves a long remote title and its translation', () => {
  const ctx=extension();ctx.original=product({title:'منتج طويل '.repeat(18)});
  const result=vm.runInContext('mergeForPublish([original], [{...normalizedItem(original),discount_percent:30}], remoteHashes([original]))[0]',ctx);
  assert.equal(result.title,ctx.original.title);assert.equal(result.title_en,ctx.original.title_en);
});

test('baseline hashes are scoped to owner, repository, branch and file, including legacy migration', async () => {
  const data={};const ctx=extension({chrome:{storage:{local:{get(keys,cb){cb(data)},set(value,cb){Object.assign(data,value);cb()}}}}});
  ctx.config={owner:'fixture',repo:'first',branch:'main',path:'deals.json'};ctx.original=product();
  data.overly_remote_hashes_v5={old:'hash'};
  assert.deepEqual(plain(await vm.runInContext('baselineFor(config)',ctx)),{});
  await vm.runInContext('saveRemoteState([original],config)',ctx);
  assert.ok(Object.keys(await vm.runInContext('baselineFor(config)',ctx)).length);
  for(const key of ['owner','repo','branch','path']) {
    ctx.other={...ctx.config,[key]:'different'};
    assert.deepEqual(plain(await vm.runInContext('baselineFor(other)',ctx)),{});
  }
});
test('extraction only runs on real marketplace hosts, not lookalikes or links mentioning them', () => {
  const ctx=extension();
  for(const url of ['https://evil.example/?amazon.sa','https://notamazon.sa/dp/test','https://aliexpress.com.evil.example/item/1','https://evilaliexpress.com/item/1']) {
    ctx.url=url;assert.equal(vm.runInContext('productPageStore(url)',ctx),'');
  }
  for(const [url,store] of [['https://www.amazon.sa/dp/B0DL5FT193','amazon'],['https://ar.aliexpress.com/item/1005001234567.html','aliexpress']]) {
    ctx.url=url;assert.equal(vm.runInContext('productPageStore(url)',ctx),store);
  }
});

test('malformed identifiers are rejected rather than silently truncated into another product', () => {
  const ctx=extension();
  for(const id of ['xB0DL5FT193','B0DL5FT193x','https://amazon.sa/dp/B0DL5FT193']) {
    ctx.id=id;assert.equal(vm.runInContext('normalizeAsin(id)',ctx),'');
  }
  for(const id of ['x1005001234567','10050012345678901234567','1005001234567.html']) {
    ctx.id=id;assert.equal(vm.runInContext('normalizeProductId(id)',ctx),'');
  }
  assert.equal(vm.runInContext('normalizeAsin(" b0dl5ft193 ")',ctx),'B0DL5FT193');
});

test('extension image and affiliate validation rejects unsupported origins and credential-bearing URLs', () => {
  const ctx=fixture();
  for(const image of ['https://evil.example/photo.jpg','https://m.media-amazon.com.evil.example/photo.jpg','https://name:pass@m.media-amazon.com/photo.jpg','https://m.media-amazon.com:8443/photo.jpg']) {
    ctx.image=image;assert.ok(vm.runInContext('validateItem({...local,image}).length',ctx));
  }
  for(const url of ['https://name:pass@s.click.aliexpress.com/e/test','https://s.click.aliexpress.com:8443/e/test']) {
    ctx.url=url;assert.equal(vm.runInContext('isAliExpressAffiliateUrl(url)',ctx),false);
  }
  for(const image of ['https://m.media-amazon.com/photo.jpg','https://overly.live/assets/amazon-manual/photo.webp']) {
    ctx.image=image;assert.equal(vm.runInContext('validateItem({...local,image}).length',ctx),0);
  }
});

test('publishing flow skips unchanged rows, keeps metadata and performs no external network I/O', async () => {
  const localStore={}, elements=new Map(), requests=[];
  const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',classList:{remove(){},add(){}},scrollIntoView(){}});return elements.get(id)};
  let remote={count:1,deals:[product()], custom_metadata:'preserve me'};
  const ctx=extension({document:{getElementById:el},btoa:s=>Buffer.from(s,'binary').toString('base64'),
    chrome:{storage:{local:{get(keys,cb){cb(Object.fromEntries(keys.map(k=>[k,localStore[k]])))},set(obj,cb){Object.assign(localStore,obj);cb()}}}},
    fetch:async(url,options={})=>{
      requests.push(options.method||'GET');
      if(options.method==='PUT'){remote=JSON.parse(Buffer.from(JSON.parse(options.body).content,'base64').toString('utf8'));return Response.json({commit:{html_url:'https://github.com/fixture/fixture/commit/test'}})}
      return new Response(JSON.stringify(remote));
    }
  });
  Object.assign(localStore,{collected_deals_v5:[plain(vm.runInContext(`normalizedItem(${JSON.stringify(product())})`,ctx))],overly_github_token_v5:'fixture-token'});
  for(const [id,value]of Object.entries({githubOwner:'fixture',githubRepo:'fixture',githubBranch:'main',githubPath:'deals.json'}))el(id).value=value;
  vm.runInContext('renderList = async () => {};',ctx);
  ctx.remote=remote;
  await vm.runInContext('saveRemoteState(remote.deals,configFromForm())',ctx);
  await vm.runInContext('publishToGithub()',ctx);
  assert.equal(requests.filter(x=>x==='PUT').length,0);
  localStore.collected_deals_v5[0].title='تعديل محلي لا يفقد بيانات المنتج';
  await vm.runInContext('publishToGithub()',ctx);
  assert.equal(requests.filter(x=>x==='PUT').length,1);
  assert.equal(remote.deals[0].rating,4.8);assert.equal(remote.custom_metadata,'preserve me');
});
