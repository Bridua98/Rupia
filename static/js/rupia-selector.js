(function () {
  function boot() {
    document.querySelectorAll("[data-rupia='selector']").forEach(init);
  }

  function init(root) {
    var query = root.querySelector("[data-selector-query]");
    var value = root.querySelector("[data-selector-value]");
    var list = root.querySelector("[data-selector-results]");
    var alta = root.querySelector("[data-selector-alta]");
    var formError = root.querySelector("[data-selector-form-error]");
    var timer = null;
    var active = -1;

    alta.querySelectorAll("input, select, textarea").forEach(function (input) {
      input.disabled = true;
    });

    function closeList() {
      list.hidden = true;
      query.setAttribute("aria-expanded", "false");
      active = -1;
    }

    function choose(row) {
      value.value = row.id;
      query.value = row.label;
      root.setAttribute("data-selected-label", row.label);
      closeList();
    }

    function paint(results) {
      list.innerHTML = "";
      active = -1;
      if (!results.length) {
        closeList();
        return;
      }
      results.forEach(function (row) {
        var option = document.createElement("li");
        option.setAttribute("role", "option");
        option.dataset.id = row.id;
        option.textContent = row.label;
        option.addEventListener("mousedown", function (event) {
          event.preventDefault();
          choose(row);
        });
        list.appendChild(option);
      });
      list.hidden = false;
      query.setAttribute("aria-expanded", "true");
    }

    function search() {
      var url = root.getAttribute("data-search-url");
      var q = query.value.trim();
      fetch(url + "?q=" + encodeURIComponent(q), { headers: { Accept: "application/json" } })
        .then(function (response) {
          return response.ok ? response.json() : { results: [] };
        })
        .then(function (data) {
          if (document.activeElement === query) paint(data.results || []);
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

    query.addEventListener("focus", search);
    query.addEventListener("input", function () {
      if (query.value !== root.getAttribute("data-selected-label")) {
        value.value = "";
        root.setAttribute("data-selected-label", "");
      }
      clearTimeout(timer);
      timer = setTimeout(search, 180);
    });
    query.addEventListener("keydown", function (event) {
      var options = list.querySelectorAll("[role='option']");
      if (event.key === "ArrowDown" && options.length) {
        event.preventDefault();
        mark(Math.min(options.length - 1, active + 1));
      } else if (event.key === "ArrowUp" && options.length) {
        event.preventDefault();
        mark(Math.max(0, active - 1));
      } else if (event.key === "Enter") {
        event.preventDefault();
        if (active >= 0 && options[active]) {
          choose({
            id: options[active].dataset.id || "",
            label: options[active].textContent,
          });
        }
      } else if (event.key === "Escape") {
        closeList();
      }
    });
    query.addEventListener("blur", function () {
      setTimeout(closeList, 120);
    });

    function clearAltaErrors() {
      formError.hidden = true;
      formError.textContent = "";
      alta.querySelectorAll("[data-error-for]").forEach(function (node) {
        node.hidden = true;
        node.textContent = "";
      });
    }

    function openAlta() {
      closeList();
      clearAltaErrors();
      alta.querySelectorAll("input, select, textarea").forEach(function (input) {
        input.disabled = false;
      });
      root.classList.add("is-alta");
      alta.hidden = false;
      var first = alta.querySelector("input, select, textarea");
      if (first) first.focus();
    }

    function closeAlta() {
      alta.querySelectorAll("input, select, textarea").forEach(function (input) {
        input.disabled = true;
        if (input.type !== "hidden") input.value = "";
      });
      clearAltaErrors();
      alta.hidden = true;
      root.classList.remove("is-alta");
      query.focus();
    }

    root.querySelector("[data-selector-nueva]").addEventListener("click", openAlta);
    root.querySelector("[data-selector-cancelar]").addEventListener("click", closeAlta);
    root.querySelector("[data-selector-guardar]").addEventListener("click", function () {
      clearAltaErrors();
      var token = document.querySelector("[name=csrfmiddlewaretoken]");
      var body = new FormData();
      alta.querySelectorAll("input, select, textarea").forEach(function (input) {
        if (!input.name || input.disabled) return;
        body.append(input.name, input.value);
      });
      fetch(root.getAttribute("data-create-url"), {
        method: "POST",
        body: body,
        headers: {
          Accept: "application/json",
          "X-CSRFToken": token ? token.value : "",
        },
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (result.ok) {
            closeAlta();
            choose(result.data);
            return;
          }
          var errors = (result.data && result.data.errors) || {};
          Object.keys(errors).forEach(function (key) {
            var message = errors[key].join(" ");
            if (key === "__all__") {
              formError.hidden = false;
              formError.textContent = message;
              return;
            }
            var node = alta.querySelector('[data-error-for="' + key + '"]');
            if (!node) return;
            node.hidden = false;
            node.textContent = message;
          });
        })
        .catch(function () {
          formError.hidden = false;
          formError.textContent = "No se pudo guardar.";
        });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
