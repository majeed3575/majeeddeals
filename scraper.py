#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
صائد الخصومات السعودية — Amazon.sa Gold Box Scraper (نسخة محمية)
================================================================
- يجمع العروض من أمازون كل نصف ساعة عبر GitHub Actions
- محمي: إذا رجع الجمع فاضياً، لا يمسح عروضك اليدوية إطلاقاً
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

# ---------------------------------------------------------------------------
DEALS_URL = "https://www.amazon.sa/gp/goldbox"
OUTPUT_PATH = Path(__file__).resolve().parent / "deals.json"
MAX_DEALS = 24
REQUEST_TIMEOUT = 25
RETRIES = 3

AFFILIATE_TAG = "faraj733-21"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL_USERNAME", "").strip()
MIN_DISCOUNT_TO_POST = 30
MAX_POSTS_PER_RUN = 5
REPOST_COOLDOWN_HOURS = 48
POSTED_STATE_PATH = Path(__file__).resolve().parent / "posted_deals.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

CATEGORY_KEYWORDS = {
    "الإلكترونيات": ["سماعة", "سماعات", "شاحن", "كيبل", "كابل", "لابتوب", "حاسوب", "جوال",
        "هاتف", "ساعة ذكية", "شاشة", "كاميرا", "باور بانك", "تابلت",
        "headphone", "earbud", "charger", "laptop", "phone", "watch", "camera",
        "monitor", "tablet", "usb", "ssd", "speaker"],
    "المنزل": ["مقلاة", "قلاية", "مكنسة", "خلاط", "قهوة", "مطبخ", "غسالة", "مكواة",
        "سرير", "وسادة", "إضاءة", "مصباح", "تنظيف", "ثلاجة", "ثلج", "ميزان",
        "kitchen", "vacuum", "blender", "coffee", "fryer", "pillow", "lamp",
        "cleaner", "cookware", "ice", "scale", "purifier"],
    "الموضة": ["حقيبة", "حذاء", "قميص", "عباية", "فستان", "نظارة", "عطر", "ساعة يد",
        "ملابس", "جاكيت", "مظلة",
        "bag", "shoe", "shirt", "dress", "sunglasses", "perfume", "jacket",
        "backpack", "wallet", "umbrella"],
}


def classify(title: str) -> str:
    low = title.lower()
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in low for w in words):
            return cat
    return "الإلكترونيات"


def sanitize(raw: dict) -> dict | None:
    asin = str(raw.get("asin", "")).strip().upper()
    if not re.match(r"^[A-Z0-9]{10}$", asin):
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
        "asin": asin, "title": title, "image": image,
        "discount_percent": discount, "original_price": round(price),
        "category": raw.get("category") or classify(title),
    }


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


def extract_from_cards(soup: BeautifulSoup) -> list[dict]:
    deals = []
    for card in soup.select("[data-asin]"):
        asin = (card.get("data-asin") or "").strip().upper()
        if not re.match(r"^[A-Z0-9]{10}$", asin):
            continue
        img = card.select_one("img")
        image = (img.get("src") or img.get("data-src") or "") if img else ""
        title = (img.get("alt") or "").strip() if img else ""
        if not title:
            t = card.select_one("[class*=title], h2, h3")
            title = t.get_text(strip=True) if t else ""
        text = card.get_text(" ", strip=True)
        m_disc = re.search(r"(\d{1,2})\s*%", text)
        discount = int(m_disc.group(1)) if m_disc else 0
        price = 0.0
        strike = card.select_one(".a-text-price, [class*=strike], del, s")
        if strike:
            m_price = re.search(r"([\d,]+(?:\.\d+)?)", strike.get_text())
            if m_price:
                price = float(m_price.group(1).replace(",", ""))
        deals.append({"asin": asin, "title": title, "image": image,
                      "discount_percent": discount, "original_price": price})
    return deals


def extract_from_links(soup: BeautifulSoup) -> list[dict]:
    deals = []
    for a in soup.select('a[href*="/dp/"]'):
        m = re.search(r"/dp/([A-Z0-9]{10})", a.get("href", ""))
        if not m:
            continue
        img = a.select_one("img")
        deals.append({"asin": m.group(1),
                      "title": (img.get("alt") if img else a.get_text(strip=True)) or "",
                      "image": (img.get("src") or img.get("data-src") or "") if img else "",
                      "discount_percent": 0, "original_price": 0})
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
    clean, seen = [], set()
    for raw in candidates:
        item = sanitize(raw)
        if item and item["asin"] not in seen:
            seen.add(item["asin"])
            clean.append(item)
        if len(clean) >= MAX_DEALS:
            break
    clean.sort(key=lambda d: d["discount_percent"], reverse=True)
    return clean


def write_output(deals: list[dict]) -> None:
    existing = {d["asin"] for d in deals}
    merged = deals + [f for f in FALLBACK_DEALS if f["asin"] not in existing]
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": DEALS_URL, "count": len(merged), "deals": merged,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(OUTPUT_PATH)
    print(f"[write] {len(merged)} deals -> {OUTPUT_PATH}")


def affiliate_link(asin: str) -> str:
    return f"https://www.amazon.sa/dp/{asin}/?tag={AFFILIATE_TAG}"


def deal_price(original_price: float, discount_percent: int) -> int:
    return round(original_price * (1 - discount_percent / 100))


def tg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_posted_state() -> dict:
    try:
        data = json.loads(POSTED_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_posted_state(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=REPOST_COOLDOWN_HOURS * 2)
    cleaned = {}
    for asin, ts in state.items():
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                cleaned[asin] = ts
        except ValueError:
            continue
    POSTED_STATE_PATH.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")


def recently_posted(asin: str, state: dict) -> bool:
    ts = state.get(asin)
    if not ts:
        return False
    try:
        posted_at = datetime.fromisoformat(ts)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - posted_at < timedelta(hours=REPOST_COOLDOWN_HOURS)


HEADLINES = ["🚨 عرض فلاش حصري", "🔥 خصم ناري لفترة محدودة", "⚡ صفقة اليوم", "🇸🇦 أقوى عروض أمازون السعودية"]


def build_caption(deal: dict) -> str:
    title = tg_escape(deal["title"])
    disc = deal["discount_percent"]
    original = deal["original_price"]
    final = deal_price(original, disc)
    link = affiliate_link(deal["asin"])
    headline = random.choice(HEADLINES)
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
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {"chat_id": TELEGRAM_CHANNEL, "photo": deal["image"],
               "caption": build_caption(deal), "parse_mode": "HTML"}
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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL:
        print("[telegram] secrets not set — skipping channel posting")
        return
    state = load_posted_state()
    eligible = [d for d in deals if d["discount_percent"] >= MIN_DISCOUNT_TO_POST]
    print(f"[telegram] {len(eligible)} deals meet the {MIN_DISCOUNT_TO_POST}% threshold")
    posted = 0
    for deal in eligible:
        if posted >= MAX_POSTS_PER_RUN:
            break
        if recently_posted(deal["asin"], state):
            continue
        if send_to_telegram(deal):
            state[deal["asin"]] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            posted += 1
            print(f"[telegram] posted {deal['asin']} ({deal['discount_percent']}%)")
            time.sleep(3)
    save_posted_state(state)
    print(f"[telegram] done — {posted} new post(s)")


def main() -> int:
    deals = scrape()

    # حماية العروض اليدوية: إذا رجع الجمع فاضياً وملف العروض موجود، لا نلمسه إطلاقاً
    if not deals and OUTPUT_PATH.exists():
        print("[main] scrape empty — keeping existing deals.json untouched")
        return 0

    if not deals:
        print("[main] scrape returned 0 deals — failsafe payload will be used")
    write_output(deals)

    existing = {d["asin"] for d in deals}
    merged = deals + [f for f in FALLBACK_DEALS if f["asin"] not in existing]
    post_deals_to_telegram(merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
