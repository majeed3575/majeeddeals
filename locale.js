/* Display translations. Catalog records, category IDs and affiliate URLs remain source data. */
(function (root) {
  "use strict";
  const messages = {
    "الصفحة الرئيسية": "Home",
    "التنقل الرئيسي": "Main navigation",
    "الرئيسية": "Home",
    "العروض": "Deals",
    "التصنيفات": "Categories",
    "الأدلة": "Guides",
    "لماذا أوفرلي؟": "Why Overly?",
    "تبديل مظهر الموقع": "Switch theme",
    "تفعيل الوضع الفاتح": "Switch to light mode",
    "تفعيل الوضع الداكن": "Switch to dark mode",
    "فتح البحث والفلاتر": "Open search and filters",
    "بحث وفلاتر": "Search & filters",
    "رتّب النتائج بطريقتك": "Make it your search",
    "بحث وتصنيف وترتيب في مكان واحد": "Search, filter and sort in one place",
    "إغلاق الفلاتر": "Close filters",
    "ابحث عن شاحن، منزل، حقيبة…": "Search chargers, home, bags…",
    "ابحث في العروض": "Search deals",
    "اختر التصنيف": "Choose a category",
    "كل التصنيفات": "All categories",
    "الكل": "All",
    "الإلكترونيات": "Electronics",
    "التنظيف والمنظفات": "Cleaning",
    "الأزياء والأحذية": "Fashion & shoes",
    "المطبخ والأجهزة المنزلية": "Kitchen & appliances",
    "الأثاث والديكور": "Furniture & decor",
    "المنزل": "Home",
    "السيارة": "Automotive",
    "السفر": "Travel",
    "الرحلات والبحر والتخييم": "Outdoors & camping",
    "الحدائق والزراعة": "Garden",
    "الجمال والعناية": "Beauty & care",
    "الصحة والعناية": "Health & care",
    "البقالة والمشروبات": "Grocery & drinks",
    "الرياضة": "Sports",
    "الأطفال": "Kids",
    "الألعاب": "Toys & games",
    "الحيوانات الأليفة": "Pets",
    "الأدوات والهوايات": "Tools & hobbies",
    "الترفيه المنزلي": "Home entertainment",
    "المدرسة والقرطاسية": "School & stationery",
    "الكتب والمكتب": "Books & office",
    "الساعات والمجوهرات": "Watches & jewellery",
    "تسوق متنوع": "More finds",
    "ترتيب العروض": "Sort deals",
    "اختيارات أوفرلي": "The Overly edit",
    "الأعلى خصمًا": "Biggest discount",
    "السعر قبل الخصم: الأعلى": "Original price: high to low",
    "السعر قبل الخصم: الأقل": "Original price: low to high",
    "الاسم أبجديًا": "Name: A–Z",
    "إعادة تعيين": "Reset",
    "عرض": "Show",
    "نتيجة": "results",
    "إغلاق نافذة الفلاتر": "Close filter panel",
    "تفاصيل صغيرة.": "Small details.",
    "تغيّر يومك.": "Better every day.",
    "مساحة هادئة بأثاث بترولي وإضاءة طبيعية، صورة تعبيرية للإلهام": "A calm space with teal furniture and natural light. An illustrative image for inspiration.",
    "مساحة للإلهام": "ROOM FOR INSPIRATION",
    "لذوقك، مساحة.": "Make room for you.",
    "صورة تعبيرية": "Illustrative image",
    "اكتشف منتجات أمازون السعودية وعلي إكسبريس في مكان واحد، واشترِ مباشرة من المتجر.": "Discover products from Amazon.sa and AliExpress in one place. Buy directly from the store.",
    "ابحث في منتجات أوفرلي": "Search Overly products",
    "اسم المنتج الذي تبحث عنه": "Product you are looking for",
    "وش على بالك اليوم؟": "What are you looking for?",
    "اكتشف": "Explore",
    "اكتشف ما يناسبك": "Find your next favourite",
    "كيف يعمل أوفرلي؟": "How does Overly work?",
    "ابدأ من اهتماماتك": "Start with your interests",
    "تقنية تحبّها.": "Tech to love.",
    "لتفاصيل يومك": "Made for your everyday",
    "اكتشف التقنية": "Explore tech",
    "آيباد من منتجات قسم التقنية": "iPad from the tech collection",
    "بيت يشبهك.": "Home, your way.",
    "لمساحتك الخاصة": "For your own space",
    "اكتشف المنزل": "Explore home",
    "جهاز تنقية الهواء من منتجات قسم المنزل": "Air purifier from the home collection",
    "ملخص المنصة": "At a glance",
    "منتج للاكتشاف": "products to discover",
    "٢": "2",
    "منصات تسوق": "shopping platforms",
    "مباشرة": "Direct",
    "الشراء من المتجر": "purchase from the store",
    "البداية من اهتمامك": "FOLLOW YOUR CURIOSITY",
    "وش ودّك تكتشف؟": "Where will you start?",
    "تصنيفات التسوق": "Shopping categories",
    "مرّر لاكتشاف الأقسام ← ·": "Swipe to explore → ·",
    "اختر قسمًا لعرض منتجاته هنا.": "Choose a category to see its products here.",
    "أبرز العروض": "Featured deals",
    "مزايا الموقع": "What to expect",
    "بلا مبالغة": "No exaggeration",
    "نسب الخصم كما رُصدت": "Discounts as recorded",
    "السعر الحالي": "Current price",
    "يُتحقق مباشرة لدى المتجر": "Check directly with the store",
    "طريق مختصر": "A shorter path",
    "رابط مباشر إلى صفحة المنتج": "Direct links to product pages",
    "وش تدور عليه؟": "What are you looking for?",
    "ابحث في أوفرلي أو في AliExpress مباشرة": "Search Overly or AliExpress directly",
    "نطاق البحث": "Search scope",
    "عروض أوفرلي": "Overly picks",
    "AliExpress كامل": "All AliExpress",
    "ابحث في المنتجات المحفوظة…": "Search the Overly catalog…",
    "البحث في المنتجات": "Search products",
    "تنفيذ البحث": "Search",
    "تصنيفات وعبارات رائجة": "Popular categories and searches",
    "الأكثر رواجًا": "Trending",
    "منزل ذكي": "Smart home",
    "ترفيه منزلي": "Home entertainment",
    "للسيارة": "For your car",
    "للسفر": "For travel",
    "للحدائق": "For the garden",
    "للبحر والصيد": "Fishing & sea",
    "للتخييم": "For camping",
    "للمدرسة والقرطاسية": "School & stationery",
    "اختر النطاق ثم اكتب ما تبحث عنه.": "Choose where to search, then enter a product.",
    "ابحث في AliExpress بالكامل": "Search all of AliExpress",
    "بحث مباشر عبر الواجهة الرسمية — لا يقتصر على المنتجات المحفوظة": "Live search through the official API, beyond the saved catalog",
    "يشحن إلى السعودية فقط": "Ships to Saudi Arabia only",
    "مثال: شاحن سريع، كاميرا سيارة، أداة مطبخ…": "Try a fast charger, dash cam or kitchen tool…",
    "ابحث في منتجات AliExpress القابلة للشحن للسعودية": "Search AliExpress products that ship to Saudi Arabia",
    "ابحث في AliExpress ⌕": "Search AliExpress ⌕",
    "اقتراحات بحث": "Search suggestions",
    "شواحن سريعة": "Fast chargers",
    "كاميرات سيارة": "Dash cams",
    "أدوات مطبخ": "Kitchen tools",
    "إكسسوارات سفر": "Travel accessories",
    "النتائج تعتمد على توفر الشحن إلى السعودية وقت البحث.": "Results depend on shipping availability to Saudi Arabia at the time of search.",
    "اختيارات أوفرلي الحالية": "THE CURRENT EDIT",
    "ما يستحق نظرتك": "Worth a closer look",
    "عروض": "deals",
    "اختيار منصة التسوق": "Choose a store",
    "تصفّح حسب المتجر": "Browse by store",
    "الأسعار والتوفر النهائيان لدى المنصة المختارة ·": "Final prices and availability are on the selected store ·",
    "كل العروض": "All deals",
    "تصنيفات المنتجات": "Product categories",
    "تحميل المزيد": "Load more",
    "لا توجد نتائج مطابقة": "No matching results",
    "جرّب كلمة أخرى أو غيّر التصنيف.": "Try another keyword or category.",
    "فلسفة أوفرلي": "THE OVERLY APPROACH",
    "أقل ضجيجًا. أوضح قرارًا.": "Less noise. Clearer choices.",
    "اختيار واعٍ": "Thoughtful discovery",
    "لا نعرض كل شيء.": "Not everything.",
    "نعرض ما يستحق نظرتك.": "Just things worth a look.",
    "تجربة مصممة حول الوضوح: منتج، خصم مرصود، ورابط مباشر للتحقق من السعر الحالي لدى المتجر.": "Keep it clear: a product, its recorded discount and a direct link to check the current store price.",
    "وضوح السعر": "Price clarity",
    "المتجر هو المرجع النهائي.": "The store has the final say.",
    "السعر والتوفر المعتمدان هما الظاهران على Amazon.sa أو AliExpress لحظة الشراء.": "The price and availability shown on Amazon.sa or AliExpress at checkout are what count.",
    "شفافية": "Transparency",
    "الإفصاح جزء من التجربة.": "Disclosure is part of the experience.",
    "روابط العمولة موضحة، ولا تضيف أي تكلفة على المشتري.": "Affiliate links are disclosed and add no extra cost for you.",
    "روابط واضحة لمحركات البحث والزوار": "EXPLORE THE DIRECTORY",
    "استكشف أوفرلي حسب احتياجك": "Explore Overly your way",
    "صفحات ثابتة تتحدث آليًا مع قائمة المنتجات، وتساعدك على الوصول إلى القسم المناسب بسرعة.": "Find the right category through dedicated catalog pages. Catalog and guide content is currently in Arabic.",
    "دليل أقسام أوفرلي": "Overly category directory",
    "شواحن وأجهزة وملحقات": "Chargers, devices & accessories",
    "تنظيم ومطبخ ومنزل ذكي": "Organization, kitchen & smart home",
    "أدوات وإكسسوارات عملية": "Practical tools & accessories",
    "راحة وتنظيم أثناء التنقل": "Comfort & organization on the go",
    "ري وتقليم وأدوات عملية": "Watering, pruning & garden tools",
    "صيد وغوص وتجهيزات رحلات": "Fishing, diving & outdoor gear",
    "ملابس وأحذية وإكسسوارات": "Clothing, shoes & accessories",
    "عناية شخصية وأدوات": "Personal care & tools",
    "لياقة ونشاط يومي": "Fitness & everyday activity",
    "منتجات عملية للأسرة": "Practical finds for the family",
    "أدوات للعناية اليومية": "Everyday care essentials",
    "مشروعات وهوايات منزلية": "Home projects & hobbies",
    "بروجكترات وتلفزيونات": "Projectors & televisions",
    "أدلة الشراء": "Buying guides",
    "قوائم فحص قبل الطلب": "Checklists before you order",
    "العروض أوضح. الاختيار أسرع.": "Clearer deals. Easier choices.",
    "إفصاح: بصفتنا مشاركين في برنامج أمازون أسوشيتس (Amazon Associates)، نحصل على عمولة من عمليات الشراء المؤهلة عبر روابط أمازون دون تكلفة إضافية عليك. وقد تتضمن الصفحة روابط تسويق بالعمولة لمتاجر أخرى مثل AliExpress. الأسعار ونسب الخصم كما رُصدت وقت آخر تحديث وقد تتغيّر — السعر النهائي المعتمد هو الظاهر لدى المتجر لحظة الشراء.": "Disclosure: As an Amazon Associate, we earn from qualifying purchases through Amazon links at no extra cost to you. This page may also contain affiliate links to other stores, including AliExpress. Prices and discounts were recorded at the last update and may change. The final price is the one shown by the store at checkout.",
    "الصفحات القانونية": "Legal pages",
    "عن أوفرلي": "About Overly",
    "منهجية الاختيار": "How we select",
    "سياسة الخصوصية": "Privacy policy",
    "شروط الاستخدام": "Terms of use",
    "إفصاح العمولة": "Affiliate disclosure",
    "حقوق الملكية": "Copyright",
    "التنقل السريع": "Quick navigation",
    "الأقسام": "Categories",
    "بحث": "Search",
    "إغلاق": "Close",
    "اعرض العرض لدى المتجر ↗": "View deal at the store ↗",
    "لا شكرًا، سأكمل التصفح": "No thanks, keep browsing",
    "جاري التحقق من توفر العرض…": "Opening the store…",
    "سيتم تحويلك بأمان إلى صفحة المنتج لدى المتجر خلال لحظات": "You will be taken to the store’s product page shortly",
    "إغلاق النظرة السريعة": "Close quick view",
    "صورة المنتج": "Product image",
    "رقم المنتج": "Product ID",
    "السعر والتوفر": "Price & availability",
    "يُتحقق لدى المتجر": "Check at the store",
    "اعرض السعر الحالي ↗": "View current price ↗",
    "تخطّي الجولة": "Skip tour",
    "وجهاتك المفضلة، أقرب.": "Your favourite stores, closer.",
    "متجران. مساحة واحدة للاكتشاف.": "Two stores. One place to discover.",
    "٠١ / أهلًا بك في أوفرلي": "01 / WELCOME TO OVERLY",
    "اكتشاف حلو،": "Your next great find",
    "يبدأ من هنا.": "starts here.",
    "نجمع لك منتجات من أمازون السعودية وعلي إكسبريس، عشان تبدأ بحثك من مكان واحد وتكتشف أشياء تناسبك.": "Discover products from Amazon.sa and AliExpress together. Start in one place and find things that suit you.",
    "اختر طريقك للاكتشاف": "Choose your way to explore",
    "التقنية": "Tech",
    "الأزياء": "Fashion",
    "ابحث باسم المنتج، أو ابدأ من قسم تحبّه.": "Search for a product or start with a category you love.",
    "٠٢ / على ذوقك أنت": "02 / MAKE IT YOURS",
    "عارف وش تبي؟": "Know what you want?",
    "أو جاي تكتشف؟": "Or just exploring?",
    "ابحث عن احتياجك أو تصفّح التصنيفات. استعرض تفاصيل المنتجات، واختر المتجر ورتّب النتائج بالطريقة المناسبة لك.": "Search or browse by category. Explore product details, choose a store and sort results your way.",
    "من الاكتشاف إلى اختيارك": "From discovery to your choice",
    "اختيارك من أوفرلي": "Your Overly find",
    "المنتج اللي يناسبك": "The product for you",
    "السعر والتوفر النهائيان لدى المتجر": "Final price and availability at the store",
    "أكمل عند المتجر": "Continue at the store",
    "تصفّح هنا. واشترِ مباشرة من المتجر.": "Browse here. Buy directly from the store.",
    "٠٣ / اختر وأنت على بيّنة": "03 / CHOOSE WITH CONFIDENCE",
    "عجبك شيء؟": "Found something you love?",
    "باقي خطوة.": "One step to go.",
    "افتح رابط المنتج للتحقق من السعر والشحن والتوفر، وأكمل الشراء في المتجر نفسه. أوفرلي دليل تسوّق، وليس جهة البيع.": "Open the product link to check price, shipping and availability, then buy at the store. Overly is a shopping guide, not the seller.",
    "قد نحصل على عمولة عند الشراء عبر روابطنا، دون تكلفة إضافية عليك.": "We may earn a commission when you buy through our links, at no extra cost to you.",
    "خطوات التعريف بالموقع": "Welcome tour steps",
    "الخطوة الأولى: فكرة أوفرلي": "Step 1: Meet Overly",
    "الخطوة الثانية: الاكتشاف": "Step 2: Explore",
    "الخطوة الثالثة: الشراء": "Step 3: Shop",
    "السابق": "Back",
    "التالي": "Next",
    "يلا نكتشف": "Let’s explore",
    "جولة اختيارية، على راحتك.": "An optional tour, at your own pace.",
    "الخطوة ١ من ٣": "Step 1 of 3",
    "اللغة": "Language",
    "صفحات التفاصيل ونتائج البحث المباشر غير المترجمة قد تظهر بلغتها الأصلية.": "Detail pages and untranslated live-search results may appear in their original language.",
    "التقنية والإلكترونيات": "Tech & electronics",
    "المنزل والمعيشة": "Home & living",
    "السيارة وإكسسواراتها": "Car & accessories",
    "عالم الأطفال": "Kids’ world",
    "منتج رائج": "Trending product",
    "ر.س": "SAR",
    "٪": "%",
    "{count} مبيعة": "{count} sold",
    "خصم {discount}٪": "{discount}% off",
    "وفّر {discount}٪": "Save {discount}%",
    "{store} قبل الخصم": "{store} original price",
    "السعر الحالي والتوفر يُتحقق منهما على {store}": "Check current price and availability on {store}",
    "اعرض السعر الحالي على AliExpress ↗": "View price on AliExpress ↗",
    "اعرض السعر الحالي على أمازون ↗": "View price on Amazon ↗",
    "ابحث في AliExpress القابل للشحن للسعودية…": "Search AliExpress shipping to Saudi Arabia…",
    "ستظهر نتائج AliExpress القابلة للشحن إلى السعودية فقط.": "Only AliExpress products shipping to Saudi Arabia will appear.",
    "البحث داخل قائمة أوفرلي الحالية.": "Searching the current Overly catalog.",
    "اكتب حرفين على الأقل للبحث في AliExpress.": "Enter at least two characters to search AliExpress.",
    "وجدنا {count} نتيجة مطابقة في أوفرلي.": "Found {count} matching results on Overly.",
    "يعرض أوفرلي الآن {count} من المنتجات الأكثر رواجًا.": "Overly is showing {count} trending products.",
    "أحد أبرز عروض {store}": "A featured find from {store}",
    "استعرض كل العروض": "Browse all deals",
    "تفاصيل {title}": "Details: {title}",
    "العرض السابق": "Previous deal",
    "العرض التالي": "Next deal",
    "العرض {count}": "Deal {count}",
    "جاري تحميل العروض الحالية…": "Loading the current catalog…",
    "لا توجد نتائج قابلة للشحن للسعودية": "No results shipping to Saudi Arabia",
    "عروض AliExpress قيد الإضافة": "AliExpress deals are being added",
    "نتحقق من أحدث نسخة للكتالوج، ولن نعرض بيانات قديمة بدلًا منها.": "Checking the current catalog. Outdated fallback data will not be shown.",
    "جرّب وصفاً أوسع أو كلمة مختلفة؛ النتائج تأتي مباشرة من AliExpress للسعودية.": "Try a broader description or another keyword. Results come directly from AliExpress for Saudi Arabia.",
    "جهّزنا المنصة والفلترة والروابط؛ ستظهر هنا العروض الموثقة فور إضافتها، دون منتجات أو أسعار تجريبية.": "Verified deals will appear here when added, without placeholder products or prices.",
    "جرّب كلمة أخرى أو غيّر التصنيف أو المتجر.": "Try another keyword, category or store.",
    "تحميل نتائج أخرى من AliExpress": "Load more AliExpress results",
    "تحميل {count} عرضًا إضافيًا": "Load {count} more deals",
    "واصل النزول — تُجلب نتائج AliExpress التالية تلقائيًا ({count})": "Keep scrolling for more AliExpress results ({count})",
    "واصل النزول — تظهر العروض تلقائيًا ({count} من {total})": "Keep scrolling for more deals ({count} of {total})",
    "يظهر الآن {count} نتيجة": "Showing {count} results",
    "يظهر الآن {count} من أصل {total}": "Showing {count} of {total}",
    "⌘ نظرة سريعة": "⌘ Quick view",
    "السعر على {store}": "Price on {store}",
    "تفاصيل العرض": "Deal details",
    "يُتحقق على {store}": "Check on {store}",
    "التوفر والسعر النهائي": "Availability & final price",
    "عرض السعر ↗": "View price ↗",
    "مشاركة {title}": "Share {title}",
    "مشاركة العرض": "Share deal",
    "آخر تحديث {date}": "Last updated {date}",
    "منتج من قسم {category}": "A product from {category}",
    "{count} منتج": "{count} products",
    "نجهّز لك أبواب الاكتشاف…": "Preparing your collections…",
    "تصفّح": "Browse",
    "دليل التصنيفات": "the category directory",
    "للبدء.": "to get started.",
    "الخطوة {count} من {total}": "Step {count} of {total}",
    "اكتب حرفين على الأقل، وبحد أقصى 80 حرفاً.": "Enter between 2 and 80 characters.",
    "بوابة البحث الآمنة بانتظار ربط عنوان Cloudflare.": "Live search is not configured yet.",
    "جاري جلب نتائج إضافية قابلة للشحن للسعودية…": "Loading more results shipping to Saudi Arabia…",
    "جاري البحث في AliExpress بالكامل…": "Searching AliExpress…",
    "ظهرت {count} نتيجة من AliExpress قابلة للشحن للسعودية{more}.": "Found {count} AliExpress results shipping to Saudi Arabia{more}.",
    " — واصل النزول للمزيد": " — keep scrolling for more",
    "لم تظهر نتائج قابلة للشحن للسعودية لهذه العبارة؛ جرّب كلمة أخرى.": "No products shipping to Saudi Arabia matched this search. Try another keyword.",
    "استغرق البحث وقتًا أطول من المتوقع؛ أعد المحاولة بعد قليل.": "The search took too long. Please try again shortly.",
    "تمت طلبات كثيرة خلال دقيقة؛ انتظر قليلاً ثم أعد المحاولة.": "Too many requests. Please wait a moment and try again.",
    "تعذر الوصول إلى بحث AliExpress الآن؛ حاول مرة أخرى بعد قليل.": "AliExpress search is unavailable right now. Please try again shortly.",
    "© {year} أوفرلي (Overly) — جميع الحقوق محفوظة.": "© {year} Overly — All rights reserved."
  };

  Object.assign(messages, root.OverlySiteEnglish || {});
  function create(options = {}) {
    const storageKey = "overly_language_v1";
    let language = "ar";
    try { if (options.storage?.getItem(storageKey) === "en") language = "en"; } catch (_) {}
    if (options.document?.documentElement.lang === 'en') language = 'en';
    const bindings = [];
    const normalize = value => String(value).replace(/\s+/g, " ").trim();
    const catalog = options.catalogMessages || {...(root.OverlyCatalogNativeEnglish || {}), ...(root.OverlyCatalogEnglish || {}), ...(root.OverlyCatalogAdditions || {})};
    const lookup = key => Object.prototype.hasOwnProperty.call(messages,key) ? messages[key] : Object.prototype.hasOwnProperty.call(catalog,key) ? catalog[key] : undefined;
    const english = key => root.OverlyEnglishPhrase ? root.OverlyEnglishPhrase(key,lookup) : lookup(key) ?? key;
    const has = key => lookup(key) !== undefined;
    const catalogKey = value => normalize(String(value || "").replace(/[\u0000-\u001f\u007f]/g, " ")).slice(0, 180);
    const englishTitle = deal => {
      const key = catalogKey(deal?.title);
      return Object.prototype.hasOwnProperty.call(catalog, key) && typeof catalog[key] === "string" ? catalog[key] : "";
    };
    const api = {
      get language() { return language; },
      get locale() { return language === "ar" ? "ar-SA" : "en-SA"; },
      has,
      categorySearchText(key) { return english(key); },
      productTitle(deal) { return (language === "en" && (englishTitle(deal) || deal?.title_en)) || String(deal?.title || ""); },
      productSearchText(deal) { return `${String(deal?.title || "")} ${englishTitle(deal)} ${deal?.title_en || ''}`; },
      t(key, params = {}) {
        const text = language === "en" ? english(key) : key;
        return String(text).replace(/\{(\w+)\}/g, (match, name) => Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match);
      },
      number(value) { return new Intl.NumberFormat(api.locale, {maximumFractionDigits: 0}).format(value); },
      setLanguage(value) {
        language = value === "en" ? "en" : "ar";
        try { options.storage?.setItem(storageKey, language); } catch (_) {}
        if (options.document) {
          options.document.documentElement.lang = language;
          options.document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
        }
        api.applyStatic();
        return language;
      },
      // Bind only server-rendered interface text, once, before catalog rendering.
      // Never walk fetched product data or change values, hrefs, IDs or query attributes.
      bindStatic(container) {
        const doc = options.document;
        if (!doc || !container) return;
        const walker = doc.createTreeWalker(container, 4);
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if (node.parentElement.closest('script,style,[translate="no"]')) continue;
          const key = normalize(node.nodeValue);
          if (has(key)) {
            const leading = node.nodeValue.match(/^\s*/)[0];
            const trailing = node.nodeValue.match(/\s*$/)[0];
            bindings.push({node, key, write: value => { node.nodeValue = leading + value + trailing; }});
          }
        }
        container.querySelectorAll("[aria-label],[placeholder],[title],[alt]").forEach(node => {
          if (node.closest('[translate="no"]')) return;
          for (const attribute of ["aria-label", "placeholder", "title", "alt"]) {
            const key = node.getAttribute(attribute);
            if (has(key)) bindings.push({node, key, write: value => node.setAttribute(attribute, value)});
          }
        });
        api.applyStatic();
      },
      applyStatic() {
        for (const binding of bindings) if (binding.node.isConnected) binding.write(api.t(binding.key));
      }
    };
    if (options.document) {
      options.document.documentElement.lang = language;
      options.document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    }
    return api;
  }
  root.createOverlyI18n = create;
  if (root.document) {
    let storage;
    try { storage = root.localStorage; } catch (_) {}
    root.OverlyI18n = create({storage, document: root.document});
  }
})(globalThis);
