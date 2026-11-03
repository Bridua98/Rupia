(function () {
  function boot() {
    document.querySelectorAll("[data-persona-consulta]").forEach(init);
  }

  function init(input) {
    if (input.getAttribute("data-persona-ready")) return;
    input.setAttribute("data-persona-ready", "1");
    var field = input.closest(".field") || input.parentElement;
    var list = document.createElement("ul");
    list.className = "persona-consulta-results";
    list.setAttribute("role", "listbox");
    list.hidden = true;
    field.appendChild(list);
    var timer = null;
    var active = -1;
    var rows = [];

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
      active = -1;
      rows = [];
    }

    function apply(ficha) {
      var form = input.form;
      if (!form || !ficha) return;
      var tipo = form.querySelector('[name="tipo_documento"]');
      var documento = form.querySelector('[name="documento"]');
      var razon = form.querySelector('[name="razon_social"]');
      var fecha = form.querySelector('[name="fecha_nacimiento"]');
      if (tipo && ficha.tipo_documento) tipo.value = ficha.tipo_documento;
      if (documento && ficha.documento) documento.value = ficha.documento;
      if (razon && ficha.razon_social) razon.value = ficha.razon_social;
      if (fecha && ficha.fecha_nacimiento) fecha.value = ficha.fecha_nacimiento;
    }

    function choose(row) {
      closeList();
      var url = input.getAttribute("data-persona-consulta");
      fetch(url + "?ruc=" + encodeURIComponent(row.ruc || ""), {
        headers: { Accept: "application/json" },
      })
        .then(function (response) {
          return response.ok ? response.json() : row;
        })
        .then(function (ficha) {
          apply(Object.assign({}, row, ficha || {}));
        })
        .catch(function () {
          apply(row);
        });
    }

    function paint(results) {
      list.innerHTML = "";
      active = -1;
      rows = results || [];
      if (!rows.length) {
        closeList();
        return;
      }
      rows.forEach(function (row, index) {
        var option = document.createElement("li");
        option.setAttribute("role", "option");
        option.textContent = row.label || row.razon_social || row.documento;
        option.addEventListener("mousedown", function (event) {
          event.preventDefault();
          choose(row);
        });
        option.addEventListener("mouseenter", function () {
          mark(index);
        });
        list.appendChild(option);
      });
      list.hidden = false;
    }

    function search() {
      var q = input.value.trim();
      if (!q) {
        closeList();
        return;
      }
      var url = input.getAttribute("data-persona-consulta");
      fetch(url + "?q=" + encodeURIComponent(q), { headers: { Accept: "application/json" } })
        .then(function (response) {
          return response.ok ? response.json() : { results: [] };
        })
        .then(function (data) {
          if (document.activeElement === input) paint(data.results || []);
        })
        .catch(function () {
          closeList();
        });
    }

    function mark(index) {
      var options = list.querySelectorAll("[role='option']");
      active = index;
      options.forEach(function (option, i) {
        option.setAttribute("aria-selected", i === index ? "true" : "false");
      });
      if (options[index]) options[index].scrollIntoView({ block: "nearest" });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(search, 180);
    });
    input.addEventListener("keydown", function (event) {
      var options = list.querySelectorAll("[role='option']");
      if (event.key === "ArrowDown" && options.length) {
        event.preventDefault();
        mark(Math.min(options.length - 1, active + 1));
      } else if (event.key === "ArrowUp" && options.length) {
        event.preventDefault();
        mark(Math.max(0, active - 1));
      } else if (event.key === "Enter" && !list.hidden && options.length) {
        event.preventDefault();
        if (active >= 0 && rows[active]) choose(rows[active]);
      } else if (event.key === "Escape") {
        closeList();
      }
    });
    input.addEventListener("blur", function () {
      setTimeout(closeList, 120);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
