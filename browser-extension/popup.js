const STORE_KEY = "collected_deals_v5";
const LEGACY_STORE_KEYS = ["collected_deals_v3", "collected_deals"];
const SETTINGS_KEY = "overly_github_settings_v5";
const TOKEN_KEY = "overly_github_token_v5";
const REMOTE_HASHES_KEY = "overly_remote_hashes_v5";
const LAST_SYNC_KEY = "overly_last_sync_v5";
const ALLOWED_CATEGORIES = [
  "الإلكترونيات", "المنزل", "الموضة", "السيارة", "السفر",
  "الجمال والعناية", "الرياضة", "الأطفال", "الحيوانات الأليفة", "الأدوات والهوايات"
];
const DEFAULT_GITHUB = { owner: "majeed3575", repo: "majeeddeals", branch: "main", path: "deals.json" };

const $ = (id) => document.getElementById(id);
let currentDealPrice = 0;
let busy = false;

// تُنفّذ داخل صفحة المنتج، لذلك يجب أن تبقى مستقلة ولا تعتمد على متغيرات الإضافة.
function extractFromProductPage() {
  function westernDigits(value) {
    return String(value || "")
      .replace(/[٠-٩]/g, (digit) => "٠١٢٣٤٥٦٧٨٩".indexOf(digit))
      .replace(/[۰-۹]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹".indexOf(digit));
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
  function firstPrice(selectors) { return numberFromText(firstText(selectors)); }
  function detectCategory(title) {
    const searchable = String(title || "").toLowerCase();
    const contains = (words) => words.some((word) => searchable.includes(word));
    if (contains(["قطط", "كلاب", "حيوان", "pet", "cat", "dog", "grooming"])) return "الحيوانات الأليفة";
    if (contains(["طفل", "أطفال", "رضيع", "لعبة", "baby", "kids", "child", "toy"])) return "الأطفال";
    if (contains(["مكياج", "بشرة", "شعر", "أظافر", "makeup", "beauty", "skincare", "hair", "nail"])) return "الجمال والعناية";
    if (contains(["رياضة", "لياقة", "تمارين", "يوغا", "sport", "fitness", "exercise", "yoga", "running"])) return "الرياضة";
    if (contains(["دريل", "مثقاب", "عدة", "أدوات", "drill", "wrench", "tool", "laser level"])) return "الأدوات والهوايات";
    if (contains(["سيارة", "كاربلاي", "مركبة", "car", "carplay", "vehicle"])) return "السيارة";
    if (contains(["سفر", "رحلات", "أمتعة", "travel", "luggage", "camping"])) return "السفر";
    if (contains(["مقلاة", "قلاية", "مكنسة", "خلاط", "قهوة", "مطبخ", "غسالة", "سرير", "وسادة", "إضاءة", "مصباح", "تنظيف", "ثلاجة", "ثلج", "ميزان", "تنقية", "kitchen", "vacuum", "blender", "coffee", "fryer", "pillow", "lamp", "cleaner", "ice", "scale", "purifier"])) return "المنزل";
    if (contains(["حقيبة", "حذاء", "قميص", "عباية", "فستان", "نظارة", "عطر", "ملابس", "جاكيت", "مظلة", "bag", "shoe", "shirt", "dress", "sunglasses", "perfume", "jacket", "backpack", "wallet", "umbrella"])) return "الموضة";
    return "الإلكترونيات";
  }

  if (/aliexpress\.(com|us)$/i.test(location.hostname)) {
    const productMatch = location.pathname.match(/\/item\/(\d+)\.html/i) || location.href.match(/[?&](?:productId|itemId)=(\d+)/i);
    const productId = productMatch ? productMatch[1] : "";
    const title = String(firstText(["h1[data-pl=product-title]", ".product-title-text", "h1"]) || document.querySelector('meta[property="og:title"]')?.content || "").replace(/\s+/g, " ").trim().slice(0, 140);
    const image = String(document.querySelector('meta[property="og:image"]')?.content || document.querySelector(".magnifier--image--RM17RL2, .image-view--previewBox--A0BvBKH img, img[class*=main]")?.src || "").split("?")[0];
    const dealPrice = firstPrice(["[class*=price--current]", "[class*=price-current]", "[class*=product-price-current]", ".uniform-banner-box-price", "[data-pl=product-price]"]);
    let originalPrice = firstPrice(["[class*=price--original]", "[class*=price-original]", "[class*=price-del]", "[class*=originalPrice]", "del"]);
    const discountMatch = westernDigits(firstText(["[class*=discount]", "[class*=saving]"])).match(/(\d{1,2})\s*%/);
    let discount = discountMatch ? Number.parseInt(discountMatch[1], 10) : 0;
    if (!originalPrice && dealPrice && discount > 0 && discount < 100) originalPrice = dealPrice / (1 - discount / 100);
    if (!discount && originalPrice > dealPrice && dealPrice > 0) discount = Math.round((1 - dealPrice / originalPrice) * 100);
    return { store: "aliexpress", product_id: productId, url: location.href.split("?")[0], title, image, dealPrice: Math.round(dealPrice * 100) / 100, originalPrice: Math.round(originalPrice * 100) / 100, discount, category: detectCategory(title) };
  }

  const asinMatch = location.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i) || location.href.match(/[?&]asin=([A-Z0-9]{10})/i);
  const asinInput = document.getElementById("ASIN") || document.querySelector("[name=ASIN]");
  const asin = (asinMatch ? asinMatch[1] : asinInput?.value || "").toUpperCase();
  const title = String(document.getElementById("productTitle")?.textContent || document.querySelector('meta[property="og:title"]')?.content || "").replace(/\s+/g, " ").trim().slice(0, 140);
  const imageElement = document.getElementById("landingImage") || document.querySelector("#imgTagWrapperId img, #main-image");
  const image = String(imageElement?.getAttribute("data-old-hires") || imageElement?.src || document.querySelector('meta[property="og:image"]')?.content || "").split("?")[0];
  const dealPrice = firstPrice([".priceToPay .a-offscreen", "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen", "#corePrice_feature_div .a-price .a-offscreen", ".apexPriceToPay .a-offscreen", ".a-price .a-offscreen"]);
  let originalPrice = firstPrice([".basisPrice .a-offscreen", "[data-a-strike=true] .a-offscreen", ".a-text-price .a-offscreen", "#listPrice", ".priceBlockStrikePriceString"]);
  const discountMatch = westernDigits(firstText([".savingsPercentage", "[class*=savingPercentage]"])).match(/(\d{1,2})/);
  let discount = discountMatch ? Number.parseInt(discountMatch[1], 10) : 0;
  if (!originalPrice && dealPrice && discount > 0 && discount < 100) originalPrice = dealPrice / (1 - discount / 100);
  if (!discount && originalPrice > dealPrice && dealPrice > 0) discount = Math.round((1 - dealPrice / originalPrice) * 100);
  return { store: "amazon", url: location.href, asin, title, image, dealPrice: Math.round(dealPrice * 100) / 100, originalPrice: Math.round(originalPrice * 100) / 100, discount, category: detectCategory(title) };
}

function storageGet(keys) { return new Promise((resolve) => chrome.storage.local.get(keys, resolve)); }
function storageSet(values) { return new Promise((resolve) => chrome.storage.local.set(values, resolve)); }
function storageRemove(keys) { return new Promise((resolve) => chrome.storage.local.remove(keys, resolve)); }

async function getList() {
  const result = await storageGet([STORE_KEY, ...LEGACY_STORE_KEYS]);
  if (Array.isArray(result[STORE_KEY])) return result[STORE_KEY];
  for (const key of LEGACY_STORE_KEYS) {
    if (Array.isArray(result[key])) {
      const migrated = result[key].map(normalizedItem).filter((item) => itemIdentity(item));
      await storageSet({ [STORE_KEY]: migrated });
      return migrated;
    }
  }
  return [];
}
async function saveList(list) { await storageSet({ [STORE_KEY]: list }); }

function showStatus(message, type = "") {
  const status = $("status");
  status.className = `notice${type ? ` ${type}` : ""}`;
  status.textContent = message;
}
function normalizeAsin(value) { const match = String(value || "").toUpperCase().match(/[A-Z0-9]{10}/); return match ? match[0] : ""; }
function normalizeProductId(value) { const match = String(value || "").match(/\d{6,20}/); return match ? match[0] : ""; }
function itemStore(raw) { return String(raw?.store || "amazon").toLowerCase() === "aliexpress" ? "aliexpress" : "amazon"; }
function roundPrice(value) { const number = Number(value); return Number.isFinite(number) ? Math.round(number * 100) / 100 : 0; }
function normalizedItem(raw) {
  const store = itemStore(raw);
  const item = {
    store,
    title: String(raw?.title || "").replace(/\s+/g, " ").trim().slice(0, 140),
    image: String(raw?.image || "").trim(),
    discount_percent: Math.round(Number(raw?.discount_percent || raw?.discount || 0)),
    original_price: roundPrice(raw?.original_price || raw?.originalPrice),
    category: ALLOWED_CATEGORIES.includes(raw?.category) ? raw.category : "الإلكترونيات"
  };
  if (store === "aliexpress") {
    item.product_id = normalizeProductId(raw?.product_id || raw?.asin);
    item.url = String(raw?.url || "").trim();
  } else item.asin = normalizeAsin(raw?.asin);
  return item;
}
function itemIdentity(item) { return itemStore(item) === "aliexpress" ? normalizeProductId(item?.product_id) : normalizeAsin(item?.asin); }
function itemKey(item) { return `${itemStore(item)}:${itemIdentity(item)}`; }
function itemHash(item) { return JSON.stringify(normalizedItem(item)); }
function validateItem(item) {
  const errors = [];
  if (itemStore(item) === "amazon" && !/^[A-Z0-9]{10}$/.test(item.asin)) errors.push("رقم ASIN غير صحيح");
  if (itemStore(item) === "aliexpress" && !/^\d{6,20}$/.test(item.product_id)) errors.push("رقم AliExpress غير صحيح");
  if (itemStore(item) === "aliexpress" && !/^https:\/\/([a-z0-9-]+\.)*(aliexpress\.com|aliexpress\.us)\//i.test(item.url)) errors.push("رابط AliExpress غير صحيح");
  if (item.title.length < 8) errors.push("اسم المنتج قصير");
  if (!item.image.startsWith("https://")) errors.push("رابط الصورة غير صحيح");
  if (!(item.original_price > 0)) errors.push("سعر ما قبل الخصم غير صحيح");
  if (!(item.discount_percent >= 5 && item.discount_percent <= 95)) errors.push("الخصم يجب أن يكون 5٪–95٪");
  if (!ALLOWED_CATEGORIES.includes(item.category)) errors.push("التصنيف غير مسموح");
  return errors;
}
function auditList(list) {
  const seen = new Set();
  return list.map((raw) => {
    const item = normalizedItem(raw);
    const errors = validateItem(item);
    const key = itemKey(item);
    if (seen.has(key)) errors.push("منتج مكرر");
    seen.add(key);
    return { item, errors };
  });
}

function setEditor(data, editing = false) {
  $("editor").classList.remove("hidden");
  $("editor").open = true;
  $("editorTitle").textContent = editing ? "تعديل المنتج المحفوظ" : "مراجعة المنتج الحالي";
  const store = itemStore(data);
  $("store").value = store;
  $("asin").value = store === "aliexpress" ? normalizeProductId(data.product_id || data.asin) : normalizeAsin(data.asin);
  $("productUrl").value = data.url || "";
  $("title").value = data.title || "";
  $("image").value = data.image || "";
  $("dealPrice").value = data.dealPrice || "";
  $("originalPrice").value = data.original_price || data.originalPrice || "";
  $("discount").value = data.discount_percent || data.discount || "";
  $("category").value = ALLOWED_CATEGORIES.includes(data.category) ? data.category : "الإلكترونيات";
  currentDealPrice = Number(data.dealPrice || 0);
  $("saveProduct").textContent = editing ? "حفظ تعديل المنتج" : "＋ إضافة المنتج إلى القائمة";
}
function formItem() {
  return normalizedItem({ store: $("store").value, asin: $("asin").value, product_id: $("asin").value, url: $("productUrl").value, title: $("title").value, image: $("image").value, original_price: $("originalPrice").value, discount_percent: $("discount").value, category: $("category").value });
}
function calculateDiscount() {
  const deal = Number($("dealPrice").value || currentDealPrice);
  const original = Number($("originalPrice").value);
  if (deal > 0 && original > deal) $("discount").value = Math.round((1 - deal / original) * 100);
}

function payloadFromList(list, source = "overly-extension-v5") {
  const deals = [...list].sort((a, b) => Number(b.discount_percent || 0) - Number(a.discount_percent || 0));
  return { updated_at: new Date().toISOString(), source, count: deals.length, deals };
}
function jsonFromList(list) { return JSON.stringify(payloadFromList(list), null, 2); }
function downloadJson(filename, value) {
  const url = URL.createObjectURL(new Blob([value], { type: "application/json;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function copyText(value) {
  try { await navigator.clipboard.writeText(value); }
  catch (_) {
    const output = $("jsonOutput");
    output.classList.remove("hidden");
    output.value = value;
    output.select();
    document.execCommand("copy");
  }
}
function utf8ToBase64(value) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  return btoa(binary);
}
function base64ToUtf8(value) {
  const binary = atob(String(value || "").replace(/\s/g, ""));
  return new TextDecoder().decode(Uint8Array.from(binary, (character) => character.charCodeAt(0)));
}

async function getGithubConfig() {
  const saved = await storageGet([SETTINGS_KEY, TOKEN_KEY]);
  return { ...DEFAULT_GITHUB, ...(saved[SETTINGS_KEY] || {}), token: String(saved[TOKEN_KEY] || "") };
}
function configFromForm() {
  return { owner: $("githubOwner").value.trim(), repo: $("githubRepo").value.trim(), branch: $("githubBranch").value.trim(), path: $("githubPath").value.trim().replace(/^\/+/, "") };
}
function validateGithubConfig(config) {
  if (!/^[A-Za-z0-9_.-]+$/.test(config.owner)) throw new Error("اسم حساب GitHub غير صحيح");
  if (!/^[A-Za-z0-9_.-]+$/.test(config.repo)) throw new Error("اسم المستودع غير صحيح");
  if (!config.branch || !config.path || config.path.includes("..")) throw new Error("الفرع أو مسار الملف غير صحيح");
}
function rawGithubUrl(config) {
  const path = config.path.split("/").map(encodeURIComponent).join("/");
  return `https://raw.githubusercontent.com/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/${encodeURIComponent(config.branch)}/${path}`;
}
function githubApiUrl(config) {
  const path = config.path.split("/").map(encodeURIComponent).join("/");
  return `https://api.github.com/repos/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/contents/${path}`;
}
function githubHeaders(token) {
  const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}
async function parseGithubError(response) {
  const raw = await response.text();
  let detail = raw;
  try { detail = JSON.parse(raw).message || raw; } catch (_) {}
  if (response.status === 401) return "المفتاح غير صحيح أو منتهي";
  if (response.status === 403) return "المفتاح لا يملك صلاحية الكتابة أو الحساب محظور مؤقتًا";
  if (response.status === 404) return "المستودع أو الملف غير موجود، أو المفتاح لا يستطيع الوصول إليه";
  return detail || `فشل طلب GitHub (${response.status})`;
}
function extractDeals(parsed) { return Array.isArray(parsed) ? parsed : Array.isArray(parsed?.deals) ? parsed.deals : null; }
function normalizedValidList(rawList) {
  const result = [];
  const indexes = new Map();
  for (const raw of rawList || []) {
    const item = normalizedItem(raw);
    if (!itemIdentity(item) || validateItem(item).length) continue;
    const key = itemKey(item);
    if (indexes.has(key)) result[indexes.get(key)] = item;
    else { indexes.set(key, result.length); result.push(item); }
  }
  return result;
}
function mergeNormalized(remote, local) {
  const merged = normalizedValidList(remote);
  const indexes = new Map(merged.map((item, index) => [itemKey(item), index]));
  for (const item of normalizedValidList(local)) {
    const key = itemKey(item);
    if (indexes.has(key)) merged[indexes.get(key)] = item;
    else { indexes.set(key, merged.length); merged.push(item); }
  }
  return merged;
}
function mergeForPublish(remoteRaw, local) {
  const merged = Array.isArray(remoteRaw) ? remoteRaw.map((item) => ({ ...item })) : [];
  const indexes = new Map();
  merged.forEach((raw, index) => {
    const normalized = normalizedItem(raw);
    if (itemIdentity(normalized)) indexes.set(itemKey(normalized), index);
  });
  for (const item of local) {
    const key = itemKey(item);
    if (indexes.has(key)) merged[indexes.get(key)] = item;
    else { indexes.set(key, merged.length); merged.push(item); }
  }
  return merged;
}
function remoteHashes(list) { return Object.fromEntries(normalizedValidList(list).map((item) => [itemKey(item), itemHash(item)])); }

async function saveRemoteState(remoteList) {
  const now = new Date().toISOString();
  await storageSet({ [REMOTE_HASHES_KEY]: remoteHashes(remoteList), [LAST_SYNC_KEY]: now });
  return now;
}
async function loadGithubSettings() {
  const config = await getGithubConfig();
  $("githubOwner").value = config.owner;
  $("githubRepo").value = config.repo;
  $("githubBranch").value = config.branch;
  $("githubPath").value = config.path;
  $("githubToken").value = "";
  $("tokenState").textContent = config.token ? "✓ يوجد مفتاح محفوظ محليًا في هذا المتصفح." : "لا يوجد مفتاح محفوظ بعد.";
  const stored = await storageGet([LAST_SYNC_KEY]);
  $("syncTime").textContent = stored[LAST_SYNC_KEY] ? `آخر مزامنة: ${new Date(stored[LAST_SYNC_KEY]).toLocaleString("ar-SA")}` : "لم تتم المزامنة";
}
async function saveGithubSettings() {
  const config = configFromForm();
  validateGithubConfig(config);
  const token = $("githubToken").value.trim();
  await storageSet({ [SETTINGS_KEY]: config, ...(token ? { [TOKEN_KEY]: token } : {}) });
  $("githubToken").value = "";
  await loadGithubSettings();
  showStatus("✓ حُفظت إعدادات GitHub محليًا.", "ok");
}

async function syncFromGithub() {
  const config = { ...(await getGithubConfig()), ...configFromForm() };
  validateGithubConfig(config);
  const response = await fetch(`${rawGithubUrl(config)}?overly=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`تعذر قراءة deals.json من الموقع (${response.status})`);
  const parsed = await response.json();
  const remote = extractDeals(parsed);
  if (!remote) throw new Error("ملف الموقع لا يحتوي على قائمة deals صحيحة");
  const local = await getList();
  const merged = mergeNormalized(remote, local);
  await saveList(merged);
  const now = await saveRemoteState(remote);
  $("syncTime").textContent = `آخر مزامنة: ${new Date(now).toLocaleString("ar-SA")}`;
  await renderList();
  return { remoteCount: remote.length, localCount: merged.length };
}
async function testGithubConnection() {
  const config = { ...(await getGithubConfig()), ...configFromForm() };
  validateGithubConfig(config);
  if (!config.token) throw new Error("أضف مفتاح GitHub أولًا من إعداد النشر المباشر");
  const response = await fetch(`https://api.github.com/repos/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}`, { headers: githubHeaders(config.token), cache: "no-store" });
  if (!response.ok) throw new Error(await parseGithubError(response));
  const repo = await response.json();
  return repo.full_name || `${config.owner}/${config.repo}`;
}
async function publishToGithub() {
  const local = await getList();
  const audit = auditList(local);
  const broken = audit.filter((entry) => entry.errors.length);
  if (!local.length) throw new Error("أضف منتجًا واحدًا على الأقل أولًا");
  if (broken.length) throw new Error(`يوجد ${broken.length} منتج غير صالح. عدّله قبل النشر`);

  const config = { ...(await getGithubConfig()), ...configFromForm() };
  validateGithubConfig(config);
  if (!config.token) {
    $("githubSettings").open = true;
    $("githubSettings").scrollIntoView({ behavior: "smooth", block: "start" });
    throw new Error("أضف مفتاح GitHub في إعداد النشر المباشر ثم احفظه");
  }

  const apiUrl = githubApiUrl(config);
  const getResponse = await fetch(`${apiUrl}?ref=${encodeURIComponent(config.branch)}`, { headers: githubHeaders(config.token), cache: "no-store" });
  if (!getResponse.ok) throw new Error(await parseGithubError(getResponse));
  const currentFile = await getResponse.json();
  const parsed = JSON.parse(base64ToUtf8(currentFile.content));
  const remote = extractDeals(parsed);
  if (!remote) throw new Error("ملف deals.json الحالي غير صالح؛ أوقفت النشر لحماية الموقع");

  const merged = mergeForPublish(remote, audit.map((entry) => entry.item));
  const content = JSON.stringify(payloadFromList(merged, "overly-extension-v5"), null, 2) + "\n";
  const putResponse = await fetch(apiUrl, {
    method: "PUT",
    headers: { ...githubHeaders(config.token), "Content-Type": "application/json" },
    body: JSON.stringify({ message: `تحديث ${local.length} منتج عبر Overly Product Studio`, content: utf8ToBase64(content), sha: currentFile.sha, branch: config.branch })
  });
  if (!putResponse.ok) throw new Error(await parseGithubError(putResponse));
  const result = await putResponse.json();
  const normalizedMerged = normalizedValidList(merged);
  await saveList(normalizedMerged);
  const now = await saveRemoteState(merged);
  $("syncTime").textContent = `نُشر: ${new Date(now).toLocaleString("ar-SA")}`;
  await renderList();
  return { count: merged.length, url: result.commit?.html_url || result.content?.html_url || "" };
}

async function renderList() {
  const list = await getList();
  const stored = await storageGet([REMOTE_HASHES_KEY]);
  const hashes = stored[REMOTE_HASHES_KEY] || {};
  const audit = auditList(list);
  $("count").textContent = list.length;
  $("amazonCount").textContent = list.filter((item) => itemStore(item) === "amazon").length;
  $("aliCount").textContent = list.filter((item) => itemStore(item) === "aliexpress").length;
  $("issueCount").textContent = audit.filter((entry) => entry.errors.length).length;
  const items = $("items");
  if (!list.length) {
    items.innerHTML = '<div class="empty">افتح منتجًا على Amazon.sa أو AliExpress ثم اضغط أيقونة Overly، أو استخدم «مزامنة الموقع» لجلب المنتجات الحالية.</div>';
    return;
  }
  items.innerHTML = "";
  audit.sort((a, b) => b.item.discount_percent - a.item.discount_percent).forEach(({ item, errors }) => {
    const key = itemKey(item);
    const remoteHash = hashes[key];
    const state = errors.length ? ["bad", "يحتاج مراجعة"] : !remoteHash ? ["local", "غير منشور"] : remoteHash === itemHash(item) ? ["live", "منشور"] : ["changed", "تعديل محلي"];
    const row = document.createElement("div");
    row.className = `item${errors.length ? " invalid" : ""}`;
    const image = document.createElement("img");
    image.src = item.image;
    image.alt = "";
    image.referrerPolicy = "no-referrer";
    const info = document.createElement("div");
    const title = document.createElement("div");
    title.className = "item-title";
    title.textContent = item.title;
    title.title = item.title;
    const meta = document.createElement("div");
    meta.className = "item-meta";
    meta.textContent = `${itemStore(item) === "aliexpress" ? "AliExpress" : "Amazon"} · ${itemIdentity(item)} · خصم ${item.discount_percent}٪`;
    const badge = document.createElement("span");
    badge.className = `badge ${state[0]}`;
    badge.textContent = state[1];
    meta.append(badge);
    if (errors.length) meta.title = errors.join(" — ");
    info.append(title, meta);
    const buttons = document.createElement("div");
    buttons.className = "item-buttons";
    for (const [action, label, className] of [["edit", "تعديل", "secondary"], ["remove", "حذف", "danger"]]) {
      const button = document.createElement("button");
      button.className = className;
      button.textContent = label;
      button.dataset.action = action;
      button.dataset.key = key;
      buttons.append(button);
    }
    row.append(image, info, buttons);
    items.append(row);
  });
}

async function saveCurrentProduct() {
  const item = formItem();
  const errors = validateItem(item);
  const deal = Number($("dealPrice").value || 0);
  if (deal > 0 && deal >= item.original_price) errors.push("السعر الحالي يجب أن يكون أقل من سعر ما قبل الخصم");
  if (errors.length) return showStatus(`⚠ ${errors.join(" — ")}`, "error");
  const list = await getList();
  const index = list.findIndex((dealItem) => itemKey(dealItem) === itemKey(item));
  if (index >= 0) list[index] = item; else list.push(item);
  await saveList(list);
  await renderList();
  showStatus(index >= 0 ? "✓ تم تحديث المنتج محليًا." : "✓ تمت إضافة المنتج. أصبح جاهزًا للنشر.", "ok");
  $("saveProduct").textContent = "حفظ تعديل المنتج";
}
async function importFile(file) {
  const parsed = JSON.parse(await file.text());
  const incoming = extractDeals(parsed);
  if (!incoming) throw new Error("الملف لا يحتوي على قائمة deals صحيحة");
  const valid = normalizedValidList(incoming);
  if (!valid.length) throw new Error("لم أجد أي منتج صالح في الملف");
  const merged = mergeNormalized(await getList(), valid);
  await saveList(merged);
  await renderList();
  return { valid: valid.length, rejected: incoming.length - valid.length };
}

async function withBusy(button, work) {
  if (busy) return;
  busy = true;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "جاري التنفيذ…";
  try { await work(); }
  catch (error) { showStatus(`تعذر التنفيذ: ${error.message}`, "error"); }
  finally { button.disabled = false; button.textContent = original; busy = false; }
}

async function initialize() {
  await loadGithubSettings();
  await renderList();
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];
    const pageUrl = String(tab?.url || "");
    if (!tab || !/amazon\.sa|aliexpress\.(com|us)/i.test(pageUrl)) {
      showStatus("افتح صفحة منتج لإضافته، أو اضغط «مزامنة الموقع» لجلب المنتجات المنشورة.", "warn");
      return;
    }
    chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractFromProductPage }, async (results) => {
      if (chrome.runtime.lastError || !results?.[0]) return showStatus("تعذّرت قراءة الصفحة. حدّث صفحة المنتج ثم افتح الأداة مجددًا.", "error");
      const data = results[0].result;
      if (!data || !(data.asin || data.product_id)) return showStatus("لم أجد رقم المنتج. افتح صفحة المنتج نفسها وليس نتائج البحث.", "error");
      const normalized = normalizedItem(data);
      const existing = (await getList()).find((item) => itemKey(item) === itemKey(normalized));
      setEditor(existing ? { ...existing, dealPrice: data.dealPrice } : data, Boolean(existing));
      const missing = [];
      if (!data.title) missing.push("الاسم");
      if (!data.image) missing.push("الصورة");
      if (!data.originalPrice) missing.push("سعر ما قبل الخصم");
      if (!data.discount) missing.push("الخصم");
      showStatus(missing.length ? `راجع يدويًا: ${missing.join("، ")}.` : "✓ استخرجت البيانات. راجعها ثم أضف المنتج.", missing.length ? "warn" : "ok");
    });
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
    return showStatus("عدّل الحقول ثم اضغط حفظ.");
  }
  if (button.dataset.action === "remove" && confirm(`حذف المنتج ${itemIdentity(item)} من القائمة المحلية؟ لن يُحذف من الموقع المنشور.`)) {
    await saveList(list.filter((deal) => itemKey(deal) !== itemKey(item)));
    await renderList();
    showStatus("حُذف من القائمة المحلية فقط.", "ok");
  }
});
$("clearAll").addEventListener("click", async () => {
  if (!confirm("إفراغ القائمة المحلية؟ لن تُحذف منتجات الموقع المنشورة.")) return;
  await saveList([]);
  await renderList();
  showStatus("أُفرغت القائمة المحلية. منتجات الموقع لم تتغير.", "ok");
});
$("importButton").addEventListener("click", () => $("importFile").click());
$("importFile").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const result = await importFile(file);
    showStatus(`✓ استوردت ${result.valid} منتج${result.rejected ? ` وتجاهلت ${result.rejected} غير صالح` : ""}.`, "ok");
  } catch (error) { showStatus(`تعذر الاستيراد: ${error.message}`, "error"); }
  finally { event.target.value = ""; }
});
$("downloadDeals").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("لا توجد منتجات للتنزيل.", "error");
  downloadJson("deals.json", jsonFromList(list));
  showStatus("✓ تم تنزيل deals.json.", "ok");
});
$("downloadAsins").addEventListener("click", async () => {
  const asins = (await getList()).filter((item) => itemStore(item) === "amazon").map((item) => item.asin).filter(Boolean);
  if (!asins.length) return showStatus("لا توجد منتجات Amazon حاليًا.", "error");
  downloadJson("asins.json", JSON.stringify(asins, null, 2));
  showStatus("✓ تم تنزيل asins.json.", "ok");
});
$("downloadAli").addEventListener("click", async () => {
  const products = (await getList())
    .filter((item) => itemStore(item) === "aliexpress" && item.product_id)
    .map((item) => ({
      product_id: item.product_id,
      url: item.url,
      category: item.category
    }));
  if (!products.length) return showStatus("لا توجد منتجات AliExpress حاليًا.", "error");
  downloadJson("aliexpress_products.json", JSON.stringify({ products }, null, 2));
  showStatus("✓ تم تنزيل قائمة متابعة AliExpress.", "ok");
});
$("copyJson").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("لا توجد منتجات للنسخ.", "error");
  const json = jsonFromList(list);
  await copyText(json);
  $("jsonOutput").value = json;
  $("jsonOutput").classList.remove("hidden");
  showStatus("✓ نُسخ محتوى deals.json.", "ok");
});
$("publishGithub").addEventListener("click", async () => {
  const list = await getList();
  if (!list.length) return showStatus("لا توجد منتجات للنشر.", "error");
  await copyText(jsonFromList(list));
  const config = { ...(await getGithubConfig()), ...configFromForm() };
  chrome.tabs.create({ url: `https://github.com/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/edit/${encodeURIComponent(config.branch)}/${config.path.split("/").map(encodeURIComponent).join("/")}` });
  showStatus("نُسخ الملف وفُتح GitHub للطريقة اليدوية.", "ok");
});
$("saveGithub").addEventListener("click", (event) => withBusy(event.currentTarget, saveGithubSettings));
$("forgetToken").addEventListener("click", async () => {
  if (!confirm("نسيان مفتاح GitHub المحفوظ في هذا المتصفح؟")) return;
  await storageRemove(TOKEN_KEY);
  await loadGithubSettings();
  showStatus("تم حذف المفتاح من المتصفح.", "ok");
});
$("syncGithub").addEventListener("click", (event) => withBusy(event.currentTarget, async () => {
  const result = await syncFromGithub();
  showStatus(`✓ جلبت ${result.remoteCount} منتج من الموقع. القائمة الآن ${result.localCount} منتج.`, "ok");
}));
$("testGithub").addEventListener("click", (event) => withBusy(event.currentTarget, async () => {
  const name = await testGithubConnection();
  showStatus(`✓ الاتصال ناجح مع ${name}.`, "ok");
}));
$("publishDirect").addEventListener("click", (event) => withBusy(event.currentTarget, async () => {
  const result = await publishToGithub();
  showStatus(`✓ تم نشر ${result.count} منتج بأمان. سيظهر التحديث في الموقع خلال دقيقة.`, "ok");
  if (result.url) chrome.tabs.create({ url: result.url });
}));

initialize();
