import { createHash } from "node:crypto";

const SERVICE = "overly-aliexpress-search";
const DEFAULT_ORIGIN = "https://majeed3575.github.io";
const MAX_QUERY_LENGTH = 80;
const MAX_PAGE = 20;
const MAX_PAGE_SIZE = 24;

function json(body, status = 200, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
      "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
      "Cross-Origin-Resource-Policy": "cross-origin",
      ...headers
    }
  });
}

function allowedOrigin(request, env) {
  const origin = request.headers.get("Origin") || "";
  const production = String(env.ALLOWED_ORIGIN || DEFAULT_ORIGIN).replace(/\/$/, "");
  if (origin === production) return origin;
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin)) return origin;
  return "";
}

function cors(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin"
  };
}

function sanitizeQuery(value) {
  const query = String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
  if (query.length < 2 || query.length > MAX_QUERY_LENGTH) return "";
  return /^[\p{L}\p{N}\s+&()،,./_-]+$/u.test(query) ? query : "";
}

function boundedInteger(value, fallback, min, max) {
  const number = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
}

async function rateAllowed(request, env) {
  if (!env.SEARCH_RATE_LIMITER?.limit) return null;
  const fingerprint = [
    request.headers.get("CF-Connecting-IP") || "unknown",
    request.headers.get("User-Agent") || "unknown"
  ].join("|");
  const clientKey = createHash("sha256").update(fingerprint, "utf8").digest("hex").slice(0, 32);
  const result = await env.SEARCH_RATE_LIMITER.limit({ key: `search:${clientKey}` });
  return result.success;
}

function sign(parameters, secret) {
  const canonical = Object.keys(parameters)
    .filter(key => parameters[key] !== null && parameters[key] !== undefined)
    .sort()
    .map(key => `${key}${parameters[key]}`)
    .join("");
  return createHash("md5").update(`${secret}${canonical}${secret}`, "utf8").digest("hex").toUpperCase();
}

function numberFrom(value) {
  const match = String(value || "").replace(/,/g, "").match(/\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : 0;
}

function discountFrom(value, original, current) {
  const stated = Math.round(numberFrom(value));
  if (stated > 0) return Math.min(95, stated);
  if (original > current && current > 0) return Math.min(95, Math.round((original - current) / original * 100));
  return 0;
}

function httpsUrl(value, kind = "link") {
  let url;
  try { url = new URL(String(value || "").replace(/^http:\/\//i, "https://")); }
  catch { return ""; }
  if (url.protocol !== "https:") return "";
  const host = url.hostname.toLowerCase();
  if (kind === "image") {
    return host === "alicdn.com" || host.endsWith(".alicdn.com") ||
      host === "aliexpress-media.com" || host.endsWith(".aliexpress-media.com") ||
      host === "aliexpress.com" || host.endsWith(".aliexpress.com") ? url.href : "";
  }
  return host === "aliexpress.com" || host.endsWith(".aliexpress.com") ||
    host === "aliexpress.us" || host.endsWith(".aliexpress.us") ? url.href : "";
}

function cleanTitle(value) {
  return String(value || "")
    .replace(/<[^>]*>/g, " ")
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
}

function classify(title) {
  const text = title.toLowerCase();
  if (/pet|cat|dog|grooming|قطط|كلاب|حيوان/.test(text)) return "الحيوانات الأليفة";
  if (/baby|kids|child|toddler|toy|طفل|أطفال|رضيع|لعبة/.test(text)) return "الأطفال";
  if (/beauty|makeup|skincare|cosmetic|hair|nail|مكياج|بشرة|شعر|أظافر/.test(text)) return "الجمال والعناية";
  if (/sport|fitness|exercise|yoga|running|fishing|رياضة|لياقة|تمارين|يوغا|صيد/.test(text)) return "الرياضة";
  if (/drill|wrench|tool|laser level|دريل|مثقاب|عدة|أدوات|صيانة/.test(text)) return "الأدوات والهوايات";
  if (/car|vehicle|auto|سيار|إطار|اطار/.test(text)) return "السيارة";
  if (/travel|camp|luggage|bag|سفر|رحلات|حقيبة/.test(text)) return "السفر";
  if (/home|kitchen|clean|vacuum|light|منزل|مطبخ|تنظيف|إضاءة/.test(text)) return "المنزل";
  if (/shirt|dress|shoe|wear|fashion|ملابس|حذاء|موضة/.test(text)) return "الموضة";
  return "الإلكترونيات";
}

function unwrapProducts(result) {
  const products = result?.products?.product;
  if (Array.isArray(products)) return products;
  return products && typeof products === "object" ? [products] : [];
}

function mapProduct(product, env) {
  const productId = String(product?.product_id || "").match(/\d{6,20}/)?.[0] || "";
  const title = cleanTitle(product?.product_title);
  const image = httpsUrl(product?.product_main_image_url, "image");
  const url = httpsUrl(product?.promotion_link || product?.product_detail_url, "link");
  if (!productId || title.length < 4 || !image || !url) return null;

  const rate = numberFrom(env.USD_TO_SAR || 3.75);
  const currency = String(product?.target_sale_price_currency || product?.sale_price_currency || "USD").toUpperCase();
  const multiplier = currency === "SAR" ? 1 : rate || 3.75;
  const current = numberFrom(product?.target_sale_price || product?.sale_price) * multiplier;
  const originalRaw = numberFrom(product?.target_original_price || product?.original_price);
  const original = (originalRaw || numberFrom(product?.target_sale_price || product?.sale_price)) * multiplier;
  if (!(current > 0) || !(original > 0)) return null;

  return {
    store: "aliexpress",
    product_id: productId,
    url,
    title,
    image,
    discount_percent: discountFrom(product?.discount, original, current),
    original_price: Math.round(original * 100) / 100,
    sales_volume: Math.round(numberFrom(product?.lastest_volume)),
    rating: numberFrom(product?.evaluate_rate),
    category: classify(title),
    shipping_country: "SA"
  };
}

async function callAliExpress(query, page, pageSize, env) {
  if (!env.ALIEXPRESS_APP_KEY || !env.ALIEXPRESS_APP_SECRET) throw new Error("CONFIG");
  const method = "aliexpress.affiliate.product.query";
  const application = {
    fields: [
      "product_id", "product_title", "product_main_image_url", "product_detail_url",
      "target_original_price", "target_original_price_currency", "target_sale_price",
      "target_sale_price_currency", "sale_price", "sale_price_currency", "discount",
      "promotion_link", "evaluate_rate", "lastest_volume", "ship_to_days"
    ].join(","),
    keywords: query,
    page_no: String(page),
    page_size: String(pageSize),
    platform_product_type: "ALL",
    sort: "LAST_VOLUME_DESC",
    target_currency: String(env.ALIEXPRESS_TARGET_CURRENCY || "USD"),
    target_language: String(env.ALIEXPRESS_TARGET_LANGUAGE || "AR"),
    tracking_id: String(env.ALIEXPRESS_TRACKING_ID || "faraj733"),
    ship_to_country: "SA"
  };
  const system = {
    app_key: String(env.ALIEXPRESS_APP_KEY),
    format: "json",
    method,
    sign_method: "md5",
    timestamp: String(Date.now()),
    v: "2.0"
  };
  system.sign = sign({ ...system, ...application }, String(env.ALIEXPRESS_APP_SECRET));
  const endpoint = new URL(String(env.ALIEXPRESS_API_ENDPOINT || "https://api-sg.aliexpress.com/sync"));
  Object.entries(system).forEach(([key, value]) => endpoint.searchParams.set(key, value));

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: new URLSearchParams(application),
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) throw new Error("UPSTREAM");
  const payload = await response.json();
  if (payload?.error_response) throw new Error("UPSTREAM");
  const envelope = payload?.[`${method.replaceAll(".", "_")}_response`]?.resp_result;
  if (!envelope || ![200, "200", 200.0, "200.0"].includes(envelope.resp_code)) throw new Error("UPSTREAM");
  return envelope.result || {};
}

async function search(request, env, origin) {
  const rateStatus = await rateAllowed(request, env);
  if (rateStatus === null) {
    return json({ ok: false, error: "SERVICE_NOT_CONFIGURED" }, 503, cors(origin));
  }
  if (!rateStatus) {
    return json({ ok: false, error: "RATE_LIMIT" }, 429, { ...cors(origin), "Retry-After": "60" });
  }
  const url = new URL(request.url);
  const query = sanitizeQuery(url.searchParams.get("q"));
  if (!query) return json({ ok: false, error: "INVALID_QUERY" }, 400, cors(origin));
  const page = boundedInteger(url.searchParams.get("page"), 1, 1, MAX_PAGE);
  const pageSize = boundedInteger(url.searchParams.get("page_size"), MAX_PAGE_SIZE, 1, MAX_PAGE_SIZE);

  const cacheKey = new Request(`${url.origin}/search?q=${encodeURIComponent(query.toLowerCase())}&page=${page}&page_size=${pageSize}`, request);
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) {
    const headers = new Headers(cached.headers);
    Object.entries(cors(origin)).forEach(([key, value]) => headers.set(key, value));
    return new Response(cached.body, { status: cached.status, headers });
  }

  try {
    const result = await callAliExpress(query, page, pageSize, env);
    const products = unwrapProducts(result).map(product => mapProduct(product, env)).filter(Boolean);
    const totalPages = boundedInteger(result?.total_page_no, page, page, MAX_PAGE);
    const response = json({
      ok: true,
      query,
      page,
      page_size: pageSize,
      has_more: page < totalPages && products.length > 0,
      shipping_country: "SA",
      products
    }, 200, { ...cors(origin), "Cache-Control": "public, max-age=300, s-maxage=900" });
    await cache.put(cacheKey, response.clone());
    return response;
  } catch (error) {
    const code = error?.message === "CONFIG" ? "SERVICE_NOT_CONFIGURED" : "SEARCH_UNAVAILABLE";
    return json({ ok: false, error: code }, code === "SERVICE_NOT_CONFIGURED" ? 503 : 502, cors(origin));
  }
}

export { sanitizeQuery, sign, mapProduct, unwrapProducts };

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ ok: true, service: SERVICE }, 200, { "Cache-Control": "no-store" });
    }
    const origin = allowedOrigin(request, env);
    if (!origin) return json({ ok: false, error: "FORBIDDEN" }, 403);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
    if (url.pathname !== "/search") return json({ ok: false, error: "NOT_FOUND" }, 404, cors(origin));
    if (request.method !== "GET") return json({ ok: false, error: "METHOD_NOT_ALLOWED" }, 405, { ...cors(origin), "Allow": "GET, OPTIONS" });
    return search(request, env, origin);
  }
};
