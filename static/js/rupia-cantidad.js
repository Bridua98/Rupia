(function () {
  function init(input) {
    if (input.getAttribute("data-cantidad-ready")) return;
    input.setAttribute("data-cantidad-ready", "1");

    var maxDec = parseInt(input.getAttribute("data-cantidad-decimales") || "3", 10);
    var maxEnteros = parseInt(input.getAttribute("data-cantidad-max") || "12", 10);

    function partes(texto) {
      var crudo = String(texto || "").replace(/\s/g, "");
      var coma = crudo.lastIndexOf(",");
      if (coma < 0) {
        var punto = crudo.lastIndexOf(".");
        if (punto >= 0) {
          var der = crudo.slice(punto + 1);
          var izq = crudo.slice(0, punto).replace(/\D/g, "");
          var fracDer = der.replace(/\D/g, "");
          if (/^\d*$/.test(der) && fracDer.length <= maxDec) {
            var miles = fracDer.length === 3 && /^(?:0|[1-9]\d{0,2})$/.test(izq || "0");
            if (!miles) {
              coma = punto;
            }
          }
        }
      }
      var puntoFinal = coma < 0 && /[.,]$/.test(crudo);
      var entero;
      var frac = "";
      var decimal = coma >= 0 || puntoFinal;
      if (coma >= 0) {
        entero = crudo.slice(0, coma).replace(/\D/g, "");
        frac = crudo.slice(coma + 1).replace(/\D/g, "");
      } else {
        entero = crudo.replace(/\D/g, "");
      }
      if (entero.length > maxEnteros) entero = entero.slice(0, maxEnteros);
      if (frac.length > maxDec) frac = frac.slice(0, maxDec);
      entero = entero.replace(/^0+(?=\d)/, "") || (decimal || entero === "0" ? "0" : "");
      return { entero: entero, frac: frac, decimal: decimal };
    }

    function formatear(trozo, compacto) {
      if (!trozo.entero && !trozo.decimal) return "";
      var entero = (trozo.entero || "0").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      if (!trozo.decimal) return entero;
      if (compacto && (!trozo.frac || /^0+$/.test(trozo.frac))) return entero;
      return entero + "," + trozo.frac;
    }

    function caretEn(formateado, cantidad) {
      if (cantidad <= 0) return 0;
      var vistos = 0;
      var i;
      for (i = 0; i < formateado.length; i += 1) {
        if (/\d/.test(formateado.charAt(i))) {
          vistos += 1;
          if (vistos === cantidad) return i + 1;
        }
      }
      if (formateado.indexOf(",") >= 0 && cantidad > vistos) return formateado.length;
      return formateado.length;
    }

    function digitosHasta(valor, caret) {
      return String(valor).slice(0, caret).replace(/\D/g, "").length;
    }

    function pintar(crudo, caretDigitos, compacto) {
      var trozo = typeof crudo === "string" ? partes(crudo) : crudo;
      var formateado = formatear(trozo, compacto);
      var mover = document.activeElement === input && typeof caretDigitos === "number";
      if (input.value !== formateado) input.value = formateado;
      if (!mover) return;
      var pos = caretEn(formateado, caretDigitos);
      input.setSelectionRange(pos, pos);
    }

    if (input.value) pintar(input.value, null, true);

    input.addEventListener("focus", function () {
      var trozo = partes(input.value);
      if (trozo.decimal || (trozo.frac && !/^0+$/.test(trozo.frac))) return;
      pintar(trozo, null, false);
    });

    input.addEventListener("blur", function () {
      pintar(input.value, null, true);
    });

    input.addEventListener("keydown", function (event) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "." || event.key === "Decimal") {
        event.preventDefault();
        var start = input.selectionStart || 0;
        if (input.value.indexOf(",") >= 0) return;
        var izq = input.value.slice(0, start);
        var der = input.value.slice(input.selectionEnd || start);
        pintar(izq + "," + der, digitosHasta(izq, izq.length));
      }
    });

    input.addEventListener("input", function () {
      var start = input.selectionStart || 0;
      pintar(input.value, digitosHasta(input.value, start), false);
    });
  }

  window.rupiaInitCantidad = init;

  function boot() {
    document.querySelectorAll("[data-cantidad='py']").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
