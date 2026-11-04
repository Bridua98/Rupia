(function () {
  var root = document.querySelector("[data-pos]");
  if (!root) return;

  var searchForm = root.querySelector("[data-pos-search]");
  var searchInput = searchForm ? searchForm.querySelector("input[name='q']") : null;
  var suggest = root.querySelector("[data-pos-suggest]");
  var cabecera = document.getElementById("pos-cabecera");
  var clienteBox = root.querySelector("[data-pos-cliente]");
  var clienteQ = root.querySelector("[data-pos-cliente-q]");
  var clienteSuggest = root.querySelector("[data-pos-cliente-suggest]");
  var clienteId = clienteBox ? clienteBox.querySelector("input[name='cliente']") : null;
  var atajos = root.querySelector("[data-pos-atajos]");
  var descuentoPct = root.querySelector("[data-pos-descuento-pct]");
  var descuentoGs = root.querySelector("[data-pos-descuento]");
  var subtotal = Number(root.getAttribute("data-subtotal") || "0");
  var timer = 0;
  var clienteTimer = 0;
  var clienteItems = [];
  var clienteActivo = -1;

  function csrf() {
    var field = root.querySelector("[name='csrfmiddlewaretoken']");
    return field ? field.value : "";
  }

  function enCampo(nodo) {
    if (!nodo) return false;
    var tag = (nodo.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select";
  }

  function formatearGs(valor) {
    var entero = Math.max(0, Math.round(Number(valor) || 0));
    return String(entero).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function leerGs(texto) {
    return Number(String(texto || "0").replace(/\./g, "").replace(",", ".")) || 0;
  }

  function listar(nodo, items, onpick) {
    if (!nodo) return;
    nodo.innerHTML = "";
    if (!items.length) {
      nodo.hidden = true;
      return;
    }
    items.forEach(function (item) {
      var li = document.createElement("li");
      var titulo = document.createElement("strong");
      titulo.textContent = item.label || item.descripcion || "";
      li.appendChild(titulo);
      var meta = [item.codigo, item.precio].filter(Boolean).join(" · ");
      if (meta) {
        var detalle = document.createElement("small");
        detalle.textContent = meta;
        li.appendChild(detalle);
      }
      li.tabIndex = 0;
      li.addEventListener("click", function () { onpick(item); });
      li.addEventListener("keydown", function (event) {
        if (event.key === "Enter") onpick(item);
      });
      nodo.appendChild(li);
    });
    nodo.hidden = false;
  }

  function agregar(item) {
    var body = new URLSearchParams();
    body.set("csrfmiddlewaretoken", csrf());
    if (item && item.id) body.set("item", String(item.id));
    else if (searchInput) body.set("q", searchInput.value);
    fetch(searchForm.action, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body: body,
    }).then(function () { window.location.reload(); });
  }

  if (searchInput && suggest) {
    searchInput.addEventListener("input", function () {
      clearTimeout(timer);
      var q = searchInput.value.trim();
      if (!q) {
        suggest.hidden = true;
        return;
      }
      timer = setTimeout(function () {
        fetch("/ventas/punto-de-venta/buscar/?q=" + encodeURIComponent(q))
          .then(function (res) { return res.json(); })
          .then(function (data) {
            var resultados = data.resultados || [];
            if (resultados.length === 1 && resultados[0].codigo && resultados[0].codigo.toLowerCase() === q.toLowerCase()) {
              agregar(resultados[0]);
              return;
            }
            listar(suggest, resultados, agregar);
          });
      }, 180);
    });
    searchForm.addEventListener("submit", function (event) {
      if (suggest && !suggest.hidden && suggest.children.length) {
        event.preventDefault();
        suggest.children[0].click();
      }
    });
  }

  var codigoBtn = root.querySelector("[data-pos-codigo]");
  if (codigoBtn && searchInput) {
    codigoBtn.addEventListener("click", function () {
      searchInput.focus();
      searchInput.select();
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

  function bloquearSiFaltaCliente(event) {
    if (!faltaClienteFactura()) {
      if (clienteQ) clienteQ.setCustomValidity("");
      return;
    }
    event.preventDefault();
    avisarClienteFactura();
  }

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

  var guardarBtn = root.querySelector("[data-pos-guardar]");
  var cobrarBtn = root.querySelector("[data-pos-cobrar]");
  if (guardarBtn) guardarBtn.addEventListener("click", bloquearSiFaltaCliente);
  if (cobrarBtn) cobrarBtn.addEventListener("click", bloquearSiFaltaCliente);

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

  function pintarCliente(items) {
    clienteItems = items;
    clienteActivo = items.length ? 0 : -1;
    clienteSuggest.innerHTML = "";
    if (!clienteQ.value.trim()) {
      clienteSuggest.hidden = true;
      return;
    }
    if (!items.length) {
      var vacio = document.createElement("li");
      vacio.className = "is-empty";
      vacio.textContent = "No hay coincidencias en clientes ni en el padrón.";
      clienteSuggest.appendChild(vacio);
      clienteSuggest.hidden = false;
      return;
    }
    items.forEach(function (item, index) {
      var li = document.createElement("li");
      var titulo = document.createElement("strong");
      titulo.textContent = item.label || "";
      li.appendChild(titulo);
      var meta = item.documento || item.ruc || "";
      if (item.origen === "padron") meta = (meta ? meta + " · " : "") + "Crear cliente";
      if (meta) {
        var detalle = document.createElement("small");
        detalle.textContent = meta;
        li.appendChild(detalle);
      }
      li.tabIndex = 0;
      if (index === clienteActivo) li.classList.add("is-on");
      li.addEventListener("click", function () { elegirCliente(item); });
      clienteSuggest.appendChild(li);
    });
    clienteSuggest.hidden = false;
  }

  function marcarActivo() {
    Array.prototype.forEach.call(clienteSuggest.children, function (li, index) {
      li.classList.toggle("is-on", index === clienteActivo);
    });
  }

  function elegirCliente(item) {
    if (!item) return;
    var check = clienteBox.querySelector("[data-pos-consumidor], input[name='consumidor_final']");
    if (check) {
      check.checked = false;
      if (check.type === "hidden") check.remove();
    }
    if (item.origen === "padron" || !item.id) {
      var body = new URLSearchParams();
      body.set("csrfmiddlewaretoken", csrf());
      if (item.ruc) body.set("ruc", item.ruc);
      body.set("q", clienteQ.value.trim());
      fetch("/ventas/punto-de-venta/clientes/", {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: body,
      }).then(function (res) {
        if (!res.ok) return res.json().then(function () { window.location.reload(); });
        window.location.reload();
      }).catch(function () { window.location.reload(); });
      return;
    }
    clienteId.value = String(item.id);
    clienteQ.value = item.label;
    clienteSuggest.hidden = true;
    if (cabecera) cabecera.submit();
  }

  if (clienteQ && clienteSuggest && clienteId) {
    clienteQ.addEventListener("input", function () {
      var check = clienteBox.querySelector("[data-pos-consumidor], input[name='consumidor_final']");
      if (check) {
        check.checked = false;
        if (check.type === "hidden") check.remove();
      }
      clienteId.value = "";
      var q = clienteQ.value.trim();
      clearTimeout(clienteTimer);
      if (!q) {
        clienteSuggest.hidden = true;
        return;
      }
      clienteTimer = setTimeout(function () {
        fetch("/ventas/punto-de-venta/clientes/?q=" + encodeURIComponent(q))
          .then(function (res) { return res.json(); })
          .then(function (data) {
            pintarCliente(data.resultados || []);
          });
      }, 180);
    });
    clienteQ.addEventListener("keydown", function (event) {
      if (clienteSuggest.hidden) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (!clienteItems.length) return;
        clienteActivo = (clienteActivo + 1) % clienteItems.length;
        marcarActivo();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (!clienteItems.length) return;
        clienteActivo = (clienteActivo - 1 + clienteItems.length) % clienteItems.length;
        marcarActivo();
      } else if (event.key === "Enter") {
        if (clienteActivo >= 0 && clienteItems[clienteActivo]) {
          event.preventDefault();
          elegirCliente(clienteItems[clienteActivo]);
        }
      } else if (event.key === "Escape") {
        clienteSuggest.hidden = true;
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
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      return;
    }
    if (event.key === "F5") {
      event.preventDefault();
      if (faltaClienteFactura()) {
        avisarClienteFactura();
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
      if (faltaClienteFactura()) {
        avisarClienteFactura();
        return;
      }
      var cobrar = root.querySelector("[data-pos-cobrar]");
      if (cobrar && !cobrar.disabled) cobrar.click();
      return;
    }
    if (event.key === "Escape") {
      if (atajos && atajos.open) {
        atajos.open = false;
        return;
      }
      if (suggest && !suggest.hidden) {
        suggest.hidden = true;
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
})();
