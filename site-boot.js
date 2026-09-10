/* Restore presentation before paint; no network calls or visitor identifiers. */
(function(root){
  let theme='light',language='ar';
  try{theme=root.localStorage.getItem('site_theme')==='dark'?'dark':'light';language=root.localStorage.getItem('overly_language_v1')==='en'?'en':'ar';}catch{}
  const params=new URLSearchParams(root.location.search);
  const requested=params.get('lang'),requestedTheme=params.get('theme');
  if(['light','dark'].includes(requestedTheme)){theme=requestedTheme;try{root.localStorage.setItem('site_theme',theme);}catch{}}
  if(['ar','en'].includes(requested)){language=requested;try{root.localStorage.setItem('overly_language_v1',language);}catch{}}
  root.document.documentElement.dataset.theme=theme;
  root.document.documentElement.lang=language;
  root.document.documentElement.dir=language==='en'?'ltr':'rtl';
})(globalThis);
