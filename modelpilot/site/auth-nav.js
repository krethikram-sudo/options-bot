/* Reflect signed-in state in the marketing-site nav.
   The site is static, so it asks the console (same-site: outlay-ai.com ⇄ app.outlay-ai.com,
   so the session cookie is sent) whether you're signed in. If so, the nav shows the signed-in
   user (plain text) + an account hamburger menu with Dashboard and Sign out.
   Fails silently when signed out / offline. */
(function () {
  var APP = "https://app.outlay-ai.com";

  function injectCss() {
    if (document.getElementById("acctmenu-css")) return;
    var st = document.createElement("style");
    st.id = "acctmenu-css";
    st.textContent =
      ".acctmenu{position:relative;display:flex;align-items:center;gap:12px}" +
      ".acctname{color:#fff;font-weight:600;font-size:14px;white-space:nowrap;max-width:240px;overflow:hidden;text-overflow:ellipsis}" +
      ".acctburger{display:flex;flex-direction:column;justify-content:center;gap:4px;width:40px;height:36px;padding:0 9px;background:transparent;border:1px solid rgba(255,255,255,.35);border-radius:9px;cursor:pointer}" +
      ".acctburger span{display:block;height:2px;background:#fff;border-radius:2px}" +
      ".acctburger:hover{border-color:rgba(255,255,255,.75)}" +
      ".acctdrop{position:absolute;right:0;top:calc(100% + 10px);min-width:184px;background:#fff;border:1px solid #e4e4ea;border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.20);padding:6px;z-index:60}" +
      ".acctdrop[hidden]{display:none}" +
      ".acctdrop a{display:block;padding:10px 12px;border-radius:8px;font-size:14px;font-weight:600;color:#1f2430;text-decoration:none}" +
      ".acctdrop a:hover{background:#f3f4f6}" +
      ".acctdrop a.danger{color:#c0392b}" +
      "@media(max-width:560px){.acctname{display:none}}";
    document.head.appendChild(st);
  }

  function buildMenu(name) {
    injectCss();
    var wrap = document.createElement("div");
    wrap.className = "acctmenu";

    var nameEl = document.createElement("span");
    nameEl.className = "acctname";
    nameEl.textContent = name;        // textContent → no HTML injection from the email
    nameEl.title = name;

    var burger = document.createElement("button");
    burger.type = "button";
    burger.className = "acctburger";
    burger.setAttribute("aria-label", "Account menu");
    burger.setAttribute("aria-haspopup", "true");
    burger.setAttribute("aria-expanded", "false");
    burger.innerHTML = "<span></span><span></span><span></span>";

    var drop = document.createElement("div");
    drop.className = "acctdrop";
    drop.hidden = true;
    drop.setAttribute("role", "menu");
    drop.innerHTML =
      '<a href="' + APP + '/app" role="menuitem">Dashboard</a>' +
      '<a href="' + APP + '/logout" class="danger" role="menuitem">Sign out</a>';

    function close() { drop.hidden = true; burger.setAttribute("aria-expanded", "false"); }
    burger.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = drop.hidden;
      drop.hidden = !willOpen;
      burger.setAttribute("aria-expanded", String(willOpen));
    });
    document.addEventListener("click", function (e) { if (!wrap.contains(e.target)) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });

    wrap.appendChild(nameEl);
    wrap.appendChild(burger);
    wrap.appendChild(drop);
    return wrap;
  }

  function apply(s) {
    if (!s || !s.signed_in) return;
    // Prefer the display name; fall back to the email alias (everything before the @).
    var name = (s.name || "").trim() ||
               (s.email || "Account").split("@")[0] || "Account";
    // Replace the nav "Sign in" button with the account menu.
    var signin = document.querySelector('.navcta a.btn.primary[href*="/login"]') ||
                 document.querySelector('.navcta a[href*="app.outlay-ai.com/login"]');
    if (signin) signin.parentNode.replaceChild(buildMenu(name), signin);
    // Footer "Sign in" link → "Dashboard".
    var foot = document.querySelectorAll('footer a[href*="app.outlay-ai.com/login"]');
    Array.prototype.forEach.call(foot, function (a) {
      a.textContent = "Dashboard";
      a.setAttribute("href", APP + "/app");
    });
  }

  try {
    fetch(APP + "/api/session", { credentials: "include" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(apply)
      .catch(function () {});
  } catch (e) {}
})();
