(function () {
  var root = document.querySelector("[data-compra]");
  if (!root) return;

  var searchForm = root.querySelector("[data-compra-search]");
  var searchInput = searchForm ? searchForm.querySelector("input[name='q']") : null;
  var cabecera = document.getElementById("compra-cabecera");
  var proveedorBox = root.querySelector("[data-compra-proveedor]");
  var proveedorQ = root.querySelector("[data-compra-proveedor-q]");
  var proveedorSuggest = root.querySelector("[data-compra-proveedor-suggest]");
  var proveedorId = cabecera ? cabecera.querySelector("input[name='proveedor']") : null;
  var buscarUrl = root.getAttribute("data-buscar") || "/compras/nueva/buscar/";
  var numeroUrl = root.getAttribute("data-numero-url") || "/compras/nueva/numero/";
  var proveedoresUrl = root.getAttribute("data-proveedores") || "/compras/nueva/proveedores/";
  var modalItems = root.querySelector("[data-compra-modal-items]");
  var modalLista = root.querySelector("[data-compra-modal-list]");
  var modalQ = root.querySelector("[data-compra-modal-q]");
  var modalCodigo = root.querySelector("[data-compra-modal-codigo]");
  var codigoForm = root.querySelector("[data-compra-codigo-form]");
  var codigoQ = root.querySelector("[data-compra-codigo-q]");
  var modalPrecios = root.querySelector("[data-compra-modal-precios]");
  var numEst = root.querySelector("[data-compra-num-est]");
  var numPto = root.querySelector("[data-compra-num-pto]");
  var numSec = root.querySelector("[data-compra-num-sec]");
  var numMsg = root.querySelector("[data-compra-num-msg]");
  var timbrado = root.querySelector("[data-compra-timbrado]");
  var timer = 0;
  var numeroTimer = 0;
  var proveedorTimer = 0;
  var proveedorItems = [];
  var proveedorActivo = -1;
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

  function esFactura() {
    var radio = cabecera && cabecera.querySelector("input[name='tipo']:checked");
    return !!(radio && radio.value && radio.value.indexOf("FAC_") === 0);
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

  function metaItem(item) {
    return [item.tipo, item.marca, item.codigo, item.precio, item.unidad].filter(Boolean).join(" · ");
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
    meta.textContent = metaItem(item);
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
      vacio.textContent = "No hay ítems para esa búsqueda.";
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
    if (modalItems && modalItems.open) cerrarDialogo(modalItems);
    else alCerrarProductos();
  }

  function abrirBusqueda(query) {
    if (ignorarFocoBuscar) return;
    if (modalItems && modalItems.open) {
      if (modalQ && document.activeElement !== modalQ) modalQ.focus();
      return;
    }
    abrirDialogo(modalItems, modalQ);
    if (modalQ) modalQ.value = query || "";
    buscarProductos(query || "", false);
  }

  if (modalItems) {
    modalItems.addEventListener("close", alCerrarProductos);
    modalItems.addEventListener("cancel", function (event) {
      event.preventDefault();
      cerrarBusqueda();
    });
    modalItems.addEventListener("click", function (event) {
      if (event.target === modalItems) cerrarBusqueda();
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

  var codigoBtn = root.querySelector("[data-compra-codigo]");
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

  document.querySelectorAll("[data-compra-cuenta], input[name='tipo']").forEach(function (el) {
    el.addEventListener("change", function () {
      if (cabecera) cabecera.submit();
    });
  });

  function numeroFactura() {
    var est = (numEst && numEst.value ? numEst.value : "001").padStart(3, "0");
    var pto = (numPto && numPto.value ? numPto.value : "001").padStart(3, "0");
    var sec = (numSec && numSec.value ? numSec.value : "1").padStart(7, "0");
    return est + "-" + pto + "-" + sec;
  }

  function pintarProximo() {
    var visor = root.querySelector("[data-compra-proximo]");
    if (!visor || !esFactura()) return;
    visor.textContent = numeroFactura();
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
      "?timbrado=" + encodeURIComponent(timbrado ? timbrado.value : "") +
      "&establecimiento=" + encodeURIComponent(numEst ? numEst.value : "") +
      "&punto=" + encodeURIComponent(numPto ? numPto.value : "") +
      "&secuencial=" + encodeURIComponent(numSec.value);
    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        pintarNumeroMsg(numMsg, !!data.ok, data.error || (data.ok ? data.numero : ""));
        if (despues) despues(!!data.ok);
      })
      .catch(function () {
        if (despues) despues(false);
      });
  }

  [numEst, numPto, numSec, timbrado].forEach(function (el) {
    if (!el) return;
    el.addEventListener("input", function () {
      pintarProximo();
      clearTimeout(numeroTimer);
      numeroTimer = setTimeout(function () { validarNumero(); }, 250);
    });
  });
  pintarProximo();

  function pintarProveedores(items) {
    if (!proveedorSuggest) return;
    proveedorItems = items || [];
    proveedorActivo = proveedorItems.length ? 0 : -1;
    proveedorSuggest.innerHTML = "";
    if (!proveedorItems.length) {
      proveedorSuggest.hidden = true;
      return;
    }
    proveedorItems.forEach(function (item, index) {
      var li = document.createElement("li");
      li.textContent = item.label || "";
      if (index === proveedorActivo) li.classList.add("is-on");
      li.addEventListener("click", function () { elegirProveedor(item); });
      proveedorSuggest.appendChild(li);
    });
    proveedorSuggest.hidden = false;
  }

  function marcarProveedor() {
    if (!proveedorSuggest) return;
    Array.prototype.forEach.call(proveedorSuggest.children, function (li, index) {
      li.classList.toggle("is-on", index === proveedorActivo);
    });
  }

  function elegirProveedor(item) {
    if (!item) return;
    if (item.id && cabecera) {
      var hidden = cabecera.querySelector("input[name='proveedor']");
      if (!hidden) {
        hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = "proveedor";
        cabecera.appendChild(hidden);
      }
      hidden.value = String(item.id);
      cabecera.submit();
      return;
    }
    var body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf());
    if (item.ruc) body.set("ruc", item.ruc);
    body.set("q", item.documento || item.label || "");
    fetch(proveedoresUrl, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body: body,
    }).then(function () { window.location.reload(); });
  }

  if (proveedorQ) {
    proveedorQ.addEventListener("input", function () {
      clearTimeout(proveedorTimer);
      var q = proveedorQ.value.trim();
      proveedorTimer = setTimeout(function () {
        fetch(proveedoresUrl + "?q=" + encodeURIComponent(q))
          .then(function (res) { return res.json(); })
          .then(function (data) { pintarProveedores(data.resultados || []); });
      }, 160);
    });
    proveedorQ.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (!proveedorItems.length) return;
        proveedorActivo = (proveedorActivo + 1) % proveedorItems.length;
        marcarProveedor();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!proveedorItems.length) return;
        proveedorActivo = (proveedorActivo - 1 + proveedorItems.length) % proveedorItems.length;
        marcarProveedor();
      } else if (event.key === "Enter" && proveedorActivo >= 0) {
        event.preventDefault();
        elegirProveedor(proveedorItems[proveedorActivo]);
      } else if (event.key === "Escape") {
        proveedorSuggest.hidden = true;
      }
    });
  }

  function asegurarAfectar(valor) {
    var campo = cabecera && cabecera.querySelector("input[name='afectar_precios']");
    if (!campo && cabecera) {
      campo = document.createElement("input");
      campo.type = "hidden";
      campo.name = "afectar_precios";
      cabecera.appendChild(campo);
    }
    if (campo) campo.value = valor;
  }

  function enviarConfirmacion() {
    if (!cabecera) return;
    cabecera.setAttribute("action", cabecera.getAttribute("data-confirmar") || "/compras/nueva/confirmar/");
    var boton = root.querySelector("[data-compra-confirmar]");
    if (boton && boton.getAttribute("formaction")) {
      cabecera.setAttribute("action", boton.getAttribute("formaction"));
    }
    cabecera.submit();
  }

  var confirmarBtn = root.querySelector("[data-compra-confirmar]");
  if (confirmarBtn) {
    confirmarBtn.addEventListener("click", function (event) {
      if (!root.getAttribute("data-compra-precios")) return;
      event.preventDefault();
      abrirDialogo(modalPrecios);
    });
  }

  var preciosSi = root.querySelector("[data-compra-precios-si]");
  var preciosNo = root.querySelector("[data-compra-precios-no]");
  if (preciosSi) {
    preciosSi.addEventListener("click", function () {
      asegurarAfectar("1");
      cerrarDialogo(modalPrecios);
      enviarConfirmacion();
    });
  }
  if (preciosNo) {
    preciosNo.addEventListener("click", function () {
      asegurarAfectar("0");
      cerrarDialogo(modalPrecios);
      enviarConfirmacion();
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "F2") {
      event.preventDefault();
      abrirDialogo(modalCodigo, codigoQ);
    } else if (event.key === "F3") {
      event.preventDefault();
      abrirBusqueda(searchInput ? searchInput.value : "");
    }
  });
})();
