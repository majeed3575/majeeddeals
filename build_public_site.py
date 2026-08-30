#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني حزمة الموقع العامة من قائمة سماح صريحة لنشرها على Cloudflare.

لا ينسخ كود Workers أو الاختبارات أو الأسرار أو أدوات الإدارة. بذلك يبقى
النشر الآلي للموقع منفصلاً عن الخدمات الخلفية الموجودة في المستودع الخاص.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist-site"

PUBLIC_FILES = (
    ".nojekyll",
    "index.html",
    "404.html",
    "about.html",
    "methodology.html",
    "privacy.html",
    "terms.html",
    "affiliate-disclosure.html",
    "copyright.html",
    "aliexpress-callback.html",
    "search-config.js",
    "legal.css",
    "seo.css",
    "robots.txt",
    "sitemap.xml",
    "deals.json",
    "deals-initial.json",
    "_headers",
)
PUBLIC_DIRS = ("assets", "products", "categories", "stores", "guides")
ASSET_SUFFIXES = {".avif", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
SOURCE_ONLY_ASSETS = {
    "overly-dark-chroma.png",
    "overly-dark-logo-trimmed.png",
    "overly-dark-logo.png",
    "overly-icon.png",
}


def safe_copy(source: Path, destination: Path) -> int:
    if source.is_symlink():
        raise RuntimeError(f"رابط رمزي مرفوض داخل الحزمة العامة: {source.relative_to(ROOT)}")
    if source.is_dir():
        copied = 0
        for child in sorted(source.iterdir()):
            copied += safe_copy(child, destination / child.name)
        return copied
    if not source.is_file():
        return 0
    relative = source.relative_to(ROOT)
    if relative.parts[0] == "assets" and source.suffix.lower() not in ASSET_SUFFIXES:
        return 0
    if relative.parts[0] == "assets" and source.name in SOURCE_ONLY_ASSETS:
        return 0
    if relative.parts[0] in {"products", "categories", "stores", "guides"} and source.suffix.lower() != ".html":
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return 1


def build() -> int:
    if OUTPUT.resolve() != (ROOT / "dist-site").resolve():
        raise RuntimeError("مسار الحزمة العامة غير آمن")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    copied = 0
    for relative in PUBLIC_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise RuntimeError(f"ملف عام مطلوب مفقود: {relative}")
        copied += safe_copy(source, OUTPUT / relative)
    for relative in PUBLIC_DIRS:
        source = ROOT / relative
        if not source.is_dir():
            raise RuntimeError(f"مجلد عام مطلوب مفقود: {relative}")
        copied += safe_copy(source, OUTPUT / relative)
    for verification in ROOT.glob("google*.html"):
        if re.fullmatch(r"google[a-zA-Z0-9_-]{6,100}\.html", verification.name):
            copied += safe_copy(verification, OUTPUT / verification.name)
    forbidden = [
        path for path in OUTPUT.rglob("*")
        if path.is_file() and any(part in {".git", ".github", "node_modules", "cloudflare-worker", "cloudflare-admin", "cloudflare-amazon-bot", "overly-backend-private"} for part in path.parts)
    ]
    if forbidden:
        raise RuntimeError("الحزمة العامة تحتوي مسارات خلفية غير مسموحة")
    return copied


if __name__ == "__main__":
    print(f"[public-build] OK | files={build()} | output={OUTPUT.name}")
