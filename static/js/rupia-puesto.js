(function () {
  "use strict";

  var raiz = document.querySelector("[data-puesto]");
  if (!raiz) return;

  var sector = raiz.getAttribute("data-sector");
  var tomarUrl = raiz.getAttribute("data-tomar-url");
  var colaUrl = raiz.getAttribute("data-cola-url");
  var cola = raiz.querySelector("[data-puesto-cola]");
  var auto = raiz.querySelector("[data-puesto-auto]");
  var estado = raiz.querySelector("[data-puesto-estado]");
  var impresion = document.querySelector("[data-puesto-impresion]");
  var claveAuto = "rupia-puesto-auto-" + sector;
  var imprimiendo = false;
  var pendientesDeImprimir = [];
  var tituloBase = document.title;
  var vistos = idsCola();
  var diaAbierto = false;
  var diaPagina = 1;
  var detallesAbiertos = {};

  function csrf() {
    var campo = raiz.querySelector("input[name=csrfmiddlewaretoken]");
    return campo ? campo.value : "";
  }

  function leerAuto() {
    try {
      return window.localStorage.getItem(claveAuto) !== "0";
    } catch (error) {
      return true;
    }
  }

  function guardarAuto(valor) {
    try {
      window.localStorage.setItem(claveAuto, valor ? "1" : "0");
    } catch (error) {
      // Sin almacenamiento: vale para esta sesión.
    }
  }

  function marcarEstado(ok) {
    if (!estado) return;
    estado.textContent = ok ? "Conectado" : "Sin conexión, reintentando…";
    estado.classList.toggle("is-error", !ok);
  }

  function post(url) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf(), "X-Requested-With": "XMLHttpRequest" },
    }).then(function (respuesta) {
      if (!respuesta.ok) throw new Error(respuesta.status);
      return respuesta.json();
    });
  }

  function idsCola() {
    if (!cola) return [];
    return Array.prototype.map.call(cola.querySelectorAll("[data-envio]"), function (el) {
      return el.getAttribute("data-envio");
    });
  }

  function marcarNuevos(anteriores) {
    var hay = false;
    cola.querySelectorAll("[data-envio]").forEach(function (el) {
      if (anteriores.indexOf(el.getAttribute("data-envio")) === -1) {
        el.classList.add("is-nuevo");
        hay = true;
      }
    });
    return hay;
  }

  function actualizarTitulo() {
    var dato = cola.querySelector("[data-puesto-abiertos]");
    var n = dato ? parseInt(dato.getAttribute("data-cantidad") || "0", 10) : 0;
    document.title = n ? "(" + n + ") " + tituloBase : tituloBase;
  }

  function avisarLlegada(yaSono) {
    var actuales = idsCola();
    var hayNuevos = marcarNuevos(vistos);
    if (hayNuevos && !yaSono) sonar();
    var dato = cola.querySelector("[data-puesto-abiertos]");
    if (dato) dato.classList.toggle("is-alerta", hayNuevos);
    vistos = actuales;
    actualizarTitulo();
  }

  function sonar() {
    try {
      var Contexto = window.AudioContext || window.webkitAudioContext;
      if (!Contexto) return;
      var audio = new Contexto();
      var tono = audio.createOscillator();
      var volumen = audio.createGain();
      tono.frequency.value = 880;
      volumen.gain.value = 0.15;
      tono.connect(volumen);
      volumen.connect(audio.destination);
      tono.start();
      tono.stop(audio.currentTime + 0.25);
    } catch (error) {
      // Sin sonido no pasa nada.
    }
  }

  // Imprime de a un lote: todos los tickets juntos, uno por hoja.
  function imprimir(htmls) {
    pendientesDeImprimir = pendientesDeImprimir.concat(htmls);
    if (imprimiendo || !pendientesDeImprimir.length) return;
    imprimiendo = true;
    var lote = pendientesDeImprimir;
    pendientesDeImprimir = [];
    impresion.innerHTML = lote.join("");
    // Darle un respiro al navegador para dibujar antes de imprimir.
    setTimeout(function () {
      window.print();
      setTimeout(function () {
        impresion.innerHTML = "";
        imprimiendo = false;
        if (pendientesDeImprimir.length) imprimir([]);
      }, 500);
    }, 60);
  }

  function recordarDia() {
    var panel = cola.querySelector("[data-puesto-dia]");
    if (panel) diaAbierto = panel.open;
    detallesAbiertos = {};
    cola.querySelectorAll("[data-puesto-detalle][open]").forEach(function (el) {
      detallesAbiertos[el.getAttribute("data-puesto-detalle")] = true;
    });
  }

  function aplicarDia() {
    var panel = cola.querySelector("[data-puesto-dia]");
    if (panel) panel.open = diaAbierto;
    cola.querySelectorAll("[data-puesto-detalle]").forEach(function (el) {
      if (detallesAbiertos[el.getAttribute("data-puesto-detalle")]) el.open = true;
    });
  }

  function urlCola() {
    if (!diaAbierto) return colaUrl;
    var union = colaUrl.indexOf("?") >= 0 ? "&" : "?";
    return colaUrl + union + "dia=1&pagina=" + diaPagina;
  }

  function refrescarCola(forzar) {
    // Un botón de la cola deja el foco adentro. Sin forzar, Listo no redibuja.
    if (!forzar && document.querySelector("[data-puesto-cola] :focus")) return Promise.resolve();
    recordarDia();
    return fetch(urlCola(), { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (respuesta) {
        if (!respuesta.ok) throw new Error(respuesta.status);
        return respuesta.text();
      })
      .then(function (html) {
        cola.innerHTML = html;
        aplicarDia();
        marcarEstado(true);
      })
      .catch(function () {
        marcarEstado(false);
      });
  }

  function vuelta() {
    if (!auto.checked) {
      refrescarCola().then(function () {
        avisarLlegada(false);
      });
      return;
    }
    post(tomarUrl)
      .then(function (datos) {
        marcarEstado(true);
        var tickets = (datos.tickets || []).map(function (t) { return t.html; });
        if (tickets.length) {
          sonar();
          imprimir(tickets);
        }
        return refrescarCola().then(function () {
          avisarLlegada(!!tickets.length);
        });
      })
      .catch(function () {
        marcarEstado(false);
      });
  }

  auto.checked = leerAuto();
  auto.addEventListener("change", function () {
    guardarAuto(auto.checked);
    vuelta();
  });

  // Botones de la cola (la cola se redibuja, así que se delegan).
  cola.addEventListener("toggle", function (evento) {
    var panel = evento.target;
    if (!panel.hasAttribute || !panel.hasAttribute("data-puesto-dia")) return;
    diaAbierto = panel.open;
    if (!panel.open) diaPagina = 1;
  }, true);

  cola.addEventListener("click", function (evento) {
    var link = evento.target.closest("[data-puesto-pagina]");
    if (!link) return;
    evento.preventDefault();
    diaPagina = parseInt(link.getAttribute("data-puesto-pagina"), 10) || 1;
    diaAbierto = true;
    refrescarCola(true);
  });

  cola.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-puesto-imprimir]");
    if (!boton) return;
    evento.preventDefault();
    post(boton.getAttribute("data-puesto-imprimir"))
      .then(function (datos) {
        imprimir([datos.html]);
        return refrescarCola().then(function () {
          avisarLlegada(true);
        });
      })
      .catch(function () {
        marcarEstado(false);
      });
  });

  cola.addEventListener("submit", function (evento) {
    var form = evento.target.closest("[data-puesto-listo]");
    if (!form) return;
    evento.preventDefault();
    if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
    post(form.getAttribute("action"))
      .then(function () {
        return refrescarCola(true).then(function () {
          avisarLlegada(true);
        });
      })
      .catch(function () {
        marcarEstado(false);
      });
  });

  actualizarTitulo();
  vuelta();
  setInterval(vuelta, 5000);
})();
