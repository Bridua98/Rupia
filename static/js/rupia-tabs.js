(function () {
  document.querySelectorAll("[data-rupia='tabs']").forEach(function (root) {
    var tabs = root.querySelectorAll("[data-tab]");
    var panels = root.querySelectorAll("[data-tab-panel]");

    function activate(id) {
      tabs.forEach(function (tab) {
        var on = tab.getAttribute("data-tab") === id;
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-tab-panel") !== id;
      });
    }

    root.addEventListener("click", function (event) {
      var tab = event.target.closest("[data-tab]");
      if (!tab || !root.contains(tab)) return;
      activate(tab.getAttribute("data-tab"));
    });

    root.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      var current = root.querySelector('[data-tab][aria-selected="true"]');
      if (!current) return;
      var list = Array.prototype.slice.call(tabs);
      var index = list.indexOf(current);
      if (index < 0) return;
      event.preventDefault();
      var next = event.key === "ArrowRight" ? index + 1 : index - 1;
      if (next < 0 || next >= list.length) return;
      activate(list[next].getAttribute("data-tab"));
      list[next].focus();
    });

    panels.forEach(function (panel) {
      var errores = panel.querySelectorAll(".field-error, .has-error");
      var hay = Array.prototype.some.call(errores, function (nodo) {
        if (nodo.hidden) return false;
        if (nodo.classList.contains("has-error")) return true;
        return Boolean((nodo.textContent || "").trim());
      });
      if (!hay) return;
      var badge = root.querySelector('[data-tab-badge="' + panel.getAttribute("data-tab-panel") + '"]');
      if (!badge) return;
      badge.hidden = false;
      badge.textContent = "!";
    });
  });
})();
