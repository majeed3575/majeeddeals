import test from "node:test";
import assert from "node:assert/strict";
import worker, { deviceType, mapProduct, sanitizeEvent, sanitizeQuery, sign, unwrapProducts } from "../src/index.js";

test("ينظف كلمات البحث ويرفض المدخلات غير الآمنة", () => {
  assert.equal(sanitizeQuery("  شاحن   سريع  "), "شاحن سريع");
  assert.equal(sanitizeQuery("usb-c hub"), "usb-c hub");
  assert.equal(sanitizeQuery("<script>alert(1)</script>"), "");
  assert.equal(sanitizeQuery("x"), "");
});

test("يُنتج توقيع MD5 ثابتاً دون تعديل المعلمات", () => {
  const parameters = { method: "demo", app_key: "123", page_no: "1" };
  assert.equal(sign(parameters, "secret"), "54A31DF4B9F38D13F3976524B60B2B75");
  assert.deepEqual(parameters, { method: "demo", app_key: "123", page_no: "1" });
});

test("يفك حاوية منتج واحد أو قائمة", () => {
  assert.equal(unwrapProducts({ products: { product: { product_id: 1 } } }).length, 1);
  assert.equal(unwrapProducts({ products: { product: [{ product_id: 1 }, { product_id: 2 }] } }).length, 2);
  assert.deepEqual(unwrapProducts({}), []);
});

test("يحوّل منتج AliExpress إلى مخطط الموقع السعودي", () => {
  const product = mapProduct({
    product_id: "1005001234567890",
    product_title: "USB C Hub 8 in 1",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://s.click.aliexpress.com/e/example",
    target_sale_price: "20",
    target_original_price: "25",
    target_sale_price_currency: "USD",
    discount: "20%",
    lastest_volume: "2500",
    evaluate_rate: "94.5%"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(product.store, "aliexpress");
  assert.equal(product.shipping_country, "SA");
  assert.equal(product.original_price, 93.75);
  assert.equal(product.discount_percent, 20);
  assert.equal(product.sales_volume, 2500);
});

test("يصنف بروجكترات BYINTEK وتلفزيونات TCL ضمن الترفيه المنزلي", () => {
  const base = {
    product_id: "1005001234567890",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://s.click.aliexpress.com/e/example",
    target_sale_price: "100",
    target_original_price: "120",
    target_sale_price_currency: "USD"
  };
  assert.equal(mapProduct({ ...base, product_title: "BYINTEK 4K Android Projector" }, {}).category, "الترفيه المنزلي");
  assert.equal(mapProduct({ ...base, product_title: "TCL QLED Smart TV 65 inch" }, {}).category, "الترفيه المنزلي");
});

test("يرفض الروابط والصور الخارجة عن نطاق AliExpress", () => {
  const unsafe = mapProduct({
    product_id: "1005001234567890",
    product_title: "Unsafe product test",
    product_main_image_url: "https://evil.example/image.jpg",
    promotion_link: "javascript:alert(1)",
    target_sale_price: "20",
    target_original_price: "25"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(unsafe, null);
});

test("يرفض النطاقات غير المصرح بها قبل الوصول إلى الواجهة الخارجية", async () => {
  const response = await worker.fetch(new Request("https://worker.example/search?q=charger", {
    headers: { Origin: "https://evil.example" }
  }), {});
  assert.equal(response.status, 403);
  assert.equal((await response.json()).error, "FORBIDDEN");
});

test("يطبق محدد الطلبات ويرفض كلمات البحث غير الصالحة", async () => {
  let calls = 0;
  const env = {
    ALLOWED_ORIGIN: "https://majeed3575.github.io",
    SEARCH_RATE_LIMITER: { async limit() { calls += 1; return { success: true }; } }
  };
  const response = await worker.fetch(new Request("https://worker.example/search?q=%3Cscript%3E", {
    headers: { Origin: "https://majeed3575.github.io" }
  }), env);
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error, "INVALID_QUERY");
  assert.equal(calls, 1);
});

test("يفشل بأمان عند غياب محدد الطلبات الموزع", async () => {
  const response = await worker.fetch(new Request("https://worker.example/search?q=charger", {
    headers: { Origin: "https://majeed3575.github.io" }
  }), { ALLOWED_ORIGIN: "https://majeed3575.github.io" });
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, "SERVICE_NOT_CONFIGURED");
});

test("ينظف أحداث التحليلات دون معرف شخصي", () => {
  assert.deepEqual(sanitizeEvent({ event_type: "page_view", page_path: "/majeeddeals/" }), {
    event_type: "page_view", product_key: "", product_title: "", store: "", category: "", page_path: "/majeeddeals/"
  });
  assert.equal(sanitizeEvent({
    event_type: "product_click", page_path: "/majeeddeals/", product_key: "amazon:B0DL5FT193",
    product_title: "شاحن سريع", store: "amazon", category: "الإلكترونيات"
  }).product_key, "amazon:b0dl5ft193");
  assert.equal(sanitizeEvent({ event_type: "product_click", page_path: "/", product_key: "bad" }), null);
  assert.equal(deviceType("Mozilla/5.0 (iPhone) Mobile"), "mobile");
  assert.equal(deviceType("Mozilla/5.0 (Macintosh)"), "desktop");
});

test("يسجل نقرة مجمعة في D1 دون تخزين عنوان IP", async () => {
  let bound = [];
  const env = {
    ALLOWED_ORIGIN: "https://majeed3575.github.io",
    SEARCH_RATE_LIMITER: { async limit() { return { success: true }; } },
    ANALYTICS_DB: {
      prepare(sql) {
        assert.match(sql, /INSERT INTO analytics_events/);
        return { bind(...values) { bound = values; return { async run() { return { success: true }; } }; } };
      }
    }
  };
  const response = await worker.fetch(new Request("https://worker.example/events", {
    method: "POST",
    headers: {
      Origin: "https://majeed3575.github.io",
      Referer: "https://majeed3575.github.io/majeeddeals/",
      "Content-Type": "application/json",
      "User-Agent": "Mozilla/5.0 (iPhone) Mobile",
      "CF-Connecting-IP": "203.0.113.15"
    },
    body: JSON.stringify({
      event_type: "product_click", page_path: "/majeeddeals/", product_key: "aliexpress:1005001234567890",
      product_title: "منتج رائج", store: "aliexpress", category: "المنزل"
    })
  }), env);
  assert.equal(response.status, 202);
  assert.equal(bound[2], "product_click");
  assert.equal(bound[8], "majeed3575.github.io");
  assert.equal(bound[9], "mobile");
  assert.equal(bound.includes("203.0.113.15"), false);
});
