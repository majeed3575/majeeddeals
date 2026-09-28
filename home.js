/* Homepage contains no catalog requests, affiliate actions or product popups. */
(function (root) {
  "use strict";
  const doc = root.document;
  const params = new URLSearchParams(root.location.search);
  // Preserve bookmarks and product links from the former single-page catalog.
  if (params.has("deal") || params.has("q") ||
      ["#dealsTitle", "#aliSearchSection", "#mobileSearchHub"].includes(root.location.hash)) {
    root.location.replace("browse.html" + root.location.search + root.location.hash);
    return;
  }
  const region = doc.getElementById("howItWorks");
  const slides = Array.from(doc.querySelectorAll("[data-home-slide]"));
  const tabs = Array.from(doc.querySelectorAll("[data-home-step]"));
  const play = doc.getElementById("homePlay");
  const status = doc.getElementById("homeSlideStatus");
  const motion = root.matchMedia("(prefers-reduced-motion: reduce)");
  const t = value => root.OverlyI18n?.t(value) || value;
  let index = 0, timer = null, paused = motion.matches, hovering = false, gesture = null, explicitPlay = false;
  function stop() { root.clearTimeout(timer); timer = null; }
  function schedule() {
    stop();
    if (paused || doc.hidden || (!explicitPlay && (hovering || region.contains(doc.activeElement)))) return;
    timer = root.setTimeout(() => { show(index + 1, false); }, 7000);
  }
  function controls() {
    play.setAttribute("aria-pressed", String(paused));
    play.setAttribute("aria-label", t(paused ? "تشغيل الحركة التلقائية" : "إيقاف الحركة التلقائية"));
    play.firstElementChild.textContent = paused ? "▷" : "Ⅱ";
  }
  function show(next, manual = true) {
    index = (next + slides.length) % slides.length;
    slides.forEach((slide, i) => { slide.hidden = i !== index; slide.inert = i !== index; });
    tabs.forEach((button, i) => {
      if (i === index) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
    status.setAttribute("aria-live", manual ? "polite" : "off");
    status.textContent = t("الخطوة {count} من {total}").replace("{count}", String(index + 1)).replace("{total}", String(slides.length));
    if (manual) { paused = true; explicitPlay = false; }
    controls();
    schedule();
  }
  tabs.forEach((button, i) => button.addEventListener("click", () => show(i)));
  doc.getElementById("homeNext").addEventListener("click", () => show(index + 1));
  doc.getElementById("homePrevious").addEventListener("click", () => show(index - 1));
  play.addEventListener("click", () => { paused = !paused; explicitPlay = !paused; controls(); schedule(); });
  region.addEventListener("mouseenter", () => { hovering = true; explicitPlay = false; stop(); });
  region.addEventListener("mouseleave", () => { hovering = false; schedule(); });
  // Keyboard/touch users keep control; manual navigation pauses rotation.
  region.addEventListener("focusin", () => { explicitPlay = false; stop(); });
  region.addEventListener("focusout", () => root.setTimeout(schedule, 0));
  region.addEventListener("keydown", event => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const forward = doc.documentElement.dir === "rtl" ? "ArrowLeft" : "ArrowRight";
    show(index + (event.key === forward ? 1 : -1));
  });
  region.addEventListener("touchstart", event => {
    const touch = event.touches[0];
    gesture = { x: touch.clientX, y: touch.clientY };
    stop();
  }, { passive: true });
  region.addEventListener("touchend", event => {
    if (!gesture) return;
    const touch = event.changedTouches[0];
    const dx = touch.clientX - gesture.x, dy = touch.clientY - gesture.y;
    gesture = null;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) {
      const forward = doc.documentElement.dir === "rtl" ? dx > 0 : dx < 0;
      show(index + (forward ? 1 : -1));
    } else schedule();
  }, { passive: true });
  region.addEventListener("touchcancel", () => { gesture = null; schedule(); }, { passive: true });
  doc.addEventListener("visibilitychange", schedule);
  doc.addEventListener("overly:languagechange", () => { controls(); });
  motion.addEventListener("change", () => { if (motion.matches) paused = true; controls(); schedule(); });
  show(0, false);
})(globalThis);
