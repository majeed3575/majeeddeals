import sys
import types
import unittest


# تسمح بتشغيل اختبارات الدوال النقية محلياً حتى لو لم تكن تبعيات الجمع مثبتة.
# في GitHub Actions تُستخدم requests وBeautifulSoup الحقيقيتان لأن الـ workflow يثبتهما أولاً.
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = Exception
    requests_stub.Session = object
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

try:
    import bs4  # noqa: F401
except ModuleNotFoundError:
    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = object
    sys.modules["bs4"] = bs4_stub

import generate_seo
import scraper
from verify_affiliate_links import is_aliexpress_affiliate_url, is_amazon_affiliate_url


SHORT = "https://s.click.aliexpress.com/e/example"
MARKED = "https://www.aliexpress.com/item/1005001234567890.html?aff_fcid=abc&aff_trace_key=xyz&aff_platform=api-new-product-query"
DIRECT = "https://www.aliexpress.com/item/1005001234567890.html"


class AffiliateLinkTests(unittest.TestCase):
    def test_aliexpress_links_fail_closed(self):
        self.assertTrue(is_aliexpress_affiliate_url(SHORT))
        self.assertTrue(is_aliexpress_affiliate_url(MARKED))
        self.assertFalse(is_aliexpress_affiliate_url(DIRECT))
        self.assertEqual(scraper._ali_affiliate_url(SHORT), SHORT)
        self.assertEqual(scraper._ali_affiliate_url(MARKED), MARKED)
        self.assertEqual(scraper._ali_affiliate_url(DIRECT), "")
        self.assertEqual(generate_seo.valid_aliexpress_affiliate_url(DIRECT), "")

    def test_amazon_link_requires_associate_tag(self):
        good = "https://www.amazon.sa/dp/B0DL5FT193/?tag=faraj733-21"
        self.assertTrue(is_amazon_affiliate_url(good, "B0DL5FT193"))
        self.assertFalse(is_amazon_affiliate_url("https://www.amazon.sa/dp/B0DL5FT193/", "B0DL5FT193"))

    def test_categories_are_consistent(self):
        self.assertEqual(scraper.classify("Extra White Detergent Powder 10kg"), "التنظيف والمنظفات")
        self.assertEqual(scraper.classify("بنطلون جينز رجالي"), "الأزياء والأحذية")
        self.assertEqual(scraper.classify("مصباح تخييم قابل للشحن"), "الرحلات والبحر والتخييم")
        self.assertEqual(scraper.normalize_category("الموضة"), "الأزياء والأحذية")
        self.assertEqual(generate_seo.normalize_category("الموضة"), "الأزياء والأحذية")
        self.assertEqual(generate_seo.normalize_category("البحر والصيد"), "الرحلات والبحر والتخييم")
        self.assertEqual(generate_seo.normalize_category("غير معروف"), "تسوق متنوع")

    def test_seo_rejects_direct_aliexpress_url(self):
        base = {
            "store": "aliexpress", "product_id": "1005001234567890",
            "title": "منتج AliExpress صالح للاختبار", "image": "https://ae01.alicdn.com/kf/test.jpg",
            "original_price": 50, "discount_percent": 10, "category": "تسوق متنوع",
        }
        self.assertIsNone(generate_seo.normalize_deal({**base, "url": DIRECT}))
        self.assertIsNotNone(generate_seo.normalize_deal({**base, "url": MARKED}))

    def test_legacy_category_redirects_are_internal_and_noindex(self):
        for source, target in generate_seo.LEGACY_CATEGORY_REDIRECTS.items():
            page = generate_seo.redirect_page(source, target)
            self.assertIn(f'{generate_seo.BASE_PATH}{target}', page)
            self.assertIn(f'{generate_seo.BASE_URL}{target}', page)
            self.assertIn('name="robots" content="noindex,follow"', page)
            self.assertNotIn(source, target)


if __name__ == "__main__":
    unittest.main()
