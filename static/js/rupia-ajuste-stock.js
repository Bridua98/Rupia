(function () {
  var root = document.querySelector("[data-ajuste-stock]");
  if (!root) return;

  var filas = root.querySelector("[data-ajuste-filas]");
  var vacia = root.querySelector("[data-ajuste-vacia]");
  var total = root.querySelector("[name='detalles-TOTAL_FORMS']");
  var agregar = root.querySelector("[data-ajuste-agregar]");
  var itemUrl = root.getAttribute("data-item-url") || "";
  if (!filas || !vacia || !total) return;

  function numero(texto) {
    var limpio = String(texto == null ? "" : texto).replace(/\s/g, "");
    if (!limpio) return 0;
    limpio = limpio.replace(/\./g, "").replace(",", ".");
    var valor = parseFloat(limpio);
    return isNaN(valor) ? 0 : valor;
  }

  function formatear(valor) {
    var numeroValor = Number(valor);
    if (!isFinite(numeroValor)) return "0";
    return numeroValor.toLocaleString("es-PY", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 3,
    });
  }

  function itemSeleccionado(fila) {
    var select = fila.querySelector("[data-ajuste-item]");
    return select ? select.value : "";
  }

  function unidadSeleccionada(fila) {
    var select = fila.querySelector("[data-ajuste-unidad]");
    return select ? select.value : "";
  }

  function cantidadNueva(fila) {
    var input = fila.querySelector("[data-cantidad]");
    return input ? numero(input.value) : 0;
  }

  function stocks(fila) {
    try {
      return JSON.parse(fila.getAttribute("data-stocks") || "{}");
    } catch (error) {
      return {};
    }
  }

  function aviso(fila, texto) {
    var nodo = fila.querySelector("[data-ajuste-aviso]");
    if (!nodo) return;
    nodo.textContent = texto || "";
    nodo.hidden = !texto;
  }

  function pintarStock(fila) {
    var unidad = unidadSeleccionada(fila);
    var valor = stocks(fila)[unidad];
    var anterior = valor == null ? 0 : Number(valor);
    var anteriorNodo = fila.querySelector("[data-ajuste-anterior]");
    var diferenciaNodo = fila.querySelector("[data-ajuste-diferencia]");
    if (anteriorNodo) anteriorNodo.textContent = formatear(anterior);
    if (diferenciaNodo) {
      diferenciaNodo.textContent = formatear(cantidadNueva(fila) - anterior);
    }
  }

  function opcionesUnidad(fila, unidades, seleccionada) {
    var select = fila.querySelector("[data-ajuste-unidad]");
    if (!select) return;
    select.innerHTML = "";
    if (!unidades.length) {
      var vacio = document.createElement("option");
      vacio.value = "";
      vacio.textContent = "Elegí un ítem primero";
      select.appendChild(vacio);
      select.disabled = true;
      return;
    }
    select.disabled = false;
    unidades.forEach(function (unidad) {
      var option = document.createElement("option");
      option.value = String(unidad.id);
      option.textContent = unidad.descripcion
        ? unidad.descripcion + " (" + unidad.simbolo + ")"
        : unidad.simbolo;
      if (String(unidad.id) === String(seleccionada)) option.selected = true;
      select.appendChild(option);
    });
    if (!select.value && unidades.length) select.value = String(unidades[0].id);
  }

  function cargarItem(fila) {
    var item = itemSeleccionado(fila);
    if (!item) {
      fila.setAttribute("data-stocks", "{}");
      opcionesUnidad(fila, [], "");
      aviso(fila, "");
      pintarStock(fila);
      return;
    }
    var selectUnidad = fila.querySelector("[data-ajuste-unidad]");
    var seleccionada = selectUnidad ? selectUnidad.value : "";
    var pedido = (fila._pedido || 0) + 1;
    fila._pedido = pedido;
    var url = itemUrl.replace(/0\/$/, String(item) + "/");
    fila.classList.add("is-cargando");
    fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (res) {
        if (!res.ok) throw new Error("No se pudo cargar el stock.");
        return res.json();
      })
      .then(function (data) {
        if (pedido !== fila._pedido) return;
        var unidades = data.unidades || [];
        var porUnidad = {};
        unidades.forEach(function (unidad) {
          porUnidad[String(unidad.id)] = unidad.stock;
        });
        fila.setAttribute("data-stocks", JSON.stringify(porUnidad));
        opcionesUnidad(fila, unidades, seleccionada);
        aviso(fila, data.aviso || "");
        pintarStock(fila);
      })
      .catch(function () {
        if (pedido !== fila._pedido) return;
        fila.setAttribute("data-stocks", "{}");
        opcionesUnidad(fila, [], "");
        aviso(fila, "No se pudo cargar el stock del ítem.");
        pintarStock(fila);
      })
      .finally(function () {
        if (pedido === fila._pedido) fila.classList.remove("is-cargando");
      });
  }

  function filaDesdePlantilla(html) {
    var tbody = document.createElement("tbody");
    tbody.innerHTML = html.trim();
    return tbody.querySelector("[data-ajuste-fila]");
  }

  function iniciarFila(fila) {
    var combo = fila.querySelector("[data-rupia='combo']");
    if (combo && window.rupiaInitCombo) window.rupiaInitCombo(combo);
    var selectItem = fila.querySelector("[data-ajuste-item]");
    var selectUnidad = fila.querySelector("[data-ajuste-unidad]");
    var input = fila.querySelector("[data-cantidad]");

    if (selectItem && !selectItem.dataset.ajusteReady) {
      selectItem.dataset.ajusteReady = "1";
      selectItem.addEventListener("change", function () {
        cargarItem(fila);
      });
    }
    if (selectUnidad && !selectUnidad.dataset.ajusteReady) {
      selectUnidad.dataset.ajusteReady = "1";
      selectUnidad.addEventListener("change", function () {
        pintarStock(fila);
      });
    }
    if (input) {
      if (window.rupiaInitCantidad) window.rupiaInitCantidad(input);
      if (!input.dataset.ajusteReady) {
        input.dataset.ajusteReady = "1";
        input.addEventListener("input", function () {
          pintarStock(fila);
        });
        input.addEventListener("blur", function () {
          pintarStock(fila);
        });
      }
    }

    if (itemSeleccionado(fila)) {
      cargarItem(fila);
    } else {
      opcionesUnidad(fila, [], "");
      aviso(fila, "");
      pintarStock(fila);
    }
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
    var boton = event.target.closest("[data-ajuste-quitar]");
    if (!boton || !root.contains(boton)) return;
    var fila = boton.closest("[data-ajuste-fila]");
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
      iniciarFila(fila);
    });
  }

  Array.prototype.forEach.call(filas.querySelectorAll("[data-ajuste-fila]"), iniciarFila);
})();
