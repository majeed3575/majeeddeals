"""Fast theme safeguards; verify_theme_browser.mjs additionally checks rendered CSS."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


class ThemeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "live-theme.css").read_text(encoding="utf-8")

    def test_product_cards_do_not_require_homepage_palette_attribute(self):
        rule = re.search(r"html\s+\.product-card\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(rule, "Generated pages do not set data-palette")
        self.assertIn("background:var(--panel-solid)", rule.group(1))
        self.assertIn("color:var(--ink)", rule.group(1))
        self.assertIn("border-color:var(--line)", rule.group(1))

    def test_header_surface_is_not_permanently_dark(self):
        rule = re.search(r"html\s+\.site-header\s*\{([^}]+)\}", self.css)
        self.assertIsNotNone(rule)
        self.assertIn("background:var(--panel)", rule.group(1))

    def test_all_card_text_tokens_have_normal_text_contrast_in_both_themes(self):
        for theme in ("light", "dark"):
            rule = re.search(r'html\[data-theme="' + theme + r'"\]\{([^}]+)\}', self.css)
            tokens = dict(re.findall(r"(--[\w-]+):([^;]+)", rule.group(1)))
            background = luminance(tokens["--panel-solid"])
            for name in ("--ink", "--muted", "--blue"):
                foreground = luminance(tokens[name])
                ratio = (max(foreground, background) + 0.05) / (min(foreground, background) + 0.05)
                with self.subTest(theme=theme, token=name):
                    self.assertGreaterEqual(ratio, 4.5)
