#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني طبقة SEO ثابتة وآمنة من deals.json لموقع أوفرلي.

لا يجلب هذا الملف أسعاراً ولا ينشئ مراجعات أو ادعاءات جديدة. مهمته تحويل
البيانات الموثقة الموجودة إلى صفحات منتجات وتصنيفات وأدلة قابلة للزحف، مع
خريطة موقع دقيقة وملف أولي صغير لتسريع الصفحة الرئيسية.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
DEALS_PATH = ROOT / "deals.json"
STATE_PATH = ROOT / "seo-state.json"
MANIFEST_PATH = ROOT / "seo-generated-files.json"
BASE_URL = "https://majeed3575.github.io/majeeddeals/"
BASE_PATH = "/majeeddeals/"
AFFILIATE_TAG = "faraj733-21"
PAGE_SIZE = 24
INITIAL_FEED_SIZE = 72
MAX_PRODUCT_PAGES = max(1, min(1000, int(os.environ.get("SEO_MAX_PRODUCT_PAGES", "1000"))))


CATEGORIES = {
    "الإلكترونيات": {
        "slug": "electronics",
        "description": "منتجات إلكترونية رائجة تشمل الشواحن والملحقات والأجهزة الذكية، مرتبة وفق بيانات الرواج المتاحة.",
        "audience": "من يبحث عن ملحقات وأجهزة عملية للاستخدام اليومي",
        "checks": "التوافق، نوع المنفذ أو الاتصال، والضمان الذي يوضحه المتجر",
    },
    "المنزل": {
        "slug": "home",
        "description": "اختيارات للمنزل والمطبخ والتنظيم تساعدك على الوصول إلى المنتجات الرائجة بسرعة.",
        "audience": "من يريد تحسين الاستخدام اليومي للمطبخ والمنزل",
        "checks": "الأبعاد، الخامة، ومتطلبات التشغيل أو التنظيف",
    },
    "السيارة": {
        "slug": "car",
        "description": "إكسسوارات وأدوات سيارة رائجة مع روابط مباشرة للتحقق من التوافق والسعر لدى المتجر.",
        "audience": "من يريد أدوات عملية وتنظيماً أفضل داخل السيارة",
        "checks": "توافق المقاس أو الموديل، طريقة التثبيت، ومصدر الطاقة",
    },
    "السفر": {
        "slug": "travel",
        "description": "منتجات سفر وتنظيم وراحة مختارة وفق مؤشرات الطلب المتاحة لدى المنصات.",
        "audience": "المسافرين الباحثين عن وزن أقل وتنظيم أسهل",
        "checks": "الأبعاد والوزن وسياسة الأمتعة وجودة الإغلاق",
    },
    "الموضة": {
        "slug": "fashion",
        "description": "منتجات موضة وإكسسوارات رائجة مع تنبيه واضح لمراجعة المقاس والخامة لدى المتجر.",
        "audience": "من يبحث عن إكسسوارات وقطع رائجة للاستخدام اليومي",
        "checks": "جدول المقاسات، الخامة، وصور المشترين إن توفرت",
    },
    "الجمال والعناية": {
        "slug": "beauty-care",
        "description": "منتجات جمال وعناية شخصية رائجة، مع ضرورة مراجعة المكونات والملاءمة الشخصية قبل الشراء.",
        "audience": "من يبحث عن أدوات عناية شخصية عملية ورائجة",
        "checks": "المكونات، تعليمات الاستخدام، والتحذيرات الموضحة لدى المتجر",
    },
    "الرياضة": {
        "slug": "sports",
        "description": "أدوات ولياقة ومنتجات رياضية رائجة مرتبة لتسهيل المقارنة الأولية.",
        "audience": "من يريد أدوات للتمارين المنزلية والنشاط اليومي",
        "checks": "المقاس، تحمل الوزن، ومستوى الاستخدام المناسب",
    },
    "الأطفال": {
        "slug": "kids",
        "description": "منتجات أطفال رائجة مع تذكير بمراجعة العمر المناسب وتحذيرات السلامة لدى المتجر.",
        "audience": "الأسر الباحثة عن منتجات أطفال عملية",
        "checks": "العمر الموصى به، المواد، وتحذيرات السلامة",
    },
    "الحيوانات الأليفة": {
        "slug": "pets",
        "description": "أدوات ومنتجات للحيوانات الأليفة مختارة وفق الرواج والبيانات المتاحة.",
        "audience": "مربي الحيوانات الباحثين عن أدوات يومية مفيدة",
        "checks": "المقاس، المواد، وملاءمة المنتج لنوع الحيوان",
    },
    "الأدوات والهوايات": {
        "slug": "tools-hobbies",
        "description": "أدوات وهوايات ومنتجات عملية رائجة للمشروعات المنزلية والاستخدام الشخصي.",
        "audience": "الهواة ومن ينفذ أعمالاً منزلية بسيطة",
        "checks": "المواصفات، الملحقات المتضمنة، ومتطلبات السلامة",
    },
    "الترفيه المنزلي": {
        "slug": "home-entertainment",
        "description": "بروجكترات وتلفزيونات وملحقات ترفيه منزلي رائجة مع إرشادات لفحص المواصفات قبل الشراء.",
        "audience": "من يبني تجربة مشاهدة أو ألعاب منزلية",
        "checks": "الدقة الفعلية، السطوع، المقاس، المنافذ، والضمان",
    },
}

DEFAULT_CATEGORY = "الإلكترونيات"

GUIDES = [
    {
        "slug": "choose-gan-charger",
        "title": "كيف تختار شاحن GaN مناسباً دون دفع أكثر من حاجتك؟",
        "description": "دليل عملي لفهم القدرة والمنافذ والبروتوكولات قبل شراء شاحن GaN.",
        "category": "الإلكترونيات",
        "intro": "شواحن GaN أصغر عادةً من الشواحن التقليدية ذات القدرة نفسها، لكن الرقم الكبير المكتوب على المنتج لا يعني أن كل منفذ يقدّم تلك القدرة منفرداً. القرار الصحيح يبدأ من أجهزتك، لا من أعلى رقم في صفحة المنتج.",
        "sections": [
            ("ابدأ بالأجهزة التي تملكها", "اكتب قدرة الشحن القصوى للهاتف واللوحي واللابتوب، ثم افحص نوع المنافذ التي تستخدمها. إذا كان اللابتوب يحتاج USB-C Power Delivery فابحث عن ذكر البروتوكول والقدرة لذلك المنفذ تحديداً، وليس القدرة الإجمالية للشاحن فقط."),
            ("افهم توزيع الطاقة", "في الشواحن متعددة المنافذ تنخفض قدرة بعض المخارج عند استخدام أكثر من جهاز. راجع جدول توزيع الطاقة في صفحة المتجر، وتأكد أن التوزيع عند توصيل أجهزتك الفعلية يظل كافياً."),
            ("الكابل جزء من المعادلة", "قدرة الشاحن لا تصل إلى الجهاز إذا كان الكابل لا يدعمها. للشحنات الأعلى قدرة ابحث عن كابل موضح عليه دعم القدرة المناسبة وشريحة تعريف إلكترونية عند الحاجة."),
            ("قائمة فحص سريعة", "تحقق من القابس المناسب للسعودية، دعم الجهد 100–240V إن كنت تسافر، عدد المنافذ، سياسة الضمان، وتقييمات الاستخدام الطويل. السعر النهائي والمواصفات المعتمدة هما ما يظهر لدى المتجر."),
        ],
    },
    {
        "slug": "projector-buying-guide",
        "title": "دليل اختيار بروجكتر للترفيه المنزلي",
        "description": "ما الذي يجب فحصه في الدقة والسطوع والمسافة والمنافذ قبل شراء بروجكتر؟",
        "category": "الترفيه المنزلي",
        "intro": "تتشابه صور البروجكترات في المتاجر بينما تختلف التجربة الفعلية كثيراً. لا تعتمد على عبارة 4K وحدها؛ قد تعني دعم استقبال إشارة 4K بينما تكون الدقة الأصلية أقل.",
        "sections": [
            ("الدقة الأصلية قبل التسويقية", "ابحث عن Native Resolution بوضوح. الدقة الأصلية هي عدد البكسلات التي يعرضها الجهاز فعلياً، أما Supported Resolution فتعني غالباً أنه يستطيع استقبال الإشارة ثم تحويلها."),
            ("السطوع والبيئة", "الغرفة المظلمة تحتاج سطوعاً أقل من غرفة المعيشة نهاراً. قارن أرقام ANSI Lumens حين تكون متاحة بدلاً من أرقام غير موحدة، وتذكر أن الستارة والإضاءة المحيطة تؤثران في النتيجة."),
            ("المسافة وحجم الصورة", "راجع Throw Ratio والمسافة المطلوبة قبل الشراء، وقس الجدار ومكان الجهاز. وجود تصحيح keystone لا يعوض دائماً عن وضع غير مناسب وقد يقلل حدة الصورة."),
            ("الصوت والاتصال", "افحص HDMI وARC أو مخرج الصوت والبلوتوث، وتأكد من توافق تطبيقات البث إن كان النظام ذكياً. للمشاهدة الجادة قد تحتاج سماعة خارجية حتى لو كان الجهاز يحتوي سماعات."),
        ],
    },
    {
        "slug": "tcl-tv-buying-guide",
        "title": "كيف تقارن تلفزيونات TCL قبل الشراء؟",
        "description": "خطوات لفهم حجم الشاشة ونوع اللوحة والتحديث وميزات الألعاب في تلفزيونات TCL.",
        "category": "الترفيه المنزلي",
        "intro": "الاسم التجاري وحده لا يكفي للمقارنة؛ سلسلة الموديل والسنة والمقاس قد تغير نوع اللوحة والسطوع وعدد المنافذ. ابدأ برقم الموديل الكامل كما يظهر لدى المتجر.",
        "sections": [
            ("اختر المقاس حسب المسافة", "المقاس الأكبر ليس أفضل دائماً إذا كانت مسافة الجلوس قصيرة أو جودة المحتوى منخفضة. قس المسافة وحدد مكان الشاشة والحامل قبل اختيار المقاس."),
            ("Mini-LED وQLED ليستا الشيء نفسه", "QLED تصف طبقة تحسين اللون، بينما Mini-LED تتعلق غالباً بإضاءة خلفية بعدد مناطق أكبر. افحص نوع اللوحة وعدد مناطق التعتيم والسطوع بدلاً من الاعتماد على الشعار فقط."),
            ("للاعبين", "راجع معدل التحديث الأصلي، HDMI 2.1، VRR وALLM، وعدد المنافذ التي تدعمها فعلياً. بعض المزايا قد تعمل بدقة أو معدل محدد فقط."),
            ("النظام والضمان", "اختر النظام الذي تتوفر عليه تطبيقاتك، وافحص سياسة التحديث والضمان المحلي. السعر والتوفر والمواصفات النهائية يجب تأكيدها في صفحة البائع قبل الدفع."),
        ],
    },
    {
        "slug": "smart-home-starter-guide",
        "title": "بداية عملية للمنزل الذكي دون تعقيد",
        "description": "اختر منصة موحدة واتصالاً مناسباً وابدأ بأجهزة تحقق فائدة يومية واضحة.",
        "category": "المنزل",
        "intro": "أفضل منزل ذكي ليس الأكثر أجهزة، بل الأقل احتياجاً للصيانة والأوضح فائدة. ابدأ بمشكلة واحدة مثل الإضاءة أو المراقبة أو التحكم بالطاقة، ثم وسّع النظام تدريجياً.",
        "sections": [
            ("اختر المنصة أولاً", "حدد إن كنت تعتمد Apple Home أو Google Home أو Alexa أو منصة أخرى، ثم تحقق من شعار التوافق على المنتج. معيار Matter قد يسهل الربط لكنه لا يضمن توفر كل المزايا على كل منصة."),
            ("Wi‑Fi أم Zigbee أم Thread", "أجهزة Wi‑Fi سهلة البدء لكنها تعتمد على الراوتر، بينما قد تحتاج Zigbee إلى محور. Thread مصمم لشبكة منخفضة الطاقة ويتطلب Border Router متوافقاً في بعض الحالات."),
            ("الأمان والخصوصية", "غيّر كلمات المرور الافتراضية، فعّل التحديث التلقائي والمصادقة الثنائية للحسابات، وضع أجهزة إنترنت الأشياء على شبكة منفصلة إذا كان الراوتر يدعم ذلك."),
            ("ابدأ بما يوفر وقتاً", "مقبس ذكي لمهمة متكررة أو حساس تسرب أو إضاءة تلقائية قد يكون أكثر فائدة من جهاز معقد. راجع الجهد والقابس والتوافق قبل الشراء."),
        ],
    },
    {
        "slug": "car-accessories-checklist",
        "title": "قائمة فحص قبل شراء إكسسوارات السيارة",
        "description": "تأكد من التوافق والطاقة والتثبيت ودرجات الحرارة قبل طلب إكسسوارات السيارة.",
        "category": "السيارة",
        "intro": "كثير من إكسسوارات السيارة تبدو عامة لكنها تعتمد على مقاس الفتحة أو نوع المنفذ أو تصميم لوحة القيادة. دقائق القياس قبل الطلب تقلل احتمال شراء منتج غير مناسب.",
        "sections": [
            ("التوافق الدقيق", "لا تكتفِ باسم السيارة؛ السنة والفئة قد تغيران التصميم. راجع المقاسات ورقم القطعة وصور موضع التركيب، واسأل البائع إذا لم تكن المعلومات واضحة."),
            ("الحرارة والطاقة", "مقصورة السيارة قد تصل إلى درجات حرارة مرتفعة. افحص مجال حرارة التشغيل، ونوع مصدر الطاقة، وقدرة منفذ USB أو ولاعة السيارة قبل تركيب كاميرا أو شاحن."),
            ("تثبيت آمن", "تجنب أي ملحق يحجب الرؤية أو الوسائد الهوائية أو أدوات التحكم. استخدم تثبيتاً مناسباً ولا تترك كابلات تعيق الدواسات أو الحركة."),
            ("راجع سياسة الإرجاع", "المنتجات التي تعتمد على المقاس أكثر عرضة لعدم الملاءمة؛ راجع الإرجاع والشحن إلى السعودية والسعر النهائي في صفحة المتجر قبل إكمال الطلب."),
        ],
    },
]


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def clean_text(value, limit: int = 220) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:limit].rstrip()


def number(value, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = re.sub(r"[^0-9.\-]", "", value.replace(",", ""))
        return float(value)
    except (TypeError, ValueError):
        return default


def int_number(value, default: int = 0) -> int:
    return max(0, int(round(number(value, default))))


def valid_https(value, domains: tuple[str, ...]) -> str:
    value = clean_text(value, 2000)
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return ""
    if not any(host == domain or host.endswith("." + domain) for domain in domains):
        return ""
    return value


def normalize_category(value) -> str:
    value = clean_text(value, 60)
    return value if value in CATEGORIES else DEFAULT_CATEGORY


def normalize_deal(raw: dict) -> dict | None:
    store = "aliexpress" if str(raw.get("store", "amazon")).lower() == "aliexpress" else "amazon"
    if store == "amazon":
        product_id = clean_text(raw.get("asin"), 20).upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", product_id):
            return None
        affiliate_url = f"https://www.amazon.sa/dp/{product_id}/?tag={AFFILIATE_TAG}"
        image = valid_https(raw.get("image"), ("media-amazon.com", "ssl-images-amazon.com", "amazon.com"))
        store_name = "Amazon.sa"
    else:
        product_id = clean_text(raw.get("product_id") or raw.get("id"), 24)
        if not re.fullmatch(r"\d{6,20}", product_id):
            return None
        affiliate_url = valid_https(
            raw.get("promotion_link") or raw.get("affiliate_url") or raw.get("url"),
            ("aliexpress.com", "aliexpress.us"),
        )
        image = valid_https(
            raw.get("image") or raw.get("product_main_image_url"),
            ("alicdn.com", "aliexpress-media.com", "aliexpress.com"),
        )
        store_name = "AliExpress"
    title = clean_text(raw.get("title") or raw.get("product_title"), 180)
    if len(title) < 8 or not image or not affiliate_url:
        return None
    category = normalize_category(raw.get("category"))
    discount = min(95, int_number(raw.get("discount_percent")))
    original_price = max(0.0, number(raw.get("original_price")))
    sales = int_number(raw.get("sales_volume") or raw.get("orders") or raw.get("sales"))
    rating = max(0.0, number(raw.get("rating") or raw.get("evaluate_rate")))
    rank_score = number(raw.get("rank_score") or raw.get("score"))
    angle = clean_text(raw.get("angle"), 80)
    slug_id = product_id.lower()
    path = f"products/{store}-{slug_id}/"
    return {
        "store": store,
        "store_name": store_name,
        "id": product_id,
        "title": title,
        "image": image,
        "affiliate_url": affiliate_url,
        "category": category,
        "discount_percent": discount,
        "original_price": round(original_price, 2),
        "sales_volume": sales,
        "rating": rating,
        "rank_score": rank_score,
        "angle": angle,
        "path": path,
        "url": BASE_URL + path,
        "raw": raw,
    }


def load_deals() -> tuple[list[dict], dict]:
    payload = load_json(DEALS_PATH, {})
    rows = payload.get("deals") if isinstance(payload, dict) else []
    rows = rows if isinstance(rows, list) else []
    seen: set[tuple[str, str]] = set()
    deals: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        deal = normalize_deal(row)
        if not deal:
            continue
        key = (deal["store"], deal["id"])
        if key in seen:
            continue
        seen.add(key)
        deals.append(deal)
    deals.sort(
        key=lambda item: (
            item["rank_score"], item["sales_volume"], item["rating"], item["discount_percent"]
        ),
        reverse=True,
    )
    return deals[:MAX_PRODUCT_PAGES], payload if isinstance(payload, dict) else {}


def stable_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def state_lastmod(state: dict, key: str, signature_value) -> str:
    today = date.today().isoformat()
    pages = state.setdefault("pages", {})
    signature = stable_hash(signature_value)
    previous = pages.get(key) if isinstance(pages.get(key), dict) else {}
    lastmod = previous.get("lastmod", today) if previous.get("signature") == signature else today
    pages[key] = {"signature": signature, "lastmod": lastmod}
    return lastmod


def write_if_changed(path: Path, content: str, generated: set[str]) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    generated.add(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def json_ld(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def meta_description(value: str) -> str:
    value = clean_text(value, 165)
    return value if len(value) <= 160 else value[:157].rstrip() + "…"


def page_shell(
    *, title: str, description: str, canonical: str, body: str, schema: list[dict] | None = None,
    og_type: str = "website", image: str = BASE_URL + "assets/overly-social.jpg",
    robots: str = "index,follow,max-image-preview:large", lastmod: str = ""
) -> str:
    schemas = "\n".join(
        f'  <script type="application/ld+json">{json_ld(item)}</script>' for item in (schema or [])
    )
    modified = f'  <meta property="article:modified_time" content="{esc(lastmod)}">\n' if lastmod else ""
    return f'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data: https://*.media-amazon.com https://*.ssl-images-amazon.com https://*.alicdn.com https://*.aliexpress-media.com https://*.aliexpress.com; style-src 'self'; script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests">
  <meta name="theme-color" content="#050807">
  <meta name="description" content="{esc(meta_description(description))}">
  <meta name="robots" content="{esc(robots)}">
  <link rel="canonical" href="{esc(canonical)}">
  <meta property="og:locale" content="ar_SA">
  <meta property="og:type" content="{esc(og_type)}">
  <meta property="og:site_name" content="أوفرلي | Overly">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(meta_description(description))}">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{esc(image)}">
{modified}  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(meta_description(description))}">
  <meta name="twitter:image" content="{esc(image)}">
  <title>{esc(title)}</title>
  <link rel="icon" type="image/webp" href="{BASE_PATH}assets/overly-icon.webp">
  <link rel="apple-touch-icon" sizes="180x180" href="{BASE_PATH}assets/overly-icon-180.png">
  <link rel="stylesheet" href="{BASE_PATH}seo.css">
{schemas}
</head>
<body>
  <a class="skip" href="#content">انتقل إلى المحتوى</a>
  <header class="site-header">
    <div class="shell nav">
      <a class="brand" href="{BASE_PATH}" aria-label="أوفرلي — الرئيسية"><img src="{BASE_PATH}assets/overly-dark-logo-trimmed.webp" width="230" height="74" alt="أوفرلي — Overly" decoding="async"></a>
      <nav aria-label="التنقل الرئيسي"><a href="{BASE_PATH}">الرئيسية</a><a href="{BASE_PATH}categories/electronics/">التصنيفات</a><a href="{BASE_PATH}guides/">الأدلة</a><a href="{BASE_PATH}methodology.html">منهجية الاختيار</a></nav>
    </div>
  </header>
  {body}
  <footer>
    <div class="shell footer-grid">
      <div><strong>أوفرلي | Overly</strong><p>نرتّب بيانات المنتجات لتصل إلى الخيارات الرائجة بوضوح.</p></div>
      <div class="disclosure">إفصاح: قد نحصل على عمولة من عمليات الشراء المؤهلة عبر روابط Amazon وAliExpress دون تكلفة إضافية عليك. السعر والتوفر النهائيان هما الظاهران لدى المتجر لحظة الشراء.<nav><a href="{BASE_PATH}about.html">عن أوفرلي</a><a href="{BASE_PATH}methodology.html">منهجية الاختيار</a><a href="{BASE_PATH}privacy.html">الخصوصية</a><a href="{BASE_PATH}terms.html">الشروط</a><a href="{BASE_PATH}affiliate-disclosure.html">إفصاح العمولة</a><a href="{BASE_PATH}copyright.html">الحقوق</a></nav></div>
    </div>
  </footer>
</body>
</html>
'''


def breadcrumbs(items: list[tuple[str, str]]) -> tuple[str, dict]:
    links = []
    schema_items = []
    for index, (name, href) in enumerate(items, 1):
        if index == len(items):
            links.append(f'<span aria-current="page">{esc(name)}</span>')
        else:
            links.append(f'<a href="{esc(href)}">{esc(name)}</a>')
        schema_items.append({"@type": "ListItem", "position": index, "name": name, "item": href})
    markup = '<nav class="breadcrumbs" aria-label="مسار الصفحة">' + "<i>‹</i>".join(links) + "</nav>"
    schema = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": schema_items}
    return markup, schema


def rating_text(deal: dict) -> str:
    rating = deal["rating"]
    if rating <= 0:
        return ""
    if rating <= 5:
        return f"تقييم {rating:.1f} من 5"
    return f"{int(round(rating))}٪ تقييم إيجابي"


def popularity_text(deal: dict) -> str:
    parts = []
    if deal["sales_volume"]:
        parts.append(f"{deal['sales_volume']:,} طلب مسجل لدى المنصة")
    rating = rating_text(deal)
    if rating:
        parts.append(rating)
    return " · ".join(parts) or "منتج مختار وفق بيانات الرواج المتاحة"


def product_card(deal: dict) -> str:
    badge = f"خصم مرصود {deal['discount_percent']}٪" if deal["discount_percent"] else "رائج"
    return f'''<article class="product-card">
  <a class="card-image" href="{BASE_PATH}{esc(deal['path'])}"><img src="{esc(deal['image'])}" alt="{esc(deal['title'])}" loading="lazy" decoding="async" width="520" height="520"></a>
  <div class="card-copy"><span class="badge">{esc(deal['store_name'])} · {esc(badge)}</span><h2><a href="{BASE_PATH}{esc(deal['path'])}">{esc(deal['title'])}</a></h2><p>{esc(popularity_text(deal))}</p><a class="text-link" href="{BASE_PATH}{esc(deal['path'])}">عرض التفاصيل ←</a></div>
</article>'''


def product_page(deal: dict, related: list[dict], lastmod: str) -> str:
    category = CATEGORIES[deal["category"]]
    crumb_html, crumb_schema = breadcrumbs([
        ("الرئيسية", BASE_URL),
        (deal["category"], BASE_URL + f"categories/{category['slug']}/"),
        (deal["title"], deal["url"]),
    ])
    discount = (
        f'<div class="fact"><span>الخصم المرصود</span><strong>{deal["discount_percent"]}٪</strong></div>'
        if deal["discount_percent"] else ""
    )
    before = (
        f'<div class="fact"><span>السعر قبل الخصم المرصود</span><strong>{deal["original_price"]:,.2f} ر.س</strong></div>'
        if deal["discount_percent"] and deal["original_price"] > 0 else ""
    )
    popularity = popularity_text(deal)
    reason_bits = [f"ينتمي إلى تصنيف {deal['category']}"]
    if deal["sales_volume"]:
        reason_bits.append(f"وتظهر بيانات المنصة {deal['sales_volume']:,} طلباً مسجلاً")
    if rating_text(deal):
        reason_bits.append(f"مع {rating_text(deal)}")
    reason = "، ".join(reason_bits) + ". لا يعني ظهوره أننا اختبرناه شخصياً؛ الاختيار آلي وفق البيانات المتاحة ثم يُعرض للتحقق لدى المتجر."
    related_html = "".join(product_card(item) for item in related[:4])
    body = f'''<main id="content" class="shell page-main">
  {crumb_html}
  <article class="product-hero">
    <div class="product-image"><img src="{esc(deal['image'])}" alt="{esc(deal['title'])}" width="720" height="720" fetchpriority="high" decoding="async"></div>
    <div class="product-copy">
      <span class="eyebrow">{esc(deal['store_name'])} · {esc(deal['category'])}</span>
      <h1>{esc(deal['title'])}</h1>
      <p class="lead">منتج مختار وفق مؤشرات الرواج المتاحة. راجع المواصفات والسعر والتوفر والشحن إلى السعودية لدى المتجر قبل الشراء.</p>
      <div class="facts">{discount}{before}<div class="fact"><span>مؤشر الرواج</span><strong>{esc(popularity)}</strong></div><div class="fact"><span>رقم المنتج</span><strong dir="ltr">{esc(deal['id'])}</strong></div></div>
      <a class="shop-button" href="{esc(deal['affiliate_url'])}" target="_blank" rel="sponsored noopener noreferrer">تحقق من السعر الحالي على {esc(deal['store_name'])} ↗</a>
      <small class="affiliate-note">رابط تسويق بالعمولة؛ قد نحصل على عمولة من الشراء المؤهل دون تكلفة إضافية عليك.</small>
    </div>
  </article>
  <section class="content-grid">
    <article class="content-card"><h2>لماذا ظهر في أوفرلي؟</h2><p>{esc(reason)}</p></article>
    <article class="content-card"><h2>لمن قد يكون مناسباً؟</h2><p>قد يناسب {esc(category['audience'])}. الملاءمة النهائية تعتمد على احتياجك والمواصفات التي يذكرها البائع.</p></article>
    <article class="content-card"><h2>ما الذي ينبغي التحقق منه؟</h2><p>راجع {esc(category['checks'])}، إضافة إلى الشحن للسعودية وسياسة الإرجاع والضمان والسعر النهائي لدى المتجر.</p></article>
    <article class="content-card"><h2>تنبيه مهم</h2><p>الأسعار والتوفر وبيانات المبيعات قد تتغير. أوفرلي لا يبيع المنتج ولا يدّعي اختباره؛ صفحة المتجر هي المرجع النهائي.</p></article>
  </section>
  <section class="related"><div class="section-head"><div><span>خيارات قريبة</span><h2>منتجات أخرى من {esc(deal['category'])}</h2></div><a href="{BASE_PATH}categories/{category['slug']}/">عرض التصنيف كله ←</a></div><div class="cards">{related_html or '<p class="empty">ستظهر المنتجات القريبة هنا عند توفرها.</p>'}</div></section>
</main>'''
    description = f"{deal['title']} من {deal['store_name']}: معلومات اختيار واضحة ورابط للتحقق من السعر الحالي والشحن إلى السعودية."
    product_schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": deal["title"],
        "image": [deal["image"]],
        "description": meta_description(description),
        "sku": deal["id"],
        "productID": deal["id"],
        "category": deal["category"],
        "url": deal["url"],
    }
    return page_shell(
        title=f"{deal['title']} | أوفرلي",
        description=description,
        canonical=deal["url"],
        body=body,
        schema=[product_schema, crumb_schema],
        og_type="product",
        image=deal["image"],
        lastmod=lastmod,
    )


def collection_page(
    *, title: str, description: str, canonical_path: str, deals: list[dict], page_number: int,
    path_prefix: str, crumb_items: list[tuple[str, str]], lastmod: str
) -> str:
    pages = max(1, math.ceil(len(deals) / PAGE_SIZE))
    start = (page_number - 1) * PAGE_SIZE
    page_deals = deals[start:start + PAGE_SIZE]
    canonical = BASE_URL + canonical_path
    crumb_html, crumb_schema = breadcrumbs(crumb_items + [(title, canonical)])
    cards = "".join(product_card(item) for item in page_deals)
    if not cards:
        cards = '<div class="empty"><h2>لا توجد منتجات مطابقة الآن</h2><p>تُحدّث القائمة آلياً، ويمكنك العودة لاحقاً أو استكشاف التصنيفات الأخرى.</p></div>'
    pagination = []
    if page_number > 1:
        prev = path_prefix if page_number == 2 else f"{path_prefix}page/{page_number - 1}/"
        pagination.append(f'<a rel="prev" href="{BASE_PATH}{prev}">→ الصفحة السابقة</a>')
    pagination.append(f"<span>صفحة {page_number} من {pages}</span>")
    if page_number < pages:
        pagination.append(f'<a rel="next" href="{BASE_PATH}{path_prefix}page/{page_number + 1}/">الصفحة التالية ←</a>')
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": title,
        "numberOfItems": len(page_deals),
        "itemListElement": [
            {"@type": "ListItem", "position": start + index, "url": item["url"], "name": item["title"]}
            for index, item in enumerate(page_deals, 1)
        ],
    }
    body = f'''<main id="content" class="shell page-main">{crumb_html}<header class="collection-head"><span class="eyebrow">دليل تصفح قابل للتحديث</span><h1>{esc(title)}</h1><p>{esc(description)}</p><strong>{len(deals):,} منتجاً في هذا القسم</strong></header><div class="cards">{cards}</div><nav class="pagination" aria-label="صفحات النتائج">{''.join(pagination)}</nav></main>'''
    return page_shell(
        title=f"{title} | أوفرلي",
        description=description,
        canonical=canonical,
        body=body,
        schema=[crumb_schema, item_list],
        robots="index,follow,max-image-preview:large" if deals else "noindex,follow",
        lastmod=lastmod,
    )


def guide_page(guide: dict, matching: list[dict], lastmod: str) -> str:
    canonical = BASE_URL + f"guides/{guide['slug']}/"
    crumb_html, crumb_schema = breadcrumbs([
        ("الرئيسية", BASE_URL), ("أدلة الشراء", BASE_URL + "guides/"), (guide["title"], canonical)
    ])
    sections = "".join(f'<section class="guide-section"><h2>{esc(title)}</h2><p>{esc(text)}</p></section>' for title, text in guide["sections"])
    related = "".join(product_card(item) for item in matching[:4])
    category_slug = CATEGORIES[guide["category"]]["slug"]
    article_schema = {
        "@context": "https://schema.org", "@type": "Article", "headline": guide["title"],
        "description": guide["description"], "inLanguage": "ar-SA", "dateModified": lastmod,
        "author": {"@type": "Organization", "name": "فريق أوفرلي"},
        "publisher": {"@type": "Organization", "name": "أوفرلي", "url": BASE_URL},
        "mainEntityOfPage": canonical,
    }
    body = f'''<main id="content" class="shell page-main">{crumb_html}<article class="guide"><header><span class="eyebrow">دليل مستقل · فريق أوفرلي</span><h1>{esc(guide['title'])}</h1><p class="lead">{esc(guide['intro'])}</p><div class="byline">آخر مراجعة: {esc(lastmod)} · لا يتضمن ادعاء اختبار شخصي</div></header>{sections}<aside class="guide-note"><strong>قاعدة أوفرلي</strong><p>استخدم هذا الدليل لتكوين قائمة فحص، ثم اعتمد المواصفات والسعر والتوفر والضمان الظاهرة لدى المتجر وقت الشراء.</p></aside></article><section class="related"><div class="section-head"><div><span>تطبيق الدليل</span><h2>منتجات مرتبطة</h2></div><a href="{BASE_PATH}categories/{category_slug}/">كل منتجات {esc(guide['category'])} ←</a></div><div class="cards">{related or '<p class="empty">لا توجد منتجات مرتبطة حالياً.</p>'}</div></section></main>'''
    return page_shell(
        title=f"{guide['title']} | أوفرلي", description=guide["description"], canonical=canonical,
        body=body, schema=[article_schema, crumb_schema], og_type="article", lastmod=lastmod,
    )


def static_pages(deals: list[dict], state: dict, generated: set[str], sitemap: dict[str, str]) -> int:
    changed = 0
    category_links = "".join(
        f'<a class="directory-link" href="{BASE_PATH}categories/{info["slug"]}/"><strong>{esc(name)}</strong><span>{esc(info["description"])}</span></a>'
        for name, info in CATEGORIES.items()
    )
    guide_links = "".join(
        f'<a class="directory-link" href="{BASE_PATH}guides/{guide["slug"]}/"><strong>{esc(guide["title"])}</strong><span>{esc(guide["description"])}</span></a>'
        for guide in GUIDES
    )
    pages = {
        "about.html": (
            "عن أوفرلي | Overly",
            "تعرف على أوفرلي، موقع سعودي يساعد على اكتشاف المنتجات الرائجة والتحقق منها لدى المتجر.",
            f'''<main id="content" class="shell page-main"><header class="collection-head"><span class="eyebrow">من نحن</span><h1>عن أوفرلي</h1><p>أوفرلي موقع سعودي لاكتشاف المنتجات الرائجة من Amazon السعودية وAliExpress. نحن لا نبيع المنتجات؛ ننظم البيانات العامة التي توفرها المنصات ونربطك بصفحة المتجر للتحقق والشراء.</p></header><section class="content-grid"><article class="content-card"><h2>ماذا نفعل؟</h2><p>نرتب المنتجات وفق مؤشرات مثل الطلب والتقييم والتصنيف عندما تتوفر، ونبني صفحات واضحة تساعدك على المقارنة الأولية.</p></article><article class="content-card"><h2>ماذا لا نفعل؟</h2><p>لا نخترع سعراً أو خصماً أو مراجعة، ولا ندّعي اختبار منتج لم نختبره. المتجر هو المرجع النهائي للسعر والتوفر والضمان.</p></article><article class="content-card"><h2>كيف نمول الموقع؟</h2><p>قد نحصل على عمولة من عمليات الشراء المؤهلة عبر روابط التسويق بالعمولة دون زيادة السعر على المشتري.</p></article><article class="content-card"><h2>كيف تختار؟</h2><p>اقرأ <a href="{BASE_PATH}methodology.html">منهجية الاختيار</a> وأدلة الشراء، ثم راجع مواصفات المنتج لدى البائع.</p></article></section></main>''',
        ),
        "methodology.html": (
            "منهجية اختيار المنتجات | أوفرلي",
            "كيف يجمع أوفرلي المنتجات ويرتبها، وما الذي تعنيه مؤشرات الطلب والتقييم والخصم.",
            f'''<main id="content" class="shell page-main"><header class="collection-head"><span class="eyebrow">الشفافية أولاً</span><h1>كيف يختار أوفرلي المنتجات؟</h1><p>هذه الصفحة تشرح ما نستخدمه وما لا نستخدمه، حتى تعرف حدود البيانات قبل أن تضغط رابط المتجر.</p></header><section class="guide"><section class="guide-section"><h2>1. المصدر</h2><p>نستخدم بيانات المنتجات العامة من الواجهات الرسمية أو القوائم التي يراجعها مالك الموقع. لا نطلب بيانات عملاء أو بائعين خاصة.</p></section><section class="guide-section"><h2>2. مؤشرات الرواج</h2><p>قد تشمل عدد الطلبات أو نسبة التقييم أو ترتيباً داخلياً مشتقاً من البيانات المتاحة. غياب أحد المؤشرات لا يُستبدل بقيمة مختلقة.</p></section><section class="guide-section"><h2>3. السعر والخصم</h2><p>نسبة الخصم والسعر السابق لا يظهران إلا إذا وردا في المصدر. السعر الحالي لا يُثبت داخل أوفرلي؛ يجب التحقق منه لدى المتجر لأنه قد يتغير سريعاً.</p></section><section class="guide-section"><h2>4. الشحن إلى السعودية</h2><p>بحث AliExpress يطلب نتائج قابلة للشحن إلى السعودية، لكن الوجهة والتوفر قد يتغيران حسب العنوان والوقت؛ صفحة الدفع هي المرجع النهائي.</p></section><section class="guide-section"><h2>5. التحرير والمراجعة</h2><p>الأدلة نصوص تعليمية من فريق أوفرلي وليست ادعاءات اختبار. صفحات المنتجات تضيف سياقاً وقوائم فحص ولا تعيد نشر وصف البائع بوصفه مراجعة مستقلة.</p></section><section class="guide-section"><h2>6. روابط العمولة</h2><p>كل انتقال تجاري موسوم كرابط تسويق بالعمولة. قد نحصل على عمولة من شراء مؤهل دون تكلفة إضافية عليك.</p></section></section><div class="directory">{category_links}</div></main>''',
        ),
        "guides/index.html": (
            "أدلة الشراء العملية | أوفرلي",
            "أدلة عربية عملية لفحص المواصفات والتوافق قبل شراء الإلكترونيات والمنزل والسيارة والترفيه المنزلي.",
            f'''<main id="content" class="shell page-main"><header class="collection-head"><span class="eyebrow">قرار أوضح</span><h1>أدلة الشراء</h1><p>محتوى مستقل يساعدك على معرفة الأسئلة الصحيحة قبل الانتقال إلى المتجر. لا تتضمن الأدلة ادعاء اختبار المنتجات.</p></header><div class="directory">{guide_links}</div></main>''',
        ),
        "categories/index.html": (
            "تصنيفات المنتجات | أوفرلي",
            "تصفح منتجات أوفرلي حسب الإلكترونيات والمنزل والسيارة والسفر والترفيه المنزلي وغيرها.",
            f'''<main id="content" class="shell page-main"><header class="collection-head"><span class="eyebrow">اكتشف حسب احتياجك</span><h1>كل التصنيفات</h1><p>روابط ثابتة وقابلة للتصفح إلى الأقسام التي تتحدث آلياً مع قائمة المنتجات.</p></header><div class="directory">{category_links}</div></main>''',
        ),
    }
    for relative, (title, description, body) in pages.items():
        canonical = BASE_URL + ("guides/" if relative == "guides/index.html" else "categories/" if relative == "categories/index.html" else relative)
        lastmod = state_lastmod(state, relative, [title, description, body])
        changed += write_if_changed(ROOT / relative, page_shell(title=title, description=description, canonical=canonical, body=body, lastmod=lastmod), generated)
        sitemap[canonical] = lastmod
    return changed


def cleanup_stale(previous: set[str], current: set[str]) -> int:
    allowed_roots = ("products/", "categories/", "stores/", "guides/")
    allowed_files = {"about.html", "methodology.html", "404.html", "deals-initial.json", "seo.css"}
    removed = 0
    for relative in sorted(previous - current, reverse=True):
        if not (relative.startswith(allowed_roots) or relative in allowed_files):
            continue
        target = (ROOT / relative).resolve()
        if ROOT not in target.parents or not target.is_file():
            continue
        target.unlink()
        removed += 1
        parent = target.parent
        while parent != ROOT and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return removed


def build() -> dict:
    deals, source = load_deals()
    state = load_json(STATE_PATH, {"pages": {}})
    if not isinstance(state, dict):
        state = {"pages": {}}
    previous_manifest = load_json(MANIFEST_PATH, {"files": []})
    previous_files = set(previous_manifest.get("files", [])) if isinstance(previous_manifest, dict) else set()
    generated: set[str] = set()
    sitemap: dict[str, str] = {}
    changed = 0

    css = (ROOT / "seo.css.source").read_text(encoding="utf-8") if (ROOT / "seo.css.source").exists() else ""
    if not css:
        raise RuntimeError("seo.css.source غير موجود")
    changed += write_if_changed(ROOT / "seo.css", css, generated)

    initial_payload = {
        "updated_at": source.get("updated_at") or datetime.now(timezone.utc).isoformat(),
        "count": min(len(deals), INITIAL_FEED_SIZE),
        "total_count": len(deals),
        "source": source.get("source", "generated"),
        "deals": [item["raw"] for item in deals[:INITIAL_FEED_SIZE]],
    }
    changed += write_if_changed(ROOT / "deals-initial.json", dump_json(initial_payload), generated)

    home_lastmod = state_lastmod(state, "index.html", [
        {"store": item["store"], "id": item["id"], "title": item["title"], "category": item["category"]}
        for item in deals
    ])
    sitemap[BASE_URL] = home_lastmod
    for legal in ("privacy.html", "terms.html", "affiliate-disclosure.html", "copyright.html"):
        if (ROOT / legal).exists():
            sitemap[BASE_URL + legal] = state_lastmod(state, legal, stable_hash((ROOT / legal).read_text(encoding="utf-8")))

    for deal in deals:
        signature = {key: deal[key] for key in (
            "store", "id", "title", "image", "affiliate_url", "category", "discount_percent",
            "original_price", "sales_volume", "rating", "angle"
        )}
        lastmod = state_lastmod(state, deal["path"], signature)
        related = [item for item in deals if item["category"] == deal["category"] and item["id"] != deal["id"]]
        changed += write_if_changed(ROOT / deal["path"] / "index.html", product_page(deal, related, lastmod), generated)
        sitemap[deal["url"]] = lastmod

    for category_name, info in CATEGORIES.items():
        category_deals = [item for item in deals if item["category"] == category_name]
        prefix = f"categories/{info['slug']}/"
        page_count = max(1, math.ceil(len(category_deals) / PAGE_SIZE))
        signature = [
            {key: item[key] for key in ("id", "store", "title", "image", "discount_percent", "sales_volume", "rating")}
            for item in category_deals
        ]
        lastmod = state_lastmod(state, prefix, signature)
        for page_number in range(1, page_count + 1):
            canonical_path = prefix if page_number == 1 else f"{prefix}page/{page_number}/"
            title = category_name if page_number == 1 else f"{category_name} — الصفحة {page_number}"
            content = collection_page(
                title=title, description=info["description"], canonical_path=canonical_path,
                deals=category_deals, page_number=page_number, path_prefix=prefix,
                crumb_items=[("الرئيسية", BASE_URL), ("التصنيفات", BASE_URL + "categories/")], lastmod=lastmod,
            )
            changed += write_if_changed(ROOT / canonical_path / "index.html", content, generated)
            if category_deals:
                sitemap[BASE_URL + canonical_path] = lastmod

    for store, store_name in (("amazon", "منتجات Amazon السعودية"), ("aliexpress", "منتجات AliExpress")):
        store_deals = [item for item in deals if item["store"] == store]
        prefix = f"stores/{store}/"
        page_count = max(1, math.ceil(len(store_deals) / PAGE_SIZE))
        lastmod = state_lastmod(state, prefix, [
            {key: item[key] for key in ("id", "title", "category", "image", "discount_percent", "sales_volume", "rating")}
            for item in store_deals
        ])
        for page_number in range(1, page_count + 1):
            canonical_path = prefix if page_number == 1 else f"{prefix}page/{page_number}/"
            title = store_name if page_number == 1 else f"{store_name} — الصفحة {page_number}"
            description = f"تصفح {store_name} المختارة وفق بيانات الرواج، ثم تحقق من السعر والتوفر لدى المتجر."
            content = collection_page(
                title=title, description=description, canonical_path=canonical_path, deals=store_deals,
                page_number=page_number, path_prefix=prefix, crumb_items=[("الرئيسية", BASE_URL)], lastmod=lastmod,
            )
            changed += write_if_changed(ROOT / canonical_path / "index.html", content, generated)
            if store_deals:
                sitemap[BASE_URL + canonical_path] = lastmod

    for guide in GUIDES:
        relative = f"guides/{guide['slug']}/"
        lastmod = state_lastmod(state, relative, guide)
        matching = [item for item in deals if item["category"] == guide["category"]]
        changed += write_if_changed(ROOT / relative / "index.html", guide_page(guide, matching, lastmod), generated)
        sitemap[BASE_URL + relative] = lastmod

    changed += static_pages(deals, state, generated, sitemap)

    not_found = page_shell(
        title="الصفحة غير موجودة | أوفرلي", description="الصفحة المطلوبة غير موجودة.",
        canonical=BASE_URL + "404.html", robots="noindex,follow",
        body=f'''<main id="content" class="shell page-main"><div class="empty"><span class="eyebrow">404</span><h1>الصفحة غير موجودة</h1><p>قد يكون الرابط قد تغيّر. ابدأ من الصفحة الرئيسية أو تصفح التصنيفات.</p><p><a class="shop-button" href="{BASE_PATH}">العودة إلى أوفرلي</a></p></div></main>''',
    )
    changed += write_if_changed(ROOT / "404.html", not_found, generated)
    sitemap_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, lastmod in sorted(sitemap.items()):
        sitemap_lines.extend(["  <url>", f"    <loc>{esc(url)}</loc>", f"    <lastmod>{esc(lastmod)}</lastmod>", "  </url>"])
    sitemap_lines.append("</urlset>")
    changed += write_if_changed(ROOT / "sitemap.xml", "\n".join(sitemap_lines) + "\n", generated)
    state["version"] = 1
    STATE_PATH.write_text(dump_json(state), encoding="utf-8")
    generated.add("seo-state.json")
    removed = cleanup_stale(previous_files, generated)
    manifest = {"version": 1, "files": sorted(generated)}
    MANIFEST_PATH.write_text(dump_json(manifest), encoding="utf-8")
    report = {
        "products": len(deals),
        "categories": len(CATEGORIES),
        "guides": len(GUIDES),
        "sitemap_urls": len(sitemap),
        "changed_files": changed,
        "removed_stale_files": removed,
        "source_updated_at": source.get("updated_at", ""),
    }
    (ROOT / "seo-report.json").write_text(dump_json(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = build()
    print("[seo] " + " | ".join(f"{key}={value}" for key, value in result.items()))
