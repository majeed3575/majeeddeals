import json
import re
import unittest
import zipfile
from pathlib import Path

import generate_seo

ROOT = Path(__file__).resolve().parent


class PublicContracts(unittest.TestCase):
    def test_catalog_checks_run_after_generation_and_before_publishing(self):
        workflow = (ROOT / ".github/workflows/scraper.yml").read_text()
        generation = workflow.index("run: python generate_seo.py")
        gate = workflow.index("python -m unittest discover -v")
        publish = workflow.index("- name: Commit & push (if changed)")
        self.assertLess(generation, gate)
        self.assertLess(gate, publish)
        preflight = workflow[:workflow.index("- name: Run scraper")]
        self.assertIn("test_scraper_core test_english_titles", preflight)
        self.assertNotIn("test_runtime.mjs", preflight)

    def test_extension_download_matches_reviewed_sources(self):
        files = {"manifest.json", "popup.js", "popup.html", "README.md", "icon48.png", "icon128.png"}
        with zipfile.ZipFile(ROOT / "saudi-deals-product-tool.zip") as archive:
            self.assertEqual({name for name in archive.namelist() if not name.endswith("/")},
                             {"browser-extension/" + name for name in files})
            for name in files:
                self.assertEqual(archive.read("browser-extension/" + name), (ROOT / "browser-extension" / name).read_bytes(), name)
            self.assertEqual(json.loads(archive.read("browser-extension/manifest.json"))["version"], "5.1.0")

    def test_public_image_policy_allows_both_exact_and_subdomain_hosts(self):
        hosts = ("media-amazon.com", "ssl-images-amazon.com", "amazon-adsystem.com", "amazon.com",
                 "alicdn.com", "aliexpress-media.com", "aliexpress.com")
        for name in ("_headers", "browse.html", "generate_seo.py"):
            sources = re.search(r"img-src ([^;]+)", (ROOT / name).read_text()).group(1).split()
            for host in hosts:
                self.assertIn("https://" + host, sources, name)
                self.assertIn("https://*." + host, sources, name)
        for image in ("https://name:pass@alicdn.com/x", "https://alicdn.com:8443/x", "https://alicdn.com.evil.example/x"):
            self.assertEqual(generate_seo.valid_https(image, hosts), "")
        self.assertEqual(generate_seo.valid_https("https://alicdn.com/x", hosts), "https://alicdn.com/x")

    def test_analytics_includes_config_before_script_and_never_ships_tests(self):
        import build_public_site
        self.assertIn("analytics.js", build_public_site.PUBLIC_FILES)
        self.assertNotIn("test_analytics.mjs", build_public_site.PUBLIC_FILES)
        for name in ("index.html", "browse.html", "privacy.html", "terms.html", "affiliate-disclosure.html", "copyright.html", "categories/index.html"):
            html = (ROOT / name).read_text()
            self.assertLess(html.index("search-config.js"), html.index("analytics.js"), name)


if __name__ == "__main__":
    unittest.main()
