/* Applies the same opt-in language to static pages and dynamically rendered UI.
   Changes text/accessible labels only; never data values, handlers or merchant links. */
(function(root){
  const doc=root.document,api=root.OverlyI18n;if(!doc||!api)return;
  const textState=new WeakMap(),attributeState=new WeakMap();let observer;
  const excluded='script,style,noscript,code,pre,[translate="no"],[data-language-picker]';
  function translateNode(node){
    if(!node.parentElement||node.parentElement.closest(excluded))return;
    let state=textState.get(node);
    if(!state||node.nodeValue!==state.last)state={original:node.nodeValue,last:node.nodeValue};
    const space=state.original.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const next=space[1]+api.t(space[2])+space[3];
    if(next!==node.nodeValue)node.nodeValue=next;
    state.last=next;textState.set(node,state);
  }
  function translateAttributes(node){
    if(node.closest(excluded))return;
    const states=attributeState.get(node)||{};
    for(const name of ['alt','title','placeholder','aria-label']){
      const value=node.getAttribute(name);if(value===null)continue;
      let state=states[name];if(!state||value!==state.last)state={original:value,last:value};
      const next=api.t(state.original);if(value!==next)node.setAttribute(name,next);state.last=next;states[name]=state;
    }attributeState.set(node,states);
  }
  function refresh(container=doc.body){
    if(!container)return;
    if(container.nodeType===3){translateNode(container);return;}
    if(container.nodeType!==1)return;
    if(container.closest(excluded))return;
    translateAttributes(container);
    const walk=doc.createTreeWalker(container,4);while(walk.nextNode())translateNode(walk.currentNode);
    container.querySelectorAll('[alt],[title],[placeholder],[aria-label]').forEach(translateAttributes);
    const title=doc.querySelector('title');if(title?.firstChild)translateNode(title.firstChild);
  }
  function observe(){observer?.observe(doc.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['alt','title','placeholder','aria-label']});}
  function change(language,{notify=true,remember=true}={}){
    observer?.disconnect();api.setLanguage(language);
    if(remember){try{root.localStorage.setItem('overly_language_v1',api.language);}catch{}}
    const select=doc.getElementById('languageSelect');if(select)select.value=api.language;
    refresh();observe();
    if(notify)doc.dispatchEvent(new CustomEvent('overly:languagechange',{detail:{language:api.language}}));
  }
  function init(){
    const parent=doc.querySelector('.nav-actions,.shell.nav,.legal-nav')||doc.querySelector('main');
    if(parent&&!doc.getElementById('themeToggle')){
      const button=doc.createElement('button');button.id='themeToggle';button.type='button';button.className='site-theme-control';button.textContent='◐';button.setAttribute('aria-label','الوضع الداكن / الفاتح');
      button.addEventListener('click',()=>{const theme=doc.documentElement.dataset.theme==='light'?'dark':'light';doc.documentElement.dataset.theme=theme;try{root.localStorage.setItem('site_theme',theme);}catch{}const meta=doc.querySelector('meta[name="theme-color"]');if(meta)meta.content=theme==='light'?'#f2f6fa':'#141619';});parent.append(button);
    }
    if(parent&&!doc.getElementById('languageSelect')){
      const label=doc.createElement('label');label.className='site-language-control';label.dataset.languagePicker='';label.setAttribute('translate','no');
      const select=doc.createElement('select');select.id='languageSelect';select.setAttribute('aria-label','Language / اللغة');
      for(const [value,text]of [['ar','العربية'],['en','English']]){const option=doc.createElement('option');option.value=value;option.textContent=text;select.append(option);}label.append(select);parent.append(label);
      select.addEventListener('change',()=>{const url=new URL(root.location.href);url.searchParams.set('lang',select.value);root.history.replaceState(null,'',url.pathname+url.search+url.hash);change(select.value);});
    }
    observer=new MutationObserver(records=>{observer.disconnect();const containers=new Set();for(const record of records){if(record.type==='characterData')translateNode(record.target);else if(record.type==='attributes')translateAttributes(record.target);else record.addedNodes.forEach(n=>containers.add(n));}containers.forEach(refresh);observe();});
    const requested=new URLSearchParams(root.location.search).get('lang');
    change(['ar','en'].includes(requested)?requested:api.language,{notify:true,remember:['ar','en'].includes(requested)});
    // Language-only navigation parameter; external/affiliate URLs are untouched.
    doc.addEventListener('click',event=>{const a=event.target.closest?.('a[href]');if(!a||a.target==='_blank'||a.getAttribute('href').startsWith('#'))return;try{const url=new URL(a.href,root.location.href);if(url.origin!==root.location.origin||!/^https?:$/.test(url.protocol))return;url.searchParams.set('lang',api.language);a.href=url.href;}catch{}});
  }
  root.OverlySiteLanguage={change,refresh};
  if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',init,{once:true});else init();
})(globalThis);
