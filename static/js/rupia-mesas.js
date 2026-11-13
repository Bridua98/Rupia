(function () {
  "use strict";

  // Tablero: se refresca solo, salvo que alguien esté escribiendo o tenga
  // un formulario abierto.
  var tablero = document.querySelector("[data-mesas-tablero]");
  if (tablero) {
    var url = tablero.getAttribute("data-url");
    var ocupado = function () {
      if (document.hidden) return true;
      if (document.querySelector("details[open]")) return true;
      var activo = document.activeElement;
      return !!(activo && /^(INPUT|TEXTAREA|SELECT)$/.test(activo.tagName));
    };
    setInterval(function () {
      if (ocupado()) return;
      fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
        .then(function (respuesta) {
          if (!respuesta.ok) throw new Error(respuesta.status);
          return respuesta.text();
        })
        .then(function (html) {
          if (!ocupado()) tablero.innerHTML = html;
        })
        .catch(function () {
          // Sin conexión: se reintenta en la próxima vuelta.
        });
    }, 15000);
  }

  // Búsqueda de productos: busca al dejar de escribir.
  var buscar = document.querySelector("[data-mesas-buscar]");
  if (buscar) {
    var espera = null;
    var ultimo = buscar.value;
    buscar.addEventListener("input", function () {
      clearTimeout(espera);
      espera = setTimeout(function () {
        var valor = buscar.value.trim();
        if (valor === ultimo.trim()) return;
        if (valor.length === 1) return;
        ultimo = buscar.value;
        if (buscar.form.requestSubmit) {
          buscar.form.requestSubmit();
        } else {
          buscar.form.submit();
        }
      }, 450);
    });
    if (buscar.hasAttribute("autofocus")) {
      var largo = buscar.value.length;
      buscar.focus();
      buscar.setSelectionRange(largo, largo);
    }
  }

  // Confirmaciones de acciones que no se deshacen.
  document.querySelectorAll("form[data-mesas-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (evento) {
      if (!window.confirm(form.getAttribute("data-mesas-confirmar"))) {
        evento.preventDefault();
      }
    });
  });
})();
