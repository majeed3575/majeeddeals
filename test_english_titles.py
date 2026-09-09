import unittest
from unittest.mock import patch
import scraper

class EnglishTitles(unittest.TestCase):
    def deal(self):
        return {'store':'aliexpress','product_id':'1005007777777777','title':'عنوان اختبار جديد غير موجود في القاموس','url':'https://s.click.aliexpress.com/e/test'}
    @patch.object(scraper, 'load_existing_deals', return_value=[])
    def test_requests_english_by_exact_product_id_without_changing_arabic_or_link(self, _load):
        deal = self.deal(); original = deal.copy()
        payload = {'products':{'product':[{'product_id':deal['product_id'],'product_title':'<b>Portable light</b>'},{'product_id':'1005008888888888','product_title':'Wrong product'}]}}
        with patch.object(scraper,'aliexpress_api_call',return_value=payload) as call:
            result = scraper.enrich_english_titles([deal])
        self.assertEqual(result[0]['title_en'],'Portable light')
        self.assertEqual(result[0]['title'],original['title']);self.assertEqual(result[0]['url'],original['url'])
        self.assertEqual(call.call_args.args[1]['target_language'],'EN')
        self.assertEqual(call.call_args.args[1]['product_ids'],deal['product_id'])
    def test_reuses_cached_translation_only_for_unchanged_title(self):
        old={**self.deal(),'title_en':'Portable light'}
        with patch.object(scraper,'load_existing_deals',return_value=[old]),patch.object(scraper,'aliexpress_api_call',return_value={}) as call:
            self.assertEqual(scraper.enrich_english_titles([self.deal()])[0]['title_en'],'Portable light');call.assert_not_called()
            changed={**self.deal(),'title':'عنوان منتج مختلف'}
            self.assertNotIn('title_en',scraper.enrich_english_titles([changed])[0]);call.assert_called_once()
    def test_unavailable_translation_never_drops_a_valid_product(self):
        deal=self.deal();original=deal.copy()
        with patch.object(scraper,'load_existing_deals',return_value=[]),patch.object(scraper,'aliexpress_api_call',side_effect=RuntimeError('unavailable')):
            self.assertEqual(scraper.enrich_english_titles([deal]),[original])

if __name__=='__main__': unittest.main()
