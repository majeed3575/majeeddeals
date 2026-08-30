#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فحوصات محلية سريعة لطبقة SEO قبل أن يدفعها GitHub Actions."""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
BASE_URL = (os.environ.get("OVERLY_SITE_URL") or "https://overly.live/").strip().rstrip("/") + "/"
BASE_PATH = urlparse(BASE_URL).path or "/"
MERCHANT_DOMAINS = ("amazon.sa", "aliexpress.com", "aliexpress.us")
LEGACY_CATEGORY_REDIRECTS = {
    "categories/camping/": "categories/outdoors/",
    "categories/camping/page/2/": "categories/outdoors/",
    "categories/sea-fishing/": "categories/outdoors/",
    "categories/sea-fishing/page/2/": "categories/outdoors/",
    "categories/school-education/": "categories/school-stationery/",
}
errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"JSON غير صالح: {path.relative_to(ROOT)} ({exc})")
        return {}


def local_target(href: str) -> Path | None:
    if href == BASE_PATH or href == BASE_URL:
        return ROOT / "index.html"
    if href.startswith(BASE_URL):
        relative = href[len(BASE_URL):]
    elif href.startswith(BASE_PATH):
        relative = href[len(BASE_PATH):]
    else:
        return None
    relative = relative.split("?", 1)[0].split("#", 1)[0]
    if not relative:
        return ROOT / "index.html"
    target = ROOT / relative
    return target / "index.html" if relative.endswith("/") else target


class PageAudit(HTMLParser):
    def __init__(self, path: Path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.has_h1 = False
        self.has_title = False
        self.has_description = False
        self.canonical = ""
        self.json_scripts: list[str] = []
        self._json_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_list}
        if tag == "html" and (attrs.get("lang") != "ar" or attrs.get("dir") != "rtl"):
            fail(f"lang/dir غير صحيح: {self.path.relative_to(ROOT)}")
        if tag == "h1":
            self.has_h1 = True
        if tag == "title":
            self.has_title = True
        if tag == "meta" and attrs.get("name") == "description" and attrs.get("content", "").strip():
            self.has_description = True
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href", "")
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._json_parts = []
        if tag == "a":
            href = attrs.get("href", "")
            parsed = urlparse(href)
            host = (parsed.hostname or "").lower()
            if any(host == domain or host.endswith("." + domain) for domain in MERCHANT_DOMAINS):
                rel = set(attrs.get("rel", "").split())
                if "sponsored" not in rel or "noopener" not in rel or "noreferrer" not in rel:
                    fail(f"رابط متجر بلا sponsored/noopener/noreferrer: {self.path.relative_to(ROOT)}")
            target = local_target(href)
            if target and not target.exists():
                fail(f"رابط داخلي مكسور في {self.path.relative_to(ROOT)}: {href}")
        if tag == "img" and not attrs.get("alt", "").strip():
            fail(f"صورة بلا alt: {self.path.relative_to(ROOT)}")

    def handle_data(self, data: str) -> None:
        if self._json_parts is not None:
            self._json_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._json_parts is not None:
            self.json_scripts.append("".join(self._json_parts))
            self._json_parts = None


def audit_html(path: Path) -> None:
    parser = PageAudit(path)
    try:
        parser.feed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        fail(f"تعذر قراءة HTML: {path.relative_to(ROOT)} ({exc})")
        return
    relative = path.relative_to(ROOT).as_posix()
    if relative != "aliexpress-callback.html":
        if not parser.has_h1:
            fail(f"لا يوجد H1: {relative}")
        if not parser.has_title:
            fail(f"لا يوجد title: {relative}")
        if not parser.has_description:
            fail(f"لا يوجد meta description: {relative}")
        if not parser.canonical:
            fail(f"لا يوجد canonical: {relative}")
    for raw in parser.json_scripts:
        try:
            schema = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(f"JSON-LD غير صالح في {relative}: {exc}")
            continue
        if schema.get("@type") == "Product":
            if "offers" in schema:
                fail(f"Product schema يحتوي سعراً غير مطلوب: {relative}")
            if "aggregateRating" in schema or "review" in schema:
                fail(f"Product schema يحتوي تقييماً غير موثق: {relative}")


def main() -> int:
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    expected_h1 = '<h1 id="introTitle">كل زاوية<br><span>تكشف احتمالًا.</span></h1>'
    if expected_h1 not in index:
        fail("عنوان مشهد الاكتشاف الرئيسي تغير")
    if "deals-initial.json" not in index or "requestIdleCallback" not in index:
        fail("التحميل الأولي/الخلفي غير مفعّل في الصفحة الرئيسية")
    if "deals.json?v=${Date.now()}" in index or "const dealsEndpoint" in index:
        fail("ما زال تحميل deals.json القديم المعطل للكاش موجوداً")
    if 'rel="noopener noreferrer"' in index:
        fail("يوجد رابط عمولة في index.html بلا وسم sponsored")
    if '"@type":"Organization"' not in index or '"@type":"WebSite"' not in index:
        fail("بيانات Organization/WebSite المنظمة ناقصة")

    initial = read_json(ROOT / "deals-initial.json")
    initial_deals = initial.get("deals", []) if isinstance(initial, dict) else []
    if not isinstance(initial_deals, list) or len(initial_deals) > 72:
        fail("deals-initial.json يجب ألا يتجاوز 72 منتجاً")
    if int(initial.get("total_count", 0) or 0) < len(initial_deals):
        fail("total_count أصغر من القائمة الأولية")

    report = read_json(ROOT / "seo-report.json")
    manifest = read_json(ROOT / "seo-generated-files.json")
    generated = manifest.get("files", []) if isinstance(manifest, dict) else []
    for relative in generated:
        if not (ROOT / relative).exists():
            fail(f"ملف مذكور في manifest لكنه مفقود: {relative}")

    try:
        root = ET.parse(ROOT / "sitemap.xml").getroot()
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = [node.text or "" for node in root.findall("s:url/s:loc", namespace)]
        if len(urls) != len(set(urls)):
            fail("Sitemap يحتوي روابط مكررة")
        if len(urls) != int(report.get("sitemap_urls", -1)):
            fail("عدد روابط Sitemap لا يطابق تقرير البناء")
        for url in urls:
            target = local_target(url)
            if target and not target.exists():
                fail(f"Sitemap يشير إلى ملف مفقود: {url}")
        for old_relative in LEGACY_CATEGORY_REDIRECTS:
            if BASE_URL + old_relative in urls:
                fail(f"Sitemap يجب ألا يحتوي رابط التحويل القديم: {old_relative}")
    except (OSError, ET.ParseError) as exc:
        fail(f"Sitemap غير صالح: {exc}")

    for old_relative, target_relative in LEGACY_CATEGORY_REDIRECTS.items():
        redirect_path = ROOT / old_relative / "index.html"
        if not redirect_path.exists():
            fail(f"صفحة التحويل القديمة مفقودة: {old_relative}")
            continue
        redirect_html = redirect_path.read_text(encoding="utf-8")
        if f'rel="canonical" href="{BASE_URL + target_relative}"' not in redirect_html:
            fail(f"canonical التحويل غير صحيح: {old_relative}")
        if 'name="robots" content="noindex,follow"' not in redirect_html:
            fail(f"صفحة التحويل قابلة للفهرسة خطأً: {old_relative}")
        if BASE_URL + target_relative not in redirect_html:
            fail(f"هدف التحويل غير موجود داخل الصفحة: {old_relative}")

    html_files = [ROOT / relative for relative in generated if relative.endswith(".html")]
    html_files.append(ROOT / "index.html")
    for path in html_files:
        audit_html(path)

    workflow = (ROOT / ".github/workflows/scraper.yml").read_text(encoding="utf-8")
    if "python generate_seo.py" not in workflow:
        fail("GitHub Actions لا يشغّل مولّد SEO")
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if BASE_URL + "sitemap.xml" not in robots:
        fail("robots.txt لا يشير إلى Sitemap")
    for optimized, original in (
        ("assets/overly-dark-logo-trimmed.webp", "assets/overly-dark-logo-trimmed.png"),
        ("assets/overly-dark-chroma.webp", "assets/overly-dark-chroma.png"),
        ("assets/overly-icon.webp", "assets/overly-icon.png"),
    ):
        optimized_path, original_path = ROOT / optimized, ROOT / original
        if not optimized_path.exists():
            fail(f"الصورة المحسنة غير موجودة: {optimized}")
        elif original_path.exists() and optimized_path.stat().st_size >= original_path.stat().st_size:
            fail(f"الصورة المحسنة ليست أصغر من الأصل: {optimized}")

    if errors:
        print("[seo-check] FAILED")
        for error in errors:
            print(" - " + error)
        return 1
    print(
        f"[seo-check] OK | products={report.get('products', 0)} | "
        f"html={len(html_files)} | sitemap={report.get('sitemap_urls', 0)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
