import { createRemoteJWKSet, jwtVerify } from "jose";
import { adminPage } from "./admin-page.js";

const API_VERSION = "2026-03-10";
const MAX_BODY_BYTES = 64 * 1024;
const CATEGORIES = new Set([
  "الإلكترونيات", "التنظيف والمنظفات", "الأزياء والأحذية", "المطبخ والأجهزة المنزلية",
  "الأثاث والديكور", "المنزل", "السيارة", "السفر", "الرحلات والبحر والتخييم",
  "الحدائق والزراعة", "الجمال والعناية", "الصحة والعناية", "البقالة والمشروبات",
  "الرياضة", "الأطفال", "الألعاب", "الحيوانات الأليفة", "الأدوات والهوايات",
  "الترفيه المنزلي", "المدرسة والقرطاسية", "الكتب والمكتب", "الساعات والمجوهرات", "تسوق متنوع"
]);
const CATEGORY_ALIASES = new Map([
  ["الموضة", "الأزياء والأحذية"],
  ["الحدائق", "الحدائق والزراعة"],
  ["البحر والصيد", "الرحلات والبحر والتخييم"],
  ["التخييم", "الرحلات والبحر والتخييم"],
  ["المدرسة والتعليم", "المدرسة والقرطاسية"]
]);

function securityHeaders(contentType) {
  return {
    "Content-Type": contentType,
    "Cache-Control": "no-store, private",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin"
  };
}

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...securityHeaders("application/json; charset=utf-8"), ...extra }
  });
}

function text(body, status = 200) {
  return new Response(body, { status, headers: securityHeaders("text/plain; charset=utf-8") });
}

function normalizeTeamDomain(value) {
  try {
    const url = new URL(String(value || ""));
    if (url.protocol !== "https:" || !url.hostname.endsWith(".cloudflareaccess.com")) return "";
    return url.origin;
  } catch {
    return "";
  }
}

async function authenticate(request, env) {
  const teamDomain = normalizeTeamDomain(env.TEAM_DOMAIN);
  const audience = String(env.POLICY_AUD || "").trim();
  const allowedEmail = String(env.ADMIN_ALLOWED_EMAIL || "").trim().toLowerCase();
  const token = request.headers.get("cf-access-jwt-assertion") || "";
  if (!teamDomain || !audience || !allowedEmail || !token) return null;
  try {
    const jwks = createRemoteJWKSet(new URL(`${teamDomain}/cdn-cgi/access/certs`));
    const { payload } = await jwtVerify(token, jwks, { issuer: teamDomain, audience });
    const email = String(payload.email || "").trim().toLowerCase();
    return email && email === allowedEmail ? { email } : null;
  } catch {
    return null;
  }
}

function repoConfig(env) {
  const owner = String(env.GITHUB_OWNER || "").trim();
  const repo = String(env.GITHUB_REPO || "").trim();
  const branch = String(env.GITHUB_BRANCH || "main").trim();
  const path = String(env.GITHUB_DEALS_PATH || "deals.json").trim();
  const token = String(env.GITHUB_ADMIN_TOKEN || "").trim();
  if (!/^[A-Za-z0-9_.-]{1,100}$/.test(owner) || !/^[A-Za-z0-9_.-]{1,100}$/.test(repo)) return null;
  if (!/^[A-Za-z0-9_./-]{1,200}$/.test(branch) || !/^[A-Za-z0-9_./-]{1,200}$/.test(path) || !token) return null;
  return { owner, repo, branch, path, token };
}

function githubHeaders(config, accept = "application/vnd.github+json") {
  return {
    "Accept": accept,
    "Authorization": `Bearer ${config.token}`,
    "X-GitHub-Api-Version": API_VERSION,
    "User-Agent": "overly-admin-worker"
  };
}

function contentsUrl(config) {
  return `https://api.github.com/repos/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/contents/${config.path.split("/").map(encodeURIComponent).join("/")}?ref=${encodeURIComponent(config.branch)}`;
}

async function loadDeals(env) {
  const config = repoConfig(env);
  if (!config) throw new Error("ADMIN_NOT_CONFIGURED");
  const url = contentsUrl(config);
  const [metadataResponse, rawResponse] = await Promise.all([
    fetch(url, { headers: githubHeaders(config) }),
    fetch(url, { headers: githubHeaders(config, "application/vnd.github.raw+json") })
  ]);
  if (!metadataResponse.ok || !rawResponse.ok) throw new Error("GITHUB_READ_FAILED");
  const metadata = await metadataResponse.json();
  const raw = await rawResponse.text();
  let payload;
  try { payload = JSON.parse(raw); } catch { throw new Error("INVALID_DEALS_FILE"); }
  if (!Array.isArray(payload?.deals) || !/^[a-f0-9]{40}$/i.test(String(metadata.sha || ""))) throw new Error("INVALID_DEALS_FILE");
  return { config, payload, sha: metadata.sha };
}

function utf8ToBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

async function saveDeals(config, payload, sha, email) {
  const body = JSON.stringify({
    message: `إدارة منتجات أوفرلي عبر اللوحة (${email})`,
    content: utf8ToBase64(`${JSON.stringify(payload, null, 2)}\n`),
    sha,
    branch: config.branch
  });
  const response = await fetch(contentsUrl(config), {
    method: "PUT",
    headers: { ...githubHeaders(config), "Content-Type": "application/json" },
    body
  });
  if (response.status === 409) throw new Error("CONFLICT");
  if (!response.ok) throw new Error("GITHUB_WRITE_FAILED");
  return response.json();
}

function cleanString(value, max) {
  return String(value || "").normalize("NFKC").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

function safeHttps(value, hosts) {
  try {
    const url = new URL(String(value || "").replace(/^http:\/\//i, "https://"));
    if (url.protocol !== "https:") return "";
    const host = url.hostname.toLowerCase();
    return hosts.some(allowed => host === allowed || host.endsWith(`.${allowed}`)) ? url.href : "";
  } catch {
    return "";
  }
}

function safeAliExpressAffiliateUrl(value) {
  const safe = safeHttps(value, ["aliexpress.com", "aliexpress.us"]);
  if (!safe) return "";
  const url = new URL(safe);
  if (url.hostname.toLowerCase() === "s.click.aliexpress.com") return url.href;
  const platform = String(url.searchParams.get("aff_platform") || "").toLowerCase();
  return url.searchParams.has("aff_fcid") &&
    url.searchParams.has("aff_trace_key") && platform.includes("api") ? url.href : "";
}

function finiteNumber(value, min, max) {
  const number = Number(value);
  return Number.isFinite(number) && number >= min && number <= max ? number : null;
}

function normalizeCategory(value) {
  const raw = cleanString(value, 60);
  const category = CATEGORY_ALIASES.get(raw) || raw;
  return CATEGORIES.has(category) ? category : "";
}

function productKey(product) {
  return String(product?.store || "amazon").toLowerCase() === "aliexpress"
    ? `aliexpress:${String(product?.product_id || "").trim()}`
    : `amazon:${String(product?.asin || "").trim().toUpperCase()}`;
}

function sanitizeProduct(input) {
  const store = String(input?.store || "amazon").toLowerCase() === "aliexpress" ? "aliexpress" : "amazon";
  const title = cleanString(input?.title, 180);
  const category = normalizeCategory(input?.category);
  const originalPrice = finiteNumber(input?.original_price, 0.01, 100000);
  const discount = finiteNumber(input?.discount_percent, 0, 95);
  const sales = finiteNumber(input?.sales_volume || 0, 0, 1_000_000_000);
  const rating = finiteNumber(input?.rating || 0, 0, 100);
  const imageHosts = store === "amazon"
    ? ["media-amazon.com", "ssl-images-amazon.com"]
    : ["alicdn.com", "aliexpress-media.com", "aliexpress.com"];
  const image = safeHttps(input?.image, imageHosts);
  if (title.length < 4 || !category || originalPrice === null || discount === null || sales === null || rating === null || !image) return null;
  const common = {
    store,
    title,
    image,
    discount_percent: Math.round(discount),
    original_price: Math.round(originalPrice * 100) / 100,
    sales_volume: Math.round(sales),
    category,
    auto_discovered: false,
    owner_pinned: true,
    rank_score: 99
  };
  if (rating > 0) common.rating = Math.round(rating * 10) / 10;
  if (store === "amazon") {
    const asin = String(input?.asin || "").trim().toUpperCase();
    return /^[A-Z0-9]{10}$/.test(asin) ? { ...common, asin } : null;
  }
  const productId = String(input?.product_id || "").match(/^\d{6,20}$/)?.[0] || "";
  const url = safeAliExpressAffiliateUrl(input?.url);
  return productId && url ? { ...common, product_id: productId, url } : null;
}

async function readJson(request) {
  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > MAX_BODY_BYTES) throw new Error("PAYLOAD_TOO_LARGE");
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) throw new Error("PAYLOAD_TOO_LARGE");
  try { return JSON.parse(raw); } catch { throw new Error("INVALID_JSON"); }
}

function verifyWriteRequest(request) {
  const origin = request.headers.get("origin") || "";
  return origin === new URL(request.url).origin && request.headers.get("x-overly-admin") === "1" &&
    (request.headers.get("content-type") || "").toLowerCase().startsWith("application/json");
}

async function listProducts(request, env) {
  const { payload } = await loadDeals(env);
  const url = new URL(request.url);
  const query = cleanString(url.searchParams.get("q"), 80).toLowerCase();
  const pageSize = Math.min(60, Math.max(10, Number.parseInt(url.searchParams.get("page_size") || "40", 10) || 40));
  const all = payload.deals;
  const filtered = query ? all.filter(item => `${item.title || ""} ${item.asin || ""} ${item.product_id || ""}`.toLowerCase().includes(query)) : all;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const page = Math.min(pages, Math.max(1, Number.parseInt(url.searchParams.get("page") || "1", 10) || 1));
  return json({
    ok: true,
    page,
    pages,
    total: filtered.length,
    stats: {
      total: all.length,
      amazon: all.filter(item => String(item.store || "amazon").toLowerCase() !== "aliexpress").length,
      aliexpress: all.filter(item => String(item.store || "amazon").toLowerCase() === "aliexpress").length
    },
    products: filtered.slice((page - 1) * pageSize, page * pageSize)
  });
}

async function upsertProduct(request, env, identity) {
  if (!verifyWriteRequest(request)) return json({ ok: false, error: "INVALID_WRITE_REQUEST" }, 403);
  const input = await readJson(request);
  const product = sanitizeProduct(input?.product);
  if (!product) return json({ ok: false, error: "INVALID_PRODUCT" }, 400);
  const previousKey = cleanString(input?.previous_key, 80).toLowerCase();
  const { config, payload, sha } = await loadDeals(env);
  const key = productKey(product).toLowerCase();
  let replaced = false;
  const nextDeals = payload.deals.flatMap(item => {
    const itemKey = productKey(item).toLowerCase();
    if (previousKey && itemKey === previousKey && previousKey !== key) return [];
    if (itemKey === key) {
      replaced = true;
      return [{ ...item, ...product }];
    }
    return [item];
  });
  if (!replaced) nextDeals.unshift(product);
  const nextPayload = { ...payload, updated_at: new Date().toISOString(), source: "overly-admin", count: nextDeals.length, deals: nextDeals };
  const result = await saveDeals(config, nextPayload, sha, identity.email);
  return json({ ok: true, action: replaced ? "updated" : "created", count: nextDeals.length, commit: result?.commit?.sha || "" });
}

async function deleteProduct(request, env, identity, encodedKey) {
  if (!verifyWriteRequest(request)) return json({ ok: false, error: "INVALID_WRITE_REQUEST" }, 403);
  const key = cleanString(decodeURIComponent(encodedKey || ""), 80).toLowerCase();
  if (!/^(amazon:[a-z0-9]{10}|aliexpress:\d{6,20})$/.test(key)) return json({ ok: false, error: "INVALID_PRODUCT_KEY" }, 400);
  const { config, payload, sha } = await loadDeals(env);
  const nextDeals = payload.deals.filter(item => productKey(item).toLowerCase() !== key);
  if (nextDeals.length === payload.deals.length) return json({ ok: false, error: "NOT_FOUND" }, 404);
  const nextPayload = { ...payload, updated_at: new Date().toISOString(), source: "overly-admin", count: nextDeals.length, deals: nextDeals };
  const result = await saveDeals(config, nextPayload, sha, identity.email);
  return json({ ok: true, count: nextDeals.length, commit: result?.commit?.sha || "" });
}

async function analyticsDashboard(request, env) {
  if (!env.ANALYTICS_DB?.prepare || !env.ANALYTICS_DB?.batch) {
    return json({ ok: false, error: "ANALYTICS_NOT_CONFIGURED" }, 503);
  }
  const requestedDays = Number.parseInt(new URL(request.url).searchParams.get("days") || "30", 10);
  const days = [7, 30, 90].includes(requestedDays) ? requestedDays : 30;
  const since = `-${days - 1} days`;
  const queries = [
    env.ANALYTICS_DB.prepare(`
      SELECT
        SUM(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) AS views,
        SUM(CASE WHEN event_type = 'product_click' THEN 1 ELSE 0 END) AS clicks,
        SUM(CASE WHEN day = date('now') AND event_type = 'page_view' THEN 1 ELSE 0 END) AS views_today,
        SUM(CASE WHEN day = date('now') AND event_type = 'product_click' THEN 1 ELSE 0 END) AS clicks_today
      FROM analytics_events WHERE day >= date('now', ?)
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT day,
        SUM(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) AS views,
        SUM(CASE WHEN event_type = 'product_click' THEN 1 ELSE 0 END) AS clicks
      FROM analytics_events WHERE day >= date('now', ?)
      GROUP BY day ORDER BY day ASC
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT product_key, MAX(product_title) AS title, MAX(store) AS store,
        MAX(category) AS category, COUNT(*) AS clicks
      FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'product_click' AND product_key <> ''
      GROUP BY product_key ORDER BY clicks DESC LIMIT 15
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT category AS label, COUNT(*) AS count FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'product_click' AND category <> ''
      GROUP BY category ORDER BY count DESC LIMIT 12
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT store AS label, COUNT(*) AS count FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'product_click' AND store <> ''
      GROUP BY store ORDER BY count DESC
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT device_type AS label, COUNT(*) AS count FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'page_view' AND device_type <> ''
      GROUP BY device_type ORDER BY count DESC
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT country AS label, COUNT(*) AS count FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'page_view' AND country <> ''
      GROUP BY country ORDER BY count DESC LIMIT 10
    `).bind(since),
    env.ANALYTICS_DB.prepare(`
      SELECT referrer_host AS label, COUNT(*) AS count FROM analytics_events
      WHERE day >= date('now', ?) AND event_type = 'page_view' AND referrer_host <> ''
      GROUP BY referrer_host ORDER BY count DESC LIMIT 10
    `).bind(since)
  ];
  const results = await env.ANALYTICS_DB.batch(queries);
  const summary = results[0]?.results?.[0] || {};
  const views = Number(summary.views || 0);
  const clicks = Number(summary.clicks || 0);
  return json({
    ok: true,
    days,
    generated_at: new Date().toISOString(),
    summary: {
      views,
      clicks,
      ctr: views > 0 ? Math.round((clicks / views) * 1000) / 10 : 0,
      views_today: Number(summary.views_today || 0),
      clicks_today: Number(summary.clicks_today || 0)
    },
    daily: results[1]?.results || [],
    top_products: results[2]?.results || [],
    categories: results[3]?.results || [],
    stores: results[4]?.results || [],
    devices: results[5]?.results || [],
    countries: results[6]?.results || [],
    referrers: results[7]?.results || []
  });
}

function errorResponse(error) {
  const code = error instanceof Error ? error.message : "INTERNAL_ERROR";
  const status = code === "PAYLOAD_TOO_LARGE" ? 413 : code === "CONFLICT" ? 409 :
    code === "ADMIN_NOT_CONFIGURED" ? 503 : code.startsWith("INVALID_") ? 400 : 502;
  return json({ ok: false, error: code }, status);
}

export { analyticsDashboard, authenticate, normalizeTeamDomain, productKey, safeAliExpressAffiliateUrl, sanitizeProduct, verifyWriteRequest };

export default {
  async fetch(request, env) {
    const identity = await authenticate(request, env);
    if (!identity) return text("غير مصرح بالدخول إلى لوحة أوفرلي.", 403);
    const url = new URL(request.url);
    try {
      if (url.pathname === "/" && request.method === "GET") {
        const nonce = crypto.randomUUID().replaceAll("-", "");
        const html = adminPage({ nonce, email: identity.email, siteUrl: env.SITE_URL || "https://majeed3575.github.io/majeeddeals/" });
        const headers = securityHeaders("text/html; charset=utf-8");
        headers["Content-Security-Policy"] = `default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; connect-src 'self'; img-src 'self' data: https://*.alicdn.com https://*.aliexpress-media.com https://*.media-amazon.com https://*.ssl-images-amazon.com; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}'`;
        return new Response(html, { headers });
      }
      if (url.pathname === "/api/products" && request.method === "GET") return await listProducts(request, env);
      if (url.pathname === "/api/analytics" && request.method === "GET") return await analyticsDashboard(request, env);
      if (url.pathname === "/api/products" && request.method === "POST") return await upsertProduct(request, env, identity);
      if (url.pathname.startsWith("/api/products/") && request.method === "DELETE") {
        return await deleteProduct(request, env, identity, url.pathname.slice("/api/products/".length));
      }
      return json({ ok: false, error: "NOT_FOUND" }, 404);
    } catch (error) {
      return errorResponse(error);
    }
  }
};
