(function () {
  function init(root) {
    var tipo = root.querySelector("select[name='tipo']");
    if (!tipo) return;
    var valor = root.querySelector("[data-selector-value][name='unidad_negocio']");
    var selector = valor ? valor.closest("[data-rupia='selector']") : null;
    var query = selector ? selector.querySelector("[data-selector-query]") : null;
    var formulario = root.querySelector(".item-form");
    var tabUnidades = root.querySelector('[data-tab="unidades"]');

    function producto() {
      return tipo.value === "PRODUCTO";
    }

    function activarDatos() {
      var tabDatos = root.querySelector('[data-tab="datos"]');
      if (!tabDatos) return;
      tabDatos.setAttribute("aria-selected", "true");
      tabDatos.tabIndex = 0;
      if (tabUnidades) {
        tabUnidades.setAttribute("aria-selected", "false");
        tabUnidades.tabIndex = -1;
      }
      var panelDatos = root.querySelector('[data-tab-panel="datos"]');
      var panelUnidades = root.querySelector('[data-tab-panel="unidades"]');
      if (panelDatos) panelDatos.hidden = false;
      if (panelUnidades) panelUnidades.hidden = true;
    }

    function sync(limpiar) {
      var esProducto = producto();
      root.querySelectorAll("[data-item-solo-producto]").forEach(function (nodo) {
        if (nodo.getAttribute("data-tab-panel") === "unidades") {
          if (!esProducto) nodo.hidden = true;
          return;
        }
        nodo.hidden = !esProducto;
      });
      if (tabUnidades) tabUnidades.hidden = !esProducto;
      if (formulario) formulario.classList.toggle("is-gasto", !esProducto);
      if (selector) {
        selector.hidden = !esProducto;
        if (!esProducto && limpiar) {
          valor.value = "";
          if (query) query.value = "";
          selector.classList.remove("is-filled");
        }
      }
      if (!esProducto) activarDatos();
    }

    tipo.addEventListener("change", function () {
      sync(true);
    });
    sync(false);
  }

  document.querySelectorAll("[data-rupia='ficha']").forEach(init);
})();
