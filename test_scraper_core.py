import json
import tempfile
import unittest
from pathlib import Path

import scraper
import generate_seo


class ScraperCoreTests(unittest.TestCase):
    def test_write_output_does_not_rewrite_identical_catalog(self):
        original_path = scraper.OUTPUT_PATH
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                scraper.OUTPUT_PATH = Path(tmpdir) / "deals.json"
                deals = [{
                    "asin": "B0DL5FT193",
                    "title": "منتج صالح للاختبار المحلي",
                    "image": "https://m.media-amazon.com/images/I/test.jpg",
                    "discount_percent": 10,
                    "original_price": 100,
                    "category": "الإلكترونيات",
                }]
                self.assertTrue(scraper.write_output(deals, "test-source"))
                first_bytes = scraper.OUTPUT_PATH.read_bytes()
                self.assertFalse(scraper.write_output(deals, "test-source"))
                self.assertEqual(scraper.OUTPUT_PATH.read_bytes(), first_bytes)

                payload = json.loads(first_bytes)
                self.assertEqual(payload["count"], 1)
                self.assertEqual(payload["source"], "test-source")
        finally:
            scraper.OUTPUT_PATH = original_path

    def test_existing_catalog_is_recategorized_and_blocked_items_are_removed(self):
        cleaned, blocked, recategorized, repaired_titles = scraper.normalize_existing_deals([
            {
                "asin": "B0DL5FT193",
                "title": "حذاء رياضي رجالي للاستخدام اليومي",
                "category": "الموضة",
            },
            {
                "asin": "B0D53RXMB1",
                "title": "مشوش إشارة لاسلكي محمول",
                "category": "الإلكترونيات",
            },
        ])
        self.assertEqual(blocked, 1)
        self.assertEqual(recategorized, 1)
        self.assertEqual(repaired_titles, 0)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["category"], "الأزياء والأحذية")

    def test_existing_catalog_repairs_generic_title_and_valid_but_wrong_category(self):
        cleaned, blocked, recategorized, repaired_titles = scraper.normalize_existing_deals([
            {
                "asin": "B0CN5Q73LC",
                "title": "Amazon.sa",
                "description": "خصم 5٪ على بلايستيشن 5 PS5 سليم رقمي — بدون قرص وذاكرة 825 جيجا.",
                "category": "الإلكترونيات",
            },
            {
                "asin": "B08D22WD2W",
                "title": "صابون اكسترا وايت 10 كيلو",
                "category": "الإلكترونيات",
            },
        ])
        self.assertEqual(blocked, 0)
        self.assertEqual(repaired_titles, 1)
        self.assertEqual(recategorized, 1)
        self.assertEqual(cleaned[0]["title"], "بلايستيشن 5 PS5 سليم رقمي")
        self.assertEqual(cleaned[1]["category"], "التنظيف والمنظفات")

    def test_category_matching_does_not_match_inside_arabic_words(self):
        self.assertEqual(scraper.classify("مصباح بمستشعر حركة"), "المنزل")

    def test_existing_aliexpress_category_is_not_overridden_by_ambiguous_words(self):
        rows = [{
            "store": "aliexpress",
            "product_id": "1005000000000001",
            "title": "مصباح LED لاسلكي بمستشعر حركة",
            "category": "المنزل",
        }]
        normalized, blocked, recategorized, repaired = scraper.normalize_existing_deals(rows)
        self.assertEqual((blocked, recategorized, repaired), (0, 0, 0))
        self.assertEqual(normalized[0]["category"], "المنزل")

    def test_seo_accepts_official_amazon_associates_image(self):
        deal = generate_seo.normalize_deal({
            "asin": "B08D22WD2W",
            "title": "مسحوق تنظيف منزلي للاستخدام اليومي",
            "image": "https://ws-eu.amazon-adsystem.com/widgets/q?ASIN=B08D22WD2W",
            "discount_percent": 0,
            "original_price": 0,
            "category": "التنظيف والمنظفات",
        })
        self.assertIsNotNone(deal)
        self.assertIn("amazon-adsystem.com", deal["image"])

    def test_seo_uses_owner_verified_discount_without_inventing_before_price(self):
        deal = generate_seo.normalize_deal({
            "asin": "B08D22WD2W",
            "title": "مسحوق تنظيف منزلي للاستخدام اليومي",
            "image": "https://ws-eu.amazon-adsystem.com/widgets/q?ASIN=B08D22WD2W",
            "discount_percent": 0,
            "manual_discount_percent": 56,
            "original_price": 0,
            "category": "التنظيف والمنظفات",
        })
        self.assertIsNotNone(deal)
        self.assertEqual(deal["discount_percent"], 56)
        self.assertEqual(deal["original_price"], 0)


if __name__ == "__main__":
    unittest.main()
