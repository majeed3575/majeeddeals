/* Aggregate events only: no cookies, storage, visitor IDs, query strings or hashes. */
(() => {
  if (globalThis.OverlyAnalytics) return;
  const endpoint = (() => {
    try {
      const url = new URL(globalThis.OVERLY_CONFIG?.aliexpressSearchApi || '');
      return url.origin === 'https://overly-aliexpress-search.overly-sa.workers.dev' &&
        !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash
        ? url.origin + '/events' : '';
    } catch { return ''; }
  })();
  let pageSent = false;
  const enabled = () => endpoint && /^(www\.)?overly\.live$/.test(location.hostname) &&
    navigator.doNotTrack !== '1' && globalThis.doNotTrack !== '1' && !navigator.globalPrivacyControl && !document.prerendering;
  function send(eventType, product = null) {
    if (!enabled()) return;
    const payload = { event_type: eventType, page_path: location.pathname };
    if (eventType === 'product_click') {
      const store = product?.store;
      const id = String(store === 'aliexpress' ? product?.product_id || '' : product?.asin || '');
      if (!(store === 'amazon' && /^[a-z0-9]{10}$/i.test(id)) && !(store === 'aliexpress' && /^\d{6,20}$/.test(id))) return;
      Object.assign(payload, { product_key: `${store}:${id}`, product_title: String(product.title || '').slice(0, 180),
        store, category: String(product.category || '').slice(0, 60) });
    }
    try {
      Promise.resolve(fetch(endpoint, { method: 'POST', mode: 'cors', credentials: 'omit',
        referrerPolicy: 'origin', keepalive: true, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload) })).catch(() => {});
    } catch { /* Analytics must never interrupt browsing or merchant navigation. */ }
  }
  function pageView() {
    if (pageSent || document.visibilityState === 'hidden' || !enabled()) return;
    pageSent = true;
    send('page_view');
  }
  const productClick = product => send('product_click', product);
  globalThis.OverlyAnalytics = Object.freeze({ pageView, productClick });
  function clicked(event) {
    if ((event.type === 'click' && event.button !== 0) || (event.type === 'auxclick' && event.button !== 1)) return;
    const link = event.target?.closest?.('a[data-overly-product]');
    if (!link) return;
    const data = link.dataset;
    productClick({ store: data.overlyStore, asin: data.overlyProduct, product_id: data.overlyProduct,
      title: data.overlyTitle, category: data.overlyCategory });
  }
  document.addEventListener('click', clicked);
  document.addEventListener('auxclick', clicked);
  document.addEventListener('visibilitychange', pageView);
  document.addEventListener('prerenderingchange', pageView);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', pageView, { once: true });
  else pageView();
})();
