(function () {
  function init(root) {
    var tipo = root.querySelector("select[name='tipo']");
    if (!tipo) return;
    var valor = root.querySelector("[data-selector-value][name='unidad_negocio']");
    if (!valor) return;
    var selector = valor.closest("[data-rupia='selector']");
    if (!selector) return;
    var query = selector.querySelector("[data-selector-query]");

    function sync(limpiar) {
      var producto = tipo.value === "PRODUCTO";
      selector.hidden = !producto;
      if (!producto && limpiar) {
        valor.value = "";
        if (query) query.value = "";
        selector.classList.remove("is-filled");
      }
    }

    tipo.addEventListener("change", function () {
      sync(true);
    });
    sync(false);
  }

  document.querySelectorAll("[data-rupia='ficha']").forEach(init);
})();
