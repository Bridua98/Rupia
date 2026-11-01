(function () {
  var form = document.querySelector("[data-precios-form]");
  if (!form) return;

  var pagina = form.querySelector("[data-precios-todos-pagina]");
  var todos = form.querySelector("[name='todos_filtrados']");
  var porcentaje = form.querySelector("[name='porcentaje']");
  var cuenta = form.querySelector("[data-precios-cuenta]");
  var efecto = form.querySelector("[data-precios-efecto]");
  var aplicar = form.querySelector("[data-precios-aplicar]");
  var confirmBox = form.querySelector("[data-precios-confirm]");
  var confirmText = form.querySelector("[data-precios-confirm-text]");
  var confirmCancel = form.querySelector("[data-precios-confirm-cancel]");
  var acciones = form.querySelector("[data-precios-acciones]");
  var total = Number(form.getAttribute("data-total") || 0);

  function casillas() {
    return Array.prototype.slice.call(form.querySelectorAll("input[name='item']"));
  }

  function filas() {
    return Array.prototype.slice.call(form.querySelectorAll("tbody tr[data-segun-costo]"));
  }

  function leerPorcentaje() {
    if (!porcentaje) return null;
    var raw = String(porcentaje.value || "").trim().replace("%", "").replace(",", ".");
    if (raw === "" || raw === "-" || raw === ".") return null;
    var n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  function formatear(valor) {
    var entero = Math.trunc(valor);
    var signo = entero < 0 ? "-" : "";
    return signo + String(Math.abs(entero)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function redondear(valor) {
    return Math.round(valor);
  }

  function baseFila(row) {
    if (row.getAttribute("data-segun-costo") === "1") {
      var costo = row.getAttribute("data-costo");
      return costo === "" || costo == null ? null : Number(costo);
    }
    var precio = row.getAttribute("data-precio");
    return precio === "" || precio == null ? null : Number(precio);
  }

  function hayObjetivo() {
    if (todos && todos.checked) return total > 0;
    return casillas().some(function (box) { return box.checked; });
  }

  function syncPagina() {
    if (!pagina) return;
    var boxes = casillas();
    if (!boxes.length) {
      pagina.checked = false;
      pagina.indeterminate = false;
      return;
    }
    var marcadas = boxes.filter(function (box) { return box.checked; }).length;
    pagina.checked = marcadas === boxes.length;
    pagina.indeterminate = marcadas > 0 && marcadas < boxes.length;
  }

  function textoCuenta() {
    if (todos && todos.checked) {
      if (total === 1) return "1 ítem filtrado";
      return "Todos los filtrados · " + total + " ítems";
    }
    var n = casillas().filter(function (box) { return box.checked; }).length;
    if (!n) return "Ningún ítem elegido";
    if (n === 1) return "1 ítem elegido";
    return n + " ítems elegidos";
  }

  function pintarCelda(celda, html) {
    if (celda) celda.innerHTML = html;
  }

  function actualizarPreview() {
    var pct = leerPorcentaje();
    var todas = todos && todos.checked;
    var seleccion = {};
    casillas().forEach(function (box) {
      seleccion[box.value] = box.checked;
    });
    var visibles = 0;
    var cambian = 0;
    var omitidos = 0;

    filas().forEach(function (row) {
      var input = row.querySelector("input[name='item']");
      var celda = row.querySelector("[data-precios-nuevo]");
      var entra = todas || (input && input.checked) || (!todas && !casillas().some(function (box) { return box.checked; }));
      if (!entra || pct == null) {
        if (pct == null) pintarCelda(celda, '<span class="precios-nuevo is-vacio">—</span>');
        return;
      }
      visibles += 1;
      var base = baseFila(row);
      if (base == null) {
        omitidos += 1;
        var motivo = row.getAttribute("data-segun-costo") === "1" ? "Sin último costo" : "Sin precio";
        pintarCelda(celda, '<span class="precios-nuevo is-omitido">' + motivo + "</span>");
        return;
      }
      var nuevo = redondear(base * (1 + pct / 100));
      var actual = row.getAttribute("data-precio");
      var actualN = actual === "" || actual == null ? null : Number(actual);
      if (actualN != null && nuevo === Math.round(actualN)) {
        omitidos += 1;
        pintarCelda(
          celda,
          '<span class="precios-nuevo is-igual">' + formatear(nuevo) + '</span> <span class="precios-omitido">Sin cambio</span>'
        );
        return;
      }
      cambian += 1;
      var clase = actualN != null && nuevo < actualN ? "is-down" : "is-up";
      pintarCelda(celda, '<span class="precios-nuevo ' + clase + '">' + formatear(nuevo) + "</span>");
    });

    if (cuenta) cuenta.textContent = textoCuenta();
    if (efecto) {
      efecto.classList.remove("is-up", "is-down");
      if (pct == null) {
        efecto.textContent = "Escribí un porcentaje para ver el efecto.";
        return;
      }
      var signo = pct > 0 ? "↑" : pct < 0 ? "↓" : "=";
      var clase = pct > 0 ? "is-up" : pct < 0 ? "is-down" : "";
      if (clase) efecto.classList.add(clase);
      var partes = [signo + " " + String(pct).replace(".", ",") + "%"];
      if (visibles) {
        if (cambian === 1) partes.push("1 va a cambiar");
        else partes.push(cambian + " van a cambiar");
        if (omitidos === 1) partes.push("1 se omite");
        else if (omitidos) partes.push(omitidos + " se omiten");
      }
      efecto.textContent = partes.join(" · ");
    }
  }

  function mostrarConfirmacion(mostrar) {
    if (!confirmBox) return;
    confirmBox.hidden = !mostrar;
    if (acciones) acciones.hidden = mostrar;
  }

  if (pagina) {
    pagina.addEventListener("change", function () {
      casillas().forEach(function (box) {
        box.checked = pagina.checked;
      });
      pagina.indeterminate = false;
      if (todos) todos.checked = false;
      mostrarConfirmacion(false);
      actualizarPreview();
    });
  }

  form.addEventListener("change", function (event) {
    if (!event.target) return;
    if (event.target.name === "item") {
      if (todos) todos.checked = false;
      syncPagina();
      mostrarConfirmacion(false);
      actualizarPreview();
    }
  });

  if (todos) {
    todos.addEventListener("change", function () {
      if (todos.checked) {
        casillas().forEach(function (box) {
          box.checked = true;
        });
        if (pagina) {
          pagina.checked = true;
          pagina.indeterminate = false;
        }
      } else {
        syncPagina();
      }
      mostrarConfirmacion(false);
      actualizarPreview();
    });
  }

  if (porcentaje) {
    porcentaje.addEventListener("input", actualizarPreview);
  }

  form.querySelectorAll("[data-precios-paso]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      var paso = Number(boton.getAttribute("data-precios-paso") || 0);
      var actual = leerPorcentaje();
      if (actual == null) actual = 0;
      var siguiente = Math.round((actual + paso) * 100) / 100;
      if (siguiente <= -100) siguiente = -99;
      porcentaje.value = String(siguiente).replace(".", ",");
      mostrarConfirmacion(false);
      actualizarPreview();
      porcentaje.focus();
    });
  });

  if (aplicar && confirmBox) {
    aplicar.addEventListener("click", function (event) {
      if (!confirmBox.hidden) return;
      event.preventDefault();
      if (!hayObjetivo()) {
        if (cuenta) cuenta.textContent = "Elegí al menos un ítem.";
        if (efecto) {
          efecto.classList.remove("is-up", "is-down");
          efecto.textContent = "Marcá filas o usá todos los filtrados.";
        }
        return;
      }
      var pct = leerPorcentaje();
      var pctTexto = pct == null ? "este porcentaje" : String(pct).replace(".", ",") + "%";
      var destino;
      if (todos && todos.checked) {
        destino = total === 1 ? "el ítem filtrado" : "los " + total + " ítems filtrados";
      } else {
        var n = casillas().filter(function (box) { return box.checked; }).length;
        destino = n === 1 ? "1 ítem" : "los " + n + " ítems elegidos";
      }
      if (confirmText) {
        confirmText.textContent = "¿Aplicar " + pctTexto + " a " + destino + "? El cambio queda en el historial.";
      }
      mostrarConfirmacion(true);
    });
  }

  if (confirmCancel) {
    confirmCancel.addEventListener("click", function () {
      mostrarConfirmacion(false);
    });
  }

  syncPagina();
  actualizarPreview();
})();
