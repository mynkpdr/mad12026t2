// Look and feel only: light/dark theme, collapsed sidebar, tooltip placement.
// No feature depends on this file.
const root = document.documentElement;
root.setAttribute("data-bs-theme", localStorage.getItem("theme") || "light");
root.setAttribute("data-sidebar", localStorage.getItem("sidebar") || "open");

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-theme-toggle]").forEach((button) =>
    button.addEventListener("click", () => {
      const next = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-bs-theme", next);
      localStorage.setItem("theme", next);
      document.dispatchEvent(new Event("themechange")); // charts redraw with the new colours
    })
  );
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    const show = () => button.setAttribute("aria-expanded", root.getAttribute("data-sidebar") === "open");
    show();
    button.addEventListener("click", () => {
      const next = root.getAttribute("data-sidebar") === "open" ? "collapsed" : "open";
      root.setAttribute("data-sidebar", next);
      localStorage.setItem("sidebar", next);
      show();
    });
  });
});

// Before a tooltip shows, flip it inward if it would be cut off by the screen edge,
// the sticky top bar, or a scrolling box such as a table.
function placeTip(event) {
  const el = event.target.closest && event.target.closest("[data-tip]");
  if (!el) return;
  const tip = getComputedStyle(el, "::after");
  const r = el.getBoundingClientRect();
  const bar = document.querySelector(".topbar");
  const main = el.closest(".app-main"); // the fixed sidebar covers anything left of the main column
  const room = {
    left: main ? main.getBoundingClientRect().left : 0,
    right: innerWidth,
    top: bar && !bar.contains(el) ? bar.getBoundingClientRect().bottom : 0,
  };
  for (let box = el.parentElement; box; box = box.parentElement) {
    const style = getComputedStyle(box);
    if (style.overflowX !== "visible" || style.overflowY !== "visible") {
      const b = box.getBoundingClientRect();
      room.left = Math.max(room.left, b.left);
      room.right = Math.min(room.right, b.right);
      room.top = Math.max(room.top, b.top);
    }
  }
  const half = parseFloat(tip.width) / 2, middle = r.left + r.width / 2;
  el.dataset.tipX = middle - half < room.left ? "start" : middle + half > room.right ? "end" : "";
  el.dataset.tipY = r.top - parseFloat(tip.height) - 8 < room.top ? "below" : "";
}
document.addEventListener("pointerover", placeTip);
document.addEventListener("focusin", placeTip);
