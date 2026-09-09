import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import vm from 'node:vm';

const files=['catalog-locale.js','catalog-additions.js','catalog-native-en.js','site-copy-en.js','legal-copy-en.js','site-extra-en.js','site-angles-en.js','site-phrases.js','locale.js'];
const html=readFileSync(new URL('index.html',import.meta.url),'utf8');
const appSource=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)].filter(([,attrs])=>!attrs.includes('src=')&&!attrs.includes('ld+json')).at(-1)[2];
const fixture=JSON.parse(readFileSync(new URL('deals.json',import.meta.url),'utf8'));
function translations(context=vm.createContext({})){for(const file of files)vm.runInContext(readFileSync(new URL(file,import.meta.url),'utf8'),context,{filename:file});return context}
function element(){
  const classes=new Set(['hidden']),attrs={},listeners={};
  return {dataset:{},style:{setProperty(){}},value:'',textContent:'',innerHTML:'',hidden:false,open:false,isConnected:true,scrollTop:0,
    classList:{add:k=>classes.add(k),remove:k=>classes.delete(k),contains:k=>classes.has(k),toggle(k,force){if(force===undefined)force=!classes.has(k);force?classes.add(k):classes.delete(k);return force}},
    setAttribute:(k,v)=>attrs[k]=v,getAttribute:k=>attrs[k],removeAttribute:k=>delete attrs[k],
    addEventListener:(k,fn)=>listeners[k]=fn,querySelector:()=>null,querySelectorAll:()=>[],
    insertAdjacentHTML(_,markup){this.innerHTML+=markup},scrollIntoView(){},focus(){},showModal(){this.open=true},close(){this.open=false},closest:()=>null,listeners,attrs};
}
function app(language='ar'){
  const elements=new Map(),listeners={},requests=[];
  const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id)};
  const saved=new Map([['overly_language_v1',language]]);
  const document={documentElement:{lang:'ar',dir:'rtl',dataset:{theme:'dark'},scrollHeight:1000},body:element(),getElementById:el,querySelector:el,querySelectorAll:()=>[],addEventListener:(name,fn)=>listeners[name]=fn,createTreeWalker:()=>({nextNode:()=>false})};
  const context=vm.createContext({document,URL,URLSearchParams,Intl,Date,AbortController,console,
    location:{origin:'https://overly.live',pathname:'/',href:'https://overly.live/',search:'',hash:''},
    localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},sessionStorage:{getItem:()=>null,setItem(){}},navigator:{},
    fetch:url=>{requests.push(String(url));return new Promise(()=>{})},setTimeout:()=>1,clearTimeout(){},matchMedia:()=>({matches:false}),addEventListener(){},innerHeight:800,scrollY:0});
  context.window=context;translations(context);vm.runInContext(readFileSync(new URL('search-config.js',import.meta.url),'utf8'),context);vm.runInContext(appSource,context,{filename:'index-app.js'});
  context.fixture=fixture;vm.runInContext('applyDealPayload(fixture)',context);
  return {context,el,elements,listeners,requests,saved,document};
}
test('application runs with the current catalogue in Arabic and English',()=>{
  for(const lang of ['ar','en']){const {context,el}=app(lang);assert.equal(vm.runInContext('deals.length',context),fixture.deals.length);assert.match(el('hero').innerHTML,/live-feature/);assert.match(el('dealsGrid').innerHTML,/product-card/)}
});
test('every current product has an English title; switching back preserves all original data',()=>{
  const context=translations(),api=context.createOverlyI18n(),before=JSON.stringify(fixture);api.setLanguage('en');
  for(const deal of fixture.deals){assert.doesNotMatch(api.productTitle(deal),/[\u0600-\u06ff]/,deal.title);assert.ok(api.productSearchText(deal).includes(deal.title));}
  api.setLanguage('ar');for(const deal of fixture.deals)assert.equal(api.productTitle(deal),deal.title);assert.equal(JSON.stringify(fixture),before);
});
test('language change re-renders titles and quick view without changing affiliate destinations',()=>{
  const {context,el,listeners}=app('ar');vm.runInContext('openQuickView(dealKey(deals[0]))',context);const url=el('quickLink').href;
  context.OverlyI18n.setLanguage('en');listeners['overly:languagechange']();assert.doesNotMatch(el('quickTitle').textContent,/[\u0600-\u06ff]/);assert.equal(el('quickLink').href,url);
  context.OverlyI18n.setLanguage('ar');listeners['overly:languagechange']();assert.match(el('quickTitle').textContent,/[\u0600-\u06ff]/);assert.equal(el('quickLink').href,url);
});
test('both Arabic and English searches remain usable in either display language',()=>{
  const {context}=app();for(const query of ['charger','شاحن']){context.searchTerm=query;vm.runInContext('query=searchTerm',context);const before=vm.runInContext('filteredDeals().map(dealKey).join(",")',context);assert.ok(before);context.OverlyI18n.setLanguage('en');assert.equal(vm.runInContext('filteredDeals().map(dealKey).join(",")',context),before);}
});
test('theme switching keeps the language and persists the requested pair',()=>{
  const {context,document,saved}=app('en');for(const theme of ['light','dark']){context.nextTheme=theme;vm.runInContext('setTheme(nextTheme)',context);assert.equal(saved.get('site_theme'),theme);assert.equal(document.documentElement.dataset.theme,theme);assert.equal(context.OverlyI18n.language,'en')}
  const css=readFileSync(new URL('live-theme.css',import.meta.url),'utf8');assert.match(css,/#141619/);assert.match(css,/#f2f6fa/);assert.match(css,/overly-glass-atelier-v1.jpg/);assert.match(css,/prefers-reduced-motion/);
});
test('translated dynamic product cards, statuses and labels have no untranslated Arabic',()=>{
  const {context,elements,listeners}=app('en');vm.runInContext('visibleLimit=1000;renderAll();openQuickView(dealKey(deals[0]));runMobileSearch("charger");query="";visibleLimit=1000;renderGrid()',context);
  listeners.mouseout({clientY:0});
  const markup=[...elements.values()].map(el=>el.innerHTML+'<div>'+el.textContent+'</div>').join('\n');
  const parser='import json,sys;from test_language_coverage import Copy;p=Copy();p.feed(sys.stdin.read());print(json.dumps(sorted(p.values)))';
  const strings=JSON.parse(execFileSync('python3',['-c',parser],{cwd:new URL('.',import.meta.url),input:markup,encoding:'utf8'}));
  const missing=strings.filter(s=>/[\u0600-\u06ff]/.test(context.OverlyI18n.t(s).replace(/أوفرلي/g,'')));
  assert.deepEqual(missing,[]);
});
test('search requests follow display language and cancellation rejects stale results',async()=>{
  const {context,requests,el,listeners}=app('en');el('aliSearchInput').value='charger';vm.runInContext('searchAliExpress("charger")',context);assert.ok(requests.some(url=>url.includes('lang=en')));
  context.OverlyI18n.setLanguage('ar');listeners['overly:languagechange']();assert.ok(requests.some(url=>url.includes('lang=ar')));
  assert.match(appSource,/controller.signal.aborted \|\| aliSearchController !== controller/);
});

test('static translation adapter restores original text and never edits values or merchant links',()=>{
  const attrs={'aria-label':'اختر التصنيف',href:'https://s.click.aliexpress.com/e/test',value:'الإلكترونيات'};
  const parent={closest:()=>null};const text={nodeType:3,nodeValue:'  العروض  ',parentElement:parent};
  const control={closest:()=>null,getAttribute:k=>attrs[k]??null,setAttribute:(k,v)=>attrs[k]=v};
  const body={nodeType:1,closest:()=>null,getAttribute:()=>null,querySelectorAll:()=>[control]};
  const document={readyState:'loading',documentElement:{dataset:{},lang:'ar'},body,addEventListener(){},dispatchEvent(){},getElementById:()=>null,querySelector:()=>null,createTreeWalker(){let done=false;return {currentNode:text,nextNode(){if(done)return false;done=true;return true}}}};
  const context=translations(vm.createContext({document,CustomEvent:class{},localStorage:{getItem:()=>null,setItem(){}}}));
  vm.runInContext(readFileSync(new URL('site-language.js',import.meta.url),'utf8'),context);
  context.OverlySiteLanguage.change('en');assert.equal(text.nodeValue,'  Deals  ');assert.equal(attrs['aria-label'],'Choose a category');
  context.OverlySiteLanguage.change('ar');assert.equal(text.nodeValue,'  العروض  ');assert.equal(attrs.value,'الإلكترونيات');assert.equal(attrs.href,'https://s.click.aliexpress.com/e/test');
  text.nodeValue='الرئيسية';context.OverlySiteLanguage.change('en');assert.equal(text.nodeValue,'Home');context.OverlySiteLanguage.change('ar');assert.equal(text.nodeValue,'الرئيسية');
});
test('pre-paint restoration honours language URLs and works when browser storage is disabled',()=>{
  for(const blocked of [false,true]){
    const context=vm.createContext({URLSearchParams,location:{search:'?lang=en'},document:{documentElement:{dataset:{}}},localStorage:{getItem:k=>{if(blocked)throw Error('blocked');return k==='site_theme'?'light':'ar'},setItem(){if(blocked)throw Error('blocked')}}});
    vm.runInContext(readFileSync(new URL('site-boot.js',import.meta.url),'utf8'),context);
    assert.equal(context.document.documentElement.lang,'en');assert.equal(context.document.documentElement.dir,'ltr');assert.equal(context.document.documentElement.dataset.theme,blocked?'dark':'light');
  }
});
