/* Reflect signed-in state in the marketing-site nav.
   The site is static, so it asks the console (same-site: outlay-ai.com ⇄ app.outlay-ai.com,
   so the session cookie is sent) whether you're signed in, and if so swaps the "Sign in"
   button for "Go to dashboard" + "Sign out". Fails silently when signed out / offline. */
(function () {
  var APP = "https://app.outlay-ai.com";
  try {
    fetch(APP + "/api/session", { credentials: "include" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s || !s.signed_in) return;
        var links = document.querySelectorAll('a[href*="app.outlay-ai.com/login"]');
        Array.prototype.forEach.call(links, function (a) {
          a.setAttribute("href", APP + "/app");
          a.textContent = a.classList.contains("btn") ? "Go to dashboard" : "Dashboard";
          // Next to the primary nav button, add a "Sign out" link.
          if (a.classList.contains("primary") && !a.dataset.authNav) {
            a.dataset.authNav = "1";
            var out = document.createElement("a");
            out.setAttribute("href", APP + "/logout");
            out.className = "btn ghost";
            out.textContent = "Sign out";
            a.insertAdjacentElement("afterend", out);
          }
        });
      })
      .catch(function () {});
  } catch (e) {}
})();
