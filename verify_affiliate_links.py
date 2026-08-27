#!/usr/bin/env python3
"""بوابة نشر تمنع الروابط التجارية غير التابعة أو التصنيفات المتباعدة."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
AFFILIATE_TAG = "faraj733-21"
CANONICAL_CATEGORIES = {
    "الإلكترونيات", "التنظيف والمنظفات", "الأزياء والأحذية", "المطبخ والأجهزة المنزلية",
    "الأثاث والديكور", "المنزل", "السيارة", "السفر", "الرحلات والبحر والتخييم",
    "الحدائق والزراعة", "الجمال والعناية", "الصحة والعناية", "البقالة والمشروبات",
    "الرياضة", "الأطفال", "الألعاب", "الحيوانات الأليفة", "الأدوات والهوايات",
    "الترفيه المنزلي", "المدرسة والقرطاسية", "الكتب والمكتب", "الساعات والمجوهرات",
    "تسوق متنوع",
}
CATEGORY_ALIASES = {
    "الموضة": "الأزياء والأحذية",
    "الحدائق": "الحدائق والزراعة",
    "البحر والصيد": "الرحلات والبحر والتخييم",
    "التخييم": "الرحلات والبحر والتخييم",
    "المدرسة والتعليم": "المدرسة والقرطاسية",
}


def is_aliexpress_affiliate_url(value: object) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return False
    if host == "s.click.aliexpress.com":
        return True
    if not (host == "aliexpress.com" or host.endswith(".aliexpress.com") or
            host == "aliexpress.us" or host.endswith(".aliexpress.us")):
        return False
    query = parse_qs(parsed.query)
    platform = str((query.get("aff_platform") or [""])[0]).lower()
    return bool(query.get("aff_fcid") and query.get("aff_trace_key") and "api" in platform)


def is_amazon_affiliate_url(value: object, asin: str = "") -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    query = parse_qs(parsed.query)
    path_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)", parsed.path, re.I)
    return bool(
        parsed.scheme == "https" and (host == "amazon.sa" or host.endswith(".amazon.sa")) and
        path_match and (not asin or path_match.group(1).upper() == asin.upper()) and
        AFFILIATE_TAG in query.get("tag", [])
    )


class ShopLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        if "shop-button" in str(values.get("class") or "").split():
            self.links.append(str(values.get("href") or ""))


def load_deals(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    deals = payload.get("deals") if isinstance(payload, dict) else None
    if not isinstance(deals, list):
        raise ValueError(f"{path.name}: deals ليست قائمة")
    return [item for item in deals if isinstance(item, dict)]


def verify_deal_files(errors: list[str]) -> int:
    checked = 0
    for name in ("deals.json", "deals-initial.json"):
        path = ROOT / name
        if not path.exists():
            continue
        try:
            deals = load_deals(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            continue
        for index, deal in enumerate(deals, 1):
            checked += 1
            store = "aliexpress" if str(deal.get("store", "amazon")).lower() == "aliexpress" else "amazon"
            identity = str(deal.get("product_id") if store == "aliexpress" else deal.get("asin") or "")
            raw_category = str(deal.get("category") or "")
            category = CATEGORY_ALIASES.get(raw_category, raw_category)
            if category not in CANONICAL_CATEGORIES:
                errors.append(f"{name}[{index}] {identity}: تصنيف غير موحد: {deal.get('category')!r}")
            if store == "aliexpress" and not is_aliexpress_affiliate_url(deal.get("url")):
                errors.append(f"{name}[{index}] {identity}: رابط AliExpress غير تابع")
            if store == "amazon" and not re.fullmatch(r"[A-Z0-9]{10}", identity):
                errors.append(f"{name}[{index}]: ASIN غير صحيح")
    return checked


def verify_product_pages(errors: list[str]) -> int:
    checked = 0
    for page in sorted((ROOT / "products").glob("*/index.html")):
        directory = page.parent.name
        if not (directory.startswith("amazon-") or directory.startswith("aliexpress-")):
            continue
        parser = ShopLinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        checked += 1
        if len(parser.links) != 1:
            errors.append(f"{page.relative_to(ROOT)}: يجب وجود زر متجر واحد؛ الموجود {len(parser.links)}")
            continue
        link = parser.links[0]
        if directory.startswith("amazon-"):
            asin = directory.removeprefix("amazon-").upper()
            if not is_amazon_affiliate_url(link, asin):
                errors.append(f"{page.relative_to(ROOT)}: رابط Amazon بلا وسم العمولة الصحيح")
        elif not is_aliexpress_affiliate_url(link):
            errors.append(f"{page.relative_to(ROOT)}: رابط AliExpress غير تابع")
    return checked


def main() -> int:
    errors: list[str] = []
    deals_checked = verify_deal_files(errors)
    pages_checked = verify_product_pages(errors)
    if errors:
        print("[affiliate-verify] فشل التحقق:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"[affiliate-verify] OK — {deals_checked} سجل و{pages_checked} صفحة؛ كل روابط المتاجر التابعة سليمة")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
