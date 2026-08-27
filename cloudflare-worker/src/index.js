import { createHash } from "node:crypto";

const SERVICE = "overly-aliexpress-search";
const DEFAULT_ORIGIN = "https://majeed3575.github.io";
const MAX_QUERY_LENGTH = 80;
const MAX_PAGE = 20;
const MAX_PAGE_SIZE = 24;
const MAX_EVENT_BODY_BYTES = 4 * 1024;
const DEFAULT_MIN_SALES_VOLUME = 1000;
const DEFAULT_MIN_RATING_PERCENT = 90;
const SEARCH_CACHE_VERSION = "quality-v2-ar-en";
const MAX_QUERY_VARIANTS = 3;

// حجب محافظ لأبرز السلع الممنوعة في السعودية. لا نحجب الفئات العامة التي
// قد تكون نظامية، بل الألفاظ الدالة مباشرة على سلعة ممنوعة فقط.
const BLOCKED_PRODUCT_PATTERN = /(?:سلاح|مسدس|بندقية|ذخيرة|رصاص\s*حي|متفجر|قنبلة|مخدر|حشيش|كوكايين|هيروين|خمر|نبيذ|ويسكي|فودكا|مشروب\s*كحولي|ألعاب?\s*نارية|مفرقعات|تبغ\s*المضغ|مسيل(?:ات)?\s*الدموع|كاميرا\s*سرية|قلم\s*بكاميرا|ساعة\s*بكاميرا|نظارة\s*بكاميرا|صاعق\s*كهربائي|كاشف\s*رادار\s*السرعة|جهاز\s*تنصت|أداة\s*جنسية|جهاز\s*جنسي|حبوب\s*إجهاض|مقو(?:ي|يات)\s*جنسي|منشط\s*جنسي|جوز(?:ة)?\s*الطيب|لحم\s*خنزير|خنزير|عملة\s*مزورة|محتوى\s*إباحي|محتوى\s*للبالغين|سلعة\s*مقلدة|weapon|pistol|rifle|ammunition|live\s*ammo|explosive|grenade|cannabis|marijuana|cocaine|heroin|alcoholic\s*(?:drink|beverage)|whisk(?:e)?y|vodka|wine|fireworks?|pyrotechnic|chewing\s*tobacco|tear\s*gas|hidden\s*camera|spy\s*camera|stun\s*gun|taser|radar\s*detector|eavesdropping\s*device|wiretap|sex(?:ual)?\s*(?:toy|device)|abortion\s*pill|sexual\s*enhancer|nutmeg|pork|counterfeit\s*(?:currency|money|product)|pornograph|gambling|betting)/iu;

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
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin"
  };
}

function sanitizeQuery(value) {
  const query = String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
  if (query.length < 2 || query.length > MAX_QUERY_LENGTH) return "";
  if (!/^[\p{L}\p{N}\s+&()،,./_-]+$/u.test(query) || BLOCKED_PRODUCT_PATTERN.test(query)) return "";
  return query;
}

function normalizedArabicSearch(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[\u064b-\u065f\u0670\u06d6-\u06ed]/g, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/[^\p{L}\p{N}\s+_-]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function translateShoppingQuery(query) {
  let value = normalizedArabicSearch(query);
  const phrases = [
    [/قابل(?:ه)? للشحن/gu, "rechargeable"],
    [/شاشه حمايه/gu, "screen protector"],
    [/ساعه ذكيه/gu, "smart watch"],
    [/باور بانك/gu, "power bank"],
    [/لوحه مفاتيح/gu, "keyboard"],
    [/يو اس بي/gu, "usb"],
    [/تايب سي|نوع سي/gu, "usb c"],
    [/تي سي ال/gu, "tcl"]
  ];
  for (const [pattern, replacement] of phrases) value = value.replace(pattern, replacement);

  const words = new Map([
    ["ايفون", "iphone"], ["ابل", "apple"], ["جوال", "phone"], ["هاتف", "phone"],
    ["موبايل", "phone"], ["شاحن", "charger"], ["شحن", "charging"], ["سلك", "cable"],
    ["كيبل", "cable"], ["كابل", "cable"], ["وصله", "cable"], ["سريع", "fast"],
    ["لاسلكي", "wireless"], ["سماعه", "headphones"], ["سماعات", "headphones"],
    ["ايربودز", "earbuds"], ["بلوتوث", "bluetooth"], ["ساعه", "watch"],
    ["حامل", "holder"], ["كفر", "case"], ["غطاء", "case"], ["محول", "adapter"],
    ["يوجرين", "ugreen"], ["انكر", "anker"], ["شاومي", "xiaomi"],
    ["سامسونج", "samsung"], ["بيسوس", "baseus"], ["لابتوب", "laptop"],
    ["كمبيوتر", "computer"], ["كيبورد", "keyboard"], ["ماوس", "mouse"],
    ["بروجكتر", "projector"], ["بروجكتور", "projector"], ["تلفزيون", "tv"],
    ["منظم", "organizer"], ["مطبخ", "kitchen"], ["تنظيف", "cleaning"],
    ["منظف", "cleaner"], ["مكنسه", "vacuum"], ["مصباح", "lamp"],
    ["لمبه", "lamp"], ["اضاءه", "lighting"], ["حمام", "bathroom"],
    ["سياره", "car"], ["كاميرا", "camera"], ["حقيبه", "bag"], ["سفر", "travel"],
    ["تخييم", "camping"], ["خيمه", "tent"], ["حديقه", "garden"],
    ["حدائق", "garden"], ["صيد", "fishing"], ["بحري", "marine"],
    ["حذاء", "shoes"], ["شوز", "shoes"], ["بنطلون", "pants"],
    ["قميص", "shirt"], ["ملابس", "clothes"], ["نسائي", "women"],
    ["رجالي", "men"], ["اطفال", "kids"], ["مدرسي", "school"],
    ["مدرسيه", "school"], ["قلم", "pen"], ["اقلام", "pens"], ["العاب", "toys"],
    ["لعبه", "toy"], ["صغير", "small"], ["كبير", "large"], ["محمول", "portable"],
    ["كهربائي", "electric"], ["ذكي", "smart"]
  ]);
  const stopWords = new Set(["في", "من", "مع", "على", "عن", "الي", "الى", "لل", "ل", "حق", "افضل"]);
  const translated = value
    .split(/\s+/)
    .map(word => words.get(word) || word)
    .filter(word => !stopWords.has(word) && !/[\u0600-\u06ff]/u.test(word))
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
  return sanitizeQuery(translated);
}

function queryVariants(value) {
  const query = sanitizeQuery(value);
  if (!query) return [];
  if (!/[\u0600-\u06ff]/u.test(query)) return [query];

  const intent = normalizedArabicSearch(query);
  const variants = [];
  const add = candidate => {
    const clean = sanitizeQuery(candidate);
    if (clean && !variants.some(item => item.toLowerCase() === clean.toLowerCase())) variants.push(clean);
  };
  const hasIphone = /(?:^|\s)ايفون(?:\s|$)/u.test(intent);
  const hasCable = /(?:سلك|كيبل|كابل|وصله)/u.test(intent);
  const hasCharger = /(?:شاحن|شحن)/u.test(intent);
  const hasUsbC = /(?:تايب سي|نوع سي|usb\s*c|type\s*c)/iu.test(intent);

  if (hasIphone && hasCable) {
    add(hasUsbC ? "iphone usb c charging cable" : "iphone charging cable");
    add("lightning cable iphone");
  } else if (hasIphone && hasCharger) {
    add("iphone charger");
    add("apple iphone fast charger");
  } else if (hasCable && hasUsbC) {
    add("usb c cable");
    add("type c charging cable");
  }
  add(translateShoppingQuery(query));

  // إذا كانت العبارة خارج قاموس التسوق الحالي، نبقي البحث العربي كحل أخير.
  if (!variants.length) add(query);
  return variants.slice(0, MAX_QUERY_VARIANTS);
}

function boundedInteger(value, fallback, min, max) {
  const number = Number.parseInt(String(value || ""), 10);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : fallback;
}

function qualityThresholds(env = {}) {
  const minSales = boundedInteger(
    env.ALIEXPRESS_SEARCH_MIN_VOLUME,
    DEFAULT_MIN_SALES_VOLUME,
    0,
    1_000_000_000
  );
  const rawPercent = String(env.ALIEXPRESS_SEARCH_MIN_RATING_PERCENT ?? "").trim();
  const configuredPercent = rawPercent ? Number(rawPercent) : Number.NaN;
  const minRatingPercent = Number.isFinite(configuredPercent)
    ? Math.min(100, Math.max(0, configuredPercent))
    : DEFAULT_MIN_RATING_PERCENT;
  return {
    minSales,
    minRatingPercent,
    minRating: Math.round((minRatingPercent / 20) * 10) / 10
  };
}

function meetsQualityThreshold(product, thresholds) {
  return Boolean(
    product &&
    Number(product.sales_volume) >= thresholds.minSales &&
    Number(product.rating_percent ?? (Number(product.rating) * 20)) >= thresholds.minRatingPercent
  );
}

async function rateAllowed(request, env, bucket = "search") {
  if (!env.SEARCH_RATE_LIMITER?.limit) return null;
  const fingerprint = [
    request.headers.get("CF-Connecting-IP") || "unknown",
    request.headers.get("User-Agent") || "unknown"
  ].join("|");
  const clientKey = createHash("sha256").update(fingerprint, "utf8").digest("hex").slice(0, 32);
  const result = await env.SEARCH_RATE_LIMITER.limit({ key: `${bucket}:${clientKey}` });
  return result.success;
}

function cleanEventText(value, maxLength) {
  return String(value || "")
    .normalize("NFKC")
    .replace(/[\u0000-\u001f\u007f]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

function deviceType(userAgent) {
  const value = String(userAgent || "").toLowerCase();
  if (/ipad|tablet|playbook|silk/.test(value)) return "tablet";
  if (/mobile|iphone|ipod|android/.test(value)) return "mobile";
  return "desktop";
}

function referrerHost(request) {
  try {
    const value = new URL(request.headers.get("Referer") || "").hostname.toLowerCase();
    return cleanEventText(value, 120);
  } catch {
    return "direct";
  }
}

function sanitizeEvent(input) {
  const eventType = input?.event_type === "product_click" ? "product_click" :
    input?.event_type === "page_view" ? "page_view" : "";
  const store = input?.store === "aliexpress" ? "aliexpress" : input?.store === "amazon" ? "amazon" : "";
  const productKey = cleanEventText(input?.product_key, 80).toLowerCase();
  const pagePath = cleanEventText(input?.page_path, 160);
  if (!eventType || !pagePath.startsWith("/")) return null;
  if (eventType === "product_click" && !/^(amazon:[a-z0-9]{10}|aliexpress:\d{6,20})$/.test(productKey)) return null;
  return {
    event_type: eventType,
    product_key: eventType === "product_click" ? productKey : "",
    product_title: eventType === "product_click" ? cleanEventText(input?.product_title, 180) : "",
    store: eventType === "product_click" ? store : "",
    category: eventType === "product_click" ? cleanEventText(input?.category, 60) : "",
    page_path: pagePath
  };
}

async function recordEvent(request, env, origin) {
  if (!env.ANALYTICS_DB?.prepare) {
    return json({ ok: false, error: "ANALYTICS_NOT_CONFIGURED" }, 503, cors(origin));
  }
  const type = (request.headers.get("Content-Type") || "").toLowerCase();
  const length = Number(request.headers.get("Content-Length") || 0);
  if (!type.startsWith("application/json") || length > MAX_EVENT_BODY_BYTES) {
    return json({ ok: false, error: "INVALID_EVENT" }, 400, cors(origin));
  }
  const rateStatus = await rateAllowed(request, env, "events");
  if (rateStatus === null) return json({ ok: false, error: "SERVICE_NOT_CONFIGURED" }, 503, cors(origin));
  if (!rateStatus) return json({ ok: false, error: "RATE_LIMIT" }, 429, { ...cors(origin), "Retry-After": "60" });
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_EVENT_BODY_BYTES) {
    return json({ ok: false, error: "INVALID_EVENT" }, 400, cors(origin));
  }
  let input;
  try { input = JSON.parse(raw); } catch { return json({ ok: false, error: "INVALID_EVENT" }, 400, cors(origin)); }
  const event = sanitizeEvent(input);
  if (!event) return json({ ok: false, error: "INVALID_EVENT" }, 400, cors(origin));
  const now = new Date();
  const occurredAt = now.toISOString();
  await env.ANALYTICS_DB.prepare(`
    INSERT INTO analytics_events
      (occurred_at, day, event_type, product_key, product_title, store, category, page_path, referrer_host, device_type, country)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).bind(
    occurredAt,
    occurredAt.slice(0, 10),
    event.event_type,
    event.product_key,
    event.product_title,
    event.store,
    event.category,
    event.page_path,
    referrerHost(request),
    deviceType(request.headers.get("User-Agent")),
    cleanEventText(request.cf?.country || "", 2).toUpperCase()
  ).run();
  return json({ ok: true }, 202, { ...cors(origin), "Cache-Control": "no-store" });
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

function aliExpressAffiliateUrl(value) {
  const safe = httpsUrl(value, "link");
  if (!safe) return "";
  const url = new URL(safe);
  const host = url.hostname.toLowerCase();
  if (host === "s.click.aliexpress.com") return url.href;
  const hasAffiliateMarkers = url.searchParams.has("aff_fcid") &&
    url.searchParams.has("aff_trace_key") &&
    String(url.searchParams.get("aff_platform") || "").toLowerCase().includes("api");
  return hasAffiliateMarkers ? url.href : "";
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
  if (/byintek|\btcl\b|projector|smart tv|qled tv|television|بروجكتر|بروجكتور|تلفزيون|تلفاز|سينما منزلية/.test(text)) return "الترفيه المنزلي";
  if (/dish soap|laundry soap|detergent|cleaner|bleach|washing powder|disinfectant|صابون|منظف|منظفات|غسيل|مسحوق غسيل|مبيض|كلور|مطهر/.test(text)) return "التنظيف والمنظفات";
  if (/pants|trousers|jeans|shirt|dress|shoe|sneaker|sandals|boots|abaya|clothing|fashion|بنطلون|جينز|قميص|فستان|حذاء|شوز|سنيكرز|صندل|بوت|عباية|ملابس|جوارب|جاكيت/.test(text)) return "الأزياء والأحذية";
  if (/kitchen|cookware|pan|pot|air fryer|blender|coffee maker|espresso machine|oven|fridge|refrigerator|dishwasher|مطبخ|مقلاة|قدر|قلاية|خلاط|ماكينة قهوة|اسبريسو|فرن|ثلاجة|غسالة صحون/.test(text)) return "المطبخ والأجهزة المنزلية";
  if (/furniture|sofa|chair|table|mattress|cabinet|decor|rug|أثاث|اثاث|كنب|كرسي|طاولة|مرتبة|خزانة|ديكور|سجاد/.test(text)) return "الأثاث والديكور";
  if (/school|student|pencil|notebook|backpack|learning|education|stationery|مدرس|طالب|قلم|دفتر|حقيبة مدرسية|تعليم|قرطاسية/.test(text)) return "المدرسة والقرطاسية";
  if (/book|novel|magazine|office desk|document holder|كتاب|رواية|مجلة|مكتب|حامل مستندات/.test(text)) return "الكتب والمكتب";
  if (/toy|puzzle|doll|building blocks|board game|لعبة|ألعاب|أحجية|دمية|مكعبات/.test(text)) return "الألعاب";
  if (/pet|cat|dog|grooming|قطط|كلاب|حيوان/.test(text)) return "الحيوانات الأليفة";
  if (/baby|kids|child|toddler|diaper|stroller|طفل|أطفال|رضيع|حفاض|عربة أطفال/.test(text)) return "الأطفال";
  if (/beauty|makeup|skincare|cosmetic|hair|nail|مكياج|بشرة|شعر|أظافر/.test(text)) return "الجمال والعناية";
  if (/first aid|bandage|thermometer|blood pressure|orthopedic|hearing aid|إسعافات|اسعافات|ضماد|ميزان حرارة|ضغط الدم|طبي|صحي/.test(text)) return "الصحة والعناية";
  if (/coffee|tea|rice|pasta|snack|chocolate|juice|spice|food|قهوة|شاي|أرز|ارز|مكرونة|وجبة|شوكولاتة|عصير|بهارات|غذاء|طعام/.test(text)) return "البقالة والمشروبات";
  if (/camp|camping|tent|hiking|fishing|marine|boat|kayak|beach|picnic|رحلات برية|تخييم|خيمة|هايكنج|صيد|بحر|قارب|كاياك|شاطئ|نزهة/.test(text)) return "الرحلات والبحر والتخييم";
  if (/garden|gardening|plant|watering|pruning|lawn|seed|حديقة|حدائق|زراعة|نبات|نظام ري|خرطوم ري|تقليم|بذور/.test(text)) return "الحدائق والزراعة";
  if (/sport|fitness|exercise|yoga|running|football|basketball|رياضة|لياقة|تمارين|يوغا|جري|كرة قدم|كرة سلة/.test(text)) return "الرياضة";
  if (/drill|wrench|tool|laser level|دريل|مثقاب|عدة|أدوات|صيانة/.test(text)) return "الأدوات والهوايات";
  if (/car|vehicle|auto|سيار|إطار|اطار/.test(text)) return "السيارة";
  if (/travel|luggage|suitcase|passport holder|packing cube|سفر|أمتعة|امتعة|شنطة سفر|حقيبة سفر|حامل جواز|منظم سفر/.test(text)) return "السفر";
  if (/wrist watch|jewelry|jewellery|necklace|bracelet|ring|ساعة يد|مجوهرات|قلادة|سوار|خاتم/.test(text)) return "الساعات والمجوهرات";
  if (/phone|laptop|computer|charger|cable|usb|keyboard|mouse|headphone|earbuds|هاتف|جوال|لابتوب|كمبيوتر|شاحن|كيبل|سماعة/.test(text)) return "الإلكترونيات";
  if (/home|organizer|storage box|hanger|rack|bed sheet|blanket|pillow|curtain|vacuum|light|منزل|تنظيم|تخزين|علاقة|رف|مفرش|بطانية|وسادة|ستارة|مكنسة|إضاءة/.test(text)) return "المنزل";
  return "تسوق متنوع";
}

function ratingFrom(value) {
  const raw = numberFrom(value);
  if (!(raw > 0)) return 0;
  const rating = raw > 5 ? raw / 20 : raw;
  return Math.round(Math.min(5, rating) * 10) / 10;
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
  // لا نرجع رابط المنتج العادي كبديل؛ ظهور النتيجة مشروط بأن تمنح الواجهة
  // رابط الترويج الرسمي المرتبط بـ Tracking ID الخاص بأوفرلي.
  const url = aliExpressAffiliateUrl(product?.promotion_link);
  if (!productId || title.length < 4 || BLOCKED_PRODUCT_PATTERN.test(title) || !image || !url) return null;

  const rate = numberFrom(env.USD_TO_SAR || 3.75);
  const currency = String(product?.target_sale_price_currency || product?.sale_price_currency || "USD").toUpperCase();
  const multiplier = currency === "SAR" ? 1 : rate || 3.75;
  const current = numberFrom(product?.target_sale_price || product?.sale_price) * multiplier;
  const originalRaw = numberFrom(product?.target_original_price || product?.original_price);
  const original = (originalRaw || numberFrom(product?.target_sale_price || product?.sale_price)) * multiplier;
  const rawRating = numberFrom(product?.evaluate_rate);
  const ratingPercent = Math.min(100, rawRating > 5 ? rawRating : rawRating * 20);
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
    rating: ratingFrom(product?.evaluate_rate),
    rating_percent: ratingPercent,
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
  const thresholds = qualityThresholds(env);

  const cacheKey = new Request(
    `${url.origin}/__cache/${SEARCH_CACHE_VERSION}/search?q=${encodeURIComponent(query.toLowerCase())}` +
    `&page=${page}&page_size=${pageSize}` +
    `&min_sales=${thresholds.minSales}&min_rating=${thresholds.minRating}`,
    request
  );
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) {
    const headers = new Headers(cached.headers);
    Object.entries(cors(origin)).forEach(([key, value]) => headers.set(key, value));
    return new Response(cached.body, { status: cached.status, headers });
  }

  try {
    const variants = queryVariants(query);
    const products = [];
    const seen = new Set();
    const variantsUsed = [];
    let hasMore = false;
    let successfulCalls = 0;
    let lastError = null;

    for (const variant of variants) {
      if (products.length >= pageSize) break;
      try {
        const result = await callAliExpress(variant, page, pageSize, env);
        successfulCalls += 1;
        variantsUsed.push(variant);
        const totalPages = boundedInteger(result?.total_page_no, page, page, MAX_PAGE);
        hasMore = hasMore || page < totalPages;
        for (const rawProduct of unwrapProducts(result)) {
          const product = mapProduct(rawProduct, env);
          if (!meetsQualityThreshold(product, thresholds) || seen.has(product.product_id)) continue;
          seen.add(product.product_id);
          products.push(product);
          if (products.length >= pageSize) break;
        }
      } catch (error) {
        lastError = error;
      }
    }
    if (!successfulCalls) throw lastError || new Error("UPSTREAM");
    const response = json({
      ok: true,
      query,
      query_variants_used: variantsUsed,
      page,
      page_size: pageSize,
      has_more: hasMore,
      shipping_country: "SA",
      filters: {
        min_sales_volume: thresholds.minSales,
        min_rating_percent: thresholds.minRatingPercent,
        min_rating: thresholds.minRating
      },
      products
    }, 200, { ...cors(origin), "Cache-Control": "public, max-age=300, s-maxage=900" });
    await cache.put(cacheKey, response.clone());
    return response;
  } catch (error) {
    const code = error?.message === "CONFIG" ? "SERVICE_NOT_CONFIGURED" : "SEARCH_UNAVAILABLE";
    return json({ ok: false, error: code }, code === "SERVICE_NOT_CONFIGURED" ? 503 : 502, cors(origin));
  }
}

export {
  deviceType,
  mapProduct,
  meetsQualityThreshold,
  qualityThresholds,
  queryVariants,
  ratingFrom,
  sanitizeEvent,
  sanitizeQuery,
  sign,
  unwrapProducts
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ ok: true, service: SERVICE }, 200, { "Cache-Control": "no-store" });
    }
    const origin = allowedOrigin(request, env);
    if (!origin) return json({ ok: false, error: "FORBIDDEN" }, 403);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
    if (url.pathname === "/events" && request.method === "POST") return recordEvent(request, env, origin);
    if (url.pathname === "/search" && request.method === "GET") return search(request, env, origin);
    if (!["/search", "/events"].includes(url.pathname)) return json({ ok: false, error: "NOT_FOUND" }, 404, cors(origin));
    return json({ ok: false, error: "METHOD_NOT_ALLOWED" }, 405, { ...cors(origin), "Allow": "GET, POST, OPTIONS" });
  },

  async scheduled(_controller, env, ctx) {
    if (!env.ANALYTICS_DB?.prepare) return;
    ctx.waitUntil(env.ANALYTICS_DB.prepare(
      "DELETE FROM analytics_events WHERE occurred_at < datetime('now', '-180 days')"
    ).run());
  }
};
