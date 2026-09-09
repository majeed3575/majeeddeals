/* Whole phrases and parameterised copy, not word-by-word machine translation. */
(function(root){
  const digits=s=>String(s).replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/٪/g,'%');
  root.OverlyEnglishPhrase=function translate(value,lookup,depth=0){
    const text=String(value||'').replace(/\s+/g,' ').trim();
    const direct=lookup(text);if(direct!==undefined)return direct;
    if(depth>5)return text;
    const t=s=>translate(s,lookup,depth+1),n=digits;
    if(!/[\u0600-\u06ff]/u.test(text))return text;
    if(text.endsWith(' | أوفرلي'))return `${t(text.slice(0,-9))} | Overly`;
    if(/^[\d٠-٩.,٬٫%٪\s+−-]+$/.test(text))return n(text).replace(/٬/g,',').replace(/٫/g,'.');
    const rules=[
      [/^لا تفوّت أقوى عرض بخصم (\d+)٪$/,m=>`Don't miss this ${m[1]}% discount`],
      [/^(.*?) — الصفحة (\d+)$/,m=>`${t(m[1])} — Page ${m[2]}`],
      [/^صفحة (\d+) من (\d+)$/,m=>`Page ${m[1]} of ${m[2]}`],
      [/^([\d,٠-٩٬]+) منتجاً في هذا القسم$/,m=>`${n(m[1])} products in this category`],
      [/^تقييم ([\d.]+) من 5$/,m=>`Rated ${m[1]} out of 5`],
      [/^([\d,]+) طلب مسجل لدى المنصة$/,m=>`${m[1]} orders recorded by the platform`],
      [/^خصم مرصود (\d+)٪$/,m=>`${m[1]}% observed discount`],
      [/^(خصم|وفّر) ([\d٠-٩]+)٪$/,m=>`${n(m[2])}% ${m[1]==='خصم'?'off':'saving'}`],
      [/^([\d٠-٩.,٬]+) (?:ر\.س|مبيعة)$/,m=>`${n(m[1])} ${text.endsWith('مبيعة')?'sold':'SAR'}`],
      [/^تحقق من السعر الحالي على (.+) ↗$/,m=>`Check the current price on ${m[1]} ↗`],
      [/^منتجات أخرى من (.+)$/,m=>`More products in ${t(m[1])}`],
      [/^كل منتجات (.+) ←$/,m=>`All ${t(m[1])} products →`],
      [/^تصفح (.+) المختارة وفق بيانات الرواج، ثم تحقق من السعر والتوفر لدى المتجر\.$/,m=>`Browse ${t(m[1])} selected using available popularity data, then check the price and availability at the store.`],
      [/^قد يناسب (.+)\. الملاءمة النهائية تعتمد على احتياجك والمواصفات التي يذكرها البائع\.$/,m=>`May suit ${t(m[1])}. Final suitability depends on your needs and the seller's specifications.`],
      [/^راجع (.+)، إضافة إلى الشحن للسعودية وسياسة الإرجاع والضمان والسعر النهائي لدى المتجر\.$/,m=>`Check ${t(m[1])}, along with shipping to Saudi Arabia, returns, warranty and the final price at the store.`],
      [/^ينتمي إلى تصنيف (.+?)(?:، وتظهر بيانات المنصة ([\d,]+) طلباً مسجلاً)?(?:، مع تقييم ([\d.]+) من 5)?\. لا يعني ظهوره أننا اختبرناه شخصياً؛ الاختيار آلي وفق البيانات المتاحة ثم يُعرض للتحقق لدى المتجر\.$/,m=>`Listed under ${t(m[1])}${m[2]?`, with ${m[2]} platform-recorded orders`:''}${m[3]?` and a ${m[3]}/5 rating`:''}. Listing does not mean we have personally tested it; selection is automated using available data, which you should verify at the store.`],
      [/^آخر مراجعة: (.+) · لا يتضمن ادعاء اختبار شخصي$/,m=>`Last reviewed: ${m[1]} · No claim of personal testing`],
      [/^أحد أبرز عروض (.+)$/,m=>`A featured find from ${m[1]}`],
      [/^(?:تفاصيل|مشاركة) (.+)$/,m=>`${text.startsWith('تفاصيل')?'Details':'Share'}: ${t(m[1])}`],
      [/^العرض (\d+)$/,m=>`Offer ${m[1]}`],
      [/^(.+) قبل الخصم:?$/,m=>`${m[1]} before discount${text.endsWith(':')?':':''}`],
      [/^السعر الحالي والتوفر يُتحقق منهما على (.+)$/,m=>`Check current price and availability on ${m[1]}`],
      [/^السعر على (.+)$/,m=>`Price on ${m[1]}`],
      [/^يُتحقق على (.+)$/,m=>`Check on ${m[1]}`],
      [/^تحميل ([\d٠-٩٬,]+) عرضًا إضافيًا$/,m=>`Load ${n(m[1])} more offers`],
      [/^واصل النزول — تُجلب نتائج AliExpress التالية تلقائيًا \((.+)\)$/,m=>`Keep scrolling — more AliExpress results load automatically (${n(m[1])})`],
      [/^واصل النزول — تظهر العروض تلقائيًا \((.+) من (.+)\)$/,m=>`Keep scrolling — offers load automatically (${n(m[1])} of ${n(m[2])})`],
      [/^يظهر الآن (.+) من أصل (.+)$/,m=>`Showing ${n(m[1])} of ${n(m[2])}`],
      [/^يظهر الآن (.+) نتيجة$/,m=>`Showing ${n(m[1])} results`],
      [/^وجدنا (.+) نتيجة مطابقة في أوفرلي\.$/,m=>`Found ${n(m[1])} matching products on Overly.`],
      [/^يعرض أوفرلي الآن (.+) من المنتجات الأكثر رواجًا\.$/,m=>`Overly currently shows ${n(m[1])} popular products.`],
      [/^ظهرت (.+) نتيجة من AliExpress قابلة للشحن للسعودية( — واصل النزول للمزيد)?\.$/,m=>`${n(m[1])} AliExpress results available for shipping to Saudi Arabia${m[2]?' — scroll for more':''}.`],
      [/^آخر تحديث (.+)$/,m=>`Last updated ${n(m[1])}`],
      [/^© (\d+) أوفرلي \(Overly\) — جميع الحقوق محفوظة\.$/,m=>`© ${m[1]} Overly — All rights reserved.`],
    ];
    for(const [pattern,render]of rules){const m=text.match(pattern);if(m)return render(m);}
    for(const delimiter of [' | ',' · '])if(text.includes(delimiter))return text.split(delimiter).map(t).join(delimiter);
    return text;
  };
})(globalThis);
