(function () {
  var MENSAJE_LISTA = "Elegí una opción de la lista.";

  function boot() {
    document.querySelectorAll("[data-rupia='combo']").forEach(init);
    if (!document.documentElement.getAttribute("data-combo-submit")) {
      document.documentElement.setAttribute("data-combo-submit", "1");
      document.addEventListener("submit", onSubmit, true);
    }
  }

  function parseOptions(root) {
    var raw = root.getAttribute("data-combo-options");
    if (!raw) return [];
    try {
      var data = JSON.parse(raw);
      return Array.isArray(data) ? data : [];
    } catch (err) {
      return [];
    }
  }

  function queryEl(root) {
    return root.querySelector("[data-combo-query]");
  }

  function valueEl(root) {
    return root.querySelector("[data-combo-value]");
  }

  function listEl(root) {
    return root.querySelector("[data-combo-results]");
  }

  function errorEl(root) {
    return root.querySelector("[data-combo-error]");
  }

  function comboForm(root) {
    var value = valueEl(root);
    return value ? value.form : null;
  }

  function isRequired(root) {
    return root.getAttribute("data-required") === "1";
  }

  function requiredMessage(root) {
    return root.getAttribute("data-required-message") || MENSAJE_LISTA;
  }

  function csrfToken() {
    var field = document.querySelector("[name=csrfmiddlewaretoken]");
    return field ? field.value : "";
  }

  function closeList(root) {
    var list = listEl(root);
    var query = queryEl(root);
    if (list) list.hidden = true;
    if (query) query.setAttribute("aria-expanded", "false");
    root._comboActive = -1;
  }

  function marcar(root) {
    var value = valueEl(root);
    var query = queryEl(root);
    var tiene = Boolean(value && value.value) || Boolean(query && query.value.trim());
    root.classList.toggle("is-filled", tiene);
  }

  function showError(root, message) {
    var query = queryEl(root);
    var node = errorEl(root);
    root.classList.add("has-error");
    if (node) {
      node.hidden = !message;
      node.textContent = message || "";
    }
    if (query) {
      query.setCustomValidity(message || "");
      if (message) query.reportValidity();
    }
  }

  function clearError(root) {
    var query = queryEl(root);
    var node = errorEl(root);
    root.classList.remove("has-error");
    if (node) {
      node.hidden = true;
      node.textContent = "";
    }
    if (query) query.setCustomValidity("");
  }

  function validate(root) {
    var value = valueEl(root);
    var query = queryEl(root);
    var texto = query ? query.value.trim() : "";
    var id = value ? String(value.value || "").trim() : "";
    if (id) {
      clearError(root);
      return true;
    }
    if (!texto) {
      if (isRequired(root)) {
        showError(root, requiredMessage(root));
        if (query) query.focus();
        return false;
      }
      clearError(root);
      return true;
    }
    showError(root, MENSAJE_LISTA);
    if (query) query.focus();
    return false;
  }

  function accept(root, row, silent) {
    if (!row) return;
    var event = new CustomEvent("rupia-combo-accept", {
      bubbles: true,
      cancelable: true,
      detail: { row: row },
    });
    root.dispatchEvent(event);
    if (event.defaultPrevented) return;

    if (row.nueva) {
      abrirNueva(root);
      return;
    }
    if (row.origen === "padron" || (row.id == null && (row.ruc || row.documento))) {
      altaPadron(root, row);
      return;
    }
    if (row.id == null || row.id === "") return;

    var value = valueEl(root);
    var query = queryEl(root);
    value.value = String(row.id);
    query.value = row.label || "";
    root.setAttribute("data-selected-label", row.label || "");
    clearError(root);
    marcar(root);
    closeList(root);
    value.dispatchEvent(new Event("change", { bubbles: true }));
    if (!silent && root.getAttribute("data-submit") === "1") {
      var form = comboForm(root);
      if (form) {
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else form.submit();
      }
    }
  }

  function abrirNueva(root) {
    var base = root.getAttribute("data-nueva-persona") || "";
    if (!base) return;
    var url = new URL(base, window.location.origin);
    var query = queryEl(root);
    var q = query ? query.value.trim() : "";
    if (q) {
      if (/^\d[\d.-]*$/.test(q)) url.searchParams.set("documento", q);
      else url.searchParams.set("razon_social", q);
    }
    window.open(url.toString(), "rupia_persona", "popup=yes,width=960,height=780");
  }

  function altaPadron(root, row) {
    var url = root.getAttribute("data-alta-url");
    if (!url) return;
    var query = queryEl(root);
    var body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrfToken());
    if (row.ruc) body.set("ruc", row.ruc);
    body.set("q", (query && query.value.trim()) || row.documento || row.label || "");
    fetch(url, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body: body,
    }).then(function () {
      window.location.reload();
    });
  }

  function cloneTemplate(root, selector) {
    var node = root.querySelector(selector);
    if (!node || !node.content) return null;
    return node.content.cloneNode(true);
  }

  function paint(root, results) {
    var list = listEl(root);
    var query = queryEl(root);
    if (!list) return;
    list.innerHTML = "";
    root._comboItems = results || [];
    root._comboActive = -1;
    var isPos = root.classList.contains("is-pos");
    if (!root._comboItems.length) {
      var vacio = document.createElement("li");
      vacio.className = (isPos ? "" : "combo-option ") + "is-empty";
      vacio.setAttribute("role", "presentation");
      vacio.textContent = "No hay coincidencias.";
      list.appendChild(vacio);
      list.hidden = false;
      if (query) query.setAttribute("aria-expanded", "true");
      return;
    }
    root._comboItems.forEach(function (row, index) {
      var option = document.createElement("li");
      option.className = (isPos ? "" : "combo-option") + (row.nueva ? " is-action" : "");
      option.setAttribute("role", "option");
      option.dataset.index = String(index);
      if (row.id != null && row.id !== "") option.dataset.id = String(row.id);

      var titulo = document.createElement("strong");
      titulo.textContent = row.label || "";
      var meta = filaMeta(root, row);
      if (isPos) {
        option.appendChild(titulo);
        if (meta) {
          var detallePos = document.createElement("small");
          detallePos.textContent = meta;
          option.appendChild(detallePos);
        }
      } else {
        var copy = document.createElement("span");
        copy.className = "combo-option-copy";
        copy.appendChild(titulo);
        if (meta) {
          var detalle = document.createElement("small");
          detalle.textContent = meta;
          copy.appendChild(detalle);
        }
        option.appendChild(copy);
        var check = document.createElement("span");
        check.className = "combo-option-check";
        check.setAttribute("aria-hidden", "true");
        var checkIcon = cloneTemplate(root, "[data-combo-check-icon]");
        if (checkIcon) check.appendChild(checkIcon);
        option.appendChild(check);
      }

      option.addEventListener("mousedown", function (event) {
        event.preventDefault();
        accept(root, row);
      });
      list.appendChild(option);
    });
    root._comboActive = 0;
    mark(root, 0);
    list.hidden = false;
    if (query) query.setAttribute("aria-expanded", "true");
  }

  function filaMeta(root, row) {
    if (row.meta) return row.meta;
    if (row.nueva) return root.getAttribute("data-nueva-ayuda") || "Abrir la ficha para cargar.";
    if (row.origen === "padron") {
      var extra = root.getAttribute("data-padron-label") || "Crear";
      var doc = row.documento || row.ruc || "";
      return doc ? doc + " · " + extra : extra;
    }
    return row.documento || row.ruc || "";
  }

  function mark(root, index) {
    var list = listEl(root);
    if (!list) return;
    var options = list.querySelectorAll("[role='option']");
    root._comboActive = index;
    options.forEach(function (option, i) {
      option.setAttribute("aria-selected", i === index ? "true" : "false");
      option.classList.toggle("is-on", i === index);
    });
    if (options[index]) options[index].scrollIntoView({ block: "nearest" });
  }

  function localSearch(root, q) {
    var options = parseOptions(root);
    if (!q) return options.slice(0, 20);
    var needle = q.toLowerCase();
    return options
      .filter(function (row) {
        return String(row.label || "")
          .toLowerCase()
          .indexOf(needle) !== -1;
      })
      .slice(0, 20);
  }

  function decorate(root, results, q) {
    var items = (results || []).slice();
    var event = new CustomEvent("rupia-combo-results", {
      bubbles: true,
      detail: { results: items, query: q },
    });
    root.dispatchEvent(event);
    items = event.detail.results || items;
    if (root.getAttribute("data-nueva-persona") && q) {
      var ya = items.some(function (row) {
        return row.nueva;
      });
      if (!ya) {
        items.push({
          nueva: true,
          label: "Nueva persona",
          meta: root.getAttribute("data-nueva-ayuda") || "Abrir la ficha para cargar.",
        });
      }
    }
    return items;
  }

  function search(root) {
    var query = queryEl(root);
    var q = query ? query.value.trim() : "";
    var url = root.getAttribute("data-search-url");
    if (!url) {
      paint(root, decorate(root, localSearch(root, q), q));
      return;
    }
    var pedido = (root._comboPedido || 0) + 1;
    root._comboPedido = pedido;
    fetch(url + (url.indexOf("?") >= 0 ? "&" : "?") + "q=" + encodeURIComponent(q), {
      headers: { Accept: "application/json" },
    })
      .then(function (response) {
        return response.ok ? response.json() : { results: [] };
      })
      .then(function (data) {
        if (pedido !== root._comboPedido) return;
        if (document.activeElement !== query) return;
        var rows = data.results || data.resultados || [];
        paint(root, decorate(root, rows, q));
      })
      .catch(function () {
        if (pedido !== root._comboPedido) return;
        closeList(root);
      });
  }

  function exactMatch(root) {
    var query = queryEl(root);
    var texto = query ? query.value.trim().toLowerCase() : "";
    if (!texto) return null;
    var items = root._comboItems || [];
    var matches = items.filter(function (row) {
      return !row.nueva && String(row.label || "").toLowerCase() === texto;
    });
    if (matches.length === 1) return matches[0];
    if (items.length === 1 && !items[0].nueva) return items[0];
    return null;
  }

  function init(root) {
    if (!root || root.getAttribute("data-combo-ready")) return;
    root.setAttribute("data-combo-ready", "1");
    var query = queryEl(root);
    var value = valueEl(root);
    if (!query || !value) return;
    root._comboItems = [];
    root._comboActive = -1;
    root._comboTimer = null;

    if (root.closest(".sheet-form")) {
      if (!query.getAttribute("placeholder") || query.getAttribute("placeholder") === " ") {
        query.setAttribute("placeholder", "Buscar…");
      }
    }

    var control = root.querySelector(".combo-control");
    if (control) {
      control.addEventListener("mousedown", function (event) {
        if (event.target.closest(".selector-nueva")) return;
        if (event.target === query) return;
        event.preventDefault();
        query.focus();
      });
    }
    query.addEventListener("focus", function () {
      search(root);
    });
    query.addEventListener("input", function () {
      if (query.value !== root.getAttribute("data-selected-label")) {
        value.value = "";
        root.setAttribute("data-selected-label", "");
      }
      clearError(root);
      marcar(root);
      clearTimeout(root._comboTimer);
      root._comboTimer = setTimeout(function () {
        search(root);
      }, 180);
    });
    query.addEventListener("keydown", function (event) {
      var items = root._comboItems || [];
      var list = listEl(root);
      if (event.key === "ArrowDown" && items.length) {
        event.preventDefault();
        if (list && list.hidden) search(root);
        mark(root, Math.min(items.length - 1, (root._comboActive < 0 ? -1 : root._comboActive) + 1));
      } else if (event.key === "ArrowUp" && items.length) {
        event.preventDefault();
        mark(root, Math.max(0, root._comboActive - 1));
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (root._comboActive >= 0 && items[root._comboActive]) {
          accept(root, items[root._comboActive]);
        } else {
          var unico = exactMatch(root);
          if (unico) accept(root, unico);
        }
      } else if (event.key === "Escape") {
        closeList(root);
      }
    });
    query.addEventListener("blur", function () {
      setTimeout(function () {
        var unico = exactMatch(root);
        if (unico && !value.value) accept(root, unico, true);
        closeList(root);
        if (value.value && !query.value.trim()) {
          query.value = root.getAttribute("data-selected-label") || "";
        }
        marcar(root);
      }, 120);
    });
    marcar(root);
  }

  function onSubmit(event) {
    var form = event.target;
    if (!form || form.tagName !== "FORM") return;
    var combos = document.querySelectorAll("[data-rupia='combo']");
    var ok = true;
    var first = null;
    combos.forEach(function (root) {
      if (comboForm(root) !== form) return;
      if (!validate(root)) {
        ok = false;
        if (!first) first = queryEl(root);
      }
    });
    if (!ok) {
      event.preventDefault();
      event.stopPropagation();
      if (first) first.focus();
    }
  }

  window.rupiaInitCombo = init;
  window.rupiaComboAccept = accept;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
