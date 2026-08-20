import { createRemoteJWKSet, jwtVerify } from "jose";
import { adminPage } from "./admin-page.js";

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

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: securityHeaders("application/json; charset=utf-8")
  });
}

function text(body, status = 200) {
  return new Response(body, {
    status,
    headers: securityHeaders("text/plain; charset=utf-8")
  });
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
    const { payload } = await jwtVerify(token, jwks, {
      issuer: teamDomain,
      audience
    });
    const email = String(payload.email || "").trim().toLowerCase();
    return email && email === allowedEmail ? { email } : null;
  } catch {
    return null;
  }
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

export { analyticsDashboard, authenticate, normalizeTeamDomain };

export default {
  async fetch(request, env) {
    const identity = await authenticate(request, env);
    if (!identity) return text("غير مصرح بالدخول إلى لوحة أوفرلي.", 403);

    const url = new URL(request.url);
    try {
      if (url.pathname === "/" && request.method === "GET") {
        const nonce = crypto.randomUUID().replaceAll("-", "");
        const html = adminPage({
          nonce,
          email: identity.email,
          siteUrl: env.SITE_URL || "https://majeed3575.github.io/majeeddeals/"
        });
        const headers = securityHeaders("text/html; charset=utf-8");
        headers["Content-Security-Policy"] =
          `default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; connect-src 'self'; img-src 'self' data:; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}'`;
        return new Response(html, { headers });
      }

      if (url.pathname === "/api/analytics" && request.method === "GET") {
        return await analyticsDashboard(request, env);
      }

      return json({ ok: false, error: "NOT_FOUND" }, 404);
    } catch {
      return json({ ok: false, error: "ANALYTICS_QUERY_FAILED" }, 502);
    }
  }
};
