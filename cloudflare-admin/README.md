# لوحة إدارة أوفرلي الآمنة

لوحة خاصة لإضافة منتجات `deals.json` وتعديلها وحذفها من المتصفح. تُشغّل في Worker مستقل
وتُحمى بالكامل بواسطة Cloudflare Access. لا توجد كلمة مرور أو مفاتيح داخل HTML.

## لماذا Worker مستقل؟

بوابة البحث `overly-aliexpress-search` عامة ويحتاجها جميع الزوار. حماية الـWorker نفسه
بـAccess ستوقف البحث العام، لذلك تعمل لوحة الإدارة في Worker مستقل اسمه `overly-admin`.

## الأسرار والإعدادات المطلوبة

أضف القيم التالية من **Cloudflare → Worker overly-admin → Settings → Variables and Secrets**:

- `GITHUB_ADMIN_TOKEN` — نوع **Secret**. مفتاح GitHub Fine-grained مخصص للمستودع
  `majeed3575/majeeddeals` بصلاحية **Contents: Read and write** فقط.
- `ADMIN_ALLOWED_EMAIL` — نوع **Secret**. بريد المالك الذي سيسمح له بالدخول.
- `TEAM_DOMAIN` — قيمة مثل `https://TEAM.cloudflareaccess.com`.
- `POLICY_AUD` — Application Audience (AUD) من تطبيق Cloudflare Access.

لا ترسل هذه القيم في المحادثة ولا تكتبها في الملفات.

## إعداد Cloudflare Access

1. انشر Worker: `npm install` ثم `npm run deploy`.
2. افتح **Cloudflare Zero Trust → Access controls → Applications**.
3. أنشئ تطبيق **Self-hosted** واختر Worker المسمى `overly-admin` كاملًا.
4. أضف سياسة **Allow** لبريد المالك فقط، واترك الوضع الافتراضي Deny لبقية الأشخاص.
5. انسخ **Application Audience (AUD) Tag** إلى `POLICY_AUD`.
6. ضع Team domain الكامل في `TEAM_DOMAIN`.

حتى لو حدث خطأ في إعداد Access، يرفض الكود كل طلب لا يحمل JWT صحيحًا وموقّعًا من حساب
Cloudflare، ثم يطابق البريد مع `ADMIN_ALLOWED_EMAIL`.

## الحماية المطبقة

- تحقق كامل من توقيع Cloudflare Access JWT عبر مفاتيح الحساب الدوارة، وليس مجرد ترويسة.
- تقييد الدخول ببريد مالك واحد.
- مفتاح GitHub يبقى داخل Cloudflare Secret ولا يصل إلى المتصفح.
- حماية CSRF عبر مطابقة Origin وترويسة مخصصة وطلبات JSON فقط.
- تنظيف جميع حقول المنتجات والسماح بنطاقات الصور والروابط الرسمية فقط.
- حد صارم لحجم طلب الحفظ، ومنع الكتابة المتعارضة عبر SHA الخاص بملف GitHub.
- سياسة CSP بنمط nonce، ومنع الإطارات والكاميرا والميكروفون والموقع الجغرافي.
- كل حفظ ينتج commit في GitHub، لذلك يمكن مراجعة التغييرات والرجوع عنها.
- المنتجات المضافة يدويًا تُعلّم `owner_pinned: true` و`auto_discovered: false` حتى يحافظ
  عليها الدمج الآلي في التشغيلات التالية.

## لوحة التحليلات

ترتبط اللوحة بقاعدة D1 المشتركة `overly-analytics` عبر `ANALYTICS_DB`. تعرض فترات 7 و30
و90 يومًا، وتشمل الزيارات والنقرات وCTR والنشاط اليومي وأفضل المنتجات والتصنيفات والمتاجر
والأجهزة والدول ومصادر الزيارة. لا تعرض بيانات شخصية لأن الـWorker العام لا يخزن عنوان IP
أو معرّف زائر دائم أصلًا.
