import unittest
from pathlib import Path

import build_public_site


class PublicBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copied = build_public_site.build()
        cls.output = build_public_site.OUTPUT

    def test_bundle_contains_required_public_entrypoints(self):
        self.assertGreater(self.copied, 800)
        for relative in (
            "index.html",
            "404.html",
            "deals.json",
            "robots.txt",
            "sitemap.xml",
            "search-config.js",
        ):
            self.assertTrue((self.output / relative).is_file(), relative)

    def test_bundle_excludes_backend_source_and_repository_metadata(self):
        forbidden_parts = {
            ".git",
            ".github",
            "node_modules",
            "cloudflare-worker",
            "cloudflare-admin",
            "cloudflare-amazon-bot",
            "overly-backend-private",
        }
        forbidden_names = {
            ".env",
            ".dev.vars",
            "scraper.py",
            "wrangler.toml",
            "wrangler.jsonc",
            "package.json",
            "package-lock.json",
        }
        for path in self.output.rglob("*"):
            if not path.is_file():
                continue
            self.assertTrue(forbidden_parts.isdisjoint(path.parts), str(path))
            self.assertNotIn(path.name, forbidden_names, str(path))

    def test_bundle_does_not_publish_internal_seo_state(self):
        for name in ("seo-state.json", "seo-report.json", "seo-generated-files.json"):
            self.assertFalse((self.output / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
