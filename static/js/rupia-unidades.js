(function () {
  var root = document.querySelector("[data-unidades-rel]");
  if (!root) return;

  var filas = root.querySelector("[data-unidades-filas]");
  var vacia = root.querySelector("[data-unidades-vacia]");
  var total = root.querySelector("[name='unidades-TOTAL_FORMS']");
  var agregar = root.querySelector("[data-unidades-agregar]");
  if (!filas || !vacia || !total) return;

  function iniciarSelectores(fila) {
    if (window.rupiaInitSelector) {
      fila.querySelectorAll("[data-rupia='selector']").forEach(window.rupiaInitSelector);
    }
    if (window.rupiaInitCantidad) {
      fila.querySelectorAll("[data-cantidad]").forEach(window.rupiaInitCantidad);
    }
  }

  function filaDesdePlantilla(html) {
    var tbody = document.createElement("tbody");
    tbody.innerHTML = html.trim();
    return tbody.querySelector("[data-unidades-fila]");
  }

  function quitar(fila) {
    var borrar = fila.querySelector("input[name$='-DELETE']");
    if (borrar) {
      borrar.checked = true;
      fila.hidden = true;
      return;
    }
    fila.remove();
  }

  root.addEventListener("click", function (event) {
    var boton = event.target.closest("[data-unidades-quitar]");
    if (!boton || !root.contains(boton)) return;
    var fila = boton.closest("[data-unidades-fila]");
    if (fila) quitar(fila);
  });

  if (agregar) {
    agregar.addEventListener("click", function () {
      var indice = Number(total.value || 0);
      var html = vacia.innerHTML.replace(/__prefix__/g, String(indice));
      var fila = filaDesdePlantilla(html);
      if (!fila) return;
      filas.appendChild(fila);
      total.value = String(indice + 1);
      iniciarSelectores(fila);
    });
  }
})();
