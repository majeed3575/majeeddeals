import test from "node:test";
import assert from "node:assert/strict";
import { normalizeTeamDomain, analyticsDashboard } from "../src/index.js";

test("accepts only Cloudflare Access team domains", () => {
  assert.equal(normalizeTeamDomain("https://overly.cloudflareaccess.com"), "https://overly.cloudflareaccess.com");
  assert.equal(normalizeTeamDomain("https://example.com"), "");
  assert.equal(normalizeTeamDomain("javascript:alert(1)"), "");
});

test("analytics endpoint returns aggregated read-only metrics", async () => {
  const resultSets = [
    { results: [{ views: 20, clicks: 5, views_today: 3, clicks_today: 1 }] },
    { results: [{ day: "2026-08-20", views: 20, clicks: 5 }] },
    { results: [{ product_key: "aliexpress:123456", title: "منتج", store: "aliexpress", category: "الإلكترونيات", clicks: 5 }] },
    { results: [{ label: "الإلكترونيات", count: 5 }] },
    { results: [{ label: "aliexpress", count: 5 }] },
    { results: [{ label: "mobile", count: 20 }] },
    { results: [{ label: "SA", count: 20 }] },
    { results: [{ label: "google.com", count: 10 }] }
  ];

  const env = {
    ANALYTICS_DB: {
      prepare() {
        return { bind() { return this; } };
      },
      async batch(queries) {
        assert.equal(queries.length, 8);
        return resultSets;
      }
    }
  };

  const response = await analyticsDashboard(new Request("https://admin.example/api/analytics?days=30"), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.ok, true);
  assert.equal(body.summary.views, 20);
  assert.equal(body.summary.clicks, 5);
  assert.equal(body.summary.ctr, 25);
});

test("analytics fails closed when D1 is not bound", async () => {
  const response = await analyticsDashboard(new Request("https://admin.example/api/analytics"), {});
  assert.equal(response.status, 503);
});
