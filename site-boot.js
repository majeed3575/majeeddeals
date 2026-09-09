/* Restore presentation before paint; no network calls or visitor identifiers. */
(function(root){
  let theme='dark',language='ar';
  try{theme=root.localStorage.getItem('site_theme')==='light'?'light':'dark';language=root.localStorage.getItem('overly_language_v1')==='en'?'en':'ar';}catch{}
  const requested=new URLSearchParams(root.location.search).get('lang');
  if(['ar','en'].includes(requested)){language=requested;try{root.localStorage.setItem('overly_language_v1',language);}catch{}}
  root.document.documentElement.dataset.theme=theme;
  root.document.documentElement.lang=language;
  root.document.documentElement.dir=language==='en'?'ltr':'rtl';
})(globalThis);
