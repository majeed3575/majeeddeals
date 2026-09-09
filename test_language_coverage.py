"""Source-level bilingual coverage, not a browser/visual test."""
import json
import re
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ['catalog-locale.js', 'catalog-additions.js', 'catalog-native-en.js', 'site-copy-en.js', 'legal-copy-en.js', 'site-extra-en.js', 'site-angles-en.js', 'site-phrases.js', 'locale.js']

class Copy(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.values = set()
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'code'}: self.skip += 1
        if not self.skip:
            self.values.update(v for k,v in attrs if k in {'alt','title','placeholder','aria-label'} and v)
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'code'}: self.skip = max(0, self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip(): self.values.add(re.sub(r'\s+', ' ', data).strip())

def page_copy():
    values = set()
    for path in (ROOT/'dist-site').rglob('*.html'):
        source = path.read_text()
        if 'http-equiv="refresh"' in source or path.name.startswith('google'): continue
        parser = Copy(); parser.feed(source); values.update(parser.values)
    return sorted(values)

def missing_copy():
    script = """
    const fs=require('fs'),vm=require('vm');
    for(const name of JSON.parse(process.argv[1]))vm.runInThisContext(fs.readFileSync(name,'utf8'),{filename:name});
    const api=createOverlyI18n();api.setLanguage('en');
    const values=JSON.parse(fs.readFileSync(0,'utf8'));
    console.log(JSON.stringify(values.filter(value=>/[\\u0600-\\u06ff]/.test(api.t(value).replace(/أوفرلي/g,'')))));
    """
    result = subprocess.run(['node','-e',script,json.dumps(SCRIPTS)],cwd=ROOT,input=json.dumps(page_copy()),text=True,capture_output=True,check=True)
    return json.loads(result.stdout)

class LanguageCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from build_public_site import build
        build()
    def test_all_published_copy_has_english(self):
        missing = missing_copy()
        self.assertEqual(missing, [], f'{len(missing)} untranslated strings: {missing[:8]}')
    def test_presentation_assets_on_every_content_page(self):
        for path in (ROOT/'dist-site').rglob('*.html'):
            source = path.read_text()
            if 'http-equiv="refresh"' in source or path.name.startswith('google'): continue
            for asset in ['site-boot.js','site-language.js','site-language.css','live-theme.css']:
                self.assertIn(asset,source,str(path))

if __name__ == '__main__':
    import sys
    if '--report' in sys.argv: print(json.dumps(missing_copy(),ensure_ascii=False,indent=2))
    else: unittest.main()
