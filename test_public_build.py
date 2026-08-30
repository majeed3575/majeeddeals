import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

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
            "assets/overly-next.css",
            "assets/overly-visual-system.js",
            "deals.json",
            "robots.txt",
            "sitemap.xml",
            "search-config.js",
            "_headers",
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

    def test_bundle_excludes_large_source_only_brand_assets(self):
        for name in build_public_site.SOURCE_ONLY_ASSETS:
            self.assertFalse((self.output / "assets" / name).exists(), name)

    def test_bundle_has_baseline_security_headers(self):
        headers = (self.output / "_headers").read_text(encoding="utf-8")
        self.assertIn("X-Frame-Options: DENY", headers)
        self.assertIn("X-Content-Type-Options: nosniff", headers)
        self.assertIn("Content-Security-Policy:", headers)
        self.assertIn("frame-ancestors 'none'", headers)

    def test_bundle_has_no_broken_internal_links_or_assets(self):
        class ReferenceParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.references = []

            def handle_starttag(self, _tag, attrs):
                attributes = dict(attrs)
                for name in ("href", "src"):
                    if attributes.get(name):
                        self.references.append(attributes[name])

        missing = []
        checked = 0
        for html_path in self.output.rglob("*.html"):
            parser = ReferenceParser()
            parser.feed(html_path.read_text(encoding="utf-8"))
            for reference in parser.references:
                if reference.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
                    continue
                parsed = urlparse(reference)
                if parsed.scheme and parsed.netloc not in ("overly.live", "www.overly.live"):
                    continue
                if parsed.netloc in ("overly.live", "www.overly.live") or parsed.path.startswith("/"):
                    target = self.output / unquote(parsed.path).lstrip("/")
                else:
                    target = html_path.parent / unquote(parsed.path)
                candidates = [target]
                if parsed.path.endswith("/"):
                    candidates.append(target / "index.html")
                elif not target.suffix:
                    candidates.extend((target / "index.html", target.with_suffix(".html")))
                checked += 1
                if not any(candidate.exists() for candidate in candidates):
                    missing.append((str(html_path.relative_to(self.output)), reference))
        self.assertGreater(checked, 1000)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
