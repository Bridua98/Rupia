(function () {
  var dataNode = document.getElementById("dash-chart-data");
  var data = dataNode ? JSON.parse(dataNode.textContent) : null;

  function numero(valor) {
    var n = Number(valor);
    return Number.isFinite(n) ? n : 0;
  }

  function compacto(valor) {
    var abs = Math.abs(valor);
    var formato = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 1 });
    if (abs >= 1000000) return formato.format(valor / 1000000) + " M";
    if (abs >= 1000) return formato.format(valor / 1000) + " mil";
    return formato.format(valor);
  }

  function techo(valor) {
    if (valor <= 0) return 1;
    var potencia = Math.pow(10, Math.floor(Math.log10(valor)));
    var normal = valor / potencia;
    var paso = normal <= 1 ? 1 : normal <= 2 ? 2 : normal <= 5 ? 5 : 10;
    return paso * potencia;
  }

  function svgEl(nombre, attrs) {
    var nodo = document.createElementNS("http://www.w3.org/2000/svg", nombre);
    Object.keys(attrs || {}).forEach(function (clave) {
      nodo.setAttribute(clave, attrs[clave]);
    });
    return nodo;
  }

  function limpiar(nodo) {
    while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
  }

  function mostrarTip(tip, x, y, lineas) {
    limpiar(tip);
    lineas.forEach(function (linea, indice) {
      var p = document.createElement(indice === 0 ? "strong" : "span");
      p.textContent = linea;
      tip.appendChild(p);
    });
    tip.hidden = false;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }

  function dibujarLinea() {
    if (!data || !data.lineas) return;
    var plot = document.querySelector("[data-dash-line]");
    var svg = document.querySelector("[data-line-svg]");
    var tip = document.querySelector("[data-line-tip]");
    if (!plot || !svg || !tip) return;

    var visibles = { ventas: !!data.ventas, compras: !!data.compras };
    document.querySelectorAll("[data-serie]").forEach(function (boton) {
      var serie = boton.getAttribute("data-serie");
      boton.addEventListener("click", function () {
        visibles[serie] = !visibles[serie];
        if (!visibles.ventas && !visibles.compras) visibles[serie] = true;
        boton.setAttribute("aria-pressed", visibles[serie] ? "true" : "false");
        pintar(rangoActual());
      });
    });

    var rango = "7";
    function rangoActual() {
      return rango;
    }

    var caja = { w: 640, h: 248, l: 54, r: 14, t: 18, b: 32 };
    var puntos = [];

    function pintar(clave) {
      rango = clave;
      var serie = data.lineas[clave] || [];
      puntos = serie;
      limpiar(svg);
      svg.setAttribute("viewBox", "0 0 " + caja.w + " " + caja.h);
      var ancho = caja.w - caja.l - caja.r;
      var alto = caja.h - caja.t - caja.b;
      var maximo = 1;
      serie.forEach(function (punto) {
        if (visibles.ventas) maximo = Math.max(maximo, numero(punto.v));
        if (visibles.compras) maximo = Math.max(maximo, numero(punto.c));
      });
      maximo = techo(maximo);
      var pasos = 4;
      for (var i = 0; i <= pasos; i += 1) {
        var valor = (maximo / pasos) * i;
        var y = caja.t + alto - (valor / maximo) * alto;
        svg.appendChild(
          svgEl("line", {
            x1: caja.l,
            x2: caja.w - caja.r,
            y1: y,
            y2: y,
            class: "dash-grid",
          })
        );
        var etiqueta = svgEl("text", {
          x: caja.l - 8,
          y: y + 4,
          class: "dash-axis",
          "text-anchor": "end",
        });
        etiqueta.textContent = compacto(valor);
        svg.appendChild(etiqueta);
      }

      function xDe(indice) {
        if (serie.length <= 1) return caja.l;
        return caja.l + (indice * ancho) / (serie.length - 1);
      }
      function yDe(valor) {
        return caja.t + alto - (numero(valor) / maximo) * alto;
      }

      function trazo(campo, clase) {
        if (!serie.length) return;
        var d = serie
          .map(function (punto, indice) {
            return (indice ? "L" : "M") + xDe(indice).toFixed(2) + " " + yDe(punto[campo]).toFixed(2);
          })
          .join(" ");
        var area =
          "M" +
          xDe(0).toFixed(2) +
          " " +
          (caja.t + alto).toFixed(2) +
          " " +
          serie
            .map(function (punto, indice) {
              return "L" + xDe(indice).toFixed(2) + " " + yDe(punto[campo]).toFixed(2);
            })
            .join(" ") +
          " L" +
          xDe(serie.length - 1).toFixed(2) +
          " " +
          (caja.t + alto).toFixed(2) +
          " Z";
        svg.appendChild(svgEl("path", { d: area, class: "dash-area " + clase }));
        var linea = svgEl("path", { d: d, class: "dash-stroke " + clase });
        svg.appendChild(linea);
        var largo = linea.getTotalLength ? linea.getTotalLength() : 0;
        if (largo) {
          linea.style.strokeDasharray = String(largo);
          linea.style.strokeDashoffset = String(largo);
          requestAnimationFrame(function () {
            linea.style.transition = "stroke-dashoffset 700ms ease";
            linea.style.strokeDashoffset = "0";
          });
        }
      }

      if (visibles.compras) trazo("c", "is-compras");
      if (visibles.ventas) trazo("v", "is-ventas");

      var salto = serie.length > 12 ? Math.ceil(serie.length / 6) : 1;
      serie.forEach(function (punto, indice) {
        if (indice % salto !== 0 && indice !== serie.length - 1) return;
        var texto = svgEl("text", {
          x: xDe(indice),
          y: caja.h - 8,
          class: "dash-axis",
          "text-anchor": "middle",
        });
        texto.textContent = punto.e;
        svg.appendChild(texto);
      });

      var guia = svgEl("line", {
        class: "dash-guide",
        y1: caja.t,
        y2: caja.t + alto,
        x1: 0,
        x2: 0,
      });
      guia.style.display = "none";
      svg.appendChild(guia);
      svg._guia = guia;
      svg._xDe = xDe;
      svg._yDe = yDe;
      svg._caja = caja;
    }

    document.querySelectorAll("[data-rango]").forEach(function (boton) {
      boton.addEventListener("click", function () {
        document.querySelectorAll("[data-rango]").forEach(function (otro) {
          otro.setAttribute("aria-pressed", otro === boton ? "true" : "false");
        });
        tip.hidden = true;
        pintar(boton.getAttribute("data-rango"));
      });
    });

    plot.addEventListener("mousemove", function (event) {
      if (!puntos.length || !svg._xDe) return;
      var rect = svg.getBoundingClientRect();
      if (!rect.width) return;
      var xSvg = ((event.clientX - rect.left) / rect.width) * caja.w;
      var mejor = 0;
      var distancia = Infinity;
      puntos.forEach(function (_, indice) {
        var delta = Math.abs(svg._xDe(indice) - xSvg);
        if (delta < distancia) {
          distancia = delta;
          mejor = indice;
        }
      });
      var punto = puntos[mejor];
      var x = svg._xDe(mejor);
      svg._guia.setAttribute("x1", x);
      svg._guia.setAttribute("x2", x);
      svg._guia.style.display = "";
      svg.querySelectorAll(".dash-dot").forEach(function (nodo) {
        nodo.remove();
      });
      if (visibles.ventas) {
        svg.appendChild(
          svgEl("circle", {
            cx: x,
            cy: svg._yDe(punto.v),
            r: 4.5,
            class: "dash-dot is-ventas",
          })
        );
      }
      if (visibles.compras) {
        svg.appendChild(
          svgEl("circle", {
            cx: x,
            cy: svg._yDe(punto.c),
            r: 4.5,
            class: "dash-dot is-compras",
          })
        );
      }
      var lineas = [punto.e];
      if (visibles.ventas) lineas.push("Ventas " + punto.vt);
      if (visibles.compras) lineas.push("Compras " + punto.ct);
      var localX = ((x / caja.w) * rect.width) + 12;
      var localY = 12;
      if (localX > rect.width - 160) localX = ((x / caja.w) * rect.width) - 168;
      mostrarTip(tip, localX, localY, lineas);
    });
    plot.addEventListener("mouseleave", function () {
      tip.hidden = true;
      if (svg._guia) svg._guia.style.display = "none";
      svg.querySelectorAll(".dash-dot").forEach(function (nodo) {
        nodo.remove();
      });
    });

    pintar("7");
  }

  function dibujarBarras() {
    if (!data || !data.flujo) return;
    var plot = document.querySelector("[data-dash-bars]");
    var svg = document.querySelector("[data-bars-svg]");
    var tip = document.querySelector("[data-bars-tip]");
    if (!plot || !svg || !tip) return;
    var serie = data.flujo;
    var caja = { w: 360, h: 230, l: 46, r: 8, t: 12, b: 28 };
    limpiar(svg);
    svg.setAttribute("viewBox", "0 0 " + caja.w + " " + caja.h);
    var ancho = caja.w - caja.l - caja.r;
    var alto = caja.h - caja.t - caja.b;
    var maximo = 1;
    serie.forEach(function (punto) {
      maximo = Math.max(maximo, numero(punto.entra), numero(punto.sale));
    });
    maximo = techo(maximo);
    for (var i = 0; i <= 4; i += 1) {
      var valor = (maximo / 4) * i;
      var y = caja.t + alto - (valor / maximo) * alto;
      svg.appendChild(
        svgEl("line", { x1: caja.l, x2: caja.w - caja.r, y1: y, y2: y, class: "dash-grid" })
      );
      var etiqueta = svgEl("text", {
        x: caja.l - 6,
        y: y + 4,
        class: "dash-axis",
        "text-anchor": "end",
      });
      etiqueta.textContent = compacto(valor);
      svg.appendChild(etiqueta);
    }
    var grupo = serie.length ? ancho / serie.length : ancho;
    serie.forEach(function (punto, indice) {
      var centro = caja.l + grupo * indice + grupo / 2;
      var barra = Math.min(16, grupo * 0.28);
      function rect(campo, clase, desplazamiento) {
        var valor = numero(punto[campo]);
        var h = (valor / maximo) * alto;
        svg.appendChild(
          svgEl("rect", {
            x: centro + desplazamiento,
            y: caja.t + alto - h,
            width: barra,
            height: Math.max(h, valor ? 2 : 0),
            rx: 4,
            class: "dash-bar-col " + clase,
            "data-indice": String(indice),
          })
        );
      }
      rect("entra", "is-ventas", -barra - 3);
      rect("sale", "is-salidas", 3);
      var texto = svgEl("text", {
        x: centro,
        y: caja.h - 8,
        class: "dash-axis",
        "text-anchor": "middle",
      });
      texto.textContent = punto.e;
      svg.appendChild(texto);
    });

    function resaltar(indice) {
      svg.querySelectorAll(".dash-bar-col").forEach(function (barra) {
        barra.classList.toggle("is-dim", indice !== null && barra.getAttribute("data-indice") !== String(indice));
      });
    }

    plot.addEventListener("mousemove", function (event) {
      var rect = svg.getBoundingClientRect();
      if (!rect.width || !serie.length) return;
      var x = ((event.clientX - rect.left) / rect.width) * caja.w;
      var indice = Math.floor((x - caja.l) / grupo);
      if (indice < 0 || indice >= serie.length) {
        tip.hidden = true;
        resaltar(null);
        return;
      }
      resaltar(indice);
      var punto = serie[indice];
      var localX = event.clientX - plot.getBoundingClientRect().left + 12;
      if (localX > plot.clientWidth - 170) localX -= 180;
      mostrarTip(tip, localX, 8, [punto.e, "Entradas " + punto.et, "Salidas " + punto.st]);
    });
    plot.addEventListener("mouseleave", function () {
      tip.hidden = true;
      resaltar(null);
    });
  }

  function activarCorte() {
    var botones = document.querySelectorAll("[data-corte]");
    botones.forEach(function (boton) {
      boton.addEventListener("click", function () {
        var clave = boton.getAttribute("data-corte");
        botones.forEach(function (otro) {
          otro.setAttribute("aria-pressed", otro === boton ? "true" : "false");
        });
        document.querySelectorAll("[data-corte-panel]").forEach(function (panel) {
          panel.hidden = panel.getAttribute("data-corte-panel") !== clave;
        });
      });
    });
  }

  function activarDonut() {
    var root = document.querySelector("[data-dash-donut]");
    if (!root) return;
    var svg = root.querySelector("svg");
    function marcar(nombre) {
      svg.querySelectorAll(".dash-arc").forEach(function (arco) {
        var coincide = !nombre || arco.getAttribute("data-slice") === nombre;
        arco.classList.toggle("is-dim", !!nombre && !coincide);
        arco.classList.toggle("is-on", !!nombre && coincide);
      });
      document.querySelectorAll(".dash-donut-legend button").forEach(function (boton) {
        boton.classList.toggle("is-on", !!nombre && boton.getAttribute("data-slice") === nombre);
      });
    }
    document.querySelectorAll(".dash-donut-legend button, .dash-arc").forEach(function (nodo) {
      nodo.addEventListener("mouseenter", function () {
        marcar(nodo.getAttribute("data-slice"));
      });
      nodo.addEventListener("focus", function () {
        marcar(nodo.getAttribute("data-slice"));
      });
      nodo.addEventListener("mouseleave", function () {
        marcar("");
      });
      nodo.addEventListener("blur", function () {
        marcar("");
      });
    });
  }

  dibujarLinea();
  dibujarBarras();
  activarCorte();
  activarDonut();
})();
