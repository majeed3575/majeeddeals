import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXTENSION = ROOT / "browser-extension"


class ExtensionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        cls.popup_html = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        cls.popup_js = (EXTENSION / "popup.js").read_text(encoding="utf-8")

    def test_extension_uses_manifest_v3_and_minimal_permissions(self):
        self.assertEqual(self.manifest["manifest_version"], 3)
        self.assertEqual(set(self.manifest["permissions"]), {"activeTab", "scripting", "storage"})
        self.assertNotIn("<all_urls>", self.manifest.get("host_permissions", []))
        self.assertEqual(
            set(self.manifest.get("host_permissions", [])),
            {
                "*://*.amazon.sa/*",
                "*://*.aliexpress.com/*",
                "*://*.aliexpress.us/*",
                "https://api.github.com/*",
                "https://raw.githubusercontent.com/*",
            },
        )

    def test_extension_has_no_remote_or_inline_script_execution(self):
        self.assertIn('<script src="popup.js"></script>', self.popup_html)
        self.assertNotRegex(self.popup_html, r"<script[^>]+src=[\"']https?://")
        self.assertNotRegex(self.popup_html, r"\son[a-z]+\s*=")
        self.assertNotIn("eval(", self.popup_js)
        self.assertNotIn("new Function", self.popup_js)
        self.assertNotIn("document.write", self.popup_js)

    def test_github_token_is_local_only_and_never_logged(self):
        self.assertIn("chrome.storage.local", self.popup_js)
        self.assertIn("storageRemove(TOKEN_KEY)", self.popup_js)
        self.assertNotRegex(self.popup_js, r"console\.(?:log|info|debug|warn|error)")
        token_literals = re.findall(
            r"(?:github_pat_[A-Za-z0-9_]{20,}|gh[oprsu]_[A-Za-z0-9]{20,})",
            self.popup_js,
            flags=re.I,
        )
        self.assertEqual(token_literals, [])


if __name__ == "__main__":
    unittest.main()
