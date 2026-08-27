import test from "node:test";
import assert from "node:assert/strict";
import worker, { analyticsDashboard, normalizeTeamDomain, productKey, safeAliExpressAffiliateUrl, sanitizeProduct, verifyWriteRequest } from "../src/index.js";

test("يرفض نطاقات Access غير الرسمية", () => {
  assert.equal(normalizeTeamDomain("https://overly.cloudflareaccess.com"), "https://overly.cloudflareaccess.com");
  assert.equal(normalizeTeamDomain("https://evil.example"), "");
  assert.equal(normalizeTeamDomain("javascript:alert(1)"), "");
});

test("ينظف منتج Amazon يدوي صالح", () => {
  const product = sanitizeProduct({
    store: "amazon",
    asin: "b0dl5ft193",
    title: "منتج Amazon موثوق للاختبار",
    image: "https://m.media-amazon.com/images/I/test.jpg",
    original_price: 379,
    discount_percent: 20,
    sales_volume: 1200,
    rating: 94.5,
    category: "الإلكترونيات"
  });
  assert.equal(product.asin, "B0DL5FT193");
  assert.equal(product.owner_pinned, true);
  assert.equal(product.auto_discovered, false);
  assert.equal(productKey(product), "amazon:B0DL5FT193");
});

test("ينظف منتج AliExpress ويرفض رابطاً خارجياً", () => {
  const base = {
    store: "aliexpress",
    product_id: "1005001234567890",
    title: "منتج AliExpress موثوق للاختبار",
    image: "https://ae01.alicdn.com/kf/test.jpg",
    original_price: 44.5,
    discount_percent: 0,
    category: "المنزل"
  };
  assert.equal(sanitizeProduct({ ...base, url: "https://s.click.aliexpress.com/e/test" }).product_id, "1005001234567890");
  assert.equal(sanitizeProduct({ ...base, url: "https://www.aliexpress.com/item/1005001234567890.html" }), null);
  const marked = "https://www.aliexpress.com/item/1005001234567890.html?aff_fcid=abc&aff_trace_key=xyz&aff_platform=api-new-product-query";
  assert.equal(sanitizeProduct({ ...base, url: marked }).url, marked);
  assert.equal(safeAliExpressAffiliateUrl(marked), marked);
  assert.equal(sanitizeProduct({ ...base, url: "https://evil.example/item" }), null);
});

test("يرفض الكتابة دون أصل مطابق وترويسة الإدارة", () => {
  const good = new Request("https://admin.example/api/products", {
    method: "POST",
    headers: { Origin: "https://admin.example", "Content-Type": "application/json", "X-Overly-Admin": "1" },
    body: "{}"
  });
  assert.equal(verifyWriteRequest(good), true);
  const bad = new Request("https://admin.example/api/products", {
    method: "POST",
    headers: { Origin: "https://evil.example", "Content-Type": "application/json", "X-Overly-Admin": "1" },
    body: "{}"
  });
  assert.equal(verifyWriteRequest(bad), false);
});

test("يفشل مغلقاً عند غياب إعدادات Cloudflare Access", async () => {
  const response = await worker.fetch(new Request("https://admin.example/"), {});
  assert.equal(response.status, 403);
  assert.match(await response.text(), /غير مصرح/);
});

test("يعيد ملخص التحليلات وحساب معدل النقر", async () => {
  const fakeResults = [
    { results: [{ views: 200, clicks: 36, views_today: 12, clicks_today: 3 }] },
    { results: [{ day: "2026-08-16", views: 12, clicks: 3 }] },
    { results: [{ product_key: "amazon:B0DL5FT193", title: "شاحن", clicks: 8 }] },
    { results: [{ label: "الإلكترونيات", count: 8 }] },
    { results: [{ label: "amazon", count: 8 }] },
    { results: [{ label: "mobile", count: 10 }] },
    { results: [{ label: "SA", count: 10 }] },
    { results: [{ label: "direct", count: 9 }] }
  ];
  const env = {
    ANALYTICS_DB: {
      prepare(sql) { return { bind(...values) { return { sql, values }; } }; },
      async batch(statements) { assert.equal(statements.length, 8); return fakeResults; }
    }
  };
  const response = await analyticsDashboard(new Request("https://admin.example/api/analytics?days=30"), env);
  const payload = await response.json();
  assert.equal(response.status, 200);
  assert.equal(payload.summary.views, 200);
  assert.equal(payload.summary.ctr, 18);
  assert.equal(payload.top_products[0].clicks, 8);
});
