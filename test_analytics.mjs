import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('analytics.js',import.meta.url),'utf8');
function app(options={}){
  const calls=[],listeners={};
  const document={readyState:'complete',visibilityState:'visible',addEventListener:(name,fn)=>listeners[name]=fn,...options.document};
  const context=vm.createContext({URL,document,navigator:options.navigator||{},
    location:{hostname:'overly.live',pathname:'/categories/kids/',search:'?q=private',hash:'#private',...options.location},
    OVERLY_CONFIG:{aliexpressSearchApi:options.api||'https://overly-aliexpress-search.overly-sa.workers.dev'},
    fetch:(url,init)=>{calls.push({url,init,body:JSON.parse(init.body)});return options.fail?Promise.reject(Error('offline')):Promise.resolve({ok:true});}});
  vm.runInContext(source,context);return{context,document,listeners,calls,api:context.OverlyAnalytics};
}
test('page view is sent once without query, hash, credentials or visitor identifiers',()=>{
  const a=app();a.api.pageView();a.listeners.visibilitychange();vm.runInContext(source,a.context);
  assert.equal(a.calls.length,1);assert.deepEqual(a.calls[0].body,{event_type:'page_view',page_path:'/categories/kids/'});
  assert.equal(a.calls[0].init.credentials,'omit');assert.equal(a.calls[0].init.referrerPolicy,'origin');
  assert.doesNotMatch(source,/localStorage|sessionStorage|document\.cookie/);
});
test('DNT, global privacy control, nonproduction hosts and foreign endpoints disable analytics',()=>{
  for(const options of [{navigator:{doNotTrack:'1'}},{navigator:{globalPrivacyControl:true}},
    {location:{hostname:'overly-staging-site.overly-sa.workers.dev'}},{api:'https://evil.example'},{api:'https://user:pass@overly-aliexpress-search.overly-sa.workers.dev'}]){
    const a=app(options);a.api.pageView();a.api.productClick({store:'amazon',asin:'B0DL5FT193'});assert.equal(a.calls.length,0);
  }
});
test('background/prerendered loads wait for visibility and do not double-count',()=>{
  for(const initial of [{visibilityState:'hidden'},{prerendering:true}]){
    const a=app({document:initial});assert.equal(a.calls.length,0);
    Object.assign(a.document,{visibilityState:'visible',prerendering:false});a.listeners.visibilitychange();a.listeners.prerenderingchange();assert.equal(a.calls.length,1);
  }
});
test('valid product clicks carry only catalog data; invalid IDs are ignored',()=>{
  const a=app();a.api.productClick({store:'amazon',asin:'B0DL5FT193',title:'اختبار',category:'الإلكترونيات',email:'never-send'});
  a.api.productClick({store:'aliexpress',product_id:'1005001234567890'});
  a.api.productClick({store:'amazon',asin:'wrong'});a.api.productClick({store:'external',asin:'B0DL5FT193'});
  assert.equal(a.calls.length,3);assert.equal(a.calls[1].body.product_key,'amazon:B0DL5FT193');assert.ok(!('email' in a.calls[1].body));
});
test('static merchant links count primary and middle clicks without intercepting navigation',()=>{
  const a=app(), target={closest:()=>({dataset:{overlyProduct:'B0DL5FT193',overlyStore:'amazon',overlyTitle:'اختبار'}})};
  for(const [type,button]of [['click',0],['auxclick',1],['auxclick',2]])a.listeners[type]({type,button,target,preventDefault(){assert.fail('Must not interfere with merchant navigation')}});
  assert.equal(a.calls.filter(call=>call.body.event_type==='product_click').length,2);
});
test('analytics outages cannot reject product navigation',async()=>{
  const a=app({fail:true});assert.doesNotThrow(()=>a.api.productClick({store:'amazon',asin:'B0DL5FT193'}));
  await new Promise(resolve=>setImmediate(resolve));
});
