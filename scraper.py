#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
صائد الخصومات السعودية — Amazon.sa Gold Box Scraper
====================================================
- Python 3.10+ / Requests / BeautifulSoup4
- مصمم للتشغيل Serverless عبر GitHub Actions كل ساعة
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
from urllib.parse import parse_qs, urlsplit

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
TELEGRAM_MAX_NEW_POSTS = max(
    1, min(10, int(os.environ.get("TELEGRAM_MAX_NEW_POSTS") or "10"))
)
TELEGRAM_SEND_DELAY_SECONDS = max(
    1.0, min(10.0, float(os.environ.get("TELEGRAM_SEND_DELAY_SECONDS") or "3"))
)
TELEGRAM_API_ATTEMPTS = 3
TELEGRAM_MAX_RETRY_AFTER_SECONDS = 60
# منتج مميز واحد كل ساعتين، وبحد أقصى 10 منتجات في اليوم بتوقيت الرياض.
TELEGRAM_FEATURED_INTERVAL_HOURS = max(
    2, int(os.environ.get("TELEGRAM_FEATURED_INTERVAL_HOURS") or "2")
)
TELEGRAM_FEATURED_DAILY_LIMIT = max(
    1, min(10, int(os.environ.get("TELEGRAM_FEATURED_DAILY_LIMIT") or "10"))
)
REPOST_COOLDOWN_HOURS = 168       # لا يعاد المنتج المميز نفسه خلال 7 أيام
TELEGRAM_STATE_RETENTION_DAYS = 30
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
    1, min(1000, int(os.environ.get("ALIEXPRESS_AUTO_LIMIT") or "1000"))
)
ALIEXPRESS_MAX_PER_ANGLE = max(
    1, min(40, int(os.environ.get("ALIEXPRESS_MAX_PER_ANGLE") or "24"))
)
ALIEXPRESS_QUERY_PAGE_SIZE = max(
    20, min(50, int(os.environ.get("ALIEXPRESS_QUERY_PAGE_SIZE") or "50"))
)
ALIEXPRESS_QUERY_PAGES = max(
    1, min(6, int(os.environ.get("ALIEXPRESS_QUERY_PAGES") or "4"))
)
ALIEXPRESS_AUTO_MIN_VOLUME = max(
    0, int(os.environ.get("ALIEXPRESS_AUTO_MIN_VOLUME") or "1000")
)
ALIEXPRESS_AUTO_MIN_RATING = max(
    0, min(100, int(os.environ.get("ALIEXPRESS_AUTO_MIN_RATING") or "90"))
)
ALIEXPRESS_AUTO_MIN_PRICE_SAR = max(
    0.0, float(os.environ.get("ALIEXPRESS_AUTO_MIN_PRICE_SAR") or "10")
)
ALIEXPRESS_AUTO_MAX_PRICE_SAR = max(
    ALIEXPRESS_AUTO_MIN_PRICE_SAR,
    float(os.environ.get("ALIEXPRESS_AUTO_MAX_PRICE_SAR") or "5000"),
)
# الاكتشاف الموجّه هو الوضع الافتراضي: يمنع امتلاء الموقع بمنتجات عامة عشوائية.
ALIEXPRESS_FOCUS_DISCOVERY = (
    os.environ.get("ALIEXPRESS_FOCUS_DISCOVERY") or "true"
).strip().lower() in {"1", "true", "yes", "on"}
ALIEXPRESS_FOCUS_QUERIES = [
    {
        "topic": "tech", "keywords": "magnetic power bank", "category": "الإلكترونيات",
        "angle": "شحن متنقل", "include": ("power bank", "بنك طاقة", "باور بانك", "شاحن متنقل"),
    },
    {
        "topic": "tech", "keywords": "wireless lavalier microphone", "category": "الإلكترونيات",
        "angle": "صناعة المحتوى", "include": ("microphone", "ميكروفون", "مايكروفون", "لافالير"),
    },
    {
        "topic": "tech", "keywords": "smart tag tracker", "category": "الإلكترونيات",
        "angle": "تتبّع ذكي", "include": ("tracker", "smart tag", "متتبع", "تتبع", "علامة ذكية"),
    },
    {
        "topic": "tech", "keywords": "wireless carplay adapter", "category": "السيارة",
        "angle": "تقنية السيارة", "include": ("carplay", "كاربلاي", "سيارة", "car play"),
    },
    {
        "topic": "tech", "keywords": "usb c hub 4k", "category": "الإلكترونيات",
        "angle": "مكتب وتقنية", "include": ("usb c hub", "usb-c hub", "موزع usb", "محول usb", "hub"),
    },
    {
        "topic": "tech", "keywords": "rechargeable motion sensor light", "category": "المنزل",
        "angle": "منزل ذكي", "include": ("motion sensor", "مستشعر حركة", "استشعار الحركة", "مصباح", "إضاءة"),
    },
    {
        "topic": "tech", "keywords": "gan charger usb c fast", "category": "الإلكترونيات",
        "angle": "شحن سريع", "include": ("gan charger", "شاحن gan", "شاحن سريع", "usb c charger"),
    },
    {
        "topic": "tech", "keywords": "portable tire inflator digital", "category": "السيارة",
        "angle": "طوارئ السيارة", "include": ("tire inflator", "air compressor", "منفاخ إطارات", "ضاغط هواء", "نفخ الإطارات"),
    },
    {
        "topic": "tech", "keywords": "bluetooth thermal label printer", "category": "الإلكترونيات",
        "angle": "تنظيم ذكي", "include": ("label printer", "thermal printer", "طابعة ملصقات", "طابعة حرارية"),
    },
    {
        "topic": "tech", "keywords": "wireless earbuds noise cancelling", "category": "الإلكترونيات",
        "angle": "صوت وتقنية", "include": ("wireless earbuds", "bluetooth earbuds", "سماعات لاسلكية", "سماعات بلوتوث"),
    },
    {
        "topic": "tech", "keywords": "portable bluetooth speaker", "category": "الإلكترونيات",
        "angle": "صوت محمول", "include": ("bluetooth speaker", "wireless speaker", "مكبر صوت بلوتوث", "سماعة بلوتوث"),
    },
    {
        "topic": "tech", "keywords": "mechanical keyboard", "category": "الإلكترونيات",
        "angle": "لوحة مفاتيح", "include": ("mechanical keyboard", "gaming keyboard", "لوحة مفاتيح ميكانيكية"),
    },
    {
        "topic": "tech", "keywords": "wireless mouse ergonomic", "category": "الإلكترونيات",
        "angle": "ملحقات الكمبيوتر", "include": ("wireless mouse", "ergonomic mouse", "ماوس لاسلكي", "فأرة لاسلكية"),
    },
    {
        "topic": "tech", "keywords": "smart plug wifi", "category": "الإلكترونيات",
        "angle": "تحكم ذكي", "include": ("smart plug", "wifi plug", "smart socket", "مقبس ذكي"),
    },
    {
        "topic": "tech", "keywords": "led desk lamp usb", "category": "المنزل",
        "angle": "مكتب ذكي", "include": ("desk lamp", "table lamp", "مصباح مكتب", "إضاءة مكتب"),
    },
    {
        "topic": "tech", "keywords": "phone gimbal stabilizer", "category": "الإلكترونيات",
        "angle": "تصوير ثابت", "include": ("phone gimbal", "smartphone gimbal", "gimbal stabilizer", "مثبت هاتف"),
    },
    {
        "topic": "tech", "keywords": "car dash camera", "category": "السيارة",
        "angle": "كاميرا السيارة", "include": ("dash camera", "dash cam", "dashcam", "كاميرا سيارة"),
    },
    {
        "topic": "tech", "keywords": "car jump starter power bank", "category": "السيارة",
        "angle": "طوارئ الطاقة", "include": ("jump starter", "car starter", "تشغيل بطارية السيارة", "اشتراك سيارة"),
    },
    {
        "topic": "tech", "keywords": "electric screwdriver cordless", "category": "المنزل",
        "angle": "أدوات تقنية", "include": ("electric screwdriver", "cordless screwdriver", "مفك كهربائي", "مفك لاسلكي"),
    },
    {
        "topic": "tech", "keywords": "digital laser measure", "category": "المنزل",
        "angle": "قياس ذكي", "include": ("laser measure", "laser distance", "مقياس ليزر", "قياس ليزر"),
    },
    {
        "topic": "tech", "keywords": "car obd2 scanner bluetooth", "category": "السيارة",
        "angle": "فحص السيارة", "include": ("obd2 scanner", "obd scanner", "car diagnostic", "فحص السيارة"),
    },
    {
        "topic": "life_hack", "keywords": "electric spin scrubber bathroom", "category": "المنزل",
        "angle": "تنظيف ذكي", "include": ("spin scrubber", "bathroom scrubber", "فرشاة تنظيف كهربائية", "فرشاة دوارة"),
    },
    {
        "topic": "life_hack", "keywords": "mini bag sealer rechargeable", "category": "المنزل",
        "angle": "مطبخ عملي", "include": ("bag sealer", "sealer", "لحام الأكياس", "إغلاق الأكياس", "ختم الأكياس"),
    },
    {
        "topic": "life_hack", "keywords": "electric milk frother rechargeable", "category": "المنزل",
        "angle": "مطبخ ذكي", "include": ("milk frother", "electric frother", "مخفّق حليب", "خفاق حليب", "رغوة الحليب"),
    },
    {
        "topic": "life_hack", "keywords": "digital luggage scale travel", "category": "السفر",
        "angle": "سفر أذكى", "include": ("luggage scale", "baggage scale", "ميزان أمتعة", "ميزان حقائب", "ميزان سفر"),
    },
    {
        "topic": "life_hack", "keywords": "automatic soap dispenser rechargeable", "category": "المنزل",
        "angle": "منزل عملي", "include": ("soap dispenser", "موزع صابون", "صابون أوتوماتيكي", "صابون تلقائي"),
    },
    {
        "topic": "life_hack", "keywords": "cordless air duster rechargeable", "category": "الإلكترونيات",
        "angle": "تنظيف التقنية", "include": ("air duster", "منفاخ هواء", "هواء مضغوط", "منفضة هواء"),
    },
    {
        "topic": "life_hack", "keywords": "mini electric food chopper", "category": "المنزل",
        "angle": "تحضير أسرع", "include": ("food chopper", "electric chopper", "مفرمة كهربائية", "قطاعة كهربائية"),
    },
    {
        "topic": "life_hack", "keywords": "portable blender rechargeable", "category": "المنزل",
        "angle": "مشروبات سريعة", "include": ("portable blender", "rechargeable blender", "خلاط محمول", "خلاط قابل للشحن"),
    },
    {
        "topic": "life_hack", "keywords": "electric lint remover rechargeable", "category": "المنزل",
        "angle": "عناية بالملابس", "include": ("lint remover", "fabric shaver", "مزيل الوبر", "إزالة الوبر"),
    },
    {
        "topic": "life_hack", "keywords": "foldable electric kettle travel", "category": "السفر",
        "angle": "سفر عملي", "include": ("foldable kettle", "travel kettle", "غلاية قابلة للطي", "غلاية سفر"),
    },
    {
        "topic": "life_hack", "keywords": "handheld vacuum cordless", "category": "المنزل",
        "angle": "تنظيف سريع", "include": ("handheld vacuum", "cordless vacuum", "مكنسة محمولة", "مكنسة لاسلكية"),
    },
    {
        "topic": "life_hack", "keywords": "vacuum sealer food", "category": "المنزل",
        "angle": "حفظ الطعام", "include": ("vacuum sealer", "food sealer", "تغليف مفرغ", "حفظ الطعام"),
    },
    {
        "topic": "life_hack", "keywords": "garment steamer handheld", "category": "المنزل",
        "angle": "عناية سريعة", "include": ("garment steamer", "clothes steamer", "مكواة بخار محمولة", "بخار ملابس"),
    },
    {
        "topic": "life_hack", "keywords": "electric coffee grinder", "category": "المنزل",
        "angle": "قهوة منزلية", "include": ("coffee grinder", "electric grinder", "مطحنة قهوة", "طاحونة قهوة"),
    },
    {
        "topic": "life_hack", "keywords": "digital kitchen scale", "category": "المنزل",
        "angle": "مطبخ دقيق", "include": ("kitchen scale", "food scale", "ميزان مطبخ", "ميزان طعام"),
    },
    {
        "topic": "life_hack", "keywords": "portable neck fan", "category": "الإلكترونيات",
        "angle": "تبريد شخصي", "include": ("neck fan", "wearable fan", "مروحة رقبة", "مروحة محمولة"),
    },
    {
        "topic": "life_hack", "keywords": "mini humidifier usb", "category": "المنزل",
        "angle": "راحة المنزل", "include": ("mini humidifier", "usb humidifier", "مرطب هواء", "جهاز ترطيب"),
    },
    {
        "topic": "camping", "keywords": "camping lantern rechargeable", "category": "التخييم",
        "angle": "رحلات وتخييم", "include": ("camping lantern", "camping light", "مصباح تخييم", "إضاءة رحلات"),
    },
    {
        "topic": "life_hack", "keywords": "packing cubes travel", "category": "السفر",
        "angle": "تنظيم السفر", "include": ("packing cubes", "travel organizer", "منظم سفر", "حقائب تنظيم"),
    },
    {
        "topic": "life_hack", "keywords": "electric can opener", "category": "المنزل",
        "angle": "فتح أسهل", "include": ("electric can opener", "automatic can opener", "فتاحة علب كهربائية"),
    },
    {
        "topic": "life_hack", "keywords": "portable espresso maker", "category": "السفر",
        "angle": "قهوة متنقلة", "include": ("portable espresso", "travel coffee maker", "ماكينة اسبريسو محمولة", "قهوة محمولة"),
    },
    {
        "topic": "life_hack", "keywords": "collapsible laundry basket", "category": "المنزل",
        "angle": "تنظيم الغسيل", "include": ("laundry basket", "laundry hamper", "سلة غسيل", "سلة ملابس"),
    },
    # تصنيفات رائجة إضافية لزيادة التنوع والوصول، مع تطبيق شروط الجودة نفسها.
    {
        "topic": "tech", "keywords": "smart watch fitness tracker", "category": "الإلكترونيات",
        "angle": "تقنية قابلة للارتداء", "include": ("smart watch", "smartwatch", "fitness tracker", "ساعة ذكية"),
    },
    {
        "topic": "home_entertainment", "keywords": "mini projector android", "category": "الترفيه المنزلي",
        "angle": "ترفيه منزلي", "include": ("mini projector", "android projector", "projector", "بروجكتر", "عارض"),
    },
    {
        "topic": "home_entertainment", "keywords": "BYINTEK projector 4k", "category": "الترفيه المنزلي",
        "angle": "بروجكترات BYINTEK", "include": ("byintek",),
    },
    {
        "topic": "home_entertainment", "keywords": "BYINTEK android projector", "category": "الترفيه المنزلي",
        "angle": "بروجكترات BYINTEK", "include": ("byintek",),
    },
    {
        "topic": "home_entertainment", "keywords": "TCL smart TV", "category": "الترفيه المنزلي",
        "angle": "تلفزيونات TCL", "include": ("tcl",),
    },
    {
        "topic": "home_entertainment", "keywords": "TCL QLED TV", "category": "الترفيه المنزلي",
        "angle": "تلفزيونات TCL", "include": ("tcl",),
    },
    {
        "topic": "tech", "keywords": "bluetooth game controller", "category": "الإلكترونيات",
        "angle": "ألعاب وتقنية", "include": ("game controller", "gamepad", "gaming controller", "يد تحكم"),
    },
    {
        "topic": "tech", "keywords": "wifi repeater extender", "category": "الإلكترونيات",
        "angle": "شبكة منزلية", "include": ("wifi repeater", "wifi extender", "range extender", "مقوي واي فاي"),
    },
    {
        "topic": "tech", "keywords": "wireless charging station 3 in 1", "category": "الإلكترونيات",
        "angle": "شحن متعدد", "include": ("charging station", "wireless charger", "3 in 1 charger", "شاحن لاسلكي"),
    },
    {
        "topic": "tech", "keywords": "rgb led strip wifi", "category": "المنزل",
        "angle": "إضاءة ذكية", "include": ("led strip", "rgb strip", "smart light strip", "شريط ليد", "إضاءة rgb"),
    },
    {
        "topic": "tech", "keywords": "action camera 4k", "category": "الإلكترونيات",
        "angle": "تصوير المغامرات", "include": ("action camera", "sport camera", "4k camera", "كاميرا رياضية"),
    },
    {
        "topic": "tech", "keywords": "usb c cable 100w", "category": "الإلكترونيات",
        "angle": "شحن وكابلات", "include": ("usb c cable", "type c cable", "100w cable", "كيبل شحن", "كابل شحن"),
    },
    {
        "topic": "tech", "keywords": "smart doorbell wifi", "category": "المنزل",
        "angle": "أمان المنزل", "include": ("smart doorbell", "video doorbell", "wifi doorbell", "جرس باب ذكي"),
    },
    {
        "topic": "tech", "keywords": "digital microscope usb", "category": "الإلكترونيات",
        "angle": "استكشاف وتقنية", "include": ("digital microscope", "usb microscope", "electronic microscope", "مجهر رقمي"),
    },
    {
        "topic": "tech", "keywords": "portable monitor usb c", "category": "الإلكترونيات",
        "angle": "عمل متنقل", "include": ("portable monitor", "usb c monitor", "travel monitor", "شاشة محمولة"),
    },
    {
        "topic": "life_hack", "keywords": "manual vegetable chopper", "category": "المنزل",
        "angle": "تحضير المطبخ", "include": ("vegetable chopper", "food chopper", "manual chopper", "قطاعة خضار", "مفرمة يدوية"),
    },
    {
        "topic": "life_hack", "keywords": "oil sprayer bottle kitchen", "category": "المنزل",
        "angle": "مطبخ صحي", "include": ("oil sprayer", "oil spray bottle", "cooking sprayer", "بخاخ زيت", "رشاش زيت"),
    },
    {
        "topic": "life_hack", "keywords": "under sink organizer", "category": "المنزل",
        "angle": "تنظيم المساحات", "include": ("under sink organizer", "sink storage", "cabinet organizer", "منظم تحت المغسلة"),
    },
    {
        "topic": "life_hack", "keywords": "vacuum storage bags", "category": "المنزل",
        "angle": "توفير المساحة", "include": ("vacuum storage bag", "compression bag", "space saver bag", "أكياس تفريغ", "أكياس ضغط"),
    },
    {
        "topic": "life_hack", "keywords": "car seat gap organizer", "category": "السيارة",
        "angle": "تنظيم السيارة", "include": ("seat gap organizer", "car seat organizer", "car gap filler", "منظم مقعد السيارة"),
    },
    {
        "topic": "life_hack", "keywords": "reusable pet hair remover", "category": "المنزل",
        "angle": "تنظيف الوبر", "include": ("pet hair remover", "lint roller", "fur remover", "مزيل شعر الحيوانات", "مزيل وبر"),
    },
    {
        "topic": "life_hack", "keywords": "drawer organizer adjustable", "category": "المنزل",
        "angle": "تنظيم الأدراج", "include": ("drawer organizer", "drawer divider", "adjustable divider", "منظم أدراج", "فاصل درج"),
    },
    {
        "topic": "life_hack", "keywords": "electric cleaning brush kitchen", "category": "المنزل",
        "angle": "تنظيف المطبخ", "include": ("electric cleaning brush", "power scrubber", "cleaning scrubber", "فرشاة تنظيف كهربائية"),
    },
    {
        "topic": "life_hack", "keywords": "silicone air fryer liner", "category": "المنزل",
        "angle": "استخدام القلاية", "include": ("air fryer liner", "silicone liner", "air fryer basket", "بطانة قلاية", "سيليكون قلاية"),
    },
    {
        "topic": "life_hack", "keywords": "foldable clothes drying rack", "category": "المنزل",
        "angle": "تجفيف عملي", "include": ("drying rack", "clothes hanger rack", "foldable hanger", "منشر ملابس", "حامل تجفيف"),
    },
    {
        "topic": "life_hack", "keywords": "travel neck pillow memory foam", "category": "السفر",
        "angle": "راحة السفر", "include": ("travel pillow", "neck pillow", "memory foam pillow", "وسادة سفر", "وسادة رقبة"),
    },
    {
        "topic": "life_hack", "keywords": "shoe organizer rack", "category": "المنزل",
        "angle": "تنظيم الأحذية", "include": ("shoe organizer", "shoe rack", "shoe storage", "منظم أحذية", "رف أحذية"),
    },
    # أقسام رائجة عامة: لا ينحصر الاختيار في التقنية وLife Hacks.
    {
        "topic": "fashion", "keywords": "women shoulder bag handbag", "category": "الموضة",
        "angle": "حقائب نسائية", "include": ("shoulder bag", "handbag", "women bag", "حقيبة نسائية"),
    },
    {
        "topic": "fashion", "keywords": "men casual sneakers", "category": "الموضة",
        "angle": "أحذية رجالية", "include": ("men sneakers", "men shoes", "casual shoes", "أحذية رجالية"),
    },
    {
        "topic": "fashion", "keywords": "women modest dress", "category": "الموضة",
        "angle": "أزياء نسائية", "include": ("modest dress", "women dress", "long dress", "فستان نسائي"),
    },
    {
        "topic": "fashion", "keywords": "polarized sunglasses", "category": "الموضة",
        "angle": "نظارات شمسية", "include": ("polarized sunglasses", "sun glasses", "نظارة شمسية", "نظارات شمسية"),
    },
    {
        "topic": "fashion", "keywords": "men automatic watch", "category": "الموضة",
        "angle": "ساعات رجالية", "include": ("automatic watch", "men watch", "wrist watch", "ساعة رجالية"),
    },
    {
        "topic": "fashion", "keywords": "waterproof travel backpack", "category": "السفر",
        "angle": "حقائب ظهر", "include": ("travel backpack", "waterproof backpack", "حقيبة ظهر", "شنطة ظهر"),
    },
    {
        "topic": "beauty", "keywords": "makeup brush set", "category": "الجمال والعناية",
        "angle": "أدوات مكياج", "include": ("makeup brush", "cosmetic brush", "فرش مكياج", "فرشاة مكياج"),
    },
    {
        "topic": "beauty", "keywords": "electric hair clipper", "category": "الجمال والعناية",
        "angle": "عناية بالشعر", "include": ("hair clipper", "electric trimmer", "ماكينة حلاقة", "ماكينة شعر"),
    },
    {
        "topic": "beauty", "keywords": "hair dryer brush", "category": "الجمال والعناية",
        "angle": "تصفيف الشعر", "include": ("hair dryer brush", "hot air brush", "فرشاة استشوار", "فرشاة تجفيف"),
    },
    {
        "topic": "beauty", "keywords": "electric nail drill machine", "category": "الجمال والعناية",
        "angle": "العناية بالأظافر", "include": ("nail drill", "manicure machine", "جهاز أظافر", "مثقاب أظافر"),
    },
    {
        "topic": "beauty", "keywords": "facial cleansing brush", "category": "الجمال والعناية",
        "angle": "العناية بالبشرة", "include": ("facial cleansing", "face cleansing brush", "تنظيف الوجه", "فرشاة وجه"),
    },
    {
        "topic": "beauty", "keywords": "led face mask skincare", "category": "الجمال والعناية",
        "angle": "تقنية العناية", "include": ("led face mask", "light therapy mask", "قناع وجه led", "قناع ضوئي"),
    },
    {
        "topic": "sports", "keywords": "resistance bands set", "category": "الرياضة",
        "angle": "تمارين منزلية", "include": ("resistance band", "exercise band", "حبال مقاومة", "أشرطة مقاومة"),
    },
    {
        "topic": "sports", "keywords": "yoga mat non slip", "category": "الرياضة",
        "angle": "يوغا ولياقة", "include": ("yoga mat", "exercise mat", "سجادة يوغا", "بساط تمارين"),
    },
    {
        "topic": "sports", "keywords": "adjustable dumbbell set", "category": "الرياضة",
        "angle": "أثقال ولياقة", "include": ("adjustable dumbbell", "dumbbell set", "دمبل قابل", "مجموعة دمبل"),
    },
    {
        "topic": "sports", "keywords": "running shoes", "category": "الرياضة",
        "angle": "أحذية رياضية", "include": ("running shoes", "sport shoes", "أحذية جري", "حذاء رياضي"),
    },
    # الحدائق: أدوات عملية ورائجة مع الشروط العامة نفسها للجودة والشحن.
    {
        "topic": "garden", "keywords": "solar garden lights outdoor", "category": "الحدائق",
        "angle": "إضاءة الحدائق", "include": ("solar garden lights", "garden light", "solar lawn light", "مصباح حديقة"),
    },
    {
        "topic": "garden", "keywords": "garden hose spray nozzle", "category": "الحدائق",
        "angle": "ري الحدائق", "include": ("garden hose nozzle", "spray nozzle", "watering nozzle", "hose sprayer"),
    },
    {
        "topic": "garden", "keywords": "drip irrigation kit garden", "category": "الحدائق",
        "angle": "ري بالتنقيط", "include": ("drip irrigation", "irrigation kit", "watering system", "micro drip"),
    },
    {
        "topic": "garden", "keywords": "electric pruning shears", "category": "الحدائق",
        "angle": "تقليم الحدائق", "include": ("electric pruning shears", "pruning shear", "garden pruner", "cordless pruner"),
    },
    {
        "topic": "garden", "keywords": "garden tools set", "category": "الحدائق",
        "angle": "أدوات الحدائق", "include": ("garden tool set", "gardening tools", "hand garden tools", "garden kit"),
    },
    {
        "topic": "garden", "keywords": "plant watering timer", "category": "الحدائق",
        "angle": "ري ذكي", "include": ("watering timer", "irrigation timer", "water timer", "garden timer"),
    },
    # البحر والصيد: صيد وسباحة وتجهيزات مقاومة للماء.
    {
        "topic": "marine", "keywords": "spinning fishing reel", "category": "البحر والصيد",
        "angle": "بكرات الصيد", "include": ("fishing reel", "spinning reel", "بكرة صيد", "ماكينة صيد"),
    },
    {
        "topic": "marine", "keywords": "telescopic fishing rod", "category": "البحر والصيد",
        "angle": "قصبات الصيد", "include": ("fishing rod", "telescopic rod", "casting rod", "قصبة صيد"),
    },
    {
        "topic": "marine", "keywords": "fishing tackle box organizer", "category": "البحر والصيد",
        "angle": "تنظيم معدات الصيد", "include": ("tackle box", "fishing organizer", "fishing storage", "صندوق صيد"),
    },
    {
        "topic": "marine", "keywords": "portable fish finder", "category": "البحر والصيد",
        "angle": "تقنية الصيد", "include": ("fish finder", "sonar fish", "fishing sonar", "كاشف أسماك"),
    },
    {
        "topic": "marine", "keywords": "waterproof dry bag boating", "category": "البحر والصيد",
        "angle": "حقائب بحرية", "include": ("waterproof dry bag", "dry bag", "boating bag", "حقيبة مقاومة للماء"),
    },
    {
        "topic": "marine", "keywords": "full face snorkel mask", "category": "البحر والصيد",
        "angle": "سباحة وغوص", "include": ("snorkel mask", "diving mask", "full face snorkel", "قناع غوص"),
    },
    # التخييم: تجهيزات الرحلات العملية دون تخفيف شروط المبيعات أو التقييم.
    {
        "topic": "camping", "keywords": "camping tent waterproof", "category": "التخييم",
        "angle": "خيام التخييم", "include": ("camping tent", "waterproof tent", "خيمة تخييم", "خيمة رحلات"),
    },
    {
        "topic": "camping", "keywords": "folding camping chair", "category": "التخييم",
        "angle": "جلسات التخييم", "include": ("camping chair", "folding chair", "outdoor chair", "كرسي تخييم"),
    },
    {
        "topic": "camping", "keywords": "camping sleeping bag", "category": "التخييم",
        "angle": "النوم في الرحلات", "include": ("sleeping bag", "camping sleep bag", "sleeping sack", "كيس نوم"),
    },
    {
        "topic": "camping", "keywords": "camping cookware set", "category": "التخييم",
        "angle": "طبخ الرحلات", "include": ("camping cookware", "camping cooking set", "outdoor cookware", "أواني تخييم"),
    },
    {
        "topic": "camping", "keywords": "inflatable camping mattress", "category": "التخييم",
        "angle": "راحة التخييم", "include": ("camping mattress", "inflatable mattress", "sleeping mat", "مرتبة تخييم"),
    },
    {
        "topic": "camping", "keywords": "insulated camping cooler bag", "category": "التخييم",
        "angle": "حفظ طعام الرحلات", "include": ("cooler bag", "insulated cooler", "camping cooler", "حافظة تبريد"),
    },
    {
        "topic": "kids", "keywords": "building blocks set", "category": "الأطفال",
        "angle": "ألعاب تركيب", "include": ("building blocks", "construction blocks", "مكعبات تركيب", "لعبة تركيب"),
    },
    {
        "topic": "kids", "keywords": "remote control car", "category": "الأطفال",
        "angle": "ألعاب تحكم", "include": ("remote control car", "rc car", "سيارة تحكم", "سيارة ريموت"),
    },
    {
        "topic": "kids", "keywords": "kids drawing tablet", "category": "الأطفال",
        "angle": "تعلم ورسم", "include": ("drawing tablet", "writing tablet", "لوح رسم", "سبورة كتابة"),
    },
    {
        "topic": "kids", "keywords": "baby feeding set", "category": "الأطفال",
        "angle": "مستلزمات الطفل", "include": ("baby feeding", "toddler feeding", "أدوات إطعام", "طقم طعام طفل"),
    },
    {
        "topic": "kids", "keywords": "kids school backpack", "category": "الأطفال",
        "angle": "حقائب مدرسية", "include": ("kids backpack", "school backpack", "حقيبة مدرسية", "شنطة أطفال"),
    },
    {
        "topic": "pets", "keywords": "automatic pet feeder", "category": "الحيوانات الأليفة",
        "angle": "إطعام الحيوانات", "include": ("automatic pet feeder", "cat feeder", "dog feeder", "موزع طعام حيوانات"),
    },
    {
        "topic": "pets", "keywords": "cat water fountain", "category": "الحيوانات الأليفة",
        "angle": "سقاية الحيوانات", "include": ("cat water fountain", "pet fountain", "نافورة قطط", "سقاية حيوانات"),
    },
    {
        "topic": "pets", "keywords": "pet grooming vacuum", "category": "الحيوانات الأليفة",
        "angle": "عناية بالحيوانات", "include": ("pet grooming vacuum", "pet grooming kit", "تنظيف الحيوانات", "عناية بالحيوانات"),
    },
    {
        "topic": "pets", "keywords": "dog harness reflective", "category": "الحيوانات الأليفة",
        "angle": "مستلزمات الحيوانات", "include": ("dog harness", "reflective harness", "حزام كلب", "صدرية كلب"),
    },
    {
        "topic": "tools", "keywords": "cordless drill set", "category": "الأدوات والهوايات",
        "angle": "أدوات كهربائية", "include": ("cordless drill", "electric drill", "دريل لاسلكي", "مثقاب كهربائي"),
    },
    {
        "topic": "tools", "keywords": "laser level tool", "category": "الأدوات والهوايات",
        "angle": "قياس وتسوية", "include": ("laser level", "level tool", "ميزان ليزر", "جهاز تسوية"),
    },
    {
        "topic": "tools", "keywords": "socket wrench set", "category": "الأدوات والهوايات",
        "angle": "عدة يدوية", "include": ("socket wrench", "ratchet set", "طقم مفاتيح", "عدة صيانة"),
    },
    {
        "topic": "tools", "keywords": "cordless pressure washer", "category": "الأدوات والهوايات",
        "angle": "غسيل وضغط", "include": ("pressure washer", "cordless washer", "غسالة ضغط", "مسدس غسيل"),
    },
    {
        "topic": "popular", "keywords": "robot vacuum cleaner", "category": "المنزل",
        "angle": "أجهزة منزلية رائجة", "include": ("robot vacuum", "robot cleaner", "مكنسة روبوت", "روبوت تنظيف"),
    },
    {
        "topic": "popular", "keywords": "espresso coffee machine", "category": "المنزل",
        "angle": "قهوة وأجهزة", "include": ("espresso machine", "coffee machine", "ماكينة اسبريسو", "ماكينة قهوة"),
    },
    {
        "topic": "popular", "keywords": "portable power station", "category": "الإلكترونيات",
        "angle": "طاقة محمولة", "include": ("portable power station", "solar generator", "محطة طاقة", "مولد طاقة"),
    },
    {
        "topic": "popular", "keywords": "android car stereo", "category": "السيارة",
        "angle": "شاشات السيارة", "include": ("android car stereo", "car radio", "شاشة سيارة", "مسجل سيارة"),
    },
    {
        "topic": "popular", "keywords": "electric scooter adult", "category": "الرياضة",
        "angle": "تنقل شخصي", "include": ("electric scooter", "adult scooter", "سكوتر كهربائي", "دراجة كهربائية"),
    },
    {
        "topic": "home", "keywords": "drawer organizer adjustable", "category": "المنزل",
        "angle": "تنظيم الأدراج", "include": ("drawer organizer", "drawer divider", "منظم أدراج", "فاصل أدراج"),
    },
    {
        "topic": "home", "keywords": "storage bins organizer", "category": "المنزل",
        "angle": "تخزين منزلي", "include": ("storage bin", "storage box", "صندوق تخزين", "منظم تخزين"),
    },
    {
        "topic": "home", "keywords": "microfiber floor mop", "category": "المنزل",
        "angle": "تنظيف الأرضيات", "include": ("microfiber mop", "floor mop", "ممسحة أرضية", "ممسحة مايكروفايبر"),
    },
    {
        "topic": "home", "keywords": "shoe rack organizer", "category": "المنزل",
        "angle": "تنظيم الأحذية", "include": ("shoe rack", "shoe organizer", "رف أحذية", "منظم أحذية"),
    },
    {
        "topic": "home", "keywords": "bedding sheet set", "category": "المنزل",
        "angle": "مفروشات منزلية", "include": ("bed sheet", "bedding set", "ملاءة سرير", "طقم سرير"),
    },
    {
        "topic": "fashion", "keywords": "crossbody bag casual", "category": "الموضة",
        "angle": "حقائب يومية", "include": ("crossbody bag", "shoulder bag", "حقيبة كروس", "حقيبة كتف"),
    },
    {
        "topic": "fashion", "keywords": "rfid wallet men", "category": "الموضة",
        "angle": "محافظ عملية", "include": ("rfid wallet", "leather wallet", "محفظة rfid", "محفظة رجالية"),
    },
    {
        "topic": "beauty", "keywords": "hair dryer brush", "category": "الجمال والعناية",
        "angle": "تصفيف الشعر", "include": ("hair dryer brush", "hot air brush", "فرشاة استشوار", "فرشاة هواء ساخن"),
    },
    {
        "topic": "beauty", "keywords": "makeup organizer box", "category": "الجمال والعناية",
        "angle": "تنظيم أدوات العناية", "include": ("makeup organizer", "cosmetic organizer", "منظم مكياج", "منظم مستحضرات"),
    },
    {
        "topic": "sport", "keywords": "foam roller fitness", "category": "الرياضة",
        "angle": "استشفاء رياضي", "include": ("foam roller", "massage roller", "رول تمارين", "أسطوانة تمارين"),
    },
    {
        "topic": "sport", "keywords": "cycling accessories bag", "category": "الرياضة",
        "angle": "إكسسوارات الدراجات", "include": ("bike bag", "bicycle bag", "حقيبة دراجة", "إكسسوارات دراجة"),
    },
    {
        "topic": "garden", "keywords": "soil moisture meter", "category": "الحدائق",
        "angle": "قياس التربة", "include": ("soil moisture meter", "soil tester", "مقياس رطوبة التربة", "فاحص تربة"),
    },
    {
        "topic": "garden", "keywords": "garden gloves waterproof", "category": "الحدائق",
        "angle": "عناية بالحديقة", "include": ("garden gloves", "gardening gloves", "قفازات حديقة", "قفازات زراعة"),
    },
    {
        "topic": "garden", "keywords": "plant support clips", "category": "الحدائق",
        "angle": "دعم النباتات", "include": ("plant clips", "plant support", "مشابك نبات", "دعامة نبات"),
    },
    {
        "topic": "fishing", "keywords": "fishing pliers tool", "category": "البحر والصيد",
        "angle": "أدوات الصيد", "include": ("fishing pliers", "hook remover", "كماشة صيد", "مزيل خطاف"),
    },
    {
        "topic": "camping", "keywords": "rechargeable camping lantern", "category": "التخييم",
        "angle": "إضاءة الرحلات", "include": ("camping lantern", "rechargeable lantern", "فانوس تخييم", "إضاءة رحلات"),
    },
    {
        "topic": "camping", "keywords": "folding camping table", "category": "التخييم",
        "angle": "أثاث الرحلات", "include": ("camping table", "folding table", "طاولة تخييم", "طاولة قابلة للطي"),
    },
    {
        "topic": "kids", "keywords": "magnetic building tiles", "category": "الأطفال",
        "angle": "تعلم وتركيب", "include": ("magnetic tiles", "building tiles", "مكعبات مغناطيسية", "قطع تركيب"),
    },
    {
        "topic": "pet", "keywords": "pet hair remover roller", "category": "الحيوانات الأليفة",
        "angle": "تنظيف شعر الحيوانات", "include": ("pet hair remover", "lint roller", "مزيل شعر الحيوانات", "رول إزالة الوبر"),
    },
    {
        "topic": "tools", "keywords": "digital caliper tool", "category": "الأدوات والهوايات",
        "angle": "قياس دقيق", "include": ("digital caliper", "electronic caliper", "قدمة رقمية", "مقياس رقمي"),
    },
    {
        "topic": "car", "keywords": "car phone holder", "category": "السيارة",
        "angle": "تنظيم الهاتف بالسيارة", "include": ("car phone holder", "phone mount", "حامل جوال سيارة", "حامل هاتف سيارة"),
    },
    {
        "topic": "school", "keywords": "school stationery set students", "category": "المدرسة والتعليم",
        "angle": "أدوات مدرسية", "include": ("stationery set", "school supplies", "أدوات مدرسية", "قرطاسية"),
    },
    {
        "topic": "school", "keywords": "large pencil case school", "category": "المدرسة والتعليم",
        "angle": "تنظيم الأقلام", "include": ("pencil case", "pen case", "مقلمة", "حافظة أقلام"),
    },
    {
        "topic": "school", "keywords": "school backpack students", "category": "المدرسة والتعليم",
        "angle": "حقائب مدرسية", "include": ("school backpack", "student backpack", "حقيبة مدرسية", "شنطة مدرسية"),
    },
    {
        "topic": "school", "keywords": "electric pencil sharpener students", "category": "المدرسة والتعليم",
        "angle": "تجهيز الدراسة", "include": ("pencil sharpener", "electric sharpener", "براية أقلام", "مبراة أقلام"),
    },
    {
        "topic": "school", "keywords": "geometry set school students", "category": "المدرسة والتعليم",
        "angle": "أدوات هندسية", "include": ("geometry set", "math set", "طقم هندسي", "أدوات هندسية"),
    },
    {
        "topic": "school", "keywords": "kids art drawing set", "category": "المدرسة والتعليم",
        "angle": "رسم وتلوين", "include": ("drawing set", "art set", "مجموعة رسم", "أدوات تلوين"),
    },
    {
        "topic": "school", "keywords": "educational flash cards learning", "category": "المدرسة والتعليم",
        "angle": "بطاقات تعليمية", "include": ("flash cards", "learning cards", "بطاقات تعليمية", "بطاقات تعلم"),
    },
    {
        "topic": "school", "keywords": "stem science experiment kit kids", "category": "المدرسة والتعليم",
        "angle": "تجارب تعليمية", "include": ("science kit", "stem kit", "مجموعة تجارب", "ألعاب stem"),
    },
    {
        "topic": "school", "keywords": "educational math learning game", "category": "المدرسة والتعليم",
        "angle": "ألعاب حساب تعليمية", "include": ("math learning", "educational game", "ألعاب حساب", "تعليم الرياضيات"),
    },
    {
        "topic": "school", "keywords": "educational puzzle learning board", "category": "المدرسة والتعليم",
        "angle": "ألغاز تعليمية", "include": ("educational puzzle", "learning board", "ألغاز تعليمية", "لوح تعليمي"),
    },
    {
        "topic": "school", "keywords": "kids desk organizer school", "category": "المدرسة والتعليم",
        "angle": "تنظيم مكتب الدراسة", "include": ("desk organizer", "stationery organizer", "منظم مكتب", "منظم قرطاسية"),
    },
    {
        "topic": "school", "keywords": "school lunch box reusable", "category": "المدرسة والتعليم",
        "angle": "وجبة مدرسية", "include": ("lunch box", "bento box", "علبة طعام", "لانش بوكس"),
    },
    {
        "topic": "school", "keywords": "study planner whiteboard", "category": "المدرسة والتعليم",
        "angle": "تنظيم المذاكرة", "include": ("study planner", "weekly planner", "منظم مذاكرة", "لوحة تخطيط"),
    },

]
# استبعاد الخردة والمنتجات الحساسة أو ضعيفة النية الشرائية حتى لو ظهر لها خصم مرتفع.
# فلترة محافظة مبنية على قوائم هيئة الزكاة والضريبة والجمارك السعودية.
# المصادر الرسمية:
# https://zatca.gov.sa/ar/RulesRegulations/Taxes/Pages/customs-individual/Prohibited-goods.aspx
# https://eservices.zatca.gov.sa/sites/sc/ar/CustomsGuideNew/RestrictedGoods/Pages/Pages/LandingPage.aspx
# لا يمكن للنص وحده إثبات الفسح النظامي؛ لذلك تُستبعد أيضاً السلع عالية الخطورة
# التي تحتاج عادةً موافقة أو ترخيصاً قبل إدخالها إلى المملكة.
SAUDI_COMPLIANCE_BLOCKS = {
    "أسلحة أو ذخائر": (
        "firearm", "airsoft", "bb gun", "pellet gun", "pistol", "rifle",
        "ammunition", "bullet", "crossbow", "slingshot", "brass knuckle",
        "switchblade", "butterfly knife", "combat knife", "tactical knife",
        "سلاح", "مسدس", "بندقية", "ذخيرة", "رصاص", "قوس نشاب", "قبضة حديدية",
        "سكين فراشة", "سكين قتالي",
    ),
    "صواعق أو مسيلات دموع": (
        "stun gun", "taser", "electric shock weapon", "pepper spray", "tear gas",
        "صاعق كهربائي", "مسدس صاعق", "رذاذ فلفل", "مسيل دموع",
    ),
    "ألعاب نارية أو متفجرات": (
        "firework", "firecracker", "pyrotechnic", "explosive", "detonator",
        "ألعاب نارية", "مفرقعات", "متفجرات", "صاعق تفجير",
    ),
    "كاميرا سرية أو تنصت": (
        "spy camera", "hidden camera", "camera pen", "camera glasses", "camera watch",
        "eavesdropping device", "audio bug", "gsm listening",
        "كاميرا خفية", "كاميرا سرية", "قلم بكاميرا", "نظارة بكاميرا",
        "ساعة بكاميرا", "جهاز تنصت",
    ),
    "جهاز اتصالات أو مراقبة مقيّد": (
        "signal jammer", "gps jammer", "mobile jammer", "radar detector",
        "speed camera detector", "satellite internet receiver", "cctv camera",
        "security camera", "wifi security camera", "quadcopter drone", "camera drone",
        "مشوش إشارة", "مشوش gps", "كاشف رادار", "كاشف كاميرا سرعة",
        "مستقبل إنترنت فضائي", "كاميرا مراقبة", "طائرة درون", "طائرة بدون طيار",
    ),
    "ليزر غير واضح القدرة": (
        "high power laser", "burning laser", "laser pointer", "blue laser pen",
        "ليزر عالي القدرة", "ليزر حارق", "مؤشر ليزر", "قلم ليزر أزرق",
    ),
    "منتجات جنسية أو مخلة": (
        "sex toy", "adult toy", "vibrator", "dildo", "masturbator",
        "penis enlargement", "pornographic", "erotic toy",
        "أداة جنسية", "لعبة جنسية", "جهاز جنسي", "تكبير القضيب", "مواد إباحية",
    ),
    "مخدرات أو مسكرات أو تبغ": (
        "cannabis", "marijuana", "hashish", "alcohol distiller", "wine making kit",
        "vape", "e-cigarette", "nicotine pouch", "chewing tobacco",
        "قنب", "حشيش", "جهاز تقطير كحول", "صناعة النبيذ", "سيجارة إلكترونية",
        "فيب", "نيكوتين", "تبغ مضغ",
    ),
    "دواء أو مستحضر عالي المخاطر غير قابل للتحقق": (
        "abortion pill", "sexual enhancement", "male enhancement", "slimming capsule",
        "weight loss pill", "herbal capsule", "diet pill",
        "حبوب إجهاض", "مقوي جنسي", "منشط جنسي", "حبوب تخسيس", "كبسولات أعشاب",
    ),
    "عملة مزورة أو مقلدة": (
        "counterfeit money", "fake banknote", "prop money", "replica currency",
        "عملة مزورة", "نقود مزيفة", "أوراق نقدية مقلدة",
    ),
    "أغذية محظورة واضحة": (
        "pork meat", "pork snack", "bacon food", "nutmeg powder",
        "لحم خنزير", "منتج خنزير", "مسحوق جوز الطيب",
    ),
}

# استبعاد الخردة والمنتجات ضعيفة النية الشرائية حتى إن لم تكن محظورة.
ALIEXPRESS_BLOCK_TERMS = {
    "حبوب", "دواء", "أدوية", "طبي", "طبية", "أسنان", "تخسيس", "جنس", "بالغين",
    "مصيدة حشرات", "بعوض", "ذباب", "طارد الحشرات",
    "ملصق", "ستيكر", "حلقة معدنية", "لوحة معدنية", "قطعة غيار", "بديل",
    "تعليقة", "سلسلة مفاتيح", "تاتو", "وشم",
    "pill", "medicine", "medical", "dental", "weight loss", "adult",
    "mosquito", "insect trap", "sticker", "metal plate", "replacement", "spare part",
    "keychain", "charm", "tattoo", "grill brush", "فرشاة شواء",
}


def _saudi_title_contains(title: str, term: str) -> bool:
    phrase = str(term or "").lower().strip()
    if not phrase:
        return False
    if re.fullmatch(r"[a-z0-9 -]+", phrase):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", title))
    return phrase in title


def saudi_product_block_reason(title: object) -> str:
    """يعيد سبب الاستبعاد عند تطابق منتج مع فئة ممنوعة/مقيدة عالية الخطورة."""
    normalized = re.sub(r"\s+", " ", str(title or "").lower()).strip()
    if not normalized:
        return ""
    # كلمة gun وحدها تُحجب إلا عند وضوح أنها أداة منزلية غير سلاح.
    if _saudi_title_contains(normalized, "gun") and not any(
        safe in normalized for safe in ("heat gun", "glue gun", "massage gun", "nail gun", "spray gun")
    ):
        return "سلاح أو منتج مشابه للسلاح"
    for reason, terms in SAUDI_COMPLIANCE_BLOCKS.items():
        if any(_saudi_title_contains(normalized, term) for term in terms):
            return reason
    return ""


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


# تصنيف موحّد بين الموقع، أداة الإضافة، لوحة الإدارة وبوت Telegram.
CATEGORY_KEYWORDS = {
    "الترفيه المنزلي": ["بروجكتر", "بروجكتور", "جهاز عرض", "تلفزيون", "تلفاز", "سينما منزلية", "projector", "home cinema", "home theater", "smart tv", "qled tv", "television", "byintek", "tcl"],
    "التنظيف والمنظفات": ["صابون", "منظف", "منظفات", "غسيل", "مسحوق غسيل", "مبيض", "كلور", "مطهر", "dish soap", "laundry soap", "detergent", "cleaner", "bleach", "washing powder", "disinfectant"],
    "الأزياء والأحذية": ["بنطلون", "جينز", "قميص", "فستان", "حذاء", "شوز", "سنيكرز", "صندل", "بوت", "عباية", "ملابس", "جوارب", "جاكيت", "pants", "trousers", "jeans", "shirt", "dress", "shoe", "sneaker", "sandals", "boots", "abaya", "clothing", "fashion"],
    "المطبخ والأجهزة المنزلية": ["مطبخ", "مقلاة", "قدر", "قلاية", "خلاط", "ماكينة قهوة", "اسبريسو", "فرن", "ثلاجة", "غسالة صحون", "kitchen", "cookware", "pan", "pot", "air fryer", "blender", "coffee maker", "espresso machine", "oven", "fridge", "refrigerator", "dishwasher"],
    "الأثاث والديكور": ["أثاث", "اثاث", "كنب", "كرسي", "طاولة", "مرتبة", "خزانة", "ديكور", "سجاد", "furniture", "sofa", "chair", "table", "mattress", "cabinet", "decor", "rug"],
    "الإلكترونيات": ["سماعة", "سماعات", "شاحن", "كيبل", "كابل", "لابتوب", "حاسوب", "جوال", "هاتف", "ساعة ذكية", "شاشة", "كاميرا", "باور بانك", "تابلت", "headphone", "earbud", "charger", "laptop", "phone", "watch", "camera", "monitor", "tablet", "usb", "ssd", "speaker"],
    "المنزل": ["مكنسة", "مكواة", "سرير", "وسادة", "إضاءة", "مصباح", "vacuum", "pillow", "lamp", "home", "organizer", "storage box", "hanger", "rack", "blanket", "curtain"],
    "السيارة": ["سيارة", "سيارات", "كاربلاي", "مركبة", "carplay", "car", "vehicle", "dashboard", "dashcam"],
    "السفر": ["سفر", "أمتعة", "شنطة سفر", "منظم سفر", "travel", "luggage", "packing", "trip"],
    "الرحلات والبحر والتخييم": ["رحلات برية", "تخييم", "خيمة", "هايكنج", "صيد", "بحر", "قارب", "كاياك", "شاطئ", "نزهة", "camp", "camping", "tent", "hiking", "fishing", "marine", "boat", "kayak", "beach", "picnic"],
    "الحدائق والزراعة": ["حديقة", "حدائق", "زراعة", "نبات", "نظام ري", "خرطوم ري", "تقليم", "بذور", "garden", "gardening", "plant", "watering", "pruning", "lawn", "seed"],
    "الجمال والعناية": ["مكياج", "تجميل", "بشرة", "شعر", "أظافر", "حلاقة", "استشوار", "عطر", "makeup", "beauty", "skincare", "cosmetic", "hair", "nail", "clipper", "perfume"],
    "الصحة والعناية": ["إسعافات", "اسعافات", "ضماد", "ميزان حرارة", "ضغط الدم", "طبي", "صحي", "first aid", "bandage", "thermometer", "blood pressure", "orthopedic", "hearing aid"],
    "البقالة والمشروبات": ["قهوة", "شاي", "أرز", "ارز", "مكرونة", "وجبة", "شوكولاتة", "عصير", "بهارات", "غذاء", "طعام", "coffee", "tea", "rice", "pasta", "snack", "chocolate", "juice", "spice", "food"],
    "الرياضة": ["رياضة", "تمارين", "لياقة", "يوغا", "جري", "دمبل", "sport", "fitness", "exercise", "yoga", "running", "dumbbell"],
    "الأطفال": ["طفل", "أطفال", "رضيع", "حفاض", "عربة أطفال", "baby", "kids", "child", "toddler", "diaper", "stroller"],
    "الألعاب": ["لعبة", "ألعاب", "أحجية", "دمية", "مكعبات", "ريموت كنترول", "toy", "puzzle", "doll", "building blocks", "board game", "remote control"],
    "الحيوانات الأليفة": ["قطط", "كلاب", "حيوانات", "قطة", "كلب", "pet", "cat", "dog", "grooming"],
    "الأدوات والهوايات": ["دريل", "مثقاب", "عدة", "مفاتيح", "أدوات", "ليزر", "صيانة", "drill", "wrench", "tool", "laser level", "ratchet", "workshop"],
    "المدرسة والقرطاسية": ["مدرسة", "طالب", "قلم", "دفتر", "حقيبة مدرسية", "تعليم", "قرطاسية", "school", "student", "pencil", "notebook", "school backpack", "learning", "education", "stationery"],
    "الكتب والمكتب": ["كتاب", "رواية", "مجلة", "مكتب", "حامل مستندات", "book", "novel", "magazine", "office desk", "document holder"],
    "الساعات والمجوهرات": ["ساعة يد", "مجوهرات", "قلادة", "سوار", "خاتم", "نظارة شمسية", "wrist watch", "jewelry", "jewellery", "necklace", "bracelet", "ring", "sunglasses"],
    "تسوق متنوع": [],
}

CATEGORY_ALIASES = {
    "الموضة": "الأزياء والأحذية",
    "الحدائق": "الحدائق والزراعة",
    "البحر والصيد": "الرحلات والبحر والتخييم",
    "التخييم": "الرحلات والبحر والتخييم",
    "المدرسة والتعليم": "المدرسة والقرطاسية",
}
CATEGORY_PRIORITY = (
    "الترفيه المنزلي", "التنظيف والمنظفات", "الأزياء والأحذية",
    "المطبخ والأجهزة المنزلية", "الأثاث والديكور", "المدرسة والقرطاسية",
    "الكتب والمكتب", "الألعاب", "الحيوانات الأليفة", "الأطفال",
    "الجمال والعناية", "الصحة والعناية", "البقالة والمشروبات",
    "الرحلات والبحر والتخييم", "الحدائق والزراعة", "الرياضة",
    "الأدوات والهوايات", "السيارة", "السفر", "الساعات والمجوهرات",
    "الإلكترونيات", "المنزل",
)


def _category_keyword_matches(text: str, keyword: str) -> bool:
    """يطابق كلمة/عبارة كاملة كي لا يخلط مثلاً بين «شعر» و«مستشعر»."""
    phrase = str(keyword or "").casefold().strip()
    if not phrase:
        return False
    edge = r"A-Za-z0-9\u0600-\u06FF"
    return bool(
        re.search(
            rf"(?<![{edge}]){re.escape(phrase)}(?![{edge}])",
            text,
            flags=re.IGNORECASE,
        )
    )


def classify(title: str) -> str:
    low = str(title or "").casefold()
    for cat in CATEGORY_PRIORITY:
        if any(_category_keyword_matches(low, word) for word in CATEGORY_KEYWORDS[cat]):
            return cat
    return "تسوق متنوع"


def normalize_category(value: object, title: str = "") -> str:
    name = str(value or "").strip()
    name = CATEGORY_ALIASES.get(name, name)
    return name if name in CATEGORY_KEYWORDS else classify(title)


GENERIC_PRODUCT_TITLES = {
    "amazon", "amazon.sa", "amazon sa", "www.amazon.sa",
    "aliexpress", "aliexpress.com", "product", "منتج",
}


def normalize_catalog_title(deal: dict) -> str:
    """ينظف عنوان الكتالوج ويستعيد عنواناً مفيداً من الوصف عند وجود اسم متجر عام."""
    title = re.sub(r"\s+", " ", str(deal.get("title") or "")).strip()
    if title.casefold() not in GENERIC_PRODUCT_TITLES:
        return title[:140]

    description = re.sub(r"\s+", " ", str(deal.get("description") or "")).strip()
    candidate = re.sub(
        r"^خصم\s+\d{1,2}\s*[٪%]\s+على\s+",
        "",
        description,
        flags=re.IGNORECASE,
    )
    candidate = re.split(r"\s+[—–]\s+", candidate, maxsplit=1)[0].strip(" .:-")
    if len(candidate) < 8 or candidate.casefold() in GENERIC_PRODUCT_TITLES:
        return ""
    return candidate[:140]


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
        "category": normalize_category(raw.get("category"), title),
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
            # لا نسجل جسم رد المصادقة حتى لا يظهر أي تفصيل حساس في GitHub Actions.
            print(f"[creators] فشل التوكن HTTP {resp.status_code}")
            return None
        token = resp.json().get("access_token")
        if not token:
            print("[creators] استجابة التوكن بلا access_token")
        return token
    except (requests.RequestException, ValueError) as exc:
        print(f"[creators] خطأ التوكن: {type(exc).__name__}")
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
                print(f"[creators] getItems HTTP {resp.status_code}")
                continue
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[creators] خطأ getItems: {type(exc).__name__}")
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
    """يقرأ المنتجات التي اختارها المالك يدوياً فقط.

    الصيغ المقبولة داخل aliexpress_products.json:
    - رابط أو رقم منتج كنص.
    - كائن يحوي product_id أو url، وتصنيفاً اختيارياً.

    لا تُنسخ النتائج المكتشفة آلياً من deals.json إلى هذه القائمة؛ وإلا تتحول
    المنتجات الآلية القديمة إلى اختيارات دائمة ولا يستطيع التدوير حذفها.
    """
    try:
        data = json.loads(ALIEXPRESS_WATCHLIST_PATH.read_text(encoding="utf-8"))
        entries = data if isinstance(data, list) else data.get("products", [])
    except (FileNotFoundError, json.JSONDecodeError):
        entries = []

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
                "category": normalize_category(category) if category else None,
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
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        # التوقيع والطابع الزمني يجب تجديدهما في كل محاولة.
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
            if response.status_code == 429 and attempt < max_attempts:
                wait_seconds = 1.25 * attempt + random.random() * 0.5
                print(
                    f"[aliexpress] حد سرعة HTTP 429 — إعادة المحاولة "
                    f"{attempt + 1}/{max_attempts} بعد {wait_seconds:.1f}ث"
                )
                time.sleep(wait_seconds)
                continue
            if response.status_code != 200:
                print(f"[aliexpress] {method} HTTP {response.status_code}")
                return None
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[aliexpress] فشل {method}: {exc}")
            return None

        if "error_response" in payload:
            error = payload.get("error_response") or {}
            code = str(error.get("code") or "")
            message = str(error.get("msg") or error.get("sub_msg") or "")
            rate_limited = code == "ApiCallLimit" or "frequency exceeds" in message.lower()
            if rate_limited and attempt < max_attempts:
                wait_seconds = 1.25 * attempt + random.random() * 0.5
                print(
                    f"[aliexpress] تقييد سرعة مؤقت — إعادة المحاولة "
                    f"{attempt + 1}/{max_attempts} بعد {wait_seconds:.1f}ث"
                )
                time.sleep(wait_seconds)
                continue
            print(f"[aliexpress] رفض النداء {method}: {code} — {message}")
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

    return None


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


def _ali_affiliate_url(value: object) -> str:
    """يقبل رابط عمولة AliExpress الرسمي فقط، ولا يقبل رابط المنتج المباشر."""
    url = str(value or "").strip()
    if url.startswith("http://s.click.aliexpress.com/"):
        url = "https://" + url.removeprefix("http://")
    if not url.startswith("https://"):
        return ""
    host = (urlsplit(url).hostname or "").lower()
    if host == "s.click.aliexpress.com":
        return url
    if not (
        host == "aliexpress.com" or host.endswith(".aliexpress.com") or
        host == "aliexpress.us" or host.endswith(".aliexpress.us")
    ):
        return ""
    query = parse_qs(urlsplit(url).query)
    platform = " ".join(query.get("aff_platform", [])).lower()
    if query.get("aff_fcid") and query.get("aff_trace_key") and "api" in platform:
        return url
    return ""


def sanitize_aliexpress(raw: dict) -> dict | None:
    """يحوّل منتج AliExpress إلى مخطط الموقع؛ الخصم اختياري وليس شرط قبول."""
    product_id = _ali_product_id(raw.get("product_id"))
    raw_title = str(raw.get("title") or "")
    block_reason = saudi_product_block_reason(raw_title)
    if block_reason:
        print(f"[compliance] حجب AliExpress {product_id or 'unknown'}: {block_reason}")
        return None
    title = _ali_click_title(raw_title, raw.get("angle"))
    image = str(raw.get("image", "")).strip()
    url = _ali_affiliate_url(raw.get("url"))
    currency = str(raw.get("currency", "")).strip().upper()

    if not product_id or len(title) < 8 or not image.startswith("https://"):
        return None
    if not url:
        return None
    if currency and currency not in {"SAR", "USD"}:
        print(
            f"[aliexpress] تجاهل {product_id}: العملة {currency} غير مدعومة"
        )
        return None

    original = _ali_number(raw.get("original_price"))
    current = _ali_number(raw.get("sale_price"))
    discount = _ali_discount(raw.get("discount_percent"))
    if not original and current > 0:
        original = current / (1 - discount / 100) if 5 <= discount <= 95 else current
    if not discount and original > current > 0:
        discount = round((original - current) / original * 100)
    if original <= 0:
        return None
    discount = max(0, min(95, discount))
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
        **({"sales_volume": int(raw.get("sales_volume"))} if raw.get("sales_volume") else {}),
        **({"rating_percent": round(float(raw.get("rating_percent")), 1)} if raw.get("rating_percent") else {}),
        "category": normalize_category(category, title),
        **({"auto_discovered": True} if raw.get("auto_discovered") else {}),
        **({"angle": str(raw.get("angle"))[:40]} if raw.get("angle") else {}),
        **({"rank_score": int(raw.get("rank_score"))} if raw.get("rank_score") else {}),
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
        promotion = _ali_affiliate_url(item.get("promotion_link"))
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


def _ali_display_title(value: object) -> str:
    """عنوان صادق ومقروء مشتق من عنوان AliExpress نفسه، بلا عبارات تسويقية زائدة."""
    title = re.sub(r"\s+", " ", str(value or "")).strip()
    title = re.sub(
        r"(?i)\b(?:new|hot sale|best seller|free shipping|dropshipping|202[0-9])\b",
        " ",
        title,
    )
    title = re.sub(r"^(?:\d+\s*)?(?:قطعة|قطع)\s*[/،,-]?\s*", "", title)
    parts: list[str] = []
    for part in re.split(r"[|;،,]+", title):
        part = re.sub(r"\s+", " ", part).strip(" -–—./")
        if len(part) < 3 or part.lower() in {item.lower() for item in parts}:
            continue
        parts.append(part)
        if len(" — ".join(parts)) >= 88 or len(parts) >= 3:
            break
    compact = " — ".join(parts) if parts else title
    compact = re.sub(r"\s+", " ", compact).strip()
    if len(compact) <= 108:
        return compact
    return compact[:108].rsplit(" ", 1)[0].rstrip(" -–—،,")


def _ali_click_title(value: object, angle: object) -> str:
    """عنوان عربي مختصر وصادق مبني على نوع المنتج بلا مواصفات غير موجودة."""
    raw = str(value or "")
    low = raw.lower()
    labels = {
        "شحن متنقل": "باور بانك مغناطيسي لاسلكي محمول",
        "صناعة المحتوى": "ميكروفون لافالير لاسلكي لصناعة المحتوى",
        "تتبّع ذكي": "متتبع ذكي للأغراض والحقائب",
        "تقنية السيارة": "محوّل CarPlay لاسلكي للسيارة",
        "مكتب وتقنية": "موزع USB-C متعدد المنافذ" + (" مع HDMI 4K" if "4k" in low and "hdmi" in low else ""),
        "منزل ذكي": "مصباح LED لاسلكي بمستشعر حركة",
        "شحن سريع": "شاحن GaN سريع متعدد المنافذ",
        "طوارئ السيارة": "منفاخ إطارات رقمي محمول للسيارة",
        "تنظيم ذكي": "طابعة ملصقات حرارية صغيرة بالبلوتوث",
        "صوت وتقنية": "سماعات أذن لاسلكية بالبلوتوث",
        "صوت محمول": "مكبر صوت بلوتوث محمول",
        "مراقبة ذكية": "كاميرا مراقبة ذكية عبر Wi-Fi",
        "لوحة مفاتيح": "لوحة مفاتيح ميكانيكية للكمبيوتر",
        "ملحقات الكمبيوتر": "فأرة لاسلكية مريحة للكمبيوتر",
        "تحكم ذكي": "مقبس ذكي يعمل عبر Wi-Fi",
        "مكتب ذكي": "مصباح مكتب LED عملي",
        "تصوير ثابت": "مثبت هاتف Gimbal للتصوير",
        "كاميرا السيارة": "كاميرا قيادة للسيارة",
        "طوارئ الطاقة": "جهاز تشغيل بطارية السيارة المحمول",
        "أدوات تقنية": "مفك كهربائي لاسلكي محمول",
        "قياس ذكي": "جهاز قياس مسافات بالليزر",
        "فحص السيارة": "جهاز فحص أعطال السيارة OBD2",
        "تنظيف ذكي": "فرشاة تنظيف كهربائية دوارة متعددة الاستخدامات",
        "مطبخ عملي": "جهاز محمول لإغلاق أكياس الطعام بالحرارة",
        "مطبخ ذكي": "مخفّق حليب كهربائي قابل لإعادة الشحن",
        "سفر أذكى": "ميزان أمتعة رقمي محمول للسفر",
        "منزل عملي": "موزع صابون أوتوماتيكي بدون لمس",
        "تنظيف التقنية": "منفاخ هواء كهربائي لاسلكي لتنظيف الأجهزة",
        "تحضير أسرع": "مفرمة طعام كهربائية صغيرة",
        "مشروبات سريعة": "خلاط محمول قابل لإعادة الشحن",
        "عناية بالملابس": "مزيل وبر كهربائي قابل لإعادة الشحن",
        "سفر عملي": "غلاية كهربائية قابلة للطي للسفر",
        "تنظيف سريع": "مكنسة لاسلكية محمولة للتنظيف السريع",
        "حفظ الطعام": "جهاز تفريغ الهواء وحفظ الطعام",
        "عناية سريعة": "مكواة بخار محمولة للملابس",
        "قهوة منزلية": "مطحنة قهوة كهربائية صغيرة",
        "مطبخ دقيق": "ميزان مطبخ رقمي دقيق",
        "تبريد شخصي": "مروحة رقبة محمولة قابلة للشحن",
        "راحة المنزل": "مرطب هواء صغير يعمل عبر USB",
        "رحلات وتخييم": "مصباح تخييم قابل لإعادة الشحن",
        "تنظيم السفر": "مجموعة منظمات للحقائب والسفر",
        "فتح أسهل": "فتاحة علب كهربائية أوتوماتيكية",
        "قهوة متنقلة": "ماكينة إسبريسو محمولة للسفر",
        "تنظيم الغسيل": "سلة غسيل قابلة للطي",
        "أدوات مدرسية": "مجموعة قرطاسية وأدوات مدرسية للطلاب",
        "تنظيم الأقلام": "مقلمة مدرسية لتنظيم الأقلام والأدوات",
        "حقائب مدرسية": "حقيبة مدرسية للطلاب",
        "تجهيز الدراسة": "براية أقلام كهربائية للدراسة",
        "أدوات هندسية": "طقم أدوات هندسية للطلاب",
        "رسم وتلوين": "مجموعة رسم وتلوين تعليمية",
        "بطاقات تعليمية": "بطاقات تعليمية للمراجعة والتعلّم",
        "تجارب تعليمية": "مجموعة تجارب علمية تعليمية STEM",
        "ألعاب حساب تعليمية": "لعبة تعليمية لتعلّم الحساب",
        "ألغاز تعليمية": "ألغاز ولوح تعليمي للتعلّم",
        "تنظيم مكتب الدراسة": "منظم مكتب للقرطاسية وأدوات الدراسة",
        "وجبة مدرسية": "علبة طعام قابلة لإعادة الاستخدام للمدرسة",
        "تنظيم المذاكرة": "لوحة تخطيط لتنظيم المذاكرة والأسبوع",
    }
    base = labels.get(str(angle or ""))
    if not base:
        return _ali_display_title(raw)

    # عند عرض أكثر من بديل للفكرة نفسها نُظهر علامة/مواصفة حقيقية من عنوان المصدر
    # كي لا تبدو البطاقات مكررة، من دون اختراع أي خاصية تسويقية.
    generic = {
        "new", "mini", "smart", "wireless", "portable", "electric", "digital",
        "rechargeable", "automatic", "cordless", "fast", "with", "for", "the",
        "bluetooth", "usb", "type", "home", "travel", "car", "phone",
    }
    details: list[str] = []
    brands = re.findall(r"\b[A-Z][A-Za-z0-9-]{2,}\b", raw)
    for brand in brands:
        if brand.lower() not in generic and not re.fullmatch(r"\d+", brand):
            details.append(brand[:24])
            break
    specs = re.findall(
        r"(?i)\b(?:\d+(?:\.\d+)?\s?(?:W|V|L|ML|mAh|RPM|dB|inch)|Bluetooth\s?\d(?:\.\d)?|USB-C|Type-C|4K)\b",
        raw,
    )
    for spec in specs:
        clean_spec = re.sub(r"\s+", "", spec)
        if clean_spec.lower() not in {item.lower() for item in details}:
            details.append(clean_spec[:20])
        if len(details) >= 2:
            break
    if not details:
        source_hint = _ali_display_title(raw)
        if source_hint and source_hint.lower() != base.lower():
            details.append(source_hint[:42].rstrip(" -–—،,"))
    return f"{base} — {' · '.join(details)}" if details else base


def _ali_sale_price_sar(product: dict) -> float:
    value = _ali_number(
        product.get("target_sale_price")
        or product.get("target_app_sale_price")
        or product.get("sale_price")
        or product.get("app_sale_price")
    )
    currency = str(
        product.get("target_sale_price_currency")
        or product.get("sale_price_currency")
        or ALIEXPRESS_TARGET_CURRENCY
    ).upper()
    return value * ALIEXPRESS_USD_TO_SAR if currency == "USD" else value


def _ali_matches_focus(product: dict, focus: dict) -> bool:
    title = str(product.get("product_title") or "").lower()

    def contains(term: object) -> bool:
        phrase = str(term or "").lower().strip()
        if not phrase:
            return False
        # الكلمات الإنجليزية القصيرة تحتاج حدود كلمة حتى لا تُحجب Toyota بسبب toy مثلاً.
        if re.fullmatch(r"[a-z0-9 -]+", phrase):
            return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", title))
        return phrase in title

    if saudi_product_block_reason(title):
        return False
    if any(contains(term) for term in ALIEXPRESS_BLOCK_TERMS):
        return False
    return any(contains(term) for term in focus.get("include", ()))


def _ali_focus_score(product: dict, focus: dict) -> float:
    """درجة الرواج: المبيعات والتقييم أولاً، ثم وضوح صلة المنتج بعبارة البحث."""
    volume = int(_ali_number(product.get("lastest_volume")))
    rating = _ali_number(product.get("evaluate_rate"))
    title = str(product.get("product_title") or "").lower()
    relevant = sum(
        1
        for term in focus.get("include", ())
        if str(term or "").lower().strip() in title
    )
    return round(
        rating * 1.10
        + min(math.log10(volume + 1) * 30, 120)
        + min(relevant, 4) * 8,
        2,
    )


def _ali_is_near_duplicate(
    title: object,
    selected: list[dict],
    angle: str = "",
) -> bool:
    """يمنع عرض عدة نسخ متشابهة جداً من المنتج نفسه."""
    tokens = _ali_title_tokens(title)
    if len(tokens) < 3:
        return False
    for item in selected:
        other = _ali_title_tokens(item.get("product_title"))
        if len(other) < 3:
            continue
        overlap = len(tokens & other) / min(len(tokens), len(other))
        same_angle = angle and angle == str(item.get("_overly_angle") or "")
        # داخل الفكرة نفسها نسمح ببدائل حقيقية، لكن نرفض النسخ شبه المتطابقة.
        # وبين الأفكار المختلفة نستخدم حداً أعلى حتى لا نحذف منتجين لمجرد تشابه كلمات عامة.
        threshold = 0.86 if same_angle else 0.94
        if overlap >= threshold:
            return True
    return False


def _ali_balanced_selection(candidates: list[dict], limit: int) -> list[dict]:
    """يغطي كل اتجاه رائج أولاً، ثم يملأ القائمة بالأعلى مبيعاً وتقييماً."""
    ranked = sorted(
        candidates,
        key=lambda item: float(item.get("_overly_score", 0)),
        reverse=True,
    )
    selected: list[dict] = []
    selected_ids: set[str] = set()
    angle_counts: dict[str, int] = {}
    used_angles: set[str] = set()

    # الجولة الأولى: منتج قوي واحد على الأقل من كل اتجاه متاح.
    for product in ranked:
        if len(selected) >= limit:
            break
        product_id = _ali_product_id(product.get("product_id"))
        if not product_id or product_id in selected_ids:
            continue
        angle = str(product.get("_overly_angle") or "")
        if angle and angle in used_angles:
            continue
        if _ali_is_near_duplicate(product.get("product_title"), selected, angle):
            continue
        selected.append(product)
        selected_ids.add(product_id)
        if angle:
            used_angles.add(angle)
            angle_counts[angle] = 1

    # الجولة الثانية: الأعلى رواجاً بلا حصة ثابتة لقسم بعينه.
    for product in ranked:
        if len(selected) >= limit:
            break
        product_id = _ali_product_id(product.get("product_id"))
        if not product_id or product_id in selected_ids:
            continue
        angle = str(product.get("_overly_angle") or "")
        if angle and angle_counts.get(angle, 0) >= ALIEXPRESS_MAX_PER_ANGLE:
            continue
        if _ali_is_near_duplicate(product.get("product_title"), selected, angle):
            continue
        selected.append(product)
        selected_ids.add(product_id)
        if angle:
            angle_counts[angle] = angle_counts.get(angle, 0) + 1
    return selected


def discover_aliexpress_products() -> list[dict]:
    """يكتشف المنتجات الرائجة من مختلف أقسام AliExpress للشحن إلى السعودية.

    يستخدم product.query المتاحة للتطبيق مع ترتيب المبيعات، ويبحث بعبارات متنوعة.
    الخصم ليس شرطاً؛ الأولوية لعدد المبيعات والتقييم والصلة، مع منع التكرار.
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
        "page_size": ALIEXPRESS_QUERY_PAGE_SIZE,
        "platform_product_type": "ALL",
        "sort": "LAST_VOLUME_DESC",
        "target_currency": ALIEXPRESS_TARGET_CURRENCY,
        "target_language": ALIEXPRESS_TARGET_LANGUAGE,
        "tracking_id": ALIEXPRESS_TRACKING_ID,
        "ship_to_country": ALIEXPRESS_SHIP_TO_COUNTRY,
    }
    discovery_queries: list[dict] = (
        ALIEXPRESS_FOCUS_QUERIES
        if ALIEXPRESS_FOCUS_DISCOVERY
        else [{"topic": "popular", "keywords": "", "category": "الإلكترونيات", "angle": "الأكثر رواجاً", "include": ()}]
    )
    candidates_by_id: dict[str, dict] = {}
    returned_count = 0
    for focus in discovery_queries:
        topic = str(focus.get("topic") or "popular")
        keywords = str(focus.get("keywords") or "")
        category = str(focus.get("category") or "الإلكترونيات")
        angle = str(focus.get("angle") or category)
        accepted_for_query = 0
        returned_for_query = 0
        for page_no in range(1, ALIEXPRESS_QUERY_PAGES + 1):
            query = {**base_query, "page_no": page_no}
            if keywords:
                query["keywords"] = keywords
            result = aliexpress_api_call(
                "aliexpress.affiliate.product.query",
                query,
            )
            products = _ali_list((result or {}).get("products"), "product")
            returned_count += len(products)
            returned_for_query += len(products)
            for product in products:
                product_id = _ali_product_id(product.get("product_id"))
                volume = int(_ali_number(product.get("lastest_volume")))
                rating = _ali_number(product.get("evaluate_rate"))
                price_sar = _ali_sale_price_sar(product)
                if not product_id:
                    continue
                if volume < ALIEXPRESS_AUTO_MIN_VOLUME:
                    continue
                # التقييم المفقود لم يعد يمر؛ الأفضل عرض عدد أقل بجودة موثوقة.
                if rating < ALIEXPRESS_AUTO_MIN_RATING:
                    continue
                if ALIEXPRESS_FOCUS_DISCOVERY and not _ali_matches_focus(product, focus):
                    continue
                if not (ALIEXPRESS_AUTO_MIN_PRICE_SAR <= price_sar <= ALIEXPRESS_AUTO_MAX_PRICE_SAR):
                    continue
                candidate = {
                    **product,
                    "auto_discovered": True,
                    "_overly_topic": topic,
                    "_overly_category": category,
                    "_overly_angle": angle,
                }
                candidate["_overly_score"] = _ali_focus_score(candidate, focus)
                previous = candidates_by_id.get(product_id)
                if previous is None or candidate["_overly_score"] > previous["_overly_score"]:
                    candidates_by_id[product_id] = candidate
                    accepted_for_query += 1
            # لا نطلب صفحات إضافية إذا انتهت النتائج مبكراً.
            if len(products) < ALIEXPRESS_QUERY_PAGE_SIZE:
                break
            time.sleep(0.25)
        label = category
        print(
            f"[aliexpress] {label} / {keywords or 'عام'}: "
            f"{accepted_for_query} من {returned_for_query} اجتاز الجودة"
        )
        time.sleep(0.35)

    accepted = _ali_balanced_selection(
        list(candidates_by_id.values()),
        ALIEXPRESS_AUTO_LIMIT,
    )
    category_counts: dict[str, int] = {}
    for item in accepted:
        item_category = str(item.get("_overly_category") or "غير مصنف")
        category_counts[item_category] = category_counts.get(item_category, 0) + 1
    category_summary = "، ".join(
        f"{name} {count}"
        for name, count in sorted(category_counts.items(), key=lambda pair: pair[1], reverse=True)
    )

    print(
        f"[aliexpress] اكتشاف رائج شامل: {len(accepted)} من {returned_count} نتيجة "
        f"({category_summary})"
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
                "evaluate_rate",
                "lastest_volume",
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
    missing_link_sources = []
    for product in raw_products:
        product_id = _ali_product_id(product.get("product_id"))
        source_url = (
            str(product.get("product_detail_url") or "").strip()
            or f"https://www.aliexpress.com/item/{product_id}.html"
        )
        source_urls.append(source_url)
        if not _ali_affiliate_url(product.get("promotion_link")):
            missing_link_sources.append(source_url)
    # أغلب نتائج product.query تعيد رابط العمولة مباشرة؛ لا نستهلك نداءاً إضافياً إلا للناقص.
    link_map = aliexpress_generate_links(missing_link_sources)

    clean: list[dict] = []
    seen: set[str] = set()
    for product, source_url in zip(raw_products, source_urls):
        product_id = _ali_product_id(product.get("product_id"))
        promotion_link = _ali_affiliate_url(product.get("promotion_link"))
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
                "sales_volume": int(_ali_number(product.get("lastest_volume"))),
                "rating_percent": _ali_number(product.get("evaluate_rate")),
                "category": categories.get(product_id) or product.get("_overly_category"),
                "auto_discovered": product.get("auto_discovered"),
                "angle": product.get("_overly_angle"),
                "rank_score": min(99, round(float(product.get("_overly_score") or 0) / 3)),
            }
        )
        if deal and product_id not in seen:
            seen.add(product_id)
            clean.append(deal)

    clean.sort(
        key=lambda deal: (
            int(deal.get("rank_score") or 0),
            int(deal.get("sales_volume") or 0),
        ),
        reverse=True,
    )
    print(f"[aliexpress] {len(clean)} عرض صالح برابط عمولة رسمي")
    return clean[:ALIEXPRESS_AUTO_LIMIT]


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
    merged.sort(
        key=lambda deal: (
            int(deal.get("rank_score") or 0)
            or int(deal.get("discount_percent", 0)) + 48,
            int(deal.get("discount_percent", 0)),
        ),
        reverse=True,
    )
    # 24 خانة احتياطية لأمازون + الحد المستهدف لعروض AliExpress.
    return merged[: MAX_DEALS + ALIEXPRESS_AUTO_LIMIT]


def normalize_existing_deals(existing_raw: list[dict]) -> tuple[list[dict], int, int, int]:
    """يعيد (العروض، المحجوب، المصنّف من جديد، العناوين المُصلحة)."""
    existing: list[dict] = []
    blocked = 0
    recategorized = 0
    repaired_titles = 0
    for deal in existing_raw:
        if not isinstance(deal, dict):
            continue
        title = normalize_catalog_title(deal)
        if not title:
            blocked += 1
            print(f"[catalog] إزالة منتج بلا عنوان مفيد {_deal_key(deal)}")
            continue
        reason = saudi_product_block_reason(title)
        if reason:
            blocked += 1
            print(f"[compliance] إزالة منتج موجود {_deal_key(deal)}: {reason}")
            continue
        normalized = dict(deal)
        if title != re.sub(r"\s+", " ", str(deal.get("title") or "")).strip():
            normalized["title"] = title
            repaired_titles += 1
        original_category = str(deal.get("category") or "").strip()
        category = normalize_category(original_category, title)
        # قوائم AliExpress الموجّهة تحمل تصنيفاً سياقياً أدق من تخمين كلمات العنوان.
        # أما سجل Amazon اليدوي أو التصنيف العام فيصحح من العنوان عند الإمكان.
        should_infer = (
            str(deal.get("store") or "").strip().lower() == "amazon"
            or bool(ASIN_RE.match(str(deal.get("asin") or "").strip().upper()))
            or category == "تسوق متنوع"
            or original_category not in CATEGORY_KEYWORDS
        )
        if should_infer:
            inferred_category = classify(title)
            if inferred_category != "تسوق متنوع":
                category = inferred_category
        if category != str(deal.get("category") or ""):
            normalized["category"] = category
            recategorized += 1
        existing.append(normalized)
    return existing, blocked, recategorized, repaired_titles


# ----------------------------------------------------------------------------
# الكتابة الآمنة
# ----------------------------------------------------------------------------
def write_output(deals: list[dict], source: str = DEALS_URL) -> bool:
    """يكتب deals.json ذريًا فقط إذا تغير المحتوى الفعلي، ويعيد هل كتب الملف."""
    if OUTPUT_PATH.exists():
        try:
            current = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            if (
                current.get("source") == source
                and current.get("count") == len(deals)
                and current.get("deals") == deals
            ):
                print(f"[write] unchanged — keeping {OUTPUT_PATH}")
                return False
        except (OSError, json.JSONDecodeError):
            # إذا كان الملف تالفًا نعيد بناءه بالكتابة الذرية أدناه.
            pass

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
    return True


# ----------------------------------------------------------------------------
# نشر تيليجرام: المنتج الجديد فوراً + اختياران يومياً + منع التكرار
# ----------------------------------------------------------------------------
def affiliate_link(asin: str) -> str:
    return f"https://www.amazon.sa/dp/{asin}/?tag={AFFILIATE_TAG}"


def tg_escape(text: object) -> str:
    """تهريب الأحرف الخاصة بـ HTML parse_mode في تيليجرام."""
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def telegram_deal_key(deal: dict) -> str:
    """معرّف ثابت يعمل مع Amazon وAliExpress ويُستخدم لمنع التكرار."""
    return _deal_key(deal)


def telegram_deal_url(deal: dict) -> str:
    if str(deal.get("store", "amazon")).lower() == "aliexpress":
        return str(deal.get("url") or "").strip()
    return affiliate_link(str(deal.get("asin") or "").strip().upper())


def telegram_store_label(deal: dict) -> str:
    return "AliExpress" if str(deal.get("store", "amazon")).lower() == "aliexpress" else "Amazon.sa"


def telegram_description(deal: dict) -> str:
    """وصف سعودي خفيف من بيانات المنتج المتاحة، من دون تكرار العنوان أو اختراع مواصفات."""
    explicit = re.sub(r"\s+", " ", str(deal.get("description") or "")).strip()
    category = str(deal.get("category") or "العروض المتنوعة").strip()
    angle = str(deal.get("angle") or "").strip()
    title = re.sub(r"\s+", " ", str(deal.get("title") or "")).strip()
    low = title.lower()

    boilerplate = ("منتج ضمن قسم", "منتج معروض في أوفرلي ضمن قسم")
    if explicit and not explicit.startswith(boilerplate):
        return explicit.rstrip(" .،")[:220] + "."

    # أوصاف محددة عندما يدل العنوان نفسه بوضوح على الاستخدام.
    if category == "المدرسة والتعليم":
        return "ينفع للمدرسة والمذاكرة، ويساعد على ترتيب وقت الدراسة وأدواتها بشكل عملي."
    if any(term in low for term in ("مصباح تخييم", "camping lantern", "camping light")):
        return "ينفع للرحلات والجلسات البرية، وسهل للحمل والتخزين."
    if any(term in low for term in ("باور بانك", "power bank")):
        return "ينفع للشحن وأنت برا البيت، وخيار عملي للدوام والسفر."
    if any(term in low for term in ("منظم", "organizer", "storage")):
        return "يساعدك ترتب أغراضك وتستفيد من المساحة بشكل عملي."
    if any(term in low for term in ("مكنسة", "vacuum", "cleaning", "تنظيف")):
        return "يسهّل عليك التنظيف اليومي ويوفر عليك وقت وجهد."
    if any(term in low for term in ("بروجكتر", "projector")):
        return "ينفع لجلسات الأفلام والمباريات في البيت، وتفاصيله كاملة في المتجر."
    if any(term in low for term in ("carplay", "سيارة", "car ")):
        return "خيار عملي للسيارة والاستخدام اليومي، وتأكد من التوافق قبل الطلب."
    if any(term in low for term in ("سفر", "travel", "luggage")):
        return "ينفع للسفر والتنقل، وفكرته عملية للي يحب يرتب رحلته."
    if any(term in low for term in ("حديقة", "garden", "plant", "ري ")):
        return "يفيدك في شغل الحديقة والعناية بالنباتات بشكل أسهل."
    if any(term in low for term in ("صيد", "fishing", "قارب", "marine")):
        return "خيار عملي لطلعات البحر والصيد، وتفاصيل استخدامه موضحة في المتجر."

    if angle:
        return f"يفيدك في {angle}، واخترناه لك من الخيارات الرائجة في {category}."
    return f"خيار عملي من {category} يستاهل تشوف تفاصيله."


def telegram_category_emoji(deal: dict) -> str:
    category = str(deal.get("category") or "")
    return {
        "التخييم": "🏕️",
        "الحدائق": "🌿",
        "البحر والصيد": "🎣",
        "الترفيه المنزلي": "📺",
        "الإلكترونيات": "🔌",
        "السيارة": "🚗",
        "السفر": "🧳",
        "المنزل": "🏠",
        "الموضة": "👟",
        "الجمال والعناية": "✨",
        "الرياضة": "🏋️",
        "المدرسة والتعليم": "🎒",
        "الأطفال": "🧸",
        "الحيوانات الأليفة": "🐾",
        "الأدوات": "🛠️",
    }.get(category, "🛍️")


def load_posted_state() -> dict:
    """يقرأ سجل تيليجرام ويزيل طابور النشر الجماعي القديم عند الترقية."""
    empty = {
        "version": 4,
        "posted": {},
        "pending": [],
        "ever_posted": [],
        "featured_day": "",
        "featured_count": 0,
        "last_featured_at": "",
    }
    try:
        data = json.loads(POSTED_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return empty

    if not isinstance(data, dict):
        return empty
    if isinstance(data.get("posted"), dict):
        posted = data.get("posted", {})
        ever_posted = data.get("ever_posted")
        if not isinstance(ever_posted, list):
            ever_posted = list(posted.keys())
        try:
            version = int(data.get("version") or 0)
        except (TypeError, ValueError):
            version = 0
        # الإصدارات الأقدم كانت تحمل مئات منتجات الكتالوج في pending.
        # لا ننقلها؛ من الإصدار 4 لا يحوي pending إلا منتجات جديدة فشل إرسالها.
        pending = (
            data.get("pending", [])
            if version >= 4 and isinstance(data.get("pending"), list)
            else []
        )
        return {
            "version": 4,
            "posted": posted,
            "pending": pending,
            "ever_posted": ever_posted,
            "featured_day": str(data.get("featured_day") or ""),
            "featured_count": int(data.get("featured_count") or 0),
            "last_featured_at": str(data.get("last_featured_at") or ""),
        }

    posted = {}
    for key, value in data.items():
        if isinstance(value, str):
            clean_key = key if ":" in str(key) else f"amazon:{str(key).strip().upper()}"
            posted[clean_key] = value
    empty["posted"] = posted
    empty["ever_posted"] = list(posted.keys())
    return empty


def save_posted_state(state: dict) -> None:
    """يحفظ المنتجات الجديدة المؤجلة وعدّاد المنتجات المميزة اليومي."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=TELEGRAM_STATE_RETENTION_DAYS)
    cleaned = {}
    for key, ts in state.get("posted", {}).items():
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                cleaned[str(key)] = ts
        except (TypeError, ValueError):
            continue

    ever_posted = []
    ever_seen = set()
    for key in [*state.get("ever_posted", []), *cleaned.keys()]:
        key = str(key)
        if key and key not in ever_seen:
            ever_seen.add(key)
            ever_posted.append(key)

    pending = []
    pending_seen = set()
    for key in state.get("pending", []):
        key = str(key)
        if key and key not in pending_seen and key not in ever_seen:
            pending_seen.add(key)
            pending.append(key)

    payload = {
        "version": 4,
        "posted": cleaned,
        "pending": pending[:100],
        "ever_posted": ever_posted[:3000],
        "featured_day": str(state.get("featured_day") or ""),
        "featured_count": max(0, int(state.get("featured_count") or 0)),
        "last_featured_at": str(state.get("last_featured_at") or ""),
    }
    POSTED_STATE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def recently_posted(key: str, posted: dict) -> bool:
    ts = posted.get(key)
    if not ts:
        return False
    try:
        posted_at = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) - posted_at < timedelta(hours=REPOST_COOLDOWN_HOURS)


def format_sar(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def build_caption(deal: dict, mode: str = "new") -> str:
    """بطاقة تيليجرام خفيفة وواضحة، مع الإفصاح الإلزامي المختصر."""
    title = tg_escape(str(deal.get("title") or "")[:150])
    description = tg_escape(telegram_description(deal))
    emoji = telegram_category_emoji(deal)
    sales = int(float(deal.get("sales_volume") or 0))
    rating_percent = float(deal.get("rating_percent") or 0)
    rating = rating_percent / 20 if rating_percent > 5 else rating_percent

    metrics = []
    if sales > 0:
        metrics.append(f"🛒 +{sales:,} طلب")
    if 0 < rating <= 5:
        metrics.append(f"⭐ {rating:.1f}")

    blocks = [
        "⭐ <b>اختيار أوفرلي</b>",
        f"{emoji} <b>{title}</b>",
        description,
    ]
    if metrics:
        blocks.append("  •  ".join(metrics))
    blocks.append("👇 شيّك التفاصيل والسعر الحالي")
    blocks.append("<i>رابط عمولة — السعر النهائي يظهر في المتجر.</i>")
    return "\n\n".join(blocks)


def telegram_retry_after(response: requests.Response) -> int:
    """يقرأ مهلة Telegram الآمنة عند HTTP 429 دون الوثوق بقيمة غير محدودة."""
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        retry_after = int((payload.get("parameters") or {}).get("retry_after") or 1)
    except (TypeError, ValueError):
        retry_after = 1
    return max(1, min(TELEGRAM_MAX_RETRY_AFTER_SECONDS, retry_after))


def telegram_api_request(method: str, payload: dict) -> tuple[bool, bool]:
    """ينفذ نداء Telegram مع احترام retry_after؛ يعيد (نجاح، تقييد سرعة)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    for attempt in range(1, TELEGRAM_API_ATTEMPTS + 1):
        try:
            response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            # لا نطبع نص الاستثناء لأنه قد يحتوي رابط Bot API المتضمن للرمز السري.
            print(f"[telegram] {method} network error: {type(exc).__name__}")
            return False, False

        try:
            response_payload = response.json()
        except ValueError:
            response_payload = {}
        if not isinstance(response_payload, dict):
            response_payload = {}
        if response.status_code == 200 and response_payload.get("ok") is True:
            return True, False

        if response.status_code == 429:
            if attempt >= TELEGRAM_API_ATTEMPTS:
                print(f"[telegram] {method} rate limited after {attempt} attempts")
                return False, True
            wait_seconds = telegram_retry_after(response) + 1
            print(
                f"[telegram] {method} rate limited — retry "
                f"{attempt + 1}/{TELEGRAM_API_ATTEMPTS} after {wait_seconds}s"
            )
            time.sleep(wait_seconds)
            continue

        print(f"[telegram] {method} failed: {response.status_code} {response.text[:160]}")
        return False, False
    return False, False


def send_to_telegram(deal: dict, mode: str = "new") -> bool:
    """يرسل صورة وبطاقة وصفية وزر شراء، مع fallback نصي عند تعذر الصورة."""
    link = telegram_deal_url(deal)
    if not link.startswith("https://"):
        print(f"[telegram] missing product URL: {telegram_deal_key(deal)}")
        return False

    caption = build_caption(deal, mode)
    reply_markup = json.dumps(
        {
            "inline_keyboard": [[
                {"text": f"عرض السعر على {telegram_store_label(deal)}", "url": link}
            ]]
        },
        ensure_ascii=False,
    )
    base_payload = {
        "chat_id": TELEGRAM_CHANNEL,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
    }

    photo_payload = {
        **base_payload,
        "photo": str(deal.get("image") or ""),
        "caption": caption,
    }
    photo_ok, rate_limited = telegram_api_request("sendPhoto", photo_payload)
    if photo_ok:
        return True
    if rate_limited:
        # لا نرسل fallback فوراً عند 429 لأنه يضاعف الضغط؛ يبقى المنتج في pending.
        print(f"[telegram] deferring rate-limited product {telegram_deal_key(deal)}")
        return False

    print(f"[telegram] image unavailable for {telegram_deal_key(deal)} — trying text fallback")
    text_ok, _ = telegram_api_request("sendMessage", {**base_payload, "text": caption})
    return text_ok


def telegram_rank(deal: dict) -> tuple[int, int, int]:
    return (
        int(deal.get("rank_score") or 0),
        int(float(deal.get("sales_volume") or 0)),
        int(deal.get("discount_percent") or 0),
    )


def post_deals_to_telegram(new_deals: list[dict], all_deals: list[dict]) -> None:
    """ينشر الجديد، ثم منتجاً مميزاً واحداً كل ساعتين بحد 10 يومياً."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL:
        print("[telegram] secrets not set — skipping channel posting")
        return

    state = load_posted_state()
    posted = state["posted"]
    ever_posted = {str(key) for key in state.get("ever_posted", []) if str(key)}
    by_key = {
        telegram_deal_key(deal): deal
        for deal in all_deals
        if telegram_deal_key(deal)
    }

    # pending في الإصدار 4 مخصص فقط للمنتجات الجديدة التي فشل إرسالها.
    pending = [
        str(key) for key in state.get("pending", [])
        if str(key) in by_key and str(key) not in ever_posted
    ]
    pending_set = set(pending)
    for deal in new_deals:
        key = telegram_deal_key(deal)
        if key and key not in pending_set and key not in ever_posted:
            pending.append(key)
            pending_set.add(key)

    sent_new = 0
    remaining = []
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat(timespec="seconds")
    for key in pending:
        deal = by_key.get(key)
        if not deal or key in ever_posted:
            continue
        if sent_new >= TELEGRAM_MAX_NEW_POSTS:
            remaining.append(key)
            continue
        if send_to_telegram(deal, "new"):
            posted[key] = now_iso
            ever_posted.add(key)
            sent_new += 1
            print(f"[telegram] posted new product {key}")
            time.sleep(TELEGRAM_SEND_DELAY_SECONDS)
        else:
            remaining.append(key)

    # توقيت الرياض ثابت UTC+3. يُصفّر العدّاد عند بداية اليوم المحلي.
    riyadh_tz = timezone(timedelta(hours=3))
    now_riyadh = now_utc.astimezone(riyadh_tz)
    featured_day = now_riyadh.strftime("%Y-%m-%d")
    if state.get("featured_day") != featured_day:
        state["featured_day"] = featured_day
        state["featured_count"] = 0

    featured_count = max(0, int(state.get("featured_count") or 0))
    last_featured_at = None
    try:
        if state.get("last_featured_at"):
            last_featured_at = datetime.fromisoformat(state["last_featured_at"])
    except (TypeError, ValueError):
        last_featured_at = None
    interval_due = (
        last_featured_at is None
        or now_utc - last_featured_at >= timedelta(hours=TELEGRAM_FEATURED_INTERVAL_HOURS)
    )
    featured_posted = 0
    if interval_due and featured_count < TELEGRAM_FEATURED_DAILY_LIMIT:
        for deal in sorted(all_deals, key=telegram_rank, reverse=True):
            key = telegram_deal_key(deal)
            if not key or key in remaining or recently_posted(key, posted):
                continue
            if send_to_telegram(deal, "featured"):
                posted[key] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                ever_posted.add(key)
                featured_posted = 1
                featured_count += 1
                state["last_featured_at"] = posted[key]
                print(
                    f"[telegram] posted featured product {key} "
                    f"({featured_count}/{TELEGRAM_FEATURED_DAILY_LIMIT} today)"
                )
                break

    state["pending"] = remaining
    state["posted"] = posted
    state["ever_posted"] = sorted(ever_posted)
    state["featured_count"] = featured_count
    save_posted_state(state)
    print(
        f"[telegram] done — new={sent_new}, featured={featured_posted}, "
        f"featured_today={featured_count}/{TELEGRAM_FEATURED_DAILY_LIMIT}, "
        f"pending_new={len(remaining)}"
    )


def main() -> int:
    existing_raw = load_existing_deals()
    existing, blocked_existing, recategorized_existing, repaired_titles = normalize_existing_deals(existing_raw)
    if blocked_existing:
        print(f"[compliance] أزيل {blocked_existing} منتج مخالف/عالي الخطورة من الكتالوج")
    if recategorized_existing:
        print(f"[catalog] وُحّد تصنيف {recategorized_existing} منتج قديم")
    if repaired_titles:
        print(f"[catalog] أصلح {repaired_titles} عنوان منتج عام/ناقص")

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
        if blocked_existing or recategorized_existing or repaired_titles:
            print("[main] لا تحديثات API، لكن سيتم حفظ تنظيف الكتالوج")
            write_output(existing, "catalog-cleanup")
        else:
            print("[main] لا عروض جديدة — إبقاء deals.json الحالي كما هو (حماية العروض اليدوية)")
        post_deals_to_telegram([], existing)
        return 0

    merged = merge_deals(existing, updates)
    existing_keys = {_deal_key(deal) for deal in existing if _deal_key(deal)}
    new_deals = [
        deal for deal in merged
        if _deal_key(deal) and _deal_key(deal) not in existing_keys
    ]
    source = "+".join(part for part in [amazon_source if amazon_updates else "", aliexpress_source if aliexpress_updates else ""] if part) or "manual"
    write_output(merged, source)

    print(f"[telegram] detected {len(new_deals)} newly added product(s)")
    post_deals_to_telegram(new_deals, merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
