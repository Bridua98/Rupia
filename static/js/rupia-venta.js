(function () {
  var root = document.querySelector("[data-pos]");
  if (!root) return;

  var claveMaquina = "rupia-maquina";
  var maquinaForm = document.querySelector("[data-pos-maquina]");
  var maquinaSelect = maquinaForm ? maquinaForm.querySelector("select[name='maquina']") : null;
  if (maquinaSelect) {
    var guardada = localStorage.getItem(claveMaquina) || "";
    var conocida = Array.prototype.some.call(maquinaSelect.options, function (opcion) {
      return opcion.value && opcion.value === guardada;
    });
    if (guardada && !conocida) {
      localStorage.removeItem(claveMaquina);
      guardada = "";
    }
    if (guardada && guardada !== maquinaSelect.value) {
      maquinaSelect.value = guardada;
      maquinaForm.submit();
      return;
    }
    if (maquinaSelect.value) localStorage.setItem(claveMaquina, maquinaSelect.value);
    maquinaSelect.addEventListener("change", function () {
      if (maquinaSelect.value) localStorage.setItem(claveMaquina, maquinaSelect.value);
      else localStorage.removeItem(claveMaquina);
      // La máquina define el punto y el timbrado: hay que fijarla en la sesión
      // antes de cobrar, si no la venta sale con la máquina anterior.
      maquinaForm.submit();
    });
  }

  var searchForm = root.querySelector("[data-pos-search]");
  var searchInput = searchForm ? searchForm.querySelector("input[name='q']") : null;
  var cabecera = document.getElementById("pos-cabecera");
  var clienteBox = root.querySelector("[data-pos-cliente]");
  var clienteCombo = clienteBox ? clienteBox.querySelector("[data-rupia='combo']") : null;
  var clienteQ = clienteCombo ? clienteCombo.querySelector("[data-combo-query]") : null;
  var clienteSuggest = clienteCombo ? clienteCombo.querySelector("[data-combo-results]") : null;
  var clienteId = clienteCombo ? clienteCombo.querySelector("[data-combo-value]") : null;
  var atajos = root.querySelector("[data-pos-atajos]");
  var descuentoPct = root.querySelector("[data-pos-descuento-pct]");
  var descuentoGs = root.querySelector("[data-pos-descuento]");
  var subtotal = Number(root.getAttribute("data-subtotal") || "0");
  var total = Number(root.getAttribute("data-total") || "0");
  var buscarUrl = root.getAttribute("data-buscar") || "/ventas/punto-de-venta/buscar/";
  var numeroUrl = root.getAttribute("data-numero-url") || "/ventas/punto-de-venta/numero/";
  var modalProductos = root.querySelector("[data-pos-modal-productos]");
  var modalLista = root.querySelector("[data-pos-modal-list]");
  var modalQ = root.querySelector("[data-pos-modal-q]");
  var modalCodigo = root.querySelector("[data-pos-modal-codigo]");
  var codigoForm = root.querySelector("[data-pos-codigo-form]");
  var codigoQ = root.querySelector("[data-pos-codigo-q]");
  var modalFactura = root.querySelector("[data-pos-modal-factura]");
  var recibido = root.querySelector("[data-pos-recibido]");
  var vueltoBox = root.querySelector("[data-pos-vuelto]");
  var numEst = root.querySelector("[data-pos-num-est]");
  var numPto = root.querySelector("[data-pos-num-pto]");
  var numSec = root.querySelector("[data-pos-num-sec]");
  var numMsg = root.querySelector("[data-pos-num-msg]");
  var timer = 0;
  var numeroTimer = 0;
  var productos = [];
  var productoActivo = -1;
  var ignorarFocoBuscar = false;
  var consultaProductos = "";
  var offsetProductos = 0;
  var hayMasProductos = false;
  var cargandoProductos = false;
  var TAMANIO_PAGINA = 20;

  function csrf() {
    var field = root.querySelector("[name='csrfmiddlewaretoken']");
    return field ? field.value : "";
  }

  function perteneceACabecera(el) {
    if (!cabecera || !el) return false;
    if (el.closest && el.closest("dialog")) return false;
    if (cabecera.contains(el)) return true;
    return !!(cabecera.id && el.getAttribute && el.getAttribute("form") === cabecera.id);
  }

  root.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") return;
    var el = event.target;
    if (el && el.closest && el.closest("[data-pos-guardar], [data-pos-cobrar]")) {
      event.preventDefault();
      return;
    }
    if (!perteneceACabecera(el)) return;
    var tag = (el.tagName || "").toLowerCase();
    if (tag === "textarea") return;
    event.preventDefault();
  });

  function enCampo(nodo) {
    if (!nodo) return false;
    var tag = (nodo.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select";
  }

  function dialogAbierto() {
    return (
      (modalProductos && modalProductos.open) ||
      (modalCodigo && modalCodigo.open) ||
      (modalFactura && modalFactura.open)
    );
  }

  function formatearGs(valor) {
    var entero = Math.max(0, Math.round(Number(valor) || 0));
    return String(entero).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function leerGs(texto) {
    return Number(String(texto || "0").replace(/\./g, "").replace(",", ".")) || 0;
  }

  function abrirDialogo(dialogo, foco) {
    if (!dialogo) return;
    if (typeof dialogo.showModal === "function") dialogo.showModal();
    else dialogo.setAttribute("open", "");
    if (foco) {
      foco.focus();
      if (typeof foco.select === "function") foco.select();
    }
  }

  function cerrarDialogo(dialogo) {
    if (!dialogo) return;
    if (typeof dialogo.close === "function") dialogo.close();
    else dialogo.removeAttribute("open");
  }

  function agregar(item, query) {
    var body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf());
    if (item && item.id) body.set("item", String(item.id));
    else body.set("q", query || (searchInput ? searchInput.value : ""));
    fetch(searchForm.action, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body: body,
    }).then(function () { window.location.reload(); });
  }

  function metaProducto(item) {
    return [item.marca, item.codigo, item.precio, item.unidad].filter(Boolean).join(" · ");
  }

  function pintarProducto(item, index) {
    var li = document.createElement("li");
    if (item.imagen) {
      var img = document.createElement("img");
      img.src = item.imagen;
      img.alt = "";
      li.appendChild(img);
    } else {
      var thumb = document.createElement("span");
      thumb.className = "pos-thumb";
      li.appendChild(thumb);
    }
    var texto = document.createElement("div");
    var titulo = document.createElement("strong");
    titulo.textContent = item.descripcion || item.label || "";
    texto.appendChild(titulo);
    var meta = document.createElement("small");
    meta.textContent = metaProducto(item);
    texto.appendChild(meta);
    li.appendChild(texto);
    li.tabIndex = 0;
    if (index === productoActivo) li.classList.add("is-on");
    li.addEventListener("click", function () { agregar(item); });
    modalLista.appendChild(li);
  }

  function pintarProductos(items, concatenar) {
    if (!modalLista) return;
    if (!concatenar) {
      productos = [];
      productoActivo = -1;
      modalLista.innerHTML = "";
    }
    if (!items.length && !productos.length) {
      var vacio = document.createElement("li");
      vacio.className = "is-empty";
      vacio.textContent = "No hay productos para esa búsqueda.";
      modalLista.appendChild(vacio);
      return;
    }
    var vacioPrevio = modalLista.querySelector("li.is-empty");
    if (vacioPrevio) vacioPrevio.remove();
    items.forEach(function (item) {
      productos.push(item);
      pintarProducto(item, productos.length - 1);
    });
    if (productoActivo < 0 && productos.length) {
      productoActivo = 0;
      marcarProducto();
    }
  }

  function marcarProducto() {
    if (!modalLista) return;
    Array.prototype.forEach.call(modalLista.children, function (li, index) {
      li.classList.toggle("is-on", index === productoActivo);
      if (index === productoActivo) li.scrollIntoView({ block: "nearest" });
    });
  }

  var pedidoProductos = 0;

  function buscarProductos(query, concatenar) {
    if (concatenar && (cargandoProductos || !hayMasProductos)) return;
    if (!concatenar) {
      offsetProductos = 0;
      hayMasProductos = false;
    }
    consultaProductos = query || "";
    cargandoProductos = true;
    var pedido = ++pedidoProductos;
    fetch(
      buscarUrl +
        "?limite=" + TAMANIO_PAGINA +
        "&offset=" + offsetProductos +
        "&q=" + encodeURIComponent(consultaProductos)
    )
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (pedido !== pedidoProductos) return;
        var resultados = data.resultados || [];
        hayMasProductos = !!data.hay_mas;
        offsetProductos = data.siguiente != null ? data.siguiente : offsetProductos + resultados.length;
        pintarProductos(resultados, concatenar);
      })
      .finally(function () {
        if (pedido === pedidoProductos) cargandoProductos = false;
      });
  }

  function alCerrarProductos() {
    ignorarFocoBuscar = true;
    if (searchInput) searchInput.blur();
    window.setTimeout(function () { ignorarFocoBuscar = false; }, 80);
  }

  function cerrarBusqueda() {
    if (modalProductos && modalProductos.open) cerrarDialogo(modalProductos);
    else alCerrarProductos();
  }

  function abrirBusqueda(query) {
    if (ignorarFocoBuscar) return;
    if (modalProductos && modalProductos.open) {
      if (modalQ && document.activeElement !== modalQ) modalQ.focus();
      return;
    }
    abrirDialogo(modalProductos, modalQ);
    if (modalQ) modalQ.value = query || "";
    buscarProductos(query || "", false);
  }

  if (modalProductos) {
    modalProductos.addEventListener("close", alCerrarProductos);
    modalProductos.addEventListener("cancel", function (event) {
      event.preventDefault();
      cerrarBusqueda();
    });
    modalProductos.addEventListener("click", function (event) {
      if (event.target === modalProductos) cerrarBusqueda();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("click", function () {
      abrirBusqueda(searchInput.value);
    });
    searchForm.addEventListener("submit", function (event) {
      event.preventDefault();
      abrirBusqueda(searchInput.value);
    });
  }

  if (modalLista) {
    modalLista.addEventListener("scroll", function () {
      if (!hayMasProductos || cargandoProductos) return;
      if (modalLista.scrollTop + modalLista.clientHeight >= modalLista.scrollHeight - 64) {
        buscarProductos(consultaProductos, true);
      }
    });
  }

  if (modalQ) {
    modalQ.addEventListener("input", function () {
      clearTimeout(timer);
      var q = modalQ.value.trim();
      timer = setTimeout(function () { buscarProductos(q, false); }, 160);
    });
    modalQ.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (!productos.length) return;
        productoActivo = (productoActivo + 1) % productos.length;
        marcarProducto();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!productos.length) return;
        productoActivo = (productoActivo - 1 + productos.length) % productos.length;
        marcarProducto();
      } else if (event.key === "Enter") {
        event.preventDefault();
        var q = modalQ.value.trim();
        if (productoActivo >= 0 && productos[productoActivo]) agregar(productos[productoActivo]);
        else if (q) agregar(null, q);
      }
    });
  }

  var codigoBtn = root.querySelector("[data-pos-codigo]");
  if (codigoBtn) {
    codigoBtn.addEventListener("click", function () {
      abrirDialogo(modalCodigo, codigoQ);
    });
  }
  if (codigoForm) {
    codigoForm.addEventListener("submit", function (event) {
      event.preventDefault();
      var q = codigoQ ? codigoQ.value.trim() : "";
      if (!q) return;
      agregar(null, q);
    });
  }

  document.querySelectorAll("select[name='caja'], select[name='cuenta_cobro']").forEach(function (el) {
    el.addEventListener("change", function () {
      if (cabecera) cabecera.submit();
    });
  });

  function esFactura() {
    var radio = cabecera && cabecera.querySelector("input[name='tipo_comprobante']:checked");
    return !!(radio && radio.value === "FACTURA");
  }

  function faltaClienteFactura() {
    return esFactura() && clienteId && !String(clienteId.value || "").trim();
  }

  function avisarClienteFactura() {
    if (!clienteQ) return;
    clienteQ.setCustomValidity("La factura pide un cliente.");
    clienteQ.reportValidity();
    clienteQ.focus();
  }

  function avisarEmision() {
    var banner =
      document.querySelector("[data-pos-emision-banner]") ||
      document.querySelector(".app-stage > .banner");
    if (banner) {
      banner.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function accionBloqueadaEnPos(cobrar) {
    if (faltaClienteFactura()) {
      avisarClienteFactura();
      return true;
    }
    if (cobrar) {
      var cobrarBtn = root.querySelector("[data-pos-cobrar]");
      if (cobrarBtn && cobrarBtn.disabled) {
        avisarEmision();
        return true;
      }
      return false;
    }
    var guardarBtn = root.querySelector("[data-pos-guardar]");
    if (guardarBtn && guardarBtn.disabled) {
      avisarEmision();
      return true;
    }
    return false;
  }

  function bloquearSiFaltaCliente(event) {
    if (!faltaClienteFactura()) {
      if (clienteQ) clienteQ.setCustomValidity("");
      return;
    }
    event.preventDefault();
    avisarClienteFactura();
  }

  function numeroFactura() {
    var est = (numEst && numEst.value ? numEst.value : "001").padStart(3, "0");
    var pto = (numPto && numPto.value ? numPto.value : "001").padStart(3, "0");
    var sec = (numSec && numSec.value ? numSec.value : "1").padStart(7, "0");
    return est + "-" + pto + "-" + sec;
  }

  function pintarProximo() {
    var visor = root.querySelector("[data-pos-proximo]");
    if (!visor) return;
    if (esFactura() && (numEst || numPto || numSec)) {
      visor.textContent = numeroFactura();
    }
  }

  function pintarNumeroMsg(nodo, ok, texto) {
    if (!nodo) return;
    nodo.hidden = !texto;
    nodo.textContent = texto || "";
    nodo.classList.toggle("is-ok", !!ok);
    nodo.classList.toggle("is-warn", !ok && !!texto);
  }

  function validarNumero(despues) {
    if (!esFactura() || !numSec) {
      if (despues) despues(true);
      return;
    }
    var url =
      numeroUrl +
      "?establecimiento=" + encodeURIComponent(numEst ? numEst.value : "") +
      "&punto=" + encodeURIComponent(numPto ? numPto.value : "") +
      "&secuencial=" + encodeURIComponent(numSec.value) +
      "&maquina=" + encodeURIComponent(root.getAttribute("data-maquina") || "");
    fetch(url)
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok && data.ok, data: data }; }); })
      .then(function (res) {
        var data = res.data || {};
        pintarNumeroMsg(numMsg, res.ok, res.ok ? "Número disponible." : (data.error || "Revisá la numeración."));
        if (despues) despues(res.ok, data);
      })
      .catch(function () {
        pintarNumeroMsg(numMsg, false, "No pude validar el número.");
        if (despues) despues(false);
      });
  }

  [numEst, numPto, numSec].forEach(function (campo) {
    if (!campo) return;
    campo.addEventListener("input", function () {
      campo.value = String(campo.value || "").replace(/\D/g, "");
      pintarProximo();
      clearTimeout(numeroTimer);
      numeroTimer = setTimeout(validarNumero, 220);
    });
  });
  pintarProximo();

  function pintarVuelto() {
    if (!vueltoBox || !recibido) return;
    var monto = leerGs(recibido.value);
    var resto = monto - total;
    var etiqueta = vueltoBox.querySelector("span");
    var valor = vueltoBox.querySelector("strong");
    vueltoBox.classList.toggle("is-faltante", resto < 0);
    if (resto < 0) {
      if (etiqueta) etiqueta.textContent = "Faltan";
      if (valor) valor.textContent = "Gs. " + formatearGs(Math.abs(resto));
    } else {
      if (etiqueta) etiqueta.textContent = "Vuelto";
      if (valor) valor.textContent = "Gs. " + formatearGs(resto);
    }
  }

  if (recibido) {
    recibido.addEventListener("input", pintarVuelto);
    recibido.addEventListener("keydown", function (event) {
      if (event.key !== "Enter") return;
      event.preventDefault();
      pintarVuelto();
      var cobrar = root.querySelector("[data-pos-cobrar]");
      if (restoSuficiente() && cobrar && !cobrar.disabled) cobrar.focus();
    });
    pintarVuelto();
  }

  function restoSuficiente() {
    if (!recibido) return true;
    return leerGs(recibido.value) >= total;
  }

  root.querySelectorAll("[data-pos-rapido]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!recibido) return;
      recibido.value = formatearGs(btn.getAttribute("data-pos-rapido"));
      pintarVuelto();
      recibido.focus();
    });
  });

  if (cabecera) {
    cabecera.querySelectorAll("input[name='medio'], input[name='tipo_comprobante'], input[name='consumidor_final']").forEach(function (el) {
      el.addEventListener("change", function () {
        if (el.name === "tipo_comprobante" && el.value === "FACTURA") {
          var consumidor = cabecera.querySelector("[data-pos-consumidor], input[name='consumidor_final']");
          if (consumidor) {
            consumidor.checked = false;
            if (consumidor.type === "hidden") consumidor.remove();
          }
        }
        cabecera.submit();
      });
    });
    cabecera.addEventListener("submit", function (event) {
      var accion = (event.submitter && event.submitter.getAttribute("name")) || "";
      var cobrar = event.submitter && event.submitter.hasAttribute("data-pos-cobrar");
      if ((accion === "guardar" || cobrar) && faltaClienteFactura()) {
        event.preventDefault();
        avisarClienteFactura();
      }
    });
  }

  function enviarCobro() {
    if (!cabecera) return;
    var cobrar = root.querySelector("[data-pos-cobrar]");
    if (!cobrar || cobrar.disabled) return;
    cabecera.setAttribute("action", cobrar.getAttribute("formaction") || "/ventas/punto-de-venta/confirmar/");
    cabecera.submit();
  }

  function pedirConfirmacionFactura() {
    var visor = root.querySelector("[data-pos-factura-confirm-num]");
    var msg = root.querySelector("[data-pos-factura-confirm-msg]");
    if (visor) visor.textContent = numeroFactura();
    abrirDialogo(modalFactura, root.querySelector("[data-pos-factura-ok]"));
    validarNumero(function (ok, data) {
      if (visor && data && data.numero) visor.textContent = data.numero;
      pintarNumeroMsg(msg, ok, ok ? "" : ((data && data.error) || "Revisá la numeración."));
      var okBtn = root.querySelector("[data-pos-factura-ok]");
      if (okBtn) okBtn.disabled = !ok;
    });
  }

  function intentarCobrar(event) {
    if (event) event.preventDefault();
    if (accionBloqueadaEnPos(true)) {
      return;
    }
    if (esFactura()) {
      pedirConfirmacionFactura();
      return;
    }
    enviarCobro();
  }

  var guardarBtn = root.querySelector("[data-pos-guardar]");
  var cobrarBtn = root.querySelector("[data-pos-cobrar]");
  if (guardarBtn) guardarBtn.addEventListener("click", bloquearSiFaltaCliente);
  if (cobrarBtn) {
    cobrarBtn.addEventListener("click", function (event) {
      if (faltaClienteFactura()) {
        bloquearSiFaltaCliente(event);
        return;
      }
      if (esFactura()) intentarCobrar(event);
    });
  }

  var facturaOk = root.querySelector("[data-pos-factura-ok]");
  var facturaCancelar = root.querySelector("[data-pos-factura-cancelar]");
  if (facturaOk) {
    facturaOk.addEventListener("click", function () {
      validarNumero(function (ok) {
        if (!ok) return;
        cerrarDialogo(modalFactura);
        enviarCobro();
      });
    });
  }
  if (facturaCancelar) {
    facturaCancelar.addEventListener("click", function () {
      cerrarDialogo(modalFactura);
    });
  }

  if (clienteQ && clienteBox) {
    clienteQ.addEventListener("input", function () {
      var check = clienteBox.querySelector("[data-pos-consumidor], input[name='consumidor_final']");
      if (check) {
        check.checked = false;
        if (check.type === "hidden") check.remove();
      }
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "F1") {
      event.preventDefault();
      if (atajos) atajos.open = !atajos.open;
      return;
    }
    if (event.key === "F2") {
      event.preventDefault();
      abrirDialogo(modalCodigo, codigoQ);
      return;
    }
    if (event.key === "F3") {
      event.preventDefault();
      abrirBusqueda(searchInput ? searchInput.value : "");
      return;
    }
    if (event.key === "F5") {
      event.preventDefault();
      if (accionBloqueadaEnPos(false)) {
        return;
      }
      var guardar = root.querySelector("[data-pos-guardar]");
      if (guardar) guardar.click();
      return;
    }
    if (event.key === "F8") {
      event.preventDefault();
      if (clienteQ) {
        clienteQ.focus();
        clienteQ.select();
      }
      return;
    }
    if (event.key === "F9") {
      event.preventDefault();
      if (descuentoPct) {
        descuentoPct.focus();
        descuentoPct.select();
      }
      return;
    }
    if (event.key === "F12") {
      event.preventDefault();
      intentarCobrar(event);
      return;
    }
    if (event.key === "Escape") {
      if (dialogAbierto()) return;
      if (atajos && atajos.open) {
        atajos.open = false;
        return;
      }
      if (clienteSuggest && !clienteSuggest.hidden) {
        clienteSuggest.hidden = true;
        return;
      }
      if (enCampo(event.target)) return;
      var cancelar = root.querySelector("[data-pos-cancelar]");
      if (cancelar) cancelar.click();
    }
  });

  if (descuentoPct && descuentoGs) {
    descuentoPct.addEventListener("input", function () {
      var pct = Number(String(descuentoPct.value || "0").replace(",", ".")) || 0;
      descuentoGs.value = formatearGs(subtotal * pct / 100);
    });
    descuentoGs.addEventListener("input", function () {
      if (!subtotal) {
        descuentoPct.value = "0";
        return;
      }
      var gs = leerGs(descuentoGs.value);
      var pct = Math.round((gs * 10000) / subtotal) / 100;
      descuentoPct.value = String(pct).replace(".", ",");
    });
  }
})();
