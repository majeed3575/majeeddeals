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
وفي حال فشلها جميعاً يضمن الـ failsafe ملفاً صالحاً دائماً.
البديل الرسمي والأكثر استقراراً هو Amazon Creators API (خلَف PA-API المتوقفة منذ مايو 2026).
عند ضبط مفاتيح Creators API (كـ GitHub Secrets) يتحوّل السكربت تلقائياً للتحديث الحيّ عبرها.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

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


# ----------------------------------------------------------------------------
# الـ Failsafe: ASIN موثّق للاختبار يضمن ألا يخرج الملف فارغاً أبداً
# ----------------------------------------------------------------------------
FALLBACK_DEALS = [
    {
        "asin": "B0BNKVGB2J",
        "title": "منتج تجريبي موثّق — عرض أمازون السعودية",
        "image": "https://m.media-amazon.com/images/I/61u48FEs0rL._AC_SL1500_.jpg",
        "discount_percent": 45,
        "original_price": 399,
        "category": "الإلكترونيات",
    }
]

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
# الكتابة الآمنة مع الـ Failsafe
# ----------------------------------------------------------------------------
def write_output(deals: list[dict], source: str = DEALS_URL) -> None:
    # الـ failsafe يُستخدم فقط عند غياب أي عروض حقيقية (تشغيلة أولى بلا ملف)،
    # ولا يُحقن إطلاقاً داخل عروض حقيقية حتى لا يظهر "منتج تجريبي" على الموقع الحي.
    merged = deals or list(FALLBACK_DEALS)

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "count": len(merged),
        "deals": merged,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # كتابة ذرّية: ملف مؤقت ثم استبدال، حتى لا يتلف deals.json أثناء الكتابة
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # تحقق نهائي قبل الاستبدال
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(OUTPUT_PATH)
    print(f"[write] {len(merged)} deals -> {OUTPUT_PATH}")


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
    eligible = [d for d in deals if d["discount_percent"] >= MIN_DISCOUNT_TO_POST]
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
    # عند توفّر مفاتيح Creators API نستخدم التحديث الحيّ الرسمي، وإلا نعود للجمع من HTML.
    if CREATORS_ENABLED:
        print("[main] مفاتيح Creators API متوفرة — تحديث حيّ للأسعار عبر الواجهة الرسمية")
        deals = scrape_creators()
        source = f"creators-api:{CREATORS_MARKETPLACE}"
    else:
        print("[main] لا توجد مفاتيح Creators API — الجمع من HTML (قد يكون محجوباً من أمازون)")
        deals = scrape()
        source = DEALS_URL

    # حماية التنسيق اليدوي: إذا رجع الجمع فاضياً وملف العروض موجود أصلاً،
    # لا نلمسه إطلاقاً — حتى لا تُمسح العروض المضافة يدوياً في كل تشغيلة.
    if not deals and OUTPUT_PATH.exists():
        print("[main] لا عروض جديدة — إبقاء deals.json الحالي كما هو (حماية العروض اليدوية)")
        return 0

    if not deals:
        print("[main] لا عروض ولا ملف سابق — سيُستخدم الـ failsafe")
    write_output(deals, source)

    # النشر للعروض الحقيقية فقط — لا يُنشر "المنتج التجريبي" (failsafe) على القناة إطلاقاً
    post_deals_to_telegram(deals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
