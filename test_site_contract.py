import json
import re
import unittest
from collections import Counter
from pathlib import Path

import generate_seo


ROOT = Path(__file__).resolve().parent


class SiteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.catalog = json.loads((ROOT / "deals.json").read_text(encoding="utf-8"))
        cls.initial = json.loads((ROOT / "deals-initial.json").read_text(encoding="utf-8"))
        cls.categories_index = (ROOT / "categories/index.html").read_text(encoding="utf-8")

    def test_initial_catalog_matches_full_catalog_metadata(self):
        self.assertEqual(self.initial["total_count"], self.catalog["count"])
        self.assertLessEqual(len(self.initial["deals"]), 72)
        full_keys = {
            (str(item.get("store") or "amazon"), str(item.get("product_id") or item.get("asin") or ""))
            for item in self.catalog["deals"]
        }
        initial_keys = {
            (str(item.get("store") or "amazon"), str(item.get("product_id") or item.get("asin") or ""))
            for item in self.initial["deals"]
        }
        self.assertTrue(initial_keys.issubset(full_keys))

    def test_site_keeps_affiliate_and_price_disclosures(self):
        self.assertIn("إفصاح", self.html)
        self.assertIn("جاري التحقق من توفر العرض", self.html)
        self.assertRegex(self.html, r"السعر (?:الحالي|النهائي)")
        self.assertNotIn("متوسط السوق المحلي", self.html)

    def test_site_has_no_embedded_stale_product_fallback(self):
        self.assertNotIn("FALLBACK_DATA", self.html)
        self.assertIn("جاري تحميل العروض الحالية", self.html)
        self.assertNotRegex(self.html, r"let\s+deals\s*=\s*\[\s*\{")

    def test_live_search_has_a_bounded_timeout_and_safe_request_state(self):
        self.assertIn("}, 12_000);", self.html)
        self.assertIn("if (aliSearchController === controller)", self.html)
        self.assertIn("استغرق البحث وقتًا أطول من المتوقع", self.html)

    def test_catalog_and_live_search_share_the_same_rating_scale(self):
        self.assertIn("const normalizedRating = product =>", self.html)
        self.assertGreaterEqual(self.html.count("const rating = normalizedRating(product);"), 2)
        self.assertGreaterEqual(self.html.count("...rating,"), 2)
        self.assertIn("Number(deal.rating).toFixed(1)", self.html)

    def test_amazon_manual_discount_never_implies_zero_before_price(self):
        self.assertIn("const discountPercent", self.html)
        self.assertIn("const hasBeforePrice", self.html)
        self.assertNotIn(
            "hasDiscount(deal) ? `<s>${formatNumber(deal.original_price)} ر.س</s>`",
            self.html,
        )

    def test_associates_widget_images_are_allowed(self):
        self.assertIn("https://*.amazon-adsystem.com", self.html)
        self.assertIn('"amazon-adsystem.com"', self.html)

    def test_owner_amazon_images_survive_local_preview_and_custom_domain(self):
        self.assertIn("https://overly.live", self.html)
        self.assertIn("https://majeed3575.github.io", self.html)
        self.assertIn('publicHost === "overly.live"', self.html)
        self.assertIn('publicHost === "majeed3575.github.io"', self.html)
        self.assertIn('/assets/amazon-manual/', self.html)
        self.assertIn('/majeeddeals/assets/amazon-manual/', self.html)

    def test_custom_domain_is_the_primary_canonical(self):
        self.assertIn('<link rel="canonical" href="https://overly.live/">', self.html)
        self.assertIn('"url":"https://overly.live/"', self.html)

    def test_model_170_drives_the_live_visual_system_without_floating_products(self):
        visual_path = ROOT / "assets" / "overly-visual-system.js"
        visual_css_path = ROOT / "assets" / "overly-next.css"
        self.assertTrue(visual_path.is_file())
        self.assertTrue(visual_css_path.is_file())

        visual_script = visual_path.read_text(encoding="utf-8")
        visual_css = visual_css_path.read_text(encoding="utf-8")
        self.assertIn('scene(170, "prism-portal"', visual_script)
        self.assertIn("LIQUID / PRISM / 170", self.html)
        self.assertIn('id="gatewaySearchForm"', self.html)
        self.assertIn("OVERLY / PRISM MIX 170", visual_css)
        self.assertIn('assets/overly-visual-system.js', self.html)

        assignments = re.findall(r'^\s+"([^"]+)": scene\((\d+),', visual_script, re.MULTILINE)
        self.assertEqual({name for name, _ in assignments}, set(generate_seo.CATEGORIES))
        self.assertEqual(len(assignments), len({model for _, model in assignments}))

        stage = re.search(
            r"function renderGatewayProductStage\(\) \{(?P<body>.*?)\n    \}\n\n    function renderCategoryCards",
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(stage)
        self.assertNotIn("gateway-product-tile", stage.group("body"))
        self.assertIn("prism-orb", stage.group("body"))

        for name, info in generate_seo.CATEGORIES.items():
            category_path = ROOT / "categories" / info["slug"] / "index.html"
            if category_path.exists():
                category_html = category_path.read_text(encoding="utf-8")
                self.assertIn(f'<body class="visual-{info["slug"]}">', category_html, name)

    def test_hourly_workflow_builds_and_deploys_only_the_public_bundle(self):
        workflow = (ROOT / ".github/workflows/scraper.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "0 * * * *"', workflow)
        self.assertIn("python build_public_site.py", workflow)
        self.assertIn("actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803", workflow)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", workflow)
        self.assertIn("cloudflare/wrangler-action@ebbaa1584979971c8614a24965b4405ff95890e0", workflow)
        self.assertIn("wrangler.site.jsonc", workflow)
        self.assertIn("Verify live security headers", workflow)
        self.assertIn("Verify live catalog matches deployed bundle", workflow)
        self.assertIn("sha256sum dist-site/deals.json", workflow)
        self.assertIn('Cache-Control: no-cache', workflow)
        self.assertIn("strict-transport-security", workflow)
        self.assertIn("content-security-policy", workflow)
        self.assertNotIn("cd cloudflare-worker", workflow)
        self.assertNotIn("cd cloudflare-admin", workflow)
        self.assertNotIn("cd cloudflare-amazon-bot", workflow)
        self.assertIn("CLOUDFLARE_API_TOKEN", workflow)
        self.assertIn("Fail clearly when Cloudflare deployment is not configured", workflow)
        self.assertNotIn("Explain skipped Cloudflare deploy", workflow)
        self.assertIn('TELEGRAM_MAX_NEW_POSTS: "10"', workflow)
        self.assertIn('TELEGRAM_SEND_DELAY_SECONDS: "3"', workflow)
        self.assertIn("timeout-minutes: 30", workflow)

    def test_empty_categories_are_not_published_or_offered_as_filters(self):
        counts = Counter(
            generate_seo.normalize_category(item.get("category"))
            for item in self.catalog["deals"]
        )
        self.assertIn("availableCategories", self.html)
        for name, info in generate_seo.CATEGORIES.items():
            category_path = ROOT / "categories" / info["slug"] / "index.html"
            link_fragment = f"categories/{info['slug']}/"
            if counts[name]:
                self.assertTrue(category_path.exists(), name)
                self.assertIn(link_fragment, self.categories_index)
            else:
                self.assertFalse(category_path.exists(), name)
                self.assertNotIn(link_fragment, self.categories_index)


if __name__ == "__main__":
    unittest.main()
