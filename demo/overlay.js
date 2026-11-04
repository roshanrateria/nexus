/**
 * Demo overlay — injected before every page load with context.add_init_script.
 *
 * Exposes window.__demo with:
 *   - a fake cursor: a 22px circle with a soft shadow that follows REAL
 *     `mousemove` events (hidden until the first one), plus a click ripple
 *     on every `mousedown`;
 *   - caption(text, ms): a lower-third glass pill, one at a time, fading
 *     250ms in/out. Sits 120px from the bottom so it never covers the
 *     filmstrip or the activity ticker;
 *   - badge(on, text): a top-right pill, shown while the run is in a
 *     time-lapse stretch.
 *
 * Everything is pointer-events:none, z-index: 2147483647, fixed-position:
 * the app's own layout is never touched. Init scripts can run before
 * `document.documentElement` exists, so the DOM mounting happens on
 * DOMContentLoaded and every API call guards on it.
 */
(function () {
  var Z = 2147483647;
  var GLASS =
    "background: rgba(14, 17, 22, 0.86);" +
    "border: 1px solid rgba(148, 163, 184, 0.28);" +
    "box-shadow: 0 18px 42px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08);" +
    "backdrop-filter: blur(10px);";

  var FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";

  var STYLE = [
    /* --- fake cursor: 22px circle, soft shadow, hidden until first move --- */
    "#demo-cursor{position:fixed;top:0;left:0;width:22px;height:22px;border-radius:50%;",
    "border:2px solid rgba(230, 234, 240, 0.95);background:rgba(96, 165, 250, 0.28);",
    "box-shadow:0 2px 10px rgba(0,0,0,.55), 0 0 18px rgba(96,165,250,.35);",
    "transform:translate3d(-110px,-110px,0);opacity:0;transition:opacity .18s ease;",
    "pointer-events:none;z-index:" + Z + ";will-change:transform,opacity;margin:0}",
    /* --- click ripple --- */
    "@keyframes demo-ripple{from{transform:translate(-50%,-50%) scale(.4);opacity:.75}",
    "to{transform:translate(-50%,-50%) scale(2.6);opacity:0}}",
    ".demo-ripple{position:fixed;width:28px;height:28px;border-radius:50%;",
    "border:2px solid rgba(192, 132, 252, 0.9);pointer-events:none;z-index:" + Z + ";",
    "animation:demo-ripple .45s ease-out forwards;margin:0}",
    /* --- caption pill --- */
    "@keyframes demo-caption-in{from{opacity:0;transform:translate(-50%, 10px)}",
    "to{opacity:1;transform:translate(-50%, 0)}}",
    "@keyframes demo-caption-out{from{opacity:1;transform:translate(-50%, 0)}",
    "to{opacity:0;transform:translate(-50%, 10px)}}",
    ".demo-anim-in{animation:demo-caption-in .25s ease-out forwards!important}",
    ".demo-anim-out{animation:demo-caption-out .25s ease-in forwards!important}",
    /* --- badge --- */
    "@keyframes demo-badge-in{from{opacity:0;transform:translateY(-6px)}",
    "to{opacity:1;transform:translateY(0)}}",
  ].join("");

  /* DOM manifest: nodes appear only after mounting. */
  var api = {
    mounted: false,
    cursor: null,
    caption: function () {},
    badge: function () {},
  };

  function mount() {
    if (api.mounted || !document.documentElement) return;

    var style = document.createElement("style");
    style.textContent = STYLE;
    document.documentElement.appendChild(style);

    /* ------------------------------------------------------ cursor */
    var cursor = document.createElement("div");
    cursor.id = "demo-cursor";
    document.documentElement.appendChild(cursor);
    api.cursor = cursor;
    var cursorOn = false;

    window.addEventListener(
      "mousemove",
      function (e) {
        cursor.style.transform = "translate3d(" + (e.clientX - 11) + "px," + (e.clientY - 11) + "px,0)";
        if (!cursorOn) {
          cursorOn = true;
          cursor.style.opacity = "1";
        }
      },
      true
    );

    window.addEventListener(
      "mousedown",
      function (e) {
        if (!cursorOn) return;
        var ripple = document.createElement("div");
        ripple.className = "demo-ripple";
        ripple.style.left = e.clientX + "px";
        ripple.style.top = e.clientY + "px";
        document.documentElement.appendChild(ripple);
        window.setTimeout(function () {
          if (ripple.parentNode) ripple.parentNode.removeChild(ripple);
        }, 520);
      },
      true
    );

    /* ----------------------------------------------------- caption */
    var caption = document.createElement("div");
    caption.id = "demo-caption";
    caption.setAttribute(
      "style",
      "position:fixed;bottom:120px;left:50%;transform:translate(-50%, 0);" +
        "max-width:900px;padding:14px 26px;border-radius:18px;" +
        "color:#e6eaf0;font:600 22px/1.35 " + FONT + ";text-align:center;" +
        "text-shadow:0 1px 3px rgba(0,0,0,.7);letter-spacing:.01em;" +
        "opacity:0;pointer-events:none;z-index:" + Z + ";" +
        "display:flex;align-items:center;justify-content:center;" + GLASS
    );
    document.documentElement.appendChild(caption);
    var hideTimer = null;

    var shown_caption = function (text, ms) {
      var msNumber = typeof ms === "number" && ms > 0 ? ms : 3600;
      if (hideTimer !== null) window.clearTimeout(hideTimer);
      caption.classList.remove("demo-anim-in", "demo-anim-out");
      void caption.offsetWidth; /* restart the animation */
      caption.textContent = text;
      caption.classList.add("demo-anim-in");
      hideTimer = window.setTimeout(function () {
        caption.classList.remove("demo-anim-in");
        caption.classList.add("demo-anim-out");
      }, msNumber);
    };
    api.caption = shown_caption;

    /* ------------------------------------------------------- badge */
    var badge = document.createElement("div");
    badge.id = "demo-badge";
    badge.setAttribute(
      "style",
      "position:fixed;top:66px;right:20px;padding:6px 14px;border-radius:999px;" +
        "color:#fbbf24;font:600 13px/1.4 " + FONT + ";" +
        "letter-spacing:.08em;text-transform:uppercase;" +
        "opacity:0;transform:translateY(-6px);" +
        "transition:opacity .25s ease, transform .25s ease;" +
        "pointer-events:none;z-index:" + Z + ";" +
        "display:flex;align-items:center;gap:8px;" + GLASS
    );
    var badgeDot = document.createElement("span");
    badgeDot.setAttribute(
      "style",
      "width:8px;height:8px;border-radius:50%;background:#fbbf24;flex:none;display:inline-block"
    );
    var badgeText = document.createElement("span");
    badgeText.textContent = "Time-lapse";
    badge.appendChild(badgeDot);
    badge.appendChild(badgeText);
    document.documentElement.appendChild(badge);

    api.badge = function (on, text) {
      badgeText.textContent = text || "Time-lapse";
      badge.style.opacity = on ? "1" : "0";
      badge.style.transform = on ? "translateY(0)" : "translateY(-6px)";
    };

    api.mounted = true;
  }

  window.__demo = api;

  /* Mount as soon as there is a document; init scripts run before it. */
  if (document.documentElement) {
    mount();
  } else {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  }
})();
