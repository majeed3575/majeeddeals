(() => {
  "use strict";

  const scene = (model, key, label, slug, palette) => Object.freeze({
    model, key, label, slug,
    bg: palette[0], ink: palette[1], accent: palette[2], accent2: palette[3], panel: palette[4]
  });

  const home = scene(170, "prism-portal", "الزجاج الطيفي", "home", ["#16152a", "#fbf9ff", "#9f76ff", "#5fcfff", "#34305b"]);
  const categories = Object.freeze({
    "الإلكترونيات": scene(101, "clear-tech", "زجاج صافي", "electronics", ["#dbeaff", "#10213b", "#6a9fff", "#b8d8ff", "#f8fbff"]),
    "المنزل": scene(123, "pearl-home", "لؤلؤ هادئ", "home", ["#eef3f2", "#20302e", "#9fc7bf", "#d4e5df", "#ffffff"]),
    "السيارة": scene(145, "titanium-auto", "تيتانيوم", "car", ["#7e8b89", "#10201f", "#bee1dc", "#4b6663", "#e8f1ef"]),
    "السفر": scene(156, "spatial-travel", "مساحة صافية", "travel", ["#dfeaf2", "#152d3b", "#72b4da", "#c8e0ed", "#f9fdff"]),
    "الأزياء والأحذية": scene(167, "prism-fashion", "طيف الغروب", "fashion", ["#251510", "#fff8f1", "#ff9b58", "#e86fd1", "#503027"]),
    "التنظيف والمنظفات": scene(104, "clear-clean", "صفاء بارد", "cleaning", ["#edf3fb", "#142033", "#88aef5", "#d1ddff", "#ffffff"]),
    "المطبخ والأجهزة المنزلية": scene(193, "ocean-kitchen", "محيط ذكي", "kitchen-appliances", ["#052d32", "#effffb", "#22b8ad", "#69e0d0", "#14575b"]),
    "الأثاث والديكور": scene(152, "spatial-interior", "مساحة بنفسجية", "furniture-decor", ["#e4e7f5", "#20213e", "#9399ff", "#cbd2ff", "#ffffff"]),
    "الرحلات والبحر والتخييم": scene(196, "ocean-outdoors", "محيط عميق", "outdoors", ["#063743", "#edffff", "#2ec5c5", "#4f9eff", "#176573"]),
    "الحدائق والزراعة": scene(185, "citrus-garden", "حمضيات خضراء", "garden", ["#e2f2be", "#20330d", "#9edc3c", "#52c7a5", "#f7ffe9"]),
    "الجمال والعناية": scene(171, "ruby-beauty", "ياقوت وردي", "beauty-care", ["#2a0a12", "#fff4f6", "#ff4d6d", "#ff9aae", "#591629"]),
    "الصحة والعناية": scene(126, "pearl-care", "لؤلؤ صحي", "health-care", ["#eff2f7", "#222c3c", "#aabbd6", "#dce5f3", "#ffffff"]),
    "البقالة والمشروبات": scene(182, "citrus-grocery", "حمضيات دافئة", "grocery", ["#fff0c7", "#3b2508", "#ffb52e", "#ff7559", "#fff9e7"]),
    "الرياضة": scene(112, "aurora-sport", "شفق كهربائي", "sports", ["#1b1230", "#fff8ff", "#e26dff", "#6de4d4", "#351b54"]),
    "الأطفال": scene(189, "citrus-kids", "حمضيات مرحة", "kids", ["#dcf4c8", "#17361e", "#5fd176", "#bddf43", "#f8fff0"]),
    "الألعاب": scene(118, "aurora-toys", "شفق مرح", "toys", ["#281916", "#fff7ef", "#ff885a", "#e269cf", "#58332c"]),
    "الحيوانات الأليفة": scene(129, "pearl-pets", "لؤلؤ ناعم", "pets", ["#f5eff1", "#392832", "#d1aabd", "#ecd4de", "#fff9fc"]),
    "الأدوات والهوايات": scene(141, "titanium-tools", "تيتانيوم صناعي", "tools-hobbies", ["#8f969e", "#111820", "#d6e1e8", "#62717e", "#edf2f5"]),
    "الترفيه المنزلي": scene(115, "aurora-cinema", "شفق سينمائي", "home-entertainment", ["#0d2630", "#f0fffb", "#43d3a5", "#68a5ff", "#164945"]),
    "المدرسة والقرطاسية": scene(159, "spatial-school", "مساحة وردية", "school-stationery", ["#f1e5ee", "#3d2334", "#dc91b8", "#efcfdf", "#fff9fc"]),
    "الكتب والمكتب": scene(140, "midnight-books", "منتصف الليل", "books-office", ["#0e0716", "#fff4ff", "#e45cff", "#5de0ce", "#321946"]),
    "الساعات والمجوهرات": scene(174, "ruby-watches", "ياقوت فاخر", "watches-jewelry", ["#321011", "#fff7ef", "#e95a3f", "#f4b16e", "#652820"]),
    "تسوق متنوع": scene(163, "prism-general", "طيف دافئ", "general", ["#24110f", "#fff8ee", "#ff7a55", "#ffd75b", "#4d2821"])
  });

  window.OVERLY_VISUAL_SYSTEM = Object.freeze({home, categories});
})();
