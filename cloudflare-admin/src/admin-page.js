function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

export function adminPage({ nonce, email, siteUrl }) {
  const safeEmail = escapeHtml(email);
  const safeSiteUrl = escapeHtml(siteUrl);
  return \`<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#071310">
<title>لوحة أوفرلي</title>
<style nonce="\${nonce}">
:root{color-scheme:dark;--bg:#06110e;--panel:#0b1b17;--panel2:#10251f;--line:rgba(160,233,214,.14);--text:#effbf7;--muted:#8fa9a1;--mint:#7fe2cd;--mint2:#45bda4;--blue:#7ac7ff;--orange:#ffc27a;--danger:#ff8e8e;--shadow:0 24px 70px rgba(0,0,0,.38)}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;min-height:100vh;background:radial-gradient(circle at 92% -10%,rgba(69,189,164,.18),transparent 32rem),radial-gradient(circle at 0 45%,rgba(41,100,87,.13),transparent 30rem),var(--bg);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Tajawal","Segoe UI",sans-serif;color:var(--text)}
button,a{font:inherit}.shell{width:min(1440px,100%);margin:auto;padding:22px clamp(16px,3vw,42px) 48px}.top{position:sticky;top:12px;z-index:5;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:15px 18px;border:1px solid var(--line);border-radius:22px;background:rgba(7,21,17,.82);backdrop-filter:blur(22px);box-shadow:var(--shadow)}
.brand{display:flex;align-items:center;gap:12px}.mark{width:45px;height:45px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(145deg,var(--mint),#b6f4e8);color:#062019;font-weight:900;box-shadow:0 12px 35px rgba(69,189,164,.25)}h1{font-size:18px;margin:0}.sub{font-size:12px;color:var(--muted);margin-top:3px}.top-actions{display:flex;align-items:center;gap:9px}.link,.range button{border:1px solid var(--line);background:var(--panel2);color:var(--text);text-decoration:none;padding:9px 13px;border-radius:12px;cursor:pointer}.link:hover,.range button:hover,.range button.active{border-color:rgba(127,226,205,.55);background:rgba(127,226,205,.12);color:var(--mint)}
.hero{padding:54px 4px 24px}.eyebrow{color:var(--mint);font-size:13px;font-weight:800;letter-spacing:.04em}.hero h2{font-size:clamp(30px,5vw,62px);letter-spacing:-.045em;margin:10px 0 9px;max-width:850px}.hero p{margin:0;color:var(--muted);font-size:15px}.toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 18px}.range{display:flex;gap:8px}.status{font-size:13px;color:var(--muted)}.status.error{color:var(--danger)}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}.card{border:1px solid var(--line);border-radius:22px;background:linear-gradient(150deg,rgba(16,37,31,.92),rgba(8,25,20,.92));box-shadow:0 20px 50px rgba(0,0,0,.18);overflow:hidden}.metric{grid-column:span 3;padding:20px;min-height:142px}.metric .label{color:var(--muted);font-size:13px}.metric .value{font-size:clamp(29px,4vw,48px);font-weight:850;letter-spacing:-.04em;margin:12px 0 4px}.metric .hint{font-size:12px;color:var(--mint)}
.chart-card{grid-column:span 8;padding:20px}.side-card{grid-column:span 4;padding:20px}.wide{grid-column:span 12;padding:20px}.card-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.card-head h3{margin:0;font-size:16px}.badge{font-size:11px;color:var(--mint);background:rgba(127,226,205,.1);border:1px solid rgba(127,226,205,.18);padding:6px 9px;border-radius:999px}
.chart{height:280px;display:flex;align-items:flex-end;gap:7px;padding:22px 2px 6px;border-bottom:1px solid var(--line);position:relative}.bar-wrap{height:100%;min-width:4px;flex:1;display:flex;align-items:flex-end;gap:2px}.bar{width:50%;min-height:2px;border-radius:6px 6px 2px 2px;background:linear-gradient(180deg,var(--mint),rgba(69,189,164,.35));transition:.25s}.bar.clicks{background:linear-gradient(180deg,var(--blue),rgba(122,199,255,.3))}.legend{display:flex;gap:18px;color:var(--muted);font-size:12px;margin-top:14px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--mint);margin-left:6px}.dot.blue{background:var(--blue)}
.list{display:grid;gap:9px}.dist{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;font-size:13px}.track{height:8px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden}.fill{height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--mint2),var(--mint))}.count{color:var(--muted);font-variant-numeric:tabular-nums}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:16px}table{border-collapse:collapse;width:100%;min-width:650px}th,td{text-align:right;padding:13px 14px;border-bottom:1px solid var(--line);font-size:13px}th{color:var(--muted);font-weight:650;background:rgba(255,255,255,.025)}td.num{font-weight:800;color:var(--mint)}tr:last-child td{border-bottom:0}.empty{color:var(--muted);text-align:center;padding:42px 12px}
.foot{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:12px;margin-top:20px;padding:0 4px}
@media(max-width:900px){.metric{grid-column:span 6}.chart-card,.side-card{grid-column:span 12}.top{position:relative;top:0}.hero{padding-top:34px}}@media(max-width:560px){.shell{padding-inline:12px}.metric{grid-column:span 12}.top,.toolbar,.foot{align-items:flex-start;flex-direction:column}.top-actions{width:100%}.link{flex:1;text-align:center}.hero h2{font-size:37px}.chart{height:220px}.range{width:100%}.range button{flex:1}}
</style>
</head>
<body>
<main class="shell">
<header class="top">
  <div class="brand"><div class="mark">O</div><div><h1>Overly Analytics</h1><div class="sub">لوحة خاصة محمية بواسطة Cloudflare Access</div></div></div>
  <div class="top-actions"><a class="link" href="\${safeSiteUrl}" target="_blank" rel="noopener">فتح الموقع ↗</a></div>
</header>
<section class="hero">
  <div class="eyebrow">لوحة المالك · \${safeEmail}</div>
  <h2>صورة واضحة لأداء أوفرلي.</h2>
  <p>إحصاءات مجمّعة تحترم الخصوصية، من دون حفظ عنوان IP أو بيانات تعريف شخصية.</p>
</section>
<div class="toolbar">
  <div class="range"><button data-days="7">٧ أيام</button><button class="active" data-days="30">٣٠ يومًا</button><button data-days="90">٩٠ يومًا</button></div>
  <div id="status" class="status">جارٍ تحميل البيانات…</div>
</div>
<section class="grid">
  <article class="card metric"><div class="label">إجمالي الزيارات</div><div id="views" class="value">—</div><div id="viewsToday" class="hint">اليوم —</div></article>
  <article class="card metric"><div class="label">نقرات المنتجات</div><div id="clicks" class="value">—</div><div id="clicksToday" class="hint">اليوم —</div></article>
  <article class="card metric"><div class="label">معدل النقر CTR</div><div id="ctr" class="value">—</div><div class="hint">النقرات ÷ الزيارات</div></article>
  <article class="card metric"><div class="label">الفترة المختارة</div><div id="period" class="value">٣٠</div><div class="hint">يومًا</div></article>
  <article class="card chart-card"><div class="card-head"><h3>حركة الزيارات والنقرات</h3><span class="badge">يومي</span></div><div id="chart" class="chart"></div><div class="legend"><span><i class="dot"></i>زيارات</span><span><i class="dot blue"></i>نقرات</span></div></article>
  <article class="card side-card"><div class="card-head"><h3>المتاجر</h3><span class="badge">حسب النقرات</span></div><div id="stores" class="list"></div><div class="card-head" style="margin-top:26px"><h3>الأجهزة</h3><span class="badge">حسب الزيارات</span></div><div id="devices" class="list"></div></article>
  <article class="card wide"><div class="card-head"><h3>المنتجات الأكثر نقرًا</h3><span class="badge">أفضل ١٥ منتجًا</span></div><div class="table-wrap"><table><thead><tr><th>#</th><th>المنتج</th><th>المتجر</th><th>التصنيف</th><th>النقرات</th></tr></thead><tbody id="topProducts"></tbody></table></div></article>
  <article class="card side-card"><div class="card-head"><h3>التصنيفات الرائجة</h3></div><div id="categories" class="list"></div></article>
  <article class="card side-card"><div class="card-head"><h3>الدول</h3></div><div id="countries" class="list"></div></article>
  <article class="card side-card"><div class="card-head"><h3>مصادر الزيارات</h3></div><div id="referrers" class="list"></div></article>
</section>
<footer class="foot"><span>© Overly — لوحة قراءة فقط</span><span id="generated">—</span></footer>
</main>
<script nonce="\${nonce}">
const $=id=>document.getElementById(id);
const fmt=n=>new Intl.NumberFormat("ar-SA").format(Number(n||0));
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let days=30;
function distribution(id,items){
  const root=$(id), list=Array.isArray(items)?items:[], max=Math.max(1,...list.map(x=>Number(x.count||0)));
  root.innerHTML=list.length?list.map(x=>\`<div class="dist"><span>\${esc(x.label||"غير محدد")}</span><div class="track"><div class="fill" style="width:\${Math.max(3,Number(x.count||0)/max*100)}%"></div></div><span class="count">\${fmt(x.count)}</span></div>\`).join(""):'<div class="empty">لا توجد بيانات بعد</div>';
}
function chart(items){
  const list=Array.isArray(items)?items:[], max=Math.max(1,...list.flatMap(x=>[Number(x.views||0),Number(x.clicks||0)]));
  $("chart").innerHTML=list.length?list.map(x=>\`<div class="bar-wrap" title="\${esc(x.day)} · زيارات \${fmt(x.views)} · نقرات \${fmt(x.clicks)}"><i class="bar" style="height:\${Math.max(1,Number(x.views||0)/max*100)}%"></i><i class="bar clicks" style="height:\${Math.max(1,Number(x.clicks||0)/max*100)}%"></i></div>\`).join(""):'<div class="empty" style="width:100%">ستظهر الحركة هنا بعد بدء تسجيل الزيارات.</div>';
}
function products(items){
  const list=Array.isArray(items)?items:[];
  $("topProducts").innerHTML=list.length?list.map((x,i)=>\`<tr><td>\${fmt(i+1)}</td><td>\${esc(x.title||x.product_key||"منتج")}</td><td>\${esc(x.store||"—")}</td><td>\${esc(x.category||"—")}</td><td class="num">\${fmt(x.clicks)}</td></tr>\`).join(""):'<tr><td colspan="5" class="empty">لا توجد نقرات مسجلة بعد</td></tr>';
}
async function load(){
  const status=$("status");status.className="status";status.textContent="جارٍ تحديث اللوحة…";
  try{
    const response=await fetch(\`/api/analytics?days=\${days}\`,{headers:{Accept:"application/json"},cache:"no-store"});
    const data=await response.json();if(!response.ok||!data.ok)throw new Error(data.error||"LOAD_FAILED");
    const s=data.summary||{};$("views").textContent=fmt(s.views);$("clicks").textContent=fmt(s.clicks);$("ctr").textContent=\`\${Number(s.ctr||0).toLocaleString("ar-SA")}%\`;$("viewsToday").textContent=\`اليوم \${fmt(s.views_today)}\`;$("clicksToday").textContent=\`اليوم \${fmt(s.clicks_today)}\`;$("period").textContent=fmt(data.days);
    chart(data.daily);products(data.top_products);distribution("stores",data.stores);distribution("devices",data.devices);distribution("categories",data.categories);distribution("countries",data.countries);distribution("referrers",data.referrers);
    const when=new Date(data.generated_at);$("generated").textContent=\`آخر تحديث: \${when.toLocaleString("ar-SA")}\`;status.textContent="البيانات محدثة";
  }catch(error){status.className="status error";status.textContent="تعذر تحميل البيانات — تحقق من ربط D1 وإعداد Cloudflare Access."}
}
document.querySelectorAll("[data-days]").forEach(button=>button.addEventListener("click",()=>{days=Number(button.dataset.days);document.querySelectorAll("[data-days]").forEach(x=>x.classList.toggle("active",x===button));load()}));
load();setInterval(load,60000);
</script>
</body>
</html>\`;
}