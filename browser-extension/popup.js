const STORE_KEY = "collected_deals_v3";
const LEGACY_STORE_KEY = "collected_deals";
const ALLOWED_CATEGORIES = ["الإلكترونيات", "المنزل", "الموضة"];
const GITHUB_EDIT_URL = "https://github.com/majeed3575/majeeddeals/edit/main/deals.json";

const $ = (id) => document.getElementById(id);
let currentDealPrice = 0;

// هذه الدالة تُنفّذ داخل صفحة منتج Amazon.sa أو AliExpress، لذلك يجب أن تبقى مستقلة.
function extractFromAmazonPage() {
  function westernDigits(value) {
    return String(value || "")
      .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
      .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d));
  }

  function numberFromText(value) {
    let text = westernDigits(value).replace(/[^\d.,]/g, "");
    if (!text) return 0;
    if (text.includes(",") && text.includes(".")) text = text.replace(/,/g, "");
    else if ((text.match(/,/g) || []).length === 1 && !text.includes(".")) {
      const parts = text.split(",");
      text = parts[1] && parts[1].length <= 2 ? parts.join(".") : parts.join("");
    } else text = text.replace(/,/g, "");
    const amount = Number.parseFloat(text);
    return Number.isFinite(amount) ? amount : 0;
  }

  function firstText(selectors) {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && element.textContent.trim()) return element.textContent.trim();
    }
    return "";
  }

  function firstPrice(selectors) {
    return numberFromText(firstText(selectors));
  }

  if (/aliexpress\.(com|us)$/i.test(location.hostname)) {
    const productMatch = location.pathname.match(/\/item\/(\d+)\.html/i)
      || location.href.match(/[?&](?:productId|itemId)=(\d+)/i);
    const productId = productMatch ? productMatch[1] : "";
    const title = String(
      firstText(["h1[data-pl=product-title]", ".product-title-text", "h1"])
      || document.querySelector('meta[property="og:title"]')?.content || ""
    ).replace(/\s+/g, " ").trim().slice(0, 140);
    const image = String(
      document.querySelector('meta[property="og:image"]')?.content
      || document.querySelector(".magnifier--image--RM17RL2, .image-view--previewBox--A0BvBKH img, img[class*=main]")?.src || ""
    ).split("?")[0];
    const dealPrice = firstPrice([
      "[class*=price--current]", "[class*=price-current]", "[class*=product-price-current]",
      ".uniform-banner-box-price", "[data-pl=product-price]"
    ]);
    let originalPrice = firstPrice([
      "[class*=price--original]", "[class*=price-original]", "[class*=price-del]",
      "[class*=originalPrice]", "del"
    ]);
    const discountText = firstText(["[class*=discount]", "[class*=saving]"]);
    const discountMatch = westernDigits(discountText).match(/(\d{1,2})\s*%/);
    let discount = discountMatch ? Number.parseInt(discountMatch[1], 10) : 0;
    if (!originalPrice && dealPrice && discount > 0 && discount < 100) originalPrice = dealPrice / (1 - discount / 100);
    if (!discount && originalPrice > dealPrice && dealPrice > 0) discount = Math.round((1 - dealPrice / originalPrice) * 100);

    const searchableTitle = title.toLowerCase();
    const contains = (words) => words.some((word) => searchableTitle.includes(word));
    let category = "الإلكترونيات";
    if (contains(["kitchen", "vacuum", "blender", "coffee", "fryer", "pillow", "lamp", "cleaner", "ice", "scale", "purifier", "مطبخ", "منزل", "تنظيف"])) category = "المنزل";
    else if (contains(["bag", "shoe", "shirt", "dress", "sunglasses", "perfume", "jacket", "backpack", "wallet", "umbrella", "حقيبة", "حذاء", "ملابس", "عطر"])) category = "الموضة";

    return {
      store: "aliexpress",
      product_id: productId,
      url: location.href.split("?")[0],
      title,
      image,
      dealPrice: Math.round(dealPrice * 100) / 100,
      originalPrice: Math.round(originalPrice * 100) / 100,
      discount,
      category
    };
  }

  const asinMatch = location.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i)
    || location.href.match(/[?&]asin=([A-Z0-9]{10})/i);
  const asinInput = document.getElementById("ASIN") || document.querySelector("[name=ASIN]");
  const asin = (asinMatch ? asinMatch[1] : asinInput && asinInput.value || "").toUpperCase();

  const titleElement = document.getElementById("productTitle");
  const ogTitle = document.querySelector('meta[property="og:title"]');
  const title = String(titleElement ? titleElement.textContent : ogTitle ? ogTitle.content : "")
    .replace(/\s+/g, " ").trim().slice(0, 140);

  const imageElement = document.getElementById("landingImage")
    || document.querySelector("#imgTagWrapperId img, #main-image");
  const ogImage = document.querySelector('meta[property="og:image"]');
  const image = String(imageElement
    ? imageElement.getAttribute("data-old-hires") || imageElement.src
    : ogImage ? ogImage.content : "").split("?")[0];

  const dealPrice = firstPrice([
    ".priceToPay .a-offscreen",
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#corePrice_feature_div .a-price .a-offscreen",
    ".apexPriceToPay .a-offscreen",
    ".a-price .a-offscreen"
  ]);
  let originalPrice = firstPrice([
    ".basisPrice .a-offscreen",
    "[data-a-strike=true] .a-offscreen",
    ".a-text-price .a-offscreen",
    "#listPrice",
    ".priceBlockStrikePriceString"
  ]);

  const discountText = firstText([".savingsPercentage", "[class*=savingPercentage]"]);
  const discountMatch = westernDigits(discountText).match(/(\d{1,2})/);
  let discount = discountMatch ? Number.parseInt(discountMatch[1], 10) : 0;
  if (!originalPrice && dealPrice && discount > 0 && discount < 100) {
    originalPrice = dealPrice / (1 - discount / 100);
  }
  if (!discount && originalPrice > dealPrice && dealPrice > 0) {
    discount = Math.round((1 - dealPrice / originalPrice) * 100);
  }

  const searchableTitle = title.toLowerCase();
  const contains = (words) => words.some((word) => searchableTitle.includes(word));
  let category = "الإلكترونيات";
  if (contains(["مقلاة", "قلاية", "مكنسة", "خلاط", "قهوة", "مطبخ", "غسالة", "سرير", "وسادة", "إضاءة", "مصباح", "تنظيف", "ثلاجة", "ثلج", "ميزان", "تنقية", "kitchen", "vacuum", "blender", "coffee", "fryer", "pillow", "lamp", "cleaner", "ice", "scale", "purifier"])) {
    category = "المنزل";
  } else if (contains(["حقيبة", "حذاء", "قميص", "عباية", "فستان", "نظارة", "عطر", "ملابس", "جاكيت", "مظلة", "bag", "shoe", "shirt", "dress", "sunglasses", "perfume", "jacket", "backpack", "wallet", "umbrella"])) {
    category = "الموضة";
  }

  return {
    store: "amazon",
    url: location.href,
    asin,
    title,
    image,
    dealPrice: Math.round(dealPrice * 100) / 100,
    originalPrice: Math.round(originalPrice * 100) / 100,
    discount,
    category
  };
}

function storageGet(keys) {
  return new Promise((resolve) => chrome.storage.local.get(keys, resolve));
}

function storageSet(values) {
  return new Promise((resolve) => chrome.storage.local.set(values, resolve));
}

async function getList() {
  const result = await storageGet([STORE_KEY, LEGACY_STORE_KEY]);
  if (Array.isArray(result[STORE_KEY])) return result[STORE_KEY];
  if (Array.isArray(result[LEGACY_STORE_KEY])) {
    await storageSet({ [STORE_KEY]: result[LEGACY_STORE_KEY] });
    return result[LEGACY_STORE_KEY];
  }
  return [];
}

async function saveList(list) {
  await storageSet({ [STORE_KEY]: list });
}

function showStatus(message, type = "") {
  const status = $("status");
  status.className = `notice${type ? ` ${type}` : ""}`;
  status.textContent = message;
}

function normalizeAsin(value) {
  const match = String(value || "").toUpperCase().match(/[A-Z0-9]{10}/);
  return match ? match[0] : "";
}

function itemStore(raw) {
  return String(raw && raw.store || "amazon").toLowerCase() === "aliexpress" ? "aliexpress" : "amazon";
}

function normalizeProductId(value) {
  const match = String(value || "").match(/\d{6,20}/);
  return match ? match[0] : "";
}

function itemKey(item) {
  return itemStore(item) === "aliexpress" ? `aliexpress:${item.product_id}` : `amazon:${item.asin}`;
}

function roundPrice(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number * 100) / 100 : 0;
}

function normalizedItem(raw) {
  const store = itemStore(raw);
  const item = {
    store,
    title: String(raw.title || "").replace(/\s+/g, " ").trim().slice(0, 140),
    image: String(raw.image || "").trim(),
    discount_percent: Math.round(Number(raw.discount_percent || raw.discount || 0)),
    original_price: roundPrice(raw.original_price || raw.originalPrice),
    category: ALLOWED_CATEGORIES.includes(raw.category) ? raw.category : "الإلكترونيات"
  };
  if (store === "aliexpress") {
    item.product_id = normalizeProductId(raw.product_id || raw.asin);
    item.url = String(raw.url || "").trim();
  } else item.asin = normalizeAsin(raw.asin);
  return item;
}

function validateItem(item) {
  const errors = [];
  if (itemStore(item) === "amazon" && !/^[A-Z0-9]{10}$/.test(item.asin)) errors.push("رقم ASIN غير صحيح");
  if (itemStore(item) === "aliexpress" && !/^\d{6,20}$/.test(item.product_id)) errors.push("رقم منتج AliExpress غير صحيح");
  if (itemStore(item) === "aliexpress" && !/^https:\/\/([a-z0-9-]+\.)*(aliexpress\.com|aliexpress\.us)\//i.test(item.url)) errors.push("رابط AliExpress غير صحيح");
  if (item.title.length < 8) errors.push("اسم المنتج قصير أو فارغ");
  if (!item.image.startsWith("https://")) errors.push("رابط الصورة يجب أن يبدأ بـ https://");
  if (!(item.original_price > 0)) errors.push("سعر ما قبل الخصم غير صحيح");
  if (!(item.discount_percent >= 5 && item.discount_percent <= 95)) errors.push("نسبة الخصم يجب أن تكون بين 5٪ و95٪");
  if (!ALLOWED_CATEGORIES.includes(item.category)) errors.push("التصنيف غير مسموح");
  return errors;
}

function setEditor(data, editing = false) {
  $("editor").classList.remove("hidden");
  $("editorTitle").textContent = editing ? "تعديل المنتج المحفوظ" : "مراجعة المنتج الحالي";
  const store = itemStore(data);
  $("store").value = store;
  $("asin").value = store === "aliexpress" ? normalizeProductId(data.product_id || data.asin) : normalizeAsin(data.asin);
  $("productUrl").value = store === "aliexpress" ? data.url || "" : data.url || "";
  $("title").value = data.title || "";
  $("image").value = data.image || "";
  $("dealPrice").value = data.dealPrice || "";
  $("originalPrice").value = data.original_price || data.originalPrice || "";
  $("discount").value = data.discount_percent || data.discount || "";
  $("category").value = ALLOWED_CATEGORIES.includes(data.category) ? data.category : "الإلكترونيات";
  currentDealPrice = Number(data.dealPrice || 0);
  $("saveProduct").textContent = editing ? "💾 حفظ تعديل المنتج" : "➕ إضافة المنتج إلى القائمة";
}

function formItem() {
  return normalizedItem({
    store: $("store").value,
    asin: $("asin").value,
    product_id: $("asin").value,
    url: $("productUrl").value,
    title: $("title").value,
    image: $("image").value,
    original_price: $("originalPrice").value,
    discount_percent: $("discount").value,
    category: $("category").value
  });
}

function calculateDiscount() {
  const deal = Number($("dealPrice").value || currentDealPrice);
  const original = Number($("originalPrice").value);
  if (deal > 0 && original > deal) {
    $("discount").value = Math.round((1 - deal / original) * 100);
  }
}

function payloadFromList(list) {
  const deals = [...list].sort((a, b) => b.discount_percent - a.discount_percent);
  return {
    updated_at: new Date().toISOString(),
    source: "browser-extension",
    count: deals.length,
    deals
  };
}

function jsonFromList(list) {
  return JSON.stringify(payloadFromList(list), null, 2);
}

function downloadJson(filename, value) {
  const blob = new Blob([value], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function copyText(value) {
  try {
    await navigator.clipboard.writeText(value);
  } catch (_) {
    const output = $("jsonOutput");
    output.classList.remove("hidden");
    output.value = value;
    output.select();
    document.execCommand("copy");
  }
}

async function renderList() {
  const list = await getList();
  $("count").textContent = list.length;
  const items = $("items");
  if (!list.length) {
    items.innerHTML = '<div class="empty">لا توجد منتجات بعد. افتح منتجًا في Amazon.sa أو AliExpress واضغط الإضافة.</div>';
    return;
  }

  items.innerHTML = "";
  [...list]
    .sort((a, b) => b.discount_percent - a.discount_percent)
    .forEach((item) => {
      const row = document.createElement("div");
      row.className = "item";

      const image = document.createElement("img");
      image.src = item.image;
      image.alt = "";

      const info = document.createElement("div");
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = item.title;
      title.title = item.title;
      const meta = document.createElement("div");
      meta.className = "item-meta";
      const storeName = itemStore(item) === "aliexpress" ? "AliExpress" : "Amazon";
      const productId = item.product_id || item.asin;
      meta.textContent = `${storeName} · ${productId} · خصم ${item.discount_percent}٪ · ${item.category}`;
      info.append(title, meta);

      const buttons = document.createElement("div");
      buttons.className = "item-buttons";
      const edit = document.createElement("button");
      edit.className = "secondary";
      edit.textContent = "تعديل";
      edit.dataset.action = "edit";
      edit.dataset.key = itemKey(item);
      const remove = document.createElement("button");
      remove.className = "danger";
      remove.textContent = "حذف";
      remove.dataset.action = "remove";
      remove.dataset.key = itemKey(item);
      buttons.append(edit, remove);

      row.append(image, info, buttons);
      items.append(row);
    });
}

async function saveCurrentProduct() {
  const item = formItem();
  const errors = validateItem(item);
  if (errors.length) {
    showStatus(`⚠️ ${errors.join(" — ")}`, "error");
    return;
  }

  const list = await getList();
  const existingIndex = list.findIndex((deal) => itemKey(deal) === itemKey(item));
  if (existingIndex >= 0) list[existingIndex] = item;
  else list.push(item);
  await saveList(list);
  await renderList();
  showStatus(existingIndex >= 0 ? "✅ تم تحديث المنتج المحفوظ." : "✅ تمت إضافة المنتج إلى القائمة.", "ok");
  $("saveProduct").textContent = "💾 تحديث بيانات المنتج";
}

async function importFile(file) {
  const text = await file.text();
  const parsed = JSON.parse(text);
  const incoming = Array.isArray(parsed) ? parsed : parsed.deals;
  if (!Array.isArray(incoming)) throw new Error("الملف لا يحتوي على قائمة deals صحيحة");

  const valid = [];
  const rejected = [];
  incoming.forEach((raw) => {
    const item = normalizedItem(raw);
    const errors = validateItem(item);
    if (errors.length) rejected.push(item.product_id || item.asin || "بدون رقم");
    else valid.push(item);
  });
  if (!valid.length) throw new Error("لم أجد أي منتج صالح في الملف");

  const merged = await getList();
  valid.forEach((item) => {
    const index = merged.findIndex((deal) => itemKey(deal) === itemKey(item));
    if (index >= 0) merged[index] = item;
    else merged.push(item);
  });
  await saveList(merged);
  await renderList();
  showStatus(`✅ تم استيراد ${valid.length} منتج${rejected.length ? `، وتجاهل ${rejected.length} غير صالح` : ""}.`, "ok");
}

async function initialize() {
  await renderList();
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];
    const pageUrl = String(tab && tab.url || "");
    const supported = /amazon\.sa|aliexpress\.(com|us)/i.test(pageUrl);
    if (!tab || !supported) {
      showStatus("افتح صفحة منتج على Amazon.sa أو AliExpress لإضافته، أو استورد deals.json الحالي من الأسفل.", "warn");
      return;
    }

    chrome.scripting.executeScript(
      { target: { tabId: tab.id }, func: extractFromAmazonPage },
      async (results) => {
        if (chrome.runtime.lastError || !results || !results[0]) {
          showStatus("تعذّرت قراءة الصفحة. حدّث صفحة المنتج ثم افتح الأداة مجددًا.", "error");
          return;
        }
        const data = results[0].result;
        const extractedId = data && (data.asin || data.product_id);
        if (!data || !extractedId) {
          showStatus("لم أجد رقم المنتج. تأكد أنك داخل صفحة المنتج نفسها وليس صفحة البحث.", "error");
          return;
        }
        const list = await getList();
        const normalizedData = normalizedItem(data);
        const existing = list.find((item) => itemKey(item) === itemKey(normalizedData));
        setEditor(existing ? { ...existing, dealPrice: data.dealPrice } : data, Boolean(existing));
        const missing = [];
        if (!data.title) missing.push("الاسم");
        if (!data.image) missing.push("الصورة");
        if (!data.originalPrice) missing.push("سعر ما قبل الخصم");
        if (!data.discount) missing.push("نسبة الخصم");
        showStatus(missing.length
          ? `راجع الحقول التالية يدويًا: ${missing.join("، ")}.`
          : "✅ تم استخراج البيانات. راجعها ثم اضغط إضافة.", missing.length ? "warn" : "ok");
      }
    );
  });
}

$("dealPrice").addEventListener("input", calculateDiscount);
$("originalPrice").addEventListener("input", calculateDiscount);
$("saveProduct").addEventListener("click", saveCurrentProduct);

$("items").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const list = await getList();
  const item = list.find((deal) => itemKey(deal) === button.dataset.key);
  if (!item) return;

  if (button.dataset.action === "edit") {
    setEditor(item, true);
    $("editor").scrollIntoView({ behavior: "smooth", block: "start" });
    showStatus("يمكنك تعديل الحقول ثم الضغط على حفظ.");
    return;
  }

  if (button.dataset.action === "remove" && confirm(`حذف المنتج ${item.product_id || item.asin} من القائمة؟`)) {
    await saveList(list.filter((deal) => itemKey(deal) !== itemKey(item)));
    await renderList();
    showStatus("تم حذف المنتج من القائمة.", "ok");
  }
});

$("clearAll").addEventListener("click", async () => {
  if (!confirm("هل تريد إفراغ جميع المنتجات المحفوظة؟")) return;
  await saveList([]);
  await renderList();
  $("jsonOutput").classList.add("hidden");
  showStatus("تم إفراغ القائمة.", "ok");
});

$("importButton").addEventListener("click", () => $("importFile").click());
$("importFile").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    await importFile(file);
  } catch (error) {
    showStatus(`تعذر الاستيراد: ${error.message}`, "error");
  } finally {
    event.target.value = "";
  }
});

$("downloadDeals").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("أضف منتجًا واحدًا على الأقل أولًا.", "error");
  downloadJson("deals.json", jsonFromList(list));
  showStatus("✅ تم تنزيل deals.json.", "ok");
});

$("downloadAsins").addEventListener("click", async () => {
  const list = await getList();
  const asins = list.filter((item) => itemStore(item) === "amazon" && item.asin).map((item) => item.asin);
  if (!asins.length) return showStatus("لا توجد منتجات Amazon لتصدير ASIN حاليًا.", "error");
  downloadJson("asins.json", JSON.stringify(asins, null, 2));
  showStatus("✅ تم تنزيل asins.json.", "ok");
});

$("copyJson").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("أضف منتجًا واحدًا على الأقل أولًا.", "error");
  const json = jsonFromList(list);
  await copyText(json);
  $("jsonOutput").value = json;
  $("jsonOutput").classList.remove("hidden");
  showStatus("✅ تم نسخ محتوى deals.json.", "ok");
});

$("publishGithub").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("أضف منتجًا واحدًا على الأقل أولًا.", "error");
  await copyText(jsonFromList(list));
  chrome.tabs.create({ url: GITHUB_EDIT_URL });
  showStatus("تم نسخ الملف وفتح GitHub. استبدل محتوى deals.json ثم اضغط Commit changes.", "ok");
});

initialize();
