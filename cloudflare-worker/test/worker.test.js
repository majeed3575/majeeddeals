import test from "node:test";
import assert from "node:assert/strict";
import worker, {
  aiQueryVariants,
  deviceType,
  mapProduct,
  meetsQualityThreshold,
  qualityThresholds,
  queryNeedsAi,
  queryVariants,
  ratingFrom,
  sanitizeEvent,
  sanitizeQuery,
  sign,
  resolvedQueryVariants,
  unwrapProducts
} from "../src/index.js";

test("ينظف كلمات البحث ويرفض المدخلات غير الآمنة", () => {
  assert.equal(sanitizeQuery("  شاحن   سريع  "), "شاحن سريع");
  assert.equal(sanitizeQuery("usb-c hub"), "usb-c hub");
  assert.equal(sanitizeQuery("<script>alert(1)</script>"), "");
  assert.equal(sanitizeQuery("x"), "");
  assert.equal(sanitizeQuery("كاميرا سرية صغيرة"), "");
});

test("يترجم البحث العربي إلى عبارات إنجليزية يفهمها AliExpress", () => {
  assert.deepEqual(queryVariants("شاحن آيفون"), ["iphone charger", "apple iphone fast charger", "charger iphone"]);
  assert.deepEqual(queryVariants("سلك ايفون"), ["iphone charging cable", "lightning cable iphone", "cable iphone"]);
  assert.deepEqual(queryVariants("كيبل تايب سي سريع"), ["usb c cable", "type c charging cable", "cable usb c fast"]);
  assert.deepEqual(queryVariants("type c cable"), ["type c cable"]);
});

test("يكتشف العبارات العربية الخارجة عن القاموس دون إبطاء البحث الإنجليزي", () => {
  assert.equal(queryNeedsAi("شاحن آيفون"), false);
  assert.equal(queryNeedsAi("طاولة جانبية مودرن"), true);
  assert.equal(queryNeedsAi("مكنسة روبوت شاومي s10"), true);
  assert.equal(queryNeedsAi("robot vacuum xiaomi s10"), false);
});

test("يترجم أي سياق تسوق عربي غير معروف ويولد صيغ بحث آمنة", async () => {
  let request;
  const env = {
    AI: {
      async run(model, input) {
        request = { model, input };
        return {
          response: {
            variants: [
              "modern side table",
              "small living room end table",
              "bedside table modern",
              "طاولة جانبية",
              "https://evil.example"
            ]
          }
        };
      }
    }
  };

  const variants = await resolvedQueryVariants("طاولة جانبية مودرن", env);
  assert.deepEqual(variants, [
    "modern side table",
    "small living room end table",
    "bedside table modern"
  ]);
  assert.equal(request.model, "@cf/meta/llama-3.1-8b-instruct-fast");
  assert.equal(request.input.response_format.type, "json_schema");
  assert.equal(request.input.messages[1].content, "طاولة جانبية مودرن");
});

test("يحافظ على الماركة والموديل ويعود للقاموس بأمان إذا تعطلت الترجمة الذكية", async () => {
  const ai = {
    async run() {
      return { response: { variants: ["xiaomi s10 robot vacuum", "robot vacuum cleaner xiaomi s10"] } };
    }
  };
  assert.deepEqual(await aiQueryVariants("مكنسة روبوت شاومي s10", { AI: ai }), [
    "xiaomi s10 robot vacuum",
    "robot vacuum cleaner xiaomi s10"
  ]);
  assert.deepEqual(await resolvedQueryVariants("مكنسة روبوت شاومي s10", {
    AI: { async run() { throw new Error("AI_UNAVAILABLE"); } }
  }), queryVariants("مكنسة روبوت شاومي s10"));
});

test("يجرّب مرادفات البحث المترجمة ويدمج النتائج بلا تكرار", async () => {
  const originalFetch = globalThis.fetch;
  const originalCaches = globalThis.caches;
  const keywords = [];
  globalThis.caches = {
    default: {
      async match() { return null; },
      async put() {}
    }
  };
  globalThis.fetch = async (_url, options) => {
    const keyword = new URLSearchParams(options.body).get("keywords");
    keywords.push(keyword);
    const product = keyword === "iphone charger" ? [] : [{
      product_id: "1005001234567890",
      product_title: "Apple iPhone fast charging cable",
      product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
      promotion_link: "https://s.click.aliexpress.com/e/example",
      target_sale_price: "20",
      target_original_price: "25",
      target_sale_price_currency: "USD",
      lastest_volume: "2500",
      evaluate_rate: "94%"
    }];
    return new Response(JSON.stringify({
      aliexpress_affiliate_product_query_response: {
        resp_result: { resp_code: 200, result: { total_page_no: 1, products: { product } } }
      }
    }), { status: 200, headers: { "Content-Type": "application/json" } });
  };

  try {
    const response = await worker.fetch(new Request("https://worker.example/search?q=شاحن%20آيفون&page_size=5", {
      headers: { Origin: "https://majeed3575.github.io" }
    }), {
      ALLOWED_ORIGIN: "https://majeed3575.github.io",
      ALIEXPRESS_APP_KEY: "test-key",
      ALIEXPRESS_APP_SECRET: "test-secret",
      SEARCH_RATE_LIMITER: { async limit() { return { success: true }; } }
    });
    const payload = await response.json();
    assert.equal(response.status, 200);
    assert.deepEqual(keywords, ["iphone charger", "apple iphone fast charger", "charger iphone"]);
    assert.deepEqual(payload.query_variants_used, keywords);
    assert.equal(payload.products.length, 1);
    assert.equal(payload.products[0].sales_volume, 2500);
    assert.equal(payload.products[0].rating, 4.7);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.caches = originalCaches;
  }
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
  assert.equal(product.rating, 4.7);
  assert.equal(product.rating_percent, 94.5);
});

test("يحوّل نسبة رضا AliExpress إلى تقييم من خمس نجوم", () => {
  assert.equal(ratingFrom("94.5%"), 4.7);
  assert.equal(ratingFrom("4.8"), 4.8);
  assert.equal(ratingFrom(""), 0);
});

test("يوحّد فلتر الجودة مع الموقع: ألف طلب وتقييم 4.5 فأعلى", () => {
  const thresholds = qualityThresholds({});
  assert.deepEqual(thresholds, { minSales: 1000, minRatingPercent: 90, minRating: 4.5 });
  assert.equal(meetsQualityThreshold({ sales_volume: 999, rating: 5 }, thresholds), false);
  assert.equal(meetsQualityThreshold({ sales_volume: 1000, rating: 4.4 }, thresholds), false);
  assert.equal(meetsQualityThreshold({ sales_volume: 1000, rating: 4.5 }, thresholds), true);
  assert.equal(meetsQualityThreshold({ sales_volume: 1000, rating: 4.5, rating_percent: 89 }, thresholds), false);
  assert.equal(meetsQualityThreshold({ sales_volume: 1000, rating: 4.5, rating_percent: 90 }, thresholds), true);
  assert.equal(meetsQualityThreshold({ sales_volume: 5000, rating: 0 }, thresholds), false);
});

test("يستبعد المنتجات المحظورة قبل إرجاعها للمتسوق", () => {
  const product = mapProduct({
    product_id: "1005001234567890",
    product_title: "Hidden spy camera pen",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://s.click.aliexpress.com/e/example",
    target_sale_price: "20",
    target_original_price: "25"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(product, null);
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

test("يوحد تصنيف المنظفات والأزياء والرحلات مع الموقع والبوت", () => {
  const base = {
    product_id: "1005001234567890",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://s.click.aliexpress.com/e/example",
    target_sale_price: "20",
    target_original_price: "25",
    target_sale_price_currency: "USD"
  };
  assert.equal(mapProduct({ ...base, product_title: "Extra White Detergent Powder 10kg" }, {}).category, "التنظيف والمنظفات");
  assert.equal(mapProduct({ ...base, product_title: "Men casual jeans pants" }, {}).category, "الأزياء والأحذية");
  assert.equal(mapProduct({ ...base, product_title: "Rechargeable camping lantern" }, {}).category, "الرحلات والبحر والتخييم");
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

test("لا يعرض منتجًا بلا رابط عمولة رسمي", () => {
  const withoutAffiliateLink = mapProduct({
    product_id: "1005001234567890",
    product_title: "USB C charger 65W",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    product_detail_url: "https://www.aliexpress.com/item/1005001234567890.html",
    target_sale_price: "20",
    target_original_price: "25"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(withoutAffiliateLink, null);

  const directPromotionLink = mapProduct({
    product_id: "1005001234567890",
    product_title: "USB C charger 65W",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://www.aliexpress.com/item/1005001234567890.html",
    target_sale_price: "20",
    target_original_price: "25"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(directPromotionLink, null);

  const markedAffiliateLink = mapProduct({
    product_id: "1005001234567890",
    product_title: "USB C charger 65W",
    product_main_image_url: "https://ae01.alicdn.com/kf/example.jpg",
    promotion_link: "https://www.aliexpress.com/item/1005001234567890.html?aff_fcid=abc&aff_trace_key=xyz&aff_platform=api-new-product-query",
    target_sale_price: "20",
    target_original_price: "25"
  }, { USD_TO_SAR: "3.75" });
  assert.equal(markedAffiliateLink?.product_id, "1005001234567890");
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
