import json
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

    def test_hourly_workflow_builds_and_deploys_only_the_public_bundle(self):
        workflow = (ROOT / ".github/workflows/scraper.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "0 * * * *"', workflow)
        self.assertIn("python build_public_site.py", workflow)
        self.assertIn("cloudflare/wrangler-action@v3", workflow)
        self.assertIn("wrangler.site.jsonc", workflow)
        self.assertNotIn("cd cloudflare-worker", workflow)
        self.assertNotIn("cd cloudflare-admin", workflow)
        self.assertNotIn("cd cloudflare-amazon-bot", workflow)

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
