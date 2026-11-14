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

  // El mismo buscador del punto de venta: catálogo, marca, código y páginas.
  var buscador = document.querySelector("[data-comanda-buscar]");
  if (buscador) {
    var buscarUrl = buscador.getAttribute("data-buscar-url");
    var agregarForm = buscador.querySelector("[data-comanda-agregar]");
    var itemInput = buscador.querySelector("[data-comanda-item]");
    var abrirInput = buscador.querySelector("[data-comanda-buscar-abrir]");
    var modal = document.querySelector("[data-comanda-modal-productos]");
    var modalLista = document.querySelector("[data-comanda-modal-list]");
    var modalQ = document.querySelector("[data-comanda-modal-q]");
    var productos = [];
    var productoActivo = -1;
    var consulta = "";
    var offset = 0;
    var hayMas = false;
    var cargando = false;
    var pedido = 0;
    var timer = 0;
    var TAMANIO = 20;

    function abrirDialogo() {
      if (!modal) return;
      if (typeof modal.showModal === "function") modal.showModal();
      else modal.setAttribute("open", "");
      if (modalQ) {
        modalQ.focus();
        modalQ.select();
      }
    }

    function cerrarDialogo() {
      if (!modal) return;
      if (typeof modal.close === "function") modal.close();
      else modal.removeAttribute("open");
    }

    function metaProducto(item) {
      return [item.marca, item.codigo, item.precio, item.unidad].filter(Boolean).join(" · ");
    }

    function marcar() {
      if (!modalLista) return;
      Array.prototype.forEach.call(modalLista.children, function (li, index) {
        li.classList.toggle("is-on", index === productoActivo);
        if (index === productoActivo) li.scrollIntoView({ block: "nearest" });
      });
    }

    function elegir(item) {
      if (!item || !agregarForm || !itemInput) return;
      itemInput.value = String(item.id);
      agregarForm.submit();
    }

    function pintar(item, index) {
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
      titulo.textContent = item.descripcion || "";
      texto.appendChild(titulo);
      var meta = document.createElement("small");
      meta.textContent = metaProducto(item);
      texto.appendChild(meta);
      li.appendChild(texto);
      li.tabIndex = 0;
      if (index === productoActivo) li.classList.add("is-on");
      li.addEventListener("click", function () { elegir(item); });
      modalLista.appendChild(li);
    }

    function pintarLista(items, concatenar) {
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
        pintar(item, productos.length - 1);
      });
      if (productoActivo < 0 && productos.length) {
        productoActivo = 0;
        marcar();
      }
    }

    function buscar(query, concatenar) {
      if (concatenar && (cargando || !hayMas)) return;
      if (!concatenar) {
        offset = 0;
        hayMas = false;
      }
      consulta = query || "";
      cargando = true;
      var actual = ++pedido;
      fetch(
        buscarUrl +
          "?limite=" + TAMANIO +
          "&offset=" + offset +
          "&q=" + encodeURIComponent(consulta)
      )
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (actual !== pedido) return;
          var resultados = data.resultados || [];
          hayMas = !!data.hay_mas;
          offset = data.siguiente != null ? data.siguiente : offset + resultados.length;
          pintarLista(resultados, concatenar);
        })
        .finally(function () {
          if (actual === pedido) cargando = false;
        });
    }

    function abrirBusqueda() {
      if (modal && modal.open) {
        if (modalQ) modalQ.focus();
        return;
      }
      abrirDialogo();
      if (modalQ) modalQ.value = "";
      buscar("", false);
    }

    if (abrirInput) {
      abrirInput.addEventListener("click", abrirBusqueda);
      agregarForm.addEventListener("submit", function (event) {
        if (!itemInput.value) {
          event.preventDefault();
          abrirBusqueda();
        }
      });
    }
    if (modal) {
      modal.addEventListener("cancel", function (event) {
        event.preventDefault();
        cerrarDialogo();
      });
      modal.addEventListener("click", function (event) {
        if (event.target === modal) cerrarDialogo();
      });
    }
    if (modalLista) {
      modalLista.addEventListener("scroll", function () {
        if (!hayMas || cargando) return;
        if (modalLista.scrollTop + modalLista.clientHeight >= modalLista.scrollHeight - 64) {
          buscar(consulta, true);
        }
      });
    }
    if (modalQ) {
      modalQ.addEventListener("input", function () {
        clearTimeout(timer);
        var q = modalQ.value.trim();
        timer = setTimeout(function () { buscar(q, false); }, 160);
      });
      modalQ.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          if (!productos.length) return;
          productoActivo = (productoActivo + 1) % productos.length;
          marcar();
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          if (!productos.length) return;
          productoActivo = (productoActivo - 1 + productos.length) % productos.length;
          marcar();
        } else if (event.key === "Enter") {
          event.preventDefault();
          if (productoActivo >= 0 && productos[productoActivo]) elegir(productos[productoActivo]);
        }
      });
    }
    document.addEventListener("keydown", function (event) {
      if (event.key !== "F3") return;
      if (modal && modal.open) return;
      var activo = document.activeElement;
      var tag = activo ? (activo.tagName || "").toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      event.preventDefault();
      abrirBusqueda();
    });
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
