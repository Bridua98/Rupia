(function () {
  function boot() {
    document.querySelectorAll("[data-rupia='selector']").forEach(init);
  }

  function init(root) {
    if (root.getAttribute("data-selector-ready")) return;
    root.setAttribute("data-selector-ready", "1");
    var combo = root.querySelector("[data-rupia='combo']");
    var alta = root.querySelector("[data-selector-alta]");
    var formError = root.querySelector("[data-selector-form-error]");
    var nueva = root.querySelector("[data-selector-nueva]");
    var guardar = root.querySelector("[data-selector-guardar]");
    var cancelar = root.querySelector("[data-selector-cancelar]");
    if (!alta || !nueva || !guardar || !cancelar) return;

    if (combo && window.rupiaInitCombo) window.rupiaInitCombo(combo);

    alta.querySelectorAll("input, select, textarea").forEach(function (input) {
      input.disabled = true;
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
      var query = combo && combo.querySelector("[data-combo-query]");
      if (query) query.focus();
    }

    nueva.addEventListener("click", openAlta);
    cancelar.addEventListener("click", closeAlta);
    guardar.addEventListener("click", function () {
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
            if (combo && window.rupiaComboAccept) window.rupiaComboAccept(combo, result.data);
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

  window.rupiaInitSelector = init;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
