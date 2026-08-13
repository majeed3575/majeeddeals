#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
صائد الخصومات السعودية — Amazon.sa Gold Box Scraper
====================================================
- Python 3.10+ / Requests / BeautifulSoup4
- مصمم للتشغيل Serverless عبر GitHub Actions كل 30 دقيقة
- يكتب deals.json بمخطط ثابت يستهلكه الواجهة الأمامية مباشرة

ملاحظة تشغيلية مهمة:
صفحة عروض أمازون تعتمد بكثافة على JavaScript وقد تحجب الطلبات الآلية.
السكربت يحاول 3 مسارات استخراج (JSON مضمّن → بطاقات data-asin → روابط /dp/)
وفي حال فشلها جميعاً يُبقي ملف العروض الحالي بلا مسح أو استبدال.
البديل الرسمي والأكثر استقراراً هو Amazon Creators API (خلَف PA-API المتوقفة منذ مايو 2026).
عند ضبط مفاتيح Creators API (كـ GitHub Secrets) يتحوّل السكربت تلقائياً للتحديث الحيّ عبرها.
كما يدعم AliExpress Affiliates API عند إضافة مفاتيحه وقائمة المنتجات المتابَعة.
"""

from __future__ import annotations

import json
import hashlib
import math
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# الإعدادات العامة
# ----------------------------------------------------------------------------
DEALS_URL = "https://www.amazon.sa/gp/goldbox"
OUTPUT_PATH = Path(__file__).resolve().parent / "deals.json"
MAX_DEALS = 24
REQUEST_TIMEOUT = 25
RETRIES = 3

# ----------------------------------------------------------------------------
# إعدادات تيليجرام
# ----------------------------------------------------------------------------
AFFILIATE_TAG = "faraj733-21"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "").strip()
MIN_DISCOUNT_TO_POST = 30          # ينشر فقط العروض ذات خصم 30٪ فأكثر
MAX_POSTS_PER_RUN = 5              # حد أقصى للمنشورات في كل تشغيلة (يحمي من السبام/الحظر)
REPOST_COOLDOWN_HOURS = 48        # لا يعيد نشر نفس المنتج خلال هذه المدة
POSTED_STATE_PATH = Path(__file__).resolve().parent / "posted_deals.json"

# ----------------------------------------------------------------------------
# إعدادات Amazon Creators API — البديل الرسمي لـ PA-API (المتوقفة نهائياً)
# ----------------------------------------------------------------------------
# • المفاتيح تُضاف كـ GitHub Secrets، ولا تُكتب داخل الكود إطلاقاً.
# • السعودية تتبع منطقة أوروبا (EU / Version 3.2): نقطة التوكن api.amazon.co.uk.
# • النداءات كلها على المضيف العالمي creatorsapi.amazon مع رأس x-marketplace.
# • الأسعار والخصومات تُجلب من OffersV2 (بيانات أمازون الرسمية — لا مقارنات مُختلَقة).
CREATORS_CLIENT_ID = os.environ.get("CREATORS_CLIENT_ID", "").strip()
CREATORS_CLIENT_SECRET = os.environ.get("CREATORS_CLIENT_SECRET", "").strip()
# نستخدم (env or default) بدل get(key, default) حتى لا تُلغي قيمة فارغة الافتراضيَّ.
CREATORS_TOKEN_ENDPOINT = (
    os.environ.get("CREATORS_TOKEN_ENDPOINT") or "https://api.amazon.co.uk/auth/o2/token"
).strip()
CREATORS_API_HOST = "https://creatorsapi.amazon"
CREATORS_MARKETPLACE = (os.environ.get("CREATORS_MARKETPLACE") or "www.amazon.sa").strip()
CREATORS_SCOPE = (os.environ.get("CREATORS_SCOPE") or "creatorsapi::default").strip()
CREATORS_LANGUAGE = os.environ.get("CREATORS_LANGUAGE", "ar_AE").strip()
CREATORS_RESOURCES = [
    "itemInfo.title",
    "images.primary.large",
    "offersV2.listings.price",
]
WATCHLIST_PATH = Path(__file__).resolve().parent / "asins.json"
# مُفعَّل تلقائياً فقط عند وجود المفتاحين — وإلا يعود السكربت للجمع من HTML.
CREATORS_ENABLED = bool(CREATORS_CLIENT_ID and CREATORS_CLIENT_SECRET)

# ----------------------------------------------------------------------------
# إعدادات AliExpress Affiliates API
# ----------------------------------------------------------------------------
# لا تُكتب المفاتيح في المستودع؛ تُمرّر من GitHub Actions Secrets فقط.
# نستخدم بوابة HTTPS مباشرة، ونوقّع الطلبات محلياً بخوارزمية Open Platform.
ALIEXPRESS_APP_KEY = os.environ.get("ALIEXPRESS_APP_KEY", "").strip()
ALIEXPRESS_APP_SECRET = os.environ.get("ALIEXPRESS_APP_SECRET", "").strip()
ALIEXPRESS_TRACKING_ID = os.environ.get("ALIEXPRESS_TRACKING_ID", "").strip()
ALIEXPRESS_API_ENDPOINT = (
    os.environ.get("ALIEXPRESS_API_ENDPOINT") or "https://api-sg.aliexpress.com/sync"
).strip()
ALIEXPRESS_TARGET_CURRENCY = (
    os.environ.get("ALIEXPRESS_TARGET_CURRENCY") or "USD"
).strip().upper()
ALIEXPRESS_TARGET_LANGUAGE = (
    os.environ.get("ALIEXPRESS_TARGET_LANGUAGE") or "AR"
).strip().upper()
ALIEXPRESS_SHIP_TO_COUNTRY = (
    os.environ.get("ALIEXPRESS_SHIP_TO_COUNTRY") or "SA"
).strip().upper()
ALIEXPRESS_USD_TO_SAR = float(os.environ.get("ALIEXPRESS_USD_TO_SAR") or "3.75")
ALIEXPRESS_WATCHLIST_PATH = Path(__file__).resolve().parent / "aliexpress_products.json"
ALIEXPRESS_ENABLED = bool(
    ALIEXPRESS_APP_KEY and ALIEXPRESS_APP_SECRET and ALIEXPRESS_TRACKING_ID
)
ALIEXPRESS_AUTO_DISCOVERY = (
    os.environ.get("ALIEXPRESS_AUTO_DISCOVERY") or "true"
).strip().lower() in {"1", "true", "yes", "on"}
ALIEXPRESS_AUTO_LIMIT = max(
    1, min(20, int(os.environ.get("ALIEXPRESS_AUTO_LIMIT") or "12"))
)
ALIEXPRESS_AUTO_MIN_DISCOUNT = max(
    5, min(95, int(os.environ.get("ALIEXPRESS_AUTO_MIN_DISCOUNT") or "20"))
)
ALIEXPRESS_AUTO_MIN_VOLUME = max(
    0, int(os.environ.get("ALIEXPRESS_AUTO_MIN_VOLUME") or "50")
)
ALIEXPRESS_AUTO_MIN_RATING = max(
    0, min(100, int(os.environ.get("ALIEXPRESS_AUTO_MIN_RATING") or "90"))
)
# الاكتشاف الموجّه هو الوضع الافتراضي: يمنع امتلاء الموقع بمنتجات عامة عشوائية.
ALIEXPRESS_FOCUS_DISCOVERY = (
    os.environ.get("ALIEXPRESS_FOCUS_DISCOVERY") or "true"
).strip().lower() in {"1", "true", "yes", "on"}
ALIEXPRESS_FOCUS_QUERIES = [
    ("tech", "usb c hub", "الإلكترونيات"),
    ("tech", "wireless charger", "الإلكترونيات"),
    ("tech", "smart home gadget", "الإلكترونيات"),
    ("tech", "computer accessories", "الإلكترونيات"),
    ("life_hack", "home organizer", "المنزل"),
    ("life_hack", "kitchen gadget", "المنزل"),
    ("life_hack", "cleaning tool", "المنزل"),
    ("life_hack", "travel organizer", "المنزل"),
]
ALIEXPRESS_FOCUS_TERMS = {
    "tech": {
        "usb", "شاحن", "شحن", "لاسلكي", "هاتف", "جوال", "ذكي", "بلوتوث",
        "كمبيوتر", "حاسوب", "لابتوب", "محول", "محوّل", "كابل", "كيبل",
        "سماعة", "لوحة", "فأرة", "ماوس", "hub", "charger", "wireless",
        "computer", "phone", "smart", "bluetooth", "adapter", "cable",
    },
    "life_hack": {
        "منظم", "منظّم", "تنظيم", "تخزين", "مطبخ", "تنظيف", "فرشاة", "حامل",
        "رف", "صندوق", "أداة", "اداة", "سفر", "حقيبة", "موزع", "قاطع",
        "organizer", "storage", "kitchen", "cleaning", "brush", "holder",
        "travel", "gadget", "tool", "rack", "dispenser",
    },
}
ALIEXPRESS_ID_RE = re.compile(r"(?<!\d)(\d{6,20})(?!\d)")

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
DP_LINK_RE = re.compile(r"/dp/([A-Z0-9]{10})")
DISCOUNT_RE = re.compile(r"(\d{1,2})\s*%")
PRICE_RE = re.compile(r"([\d,]+(?:\.\d+)?)")

# تدوير ترويسات لمحاكاة طلبات متصفح حقيقية
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def build_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar-SA,ar;q=0.9,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
    }


# تصنيف تقريبي بالكلمات المفتاحية (عربي/إنجليزي)
CATEGORY_KEYWORDS = {
    "الإلكترونيات": [
        "سماعة", "سماعات", "شاحن", "كيبل", "كابل", "لابتوب", "حاسوب", "جوال",
        "هاتف", "ساعة ذكية", "شاشة", "كاميرا", "باور بانك", "تابلت",
        "headphone", "earbud", "charger", "laptop", "phone", "watch", "camera",
        "monitor", "tablet", "usb", "ssd", "speaker",
    ],
    "المنزل": [
        "مقلاة", "قلاية", "مكنسة", "خلاط", "قهوة", "مطبخ", "غسالة", "مكواة",
        "سرير", "وسادة", "إضاءة", "مصباح", "تنظيف", "ثلاجة",
        "kitchen", "vacuum", "blender", "coffee", "fryer", "pillow", "lamp",
        "cleaner", "cookware",
    ],
    "الموضة": [
        "حقيبة", "حذاء", "قميص", "عباية", "فستان", "نظارة", "عطر", "ساعة يد",
        "ملابس", "جاكيت",
        "bag", "shoe", "shirt", "dress", "sunglasses", "perfume", "jacket",
        "backpack", "wallet",
    ],
}


def classify(title: str) -> str:
    low = title.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in low for w in words):
            return cat
    return "الإلكترونيات"


# ----------------------------------------------------------------------------
# التنظيف والتحقق البنيوي (Data Sanitation)
# ----------------------------------------------------------------------------
def sanitize(raw: dict) -> dict | None:
    """يعيد سجلاً نظيفاً بالمخطط الموحد أو None إذا كان السجل تالفاً."""
    asin = str(raw.get("asin", "")).strip().upper()
    if not ASIN_RE.match(asin):
        return None

    title = re.sub(r"\s+", " ", str(raw.get("title", "")).strip())
    if len(title) < 8:
        return None
    title = title[:140]

    image = str(raw.get("image", "")).strip()
    if not image.startswith("https://"):
        return None

    try:
        discount = int(raw.get("discount_percent", 0))
    except (TypeError, ValueError):
        return None
    if not (5 <= discount <= 95):
        return None

    try:
        price = float(raw.get("original_price", 0))
    except (TypeError, ValueError):
        price = 0
    if price <= 0:
        return None

    return {
        "store": "amazon",
        "asin": asin,
        "title": title,
        "image": image,
        "discount_percent": discount,
        "original_price": round(price),
        "category": raw.get("category") or classify(title),
    }


# ----------------------------------------------------------------------------
# مسارات الاستخراج
# ----------------------------------------------------------------------------
def fetch_page() -> str | None:
    session = requests.Session()
    for attempt in range(1, RETRIES + 1):
        try:
            resp = session.get(DEALS_URL, headers=build_headers(), timeout=REQUEST_TIMEOUT)
            print(f"[fetch] attempt {attempt}: HTTP {resp.status_code}, {len(resp.text)} bytes")
            if resp.status_code == 200 and "captcha" not in resp.text.lower():
                return resp.text
        except requests.RequestException as exc:
            print(f"[fetch] attempt {attempt} failed: {exc}")
        time.sleep(2 * attempt + random.random())
    return None


def extract_from_embedded_json(html: str) -> list[dict]:
    """أمازون تضمّن بيانات العروض داخل كتل JSON في السكربتات."""
    out = []
    for match in re.finditer(
        r'\{[^{}]*"impressionAsin"\s*:\s*"([A-Z0-9]{10})"[^{}]*\}', html
    ):
        out.append({"asin": match.group(1)})
    # نمط بديل شائع
    for match in re.finditer(r'"asin"\s*:\s*"([A-Z0-9]{10})"', html):
        out.append({"asin": match.group(1)})
    return out


def extract_from_cards(soup: BeautifulSoup) -> list[dict]:
    """بطاقات تحمل data-asin مع صورة وعنوان ونسبة خصم."""
    deals = []
    for card in soup.select("[data-asin]"):
        asin = (card.get("data-asin") or "").strip().upper()
        if not ASIN_RE.match(asin):
            continue

        img = card.select_one("img")
        image = (img.get("src") or img.get("data-src") or "") if img else ""
        title = (img.get("alt") or "").strip() if img else ""
        if not title:
            t = card.select_one("[class*=title], h2, h3")
            title = t.get_text(strip=True) if t else ""

        text = card.get_text(" ", strip=True)
        m_disc = DISCOUNT_RE.search(text)
        discount = int(m_disc.group(1)) if m_disc else 0

        price = 0.0
        strike = card.select_one(".a-text-price, [class*=strike], del, s")
        if strike:
            m_price = PRICE_RE.search(strike.get_text())
            if m_price:
                price = float(m_price.group(1).replace(",", ""))

        deals.append(
            {
                "asin": asin,
                "title": title,
                "image": image,
                "discount_percent": discount,
                "original_price": price,
            }
        )
    return deals


def extract_from_links(soup: BeautifulSoup) -> list[dict]:
    """خط دفاع أخير: أي روابط /dp/ في الصفحة."""
    deals = []
    for a in soup.select('a[href*="/dp/"]'):
        m = DP_LINK_RE.search(a.get("href", ""))
        if not m:
            continue
        img = a.select_one("img")
        deals.append(
            {
                "asin": m.group(1),
                "title": (img.get("alt") if img else a.get_text(strip=True)) or "",
                "image": (img.get("src") or img.get("data-src") or "") if img else "",
                "discount_percent": 0,
                "original_price": 0,
            }
        )
    return deals


def scrape() -> list[dict]:
    html = fetch_page()
    if not html:
        print("[scrape] page fetch failed on all attempts")
        return []

    soup = BeautifulSoup(html, "html.parser")

    candidates = extract_from_cards(soup)
    print(f"[scrape] card extractor: {len(candidates)} candidates")

    if not candidates:
        candidates = extract_from_links(soup)
        print(f"[scrape] link extractor: {len(candidates)} candidates")

    # دمج أي ASINs إضافية من JSON المضمّن (بدون تفاصيل كاملة ستُرفض في sanitize،
    # لكنها مفيدة لرصد التغطية في اللوقات)
    embedded = extract_from_embedded_json(html)
    print(f"[scrape] embedded-json extractor: {len(embedded)} asin refs")

    clean, seen = [], set()
    for raw in candidates:
        item = sanitize(raw)
        if item and item["asin"] not in seen:
            seen.add(item["asin"])
            clean.append(item)
        if len(clean) >= MAX_DEALS:
            break

    # الأعلى خصماً أولاً
    clean.sort(key=lambda d: d["discount_percent"], reverse=True)
    return clean


# ----------------------------------------------------------------------------
# مسار Amazon Creators API (التحديث الحيّ الرسمي)
# ----------------------------------------------------------------------------
def load_existing_deals() -> list[dict]:
    """يقرأ عروض deals.json الحالية (لبذر قائمة المتابعة والحفاظ على التصنيفات)."""
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        deals = data.get("deals", [])
        return deals if isinstance(deals, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def load_watchlist() -> list[str]:
    """قائمة الـ ASIN المتابَعة من asins.json (يديرها المالك).

    لو الملف غير موجود، تُبذَر تلقائياً من ASINs العروض الحالية في deals.json
    وتُحفَظ. هذا يجعل الاختيار البشري دائماً بينما يتكفّل الـ API بتحديث الأسعار.
    """
    try:
        data = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        asins = data if isinstance(data, list) else data.get("asins", [])
    except (FileNotFoundError, json.JSONDecodeError):
        asins = []

    if not asins:
        asins = [d.get("asin") for d in load_existing_deals() if d.get("asin")]
        if asins:
            WATCHLIST_PATH.write_text(
                json.dumps(asins, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"[watchlist] بُذرت asins.json بـ {len(asins)} منتج من deals.json")

    seen, clean = set(), []
    for a in asins:
        a = str(a).strip().upper()
        if ASIN_RE.match(a) and a not in seen:
            seen.add(a)
            clean.append(a)
    return clean


def creators_get_token() -> str | None:
    """يجلب توكن OAuth2 (client_credentials) صالحاً لساعة. يعيد None عند الفشل."""
    body = {
        "grant_type": "client_credentials",
        "client_id": CREATORS_CLIENT_ID,
        "client_secret": CREATORS_CLIENT_SECRET,
        "scope": CREATORS_SCOPE,
    }
    try:
        resp = requests.post(
            CREATORS_TOKEN_ENDPOINT,
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            print(f"[creators] فشل التوكن HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        token = resp.json().get("access_token")
        if not token:
            print("[creators] استجابة التوكن بلا access_token")
        return token
    except (requests.RequestException, ValueError) as exc:
        print(f"[creators] خطأ التوكن: {exc}")
        return None


def creators_get_items(asins: list[str], token: str) -> list[dict]:
    """يستدعي getItems على دفعات (≤10 ASIN للدفعة) ويجمع عناصر الاستجابة."""
    items: list[dict] = []
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-marketplace": CREATORS_MARKETPLACE,
    }
    url = f"{CREATORS_API_HOST}/catalog/v1/getItems"

    for start in range(0, len(asins), 10):
        batch = asins[start:start + 10]
        body = {
            "itemIds": batch,
            "itemIdType": "ASIN",
            "marketplace": CREATORS_MARKETPLACE,
            "partnerTag": AFFILIATE_TAG,
            "resources": CREATORS_RESOURCES,
        }
        if CREATORS_LANGUAGE:
            body["languagesOfPreference"] = [CREATORS_LANGUAGE]

        try:
            resp = requests.post(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                print(f"[creators] getItems HTTP {resp.status_code}: {resp.text[:200]}")
                continue
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[creators] خطأ getItems: {exc}")
            continue

        # حاويتان محتملتان حسب توثيق أمازون: itemResults أو itemsResult
        container = data.get("itemResults") or data.get("itemsResult") or {}
        batch_items = container.get("items", []) or []
        print(f"[creators] الدفعة {start // 10 + 1}: {len(batch_items)} عنصر")
        for err in (data.get("errors") or []):
            print(f"[creators] عنصر مرفوض: {err.get('code')} — {err.get('message')}")
        items.extend(batch_items)
        time.sleep(1)  # احترام حدود المعدل

    return items


def _money_amount(node: dict) -> float:
    """يستخرج المبلغ الرقمي من بنية Money في OffersV2 (money.amount)."""
    try:
        return float(node["money"]["amount"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def map_creators_item(item: dict, category_map: dict) -> dict | None:
    """يحوّل عنصر Creators API إلى المخطط الموحّد ثم يمرّره عبر sanitize()."""
    asin = str(item.get("asin", "")).strip().upper()

    title = ""
    try:
        title = item["itemInfo"]["title"]["displayValue"]
    except (KeyError, TypeError):
        pass

    image = ""
    for size in ("large", "medium", "small"):
        try:
            candidate = item["images"]["primary"][size]["url"]
            if candidate:
                image = candidate
                break
        except (KeyError, TypeError):
            continue

    # OffersV2 → السعر قبل الخصم (savingBasis) ونسبة الخصم (savings.percentage)
    original_price = 0.0
    discount = 0
    try:
        listing = item["offersV2"]["listings"][0]
        price_node = listing.get("price", {}) or {}
        current = _money_amount(price_node)
        basis = _money_amount(price_node.get("savingBasis", {}) or {})
        pct = (price_node.get("savings", {}) or {}).get("percentage")
        if basis > 0:
            original_price = basis
        if pct is not None:
            discount = int(round(float(pct)))
        elif basis > 0 and current > 0 and basis > current:
            discount = int(round((basis - current) / basis * 100))
    except (KeyError, TypeError, IndexError):
        pass

    return sanitize(
        {
            "asin": asin,
            "title": title,
            "image": image,
            "discount_percent": discount,
            "original_price": original_price,
            # حافظ على التصنيف اليدوي للمالك إن وُجد، وإلا صنّف تلقائياً
            "category": category_map.get(asin),
        }
    )


def scrape_creators() -> list[dict]:
    """يحدّث بيانات منتجات قائمة المتابعة حيّاً عبر Creators API.

    يخرج فقط المنتجات التي عليها خصم فعلي الآن (يمرّها sanitize)، فتظهر العروض
    وتختفي طبيعياً حسب توفّرها على أمازون — مع بقاء قائمة المتابعة ثابتة.
    """
    asins = load_watchlist()
    if not asins:
        print("[creators] قائمة المتابعة فارغة — لا شيء لتحديثه")
        return []
    print(f"[creators] تحديث {len(asins)} منتج عبر Creators API")

    token = creators_get_token()
    if not token:
        print("[creators] تعذّر الحصول على التوكن — إلغاء التحديث (تُحفظ العروض الحالية)")
        return []

    category_map = {
        d.get("asin"): d.get("category")
        for d in load_existing_deals()
        if d.get("asin")
    }

    raw_items = creators_get_items(asins, token)
    clean, seen = [], set()
    for it in raw_items:
        deal = map_creators_item(it, category_map)
        if deal and deal["asin"] not in seen:
            seen.add(deal["asin"])
            clean.append(deal)

    clean.sort(key=lambda d: d["discount_percent"], reverse=True)
    clean = clean[:MAX_DEALS]
    print(f"[creators] {len(clean)} عرض حيّ بعد التنظيف (خصم فعلي فقط)")
    return clean


# ----------------------------------------------------------------------------
# مسار AliExpress Affiliates API
# ----------------------------------------------------------------------------
def _ali_product_id(value: object) -> str:
    """يستخرج رقم منتج AliExpress من رقم أو رابط."""
    match = ALIEXPRESS_ID_RE.search(str(value or ""))
    return match.group(1) if match else ""


def load_aliexpress_watchlist() -> list[dict]:
    """يقرأ قائمة منتجات AliExpress، ويبذرها من deals.json إن كانت فارغة.

    الصيغ المقبولة داخل aliexpress_products.json:
    - رابط أو رقم منتج كنص.
    - كائن يحوي product_id أو url، وتصنيفاً اختيارياً.
    """
    try:
        data = json.loads(ALIEXPRESS_WATCHLIST_PATH.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("products", [])
    except (FileNotFoundError, json.JSONDecodeError):
        entries = []

    if not entries:
        entries = [
            {
                "product_id": deal.get("product_id"),
                "url": deal.get("url"),
                "category": deal.get("category"),
            }
            for deal in load_existing_deals()
            if str(deal.get("store", "")).lower() == "aliexpress"
        ]
        if entries:
            ALIEXPRESS_WATCHLIST_PATH.write_text(
                json.dumps({"products": entries}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"[aliexpress] بُذرت aliexpress_products.json بـ {len(entries)} منتج"
            )

    clean: list[dict] = []
    seen: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict):
            product_id = _ali_product_id(entry.get("product_id") or entry.get("url"))
            category = entry.get("category")
        else:
            product_id = _ali_product_id(entry)
            category = None
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        clean.append(
            {
                "product_id": product_id,
                "url": f"https://www.aliexpress.com/item/{product_id}.html",
                "category": category if category in CATEGORY_KEYWORDS else None,
            }
        )
    return clean


def _ali_sign(parameters: dict[str, object]) -> str:
    """توقيع Open Platform: MD5(secret + sorted key/value + secret)."""
    canonical = "".join(
        f"{key}{parameters[key]}"
        for key in sorted(parameters)
        if parameters[key] is not None
    )
    value = f"{ALIEXPRESS_APP_SECRET}{canonical}{ALIEXPRESS_APP_SECRET}"
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


def aliexpress_api_call(method: str, parameters: dict) -> dict | None:
    """ينفّذ نداءً موقّعاً عبر HTTPS ولا يسجل المفاتيح أو التوقيع في السجل."""
    application = {
        key: str(value)
        for key, value in parameters.items()
        if value is not None and value != ""
    }
    system = {
        "app_key": ALIEXPRESS_APP_KEY,
        "format": "json",
        "method": method,
        "sign_method": "md5",
        "timestamp": str(int(time.time() * 1000)),
        "v": "2.0",
    }
    sign_input = {**system, **application}
    system["sign"] = _ali_sign(sign_input)

    try:
        response = requests.post(
            ALIEXPRESS_API_ENDPOINT,
            params=system,
            data=application,
            headers={"Accept": "application/json", "User-Agent": "OverlyDeals/1.0"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            print(f"[aliexpress] {method} HTTP {response.status_code}")
            return None
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"[aliexpress] فشل {method}: {exc}")
        return None

    if "error_response" in payload:
        error = payload.get("error_response") or {}
        print(
            "[aliexpress] رفض النداء "
            f"{method}: {error.get('code')} — {error.get('msg') or error.get('sub_msg')}"
        )
        return None

    response_key = method.replace(".", "_") + "_response"
    envelope = payload.get(response_key) or {}
    result = envelope.get("resp_result") or {}
    if str(result.get("resp_code")) not in {"200", "200.0"}:
        print(
            f"[aliexpress] {method} resp_code={result.get('resp_code')} "
            f"— {result.get('resp_msg', 'استجابة غير ناجحة')}"
        )
        return None
    value = result.get("result")
    return value if isinstance(value, dict) else {}


def _ali_list(value: object, child_key: str) -> list[dict]:
    """يفك حاويات AliExpress التي قد تعيد كائناً واحداً أو قائمة."""
    if not isinstance(value, dict):
        return []
    items = value.get(child_key, [])
    if isinstance(items, dict):
        return [items]
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _ali_number(value: object) -> float:
    text = str(value or "").replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else 0.0


def _ali_discount(value: object) -> int:
    match = re.search(r"\d{1,2}", str(value or ""))
    return int(match.group(0)) if match else 0


def _ali_https_url(value: object) -> str:
    """يقبل روابط AliExpress الرسمية فقط، ويرقّي رابط العمولة من HTTP إلى HTTPS."""
    url = str(value or "").strip()
    if url.startswith("http://s.click.aliexpress.com/"):
        url = "https://" + url.removeprefix("http://")
    if not url.startswith("https://"):
        return ""
    host = (urlsplit(url).hostname or "").lower()
    if host == "aliexpress.com" or host.endswith(".aliexpress.com"):
        return url
    if host == "aliexpress.us" or host.endswith(".aliexpress.us"):
        return url
    return ""


def sanitize_aliexpress(raw: dict) -> dict | None:
    """يحوّل منتج AliExpress إلى مخطط الموقع ويعرض سعره قبل الخصم بالريال."""
    product_id = _ali_product_id(raw.get("product_id"))
    title = re.sub(r"\s+", " ", str(raw.get("title", "")).strip())[:140]
    image = str(raw.get("image", "")).strip()
    url = str(raw.get("url", "")).strip()
    currency = str(raw.get("currency", "")).strip().upper()

    if not product_id or len(title) < 8 or not image.startswith("https://"):
        return None
    if not url.startswith("https://"):
        return None
    if currency and currency not in {"SAR", "USD"}:
        print(
            f"[aliexpress] تجاهل {product_id}: العملة {currency} غير مدعومة"
        )
        return None

    original = _ali_number(raw.get("original_price"))
    current = _ali_number(raw.get("sale_price"))
    discount = _ali_discount(raw.get("discount_percent"))
    if not original and current > 0 and 5 <= discount <= 95:
        original = current / (1 - discount / 100)
    if not discount and original > current > 0:
        discount = round((original - current) / original * 100)
    if original <= 0 or not (5 <= discount <= 95):
        return None
    if currency == "USD":
        original *= ALIEXPRESS_USD_TO_SAR

    category = raw.get("category")
    return {
        "store": "aliexpress",
        "product_id": product_id,
        "url": url,
        "title": title,
        "image": image,
        "discount_percent": int(discount),
        "original_price": round(original, 2),
        "category": category if category in CATEGORY_KEYWORDS else classify(title),
        **({"auto_discovered": True} if raw.get("auto_discovered") else {}),
    }


def aliexpress_generate_links(source_urls: list[str]) -> dict[str, str]:
    """يولّد روابط العمولة الرسمية ويعيد {الرابط الأصلي: رابط العمولة}."""
    if not source_urls:
        return {}
    result = aliexpress_api_call(
        "aliexpress.affiliate.link.generate",
        {
            "promotion_link_type": 0,
            "source_values": ",".join(source_urls),
            "tracking_id": ALIEXPRESS_TRACKING_ID,
        },
    )
    links = _ali_list((result or {}).get("promotion_links"), "promotion_link")
    mapped: dict[str, str] = {}
    for item in links:
        source = str(item.get("source_value", ""))
        promotion = _ali_https_url(item.get("promotion_link"))
        if not promotion:
            continue
        if source.startswith("https://"):
            mapped[source] = promotion
        product_id = _ali_product_id(source)
        if product_id:
            mapped[product_id] = promotion
    return mapped


def _ali_title_tokens(title: object) -> set[str]:
    """كلمات قابلة للمقارنة لمنع نسخ المنتج المتشابهة جداً."""
    return {
        token
        for token in re.findall(r"[a-z0-9\u0600-\u06ff]+", str(title or "").lower())
        if len(token) >= 3
    }


def _ali_focus_score(product: dict, topic: str) -> float:
    """درجة تجمع الجودة والطلب والخصم ومدى ارتباط العنوان بالمجال."""
    discount = _ali_discount(product.get("discount"))
    volume = int(_ali_number(product.get("lastest_volume")))
    rating = _ali_number(product.get("evaluate_rate"))
    title_tokens = _ali_title_tokens(product.get("product_title"))
    relevant = len(title_tokens & ALIEXPRESS_FOCUS_TERMS.get(topic, set()))
    return round(
        rating * 0.9
        + discount * 1.25
        + min(math.log10(volume + 1) * 22, 88)
        + min(relevant, 4) * 8,
        2,
    )


def _ali_is_near_duplicate(title: object, selected: list[dict]) -> bool:
    """يمنع عرض عدة نسخ متشابهة جداً من المنتج نفسه."""
    tokens = _ali_title_tokens(title)
    if len(tokens) < 3:
        return False
    for item in selected:
        other = _ali_title_tokens(item.get("product_title"))
        if len(other) < 3:
            continue
        overlap = len(tokens & other) / min(len(tokens), len(other))
        if overlap >= 0.78:
            return True
    return False


def _ali_balanced_selection(candidates: list[dict], limit: int) -> list[dict]:
    """اختيار متوازن بين التقنية وLife Hacks مع تعبئة أي مقاعد شاغرة."""
    ranked = sorted(
        candidates,
        key=lambda item: float(item.get("_overly_score", 0)),
        reverse=True,
    )
    tech_quota = (limit + 1) // 2
    quotas = {"tech": tech_quota, "life_hack": limit - tech_quota}
    selected: list[dict] = []
    selected_ids: set[str] = set()

    for topic in ("tech", "life_hack"):
        for product in ranked:
            if len([item for item in selected if item.get("_overly_topic") == topic]) >= quotas[topic]:
                break
            product_id = _ali_product_id(product.get("product_id"))
            if product.get("_overly_topic") != topic or not product_id or product_id in selected_ids:
                continue
            if _ali_is_near_duplicate(product.get("product_title"), selected):
                continue
            selected.append(product)
            selected_ids.add(product_id)

    for product in ranked:
        if len(selected) >= limit:
            break
        product_id = _ali_product_id(product.get("product_id"))
        if not product_id or product_id in selected_ids:
            continue
        if _ali_is_near_duplicate(product.get("product_title"), selected):
            continue
        selected.append(product)
        selected_ids.add(product_id)
    return selected


def discover_aliexpress_products() -> list[dict]:
    """يكتشف منتجات تقنية وLife Hacks القابلة للشحن للسعودية.

    يستخدم product.query المتاحة للتطبيق، ويبحث بعبارات موضوعية مستقلة ثم يوازن
    النتائج بين المجالين. لا يدخل الموقع إلا المنتج ذو خصم ومبيعات وتقييم صالح.
    """
    fields = ",".join(
        [
            "product_id",
            "product_title",
            "product_main_image_url",
            "product_detail_url",
            "target_original_price",
            "target_original_price_currency",
            "target_sale_price",
            "target_sale_price_currency",
            "original_price",
            "original_price_currency",
            "sale_price",
            "sale_price_currency",
            "discount",
            "promotion_link",
            "evaluate_rate",
            "lastest_volume",
        ]
    )
    base_query = {
        "fields": fields,
        "page_no": 1,
        "page_size": 20,
        "platform_product_type": "ALL",
        "sort": "LAST_VOLUME_DESC",
        "target_currency": ALIEXPRESS_TARGET_CURRENCY,
        "target_language": ALIEXPRESS_TARGET_LANGUAGE,
        "tracking_id": ALIEXPRESS_TRACKING_ID,
        "ship_to_country": ALIEXPRESS_SHIP_TO_COUNTRY,
    }
    discovery_queries = (
        ALIEXPRESS_FOCUS_QUERIES
        if ALIEXPRESS_FOCUS_DISCOVERY
        else [("tech", "", "الإلكترونيات")]
    )
    candidates_by_id: dict[str, dict] = {}
    returned_count = 0
    for topic, keywords, category in discovery_queries:
        query = dict(base_query)
        if keywords:
            query["keywords"] = keywords
        result = aliexpress_api_call(
            "aliexpress.affiliate.product.query",
            query,
        )
        products = _ali_list((result or {}).get("products"), "product")
        returned_count += len(products)
        accepted_for_query = 0
        for product in products:
            product_id = _ali_product_id(product.get("product_id"))
            discount = _ali_discount(product.get("discount"))
            volume = int(_ali_number(product.get("lastest_volume")))
            rating = _ali_number(product.get("evaluate_rate"))
            if not product_id:
                continue
            if discount < ALIEXPRESS_AUTO_MIN_DISCOUNT:
                continue
            if volume < ALIEXPRESS_AUTO_MIN_VOLUME:
                continue
            # التقييم المفقود لم يعد يمر؛ الأفضل عرض عدد أقل بجودة موثوقة.
            if rating < ALIEXPRESS_AUTO_MIN_RATING:
                continue
            candidate = {
                **product,
                "auto_discovered": True,
                "_overly_topic": topic,
                "_overly_category": category,
            }
            candidate["_overly_score"] = _ali_focus_score(candidate, topic)
            previous = candidates_by_id.get(product_id)
            if previous is None or candidate["_overly_score"] > previous["_overly_score"]:
                candidates_by_id[product_id] = candidate
            accepted_for_query += 1
        label = "تقنية" if topic == "tech" else "Life Hacks"
        print(
            f"[aliexpress] {label} / {keywords or 'عام'}: "
            f"{accepted_for_query} من {len(products)} اجتاز الجودة"
        )
        time.sleep(0.35)

    accepted = _ali_balanced_selection(
        list(candidates_by_id.values()),
        ALIEXPRESS_AUTO_LIMIT,
    )
    tech_count = sum(item.get("_overly_topic") == "tech" for item in accepted)
    life_count = sum(item.get("_overly_topic") == "life_hack" for item in accepted)

    print(
        f"[aliexpress] اكتشاف موجّه: {len(accepted)} من {returned_count} نتيجة "
        f"(تقنية {tech_count}، Life Hacks {life_count})"
    )
    return accepted


def scrape_aliexpress() -> list[dict]:
    """يحدّث القائمة المختارة أو يكتشف الرائج آلياً، ثم يولّد روابط عمولة."""
    watchlist = load_aliexpress_watchlist()
    categories = {item["product_id"]: item.get("category") for item in watchlist}
    raw_products: list[dict] = []
    if watchlist:
        product_ids = [item["product_id"] for item in watchlist]
        fields = ",".join(
            [
                "product_id",
                "product_title",
                "product_main_image_url",
                "product_detail_url",
                "target_original_price",
                "target_original_price_currency",
                "target_sale_price",
                "target_sale_price_currency",
                "discount",
                "promotion_link",
            ]
        )
        for start in range(0, len(product_ids), 20):
            batch = product_ids[start:start + 20]
            result = aliexpress_api_call(
                "aliexpress.affiliate.productdetail.get",
                {
                    "country": ALIEXPRESS_SHIP_TO_COUNTRY,
                    "fields": fields,
                    "product_ids": ",".join(batch),
                    "target_currency": ALIEXPRESS_TARGET_CURRENCY,
                    "target_language": ALIEXPRESS_TARGET_LANGUAGE,
                    "tracking_id": ALIEXPRESS_TRACKING_ID,
                },
            )
            products = _ali_list((result or {}).get("products"), "product")
            raw_products.extend(products)
            print(f"[aliexpress] الدفعة {start // 20 + 1}: {len(products)} منتج")
            time.sleep(1)
    if ALIEXPRESS_AUTO_DISCOVERY:
        print("[aliexpress] تشغيل الاكتشاف الآلي للرائج")
        raw_products.extend(discover_aliexpress_products())
    if not raw_products:
        print("[aliexpress] قائمة المتابعة فارغة والاكتشاف الآلي متوقف")
        return []

    source_urls = []
    for product in raw_products:
        product_id = _ali_product_id(product.get("product_id"))
        source_urls.append(
            str(product.get("product_detail_url") or "").strip()
            or f"https://www.aliexpress.com/item/{product_id}.html"
        )
    link_map = aliexpress_generate_links(source_urls)

    clean: list[dict] = []
    seen: set[str] = set()
    for product, source_url in zip(raw_products, source_urls):
        product_id = _ali_product_id(product.get("product_id"))
        promotion_link = _ali_https_url(product.get("promotion_link"))
        affiliate_url = (
            promotion_link
            if promotion_link
            else link_map.get(source_url) or link_map.get(product_id, "")
        )
        deal = sanitize_aliexpress(
            {
                "product_id": product_id,
                "title": product.get("product_title"),
                "image": product.get("product_main_image_url"),
                "url": affiliate_url,
                "original_price": product.get("target_original_price")
                or product.get("original_price"),
                "sale_price": product.get("target_sale_price")
                or product.get("target_app_sale_price")
                or product.get("sale_price")
                or product.get("app_sale_price"),
                "currency": product.get("target_original_price_currency")
                or product.get("target_sale_price_currency")
                or product.get("original_price_currency")
                or product.get("sale_price_currency"),
                "discount_percent": product.get("discount"),
                "category": categories.get(product_id) or product.get("_overly_category"),
                "auto_discovered": product.get("auto_discovered"),
            }
        )
        if deal and product_id not in seen:
            seen.add(product_id)
            clean.append(deal)

    clean.sort(key=lambda deal: deal["discount_percent"], reverse=True)
    print(f"[aliexpress] {len(clean)} عرض صالح برابط عمولة رسمي")
    return clean[:MAX_DEALS]


def _deal_key(deal: dict) -> str:
    if str(deal.get("store", "amazon")).lower() == "aliexpress":
        return f"aliexpress:{_ali_product_id(deal.get('product_id'))}"
    return f"amazon:{str(deal.get('asin', '')).strip().upper()}"


def merge_deals(existing: list[dict], updates: list[dict]) -> list[dict]:
    """يدمج التحديثات ويحافظ على اليدوي مع تدوير الاكتشاف الآلي القديم."""
    merged = [dict(deal) for deal in existing if isinstance(deal, dict)]
    fresh_auto_keys = {
        _deal_key(deal)
        for deal in updates
        if deal.get("auto_discovered") and _deal_key(deal)
    }
    if fresh_auto_keys:
        merged = [
            deal
            for deal in merged
            if not deal.get("auto_discovered") or _deal_key(deal) in fresh_auto_keys
        ]
    indexes = {_deal_key(deal): index for index, deal in enumerate(merged) if _deal_key(deal)}
    for deal in updates:
        key = _deal_key(deal)
        if not key or key.endswith(":"):
            continue
        if key in indexes:
            merged[indexes[key]] = deal
        else:
            indexes[key] = len(merged)
            merged.append(deal)
    merged.sort(key=lambda deal: int(deal.get("discount_percent", 0)), reverse=True)
    return merged[: MAX_DEALS * 2]


# ----------------------------------------------------------------------------
# الكتابة الآمنة
# ----------------------------------------------------------------------------
def write_output(deals: list[dict], source: str = DEALS_URL) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "count": len(deals),
        "deals": deals,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # كتابة ذرّية: ملف مؤقت ثم استبدال، حتى لا يتلف deals.json أثناء الكتابة
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # تحقق نهائي قبل الاستبدال
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(OUTPUT_PATH)
    print(f"[write] {len(deals)} deals -> {OUTPUT_PATH}")


# ----------------------------------------------------------------------------
# نشر تيليجرام + منع التكرار (Deduplication)
# ----------------------------------------------------------------------------
def affiliate_link(asin: str) -> str:
    return f"https://www.amazon.sa/dp/{asin}/?tag={AFFILIATE_TAG}"


def deal_price(original_price: float, discount_percent: int) -> int:
    """يحسب السعر بعد الخصم تقريبياً من السعر الأصلي ونسبة الخصم."""
    return round(original_price * (1 - discount_percent / 100))


def tg_escape(text: str) -> str:
    """تهريب الأحرف الخاصة بـ HTML parse_mode في تيليجرام."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def load_posted_state() -> dict:
    """يقرأ سجل المنتجات المنشورة سابقاً {asin: ISO-timestamp}."""
    try:
        data = json.loads(POSTED_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_posted_state(state: dict) -> None:
    # تنظيف السجلات القديمة (أقدم من ضعف فترة التهدئة) حتى لا ينمو الملف بلا حدود
    cutoff = datetime.now(timezone.utc) - timedelta(hours=REPOST_COOLDOWN_HOURS * 2)
    cleaned = {}
    for asin, ts in state.items():
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                cleaned[asin] = ts
        except ValueError:
            continue
    POSTED_STATE_PATH.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def recently_posted(asin: str, state: dict) -> bool:
    """هل نُشر هذا المنتج خلال فترة التهدئة؟"""
    ts = state.get(asin)
    if not ts:
        return False
    try:
        posted_at = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - posted_at < timedelta(hours=REPOST_COOLDOWN_HOURS)


# قوالب جذابة تتناوب لتجنّب رتابة المنشورات
HEADLINES = [
    "🚨 عرض فلاش حصري",
    "🔥 خصم ناري لفترة محدودة",
    "⚡ صفقة اليوم",
    "🇸🇦 أقوى عروض أمازون السعودية",
]


def build_caption(deal: dict) -> str:
    """يبني نص المنشور العربي بصيغة HTML الخاصة بتيليجرام."""
    title = tg_escape(deal["title"])
    disc = deal["discount_percent"]
    original = deal["original_price"]
    final = deal_price(original, disc)
    link = affiliate_link(deal["asin"])
    headline = random.choice(HEADLINES)

    # ملاحظة التزام: السعر بعد الخصم تقديري محسوب من النسبة،
    # لذا نوضّح أن السعر النهائي المعتمد هو الظاهر على أمازون.
    return (
        f"{headline}\n"
        f"📢 خصم <b>{disc}%</b> لفترة محدودة!\n\n"
        f"🛍️ <b>{title}</b>\n\n"
        f"💰 السعر قبل الخصم: <s>{original} ر.س</s>\n"
        f"✅ السعر بعد الخصم: <b>~{final} ر.س</b>\n\n"
        f"🔗 <a href=\"{link}\">اضغط هنا للطلب من أمازون السعودية</a>\n\n"
        f"🇸🇦 صائد الخصومات السعودية\n"
        f"<i>السعر النهائي المعتمد هو الظاهر على أمازون لحظة الشراء.</i>"
    )


def send_to_telegram(deal: dict) -> bool:
    """يرسل صورة المنتج مع النص كتعليق عبر sendPhoto. يعيد True عند النجاح."""
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "photo": deal["image"],
        "caption": build_caption(deal),
        "parse_mode": "HTML",
    }
    try:
        resp = requests.post(api, data=payload, timeout=REQUEST_TIMEOUT)
        ok = resp.status_code == 200 and resp.json().get("ok") is True
        if not ok:
            print(f"[telegram] failed {deal['asin']}: {resp.status_code} {resp.text[:160]}")
        return ok
    except (requests.RequestException, ValueError) as exc:
        print(f"[telegram] error {deal['asin']}: {exc}")
        return False


def post_deals_to_telegram(deals: list[dict]) -> None:
    """ينشر العروض المؤهلة (خصم كافٍ + غير مكررة) ضمن الحدود المسموحة."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL:
        print("[telegram] secrets not set — skipping channel posting")
        return

    state = load_posted_state()
    # قالب تيليجرام الحالي خاص بأمازون؛ لا ننشر AliExpress قبل إعداد قالب مستقل.
    eligible = [
        d for d in deals
        if str(d.get("store", "amazon")).lower() == "amazon"
        and d["discount_percent"] >= MIN_DISCOUNT_TO_POST
    ]
    print(f"[telegram] {len(eligible)} deals meet the {MIN_DISCOUNT_TO_POST}% threshold")

    posted = 0
    for deal in eligible:
        if posted >= MAX_POSTS_PER_RUN:
            print(f"[telegram] reached cap of {MAX_POSTS_PER_RUN} posts this run")
            break
        if recently_posted(deal["asin"], state):
            continue
        if send_to_telegram(deal):
            state[deal["asin"]] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            posted += 1
            print(f"[telegram] posted {deal['asin']} ({deal['discount_percent']}%)")
            time.sleep(3)  # احترام حدود معدل تيليجرام

    save_posted_state(state)
    print(f"[telegram] done — {posted} new post(s)")


def main() -> int:
    existing = load_existing_deals()

    # عند توفّر مفاتيح Creators API نستخدم التحديث الحيّ الرسمي، وإلا نعود للجمع من HTML.
    if CREATORS_ENABLED:
        print("[main] مفاتيح Creators API متوفرة — تحديث حيّ للأسعار عبر الواجهة الرسمية")
        amazon_updates = scrape_creators()
        amazon_source = f"creators-api:{CREATORS_MARKETPLACE}"
    else:
        print("[main] لا توجد مفاتيح Creators API — الجمع من HTML (قد يكون محجوباً من أمازون)")
        amazon_updates = scrape()
        amazon_source = DEALS_URL

    if ALIEXPRESS_ENABLED:
        print("[main] مفاتيح AliExpress متوفرة — تحديث المنتجات وروابط العمولة الرسمية")
        aliexpress_updates = scrape_aliexpress()
        aliexpress_source = "aliexpress-affiliates-api"
    else:
        print("[main] مفاتيح AliExpress غير مكتملة — إبقاء منتجات AliExpress الحالية")
        aliexpress_updates = []
        aliexpress_source = ""

    updates = amazon_updates + aliexpress_updates

    # حماية التنسيق اليدوي: إذا رجع الجمع فاضياً وملف العروض موجود أصلاً،
    # لا نلمسه إطلاقاً — حتى لا تُمسح العروض المضافة يدوياً في كل تشغيلة.
    if not updates and OUTPUT_PATH.exists():
        print("[main] لا عروض جديدة — إبقاء deals.json الحالي كما هو (حماية العروض اليدوية)")
        return 0

    merged = merge_deals(existing, updates)
    source = "+".join(part for part in [amazon_source if amazon_updates else "", aliexpress_source if aliexpress_updates else ""] if part) or "manual"
    write_output(merged, source)

    post_deals_to_telegram(updates)
    return 0


if __name__ == "__main__":
    sys.exit(main())
