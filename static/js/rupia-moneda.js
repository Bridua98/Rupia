(function () {
  function digitos(texto) {
    return String(texto || "").replace(/\D/g, "");
  }

  function formatear(crudo, maximo) {
    var limpio = crudo.replace(/^0+(?=\d)/, "");
    if (limpio.length > maximo) limpio = limpio.slice(0, maximo);
    var miles = ".";
    return limpio.replace(/\B(?=(\d{3})+(?!\d))/g, miles);
  }

  function digitosHasta(valor, caret) {
    return digitos(String(valor).slice(0, caret)).length;
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
    return formateado.length;
  }

  function pintar(input, crudo, caretDigitos) {
    var maximo = parseInt(input.getAttribute("data-moneda-max") || "12", 10);
    var formateado = formatear(crudo, maximo);
    var mover = document.activeElement === input && typeof caretDigitos === "number";
    if (input.value !== formateado) input.value = formateado;
    if (!mover) return;
    var pos = caretEn(formateado, Math.min(caretDigitos, digitos(formateado).length));
    input.setSelectionRange(pos, pos);
  }

  function init(input) {
    if (input.value) pintar(input, digitos(input.value));

    input.addEventListener("keydown", function (event) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === "," || event.key === "." || event.key === "Decimal") {
        event.preventDefault();
        return;
      }
      if (event.key !== "Backspace" && event.key !== "Delete") return;
      var start = input.selectionStart;
      var end = input.selectionEnd;
      if (start == null || start !== end) return;
      var idx = event.key === "Backspace" ? start - 1 : start;
      if (idx < 0 || idx >= input.value.length) return;
      if (input.value.charAt(idx) !== ".") return;
      event.preventDefault();
      var actual = digitos(input.value);
      var pos = digitosHasta(input.value, start);
      var quitar = event.key === "Backspace" ? pos - 1 : pos;
      if (quitar < 0 || quitar >= actual.length) return;
      var siguiente = actual.slice(0, quitar) + actual.slice(quitar + 1);
      pintar(input, siguiente, quitar);
    });

    input.addEventListener("input", function () {
      var start = input.selectionStart || 0;
      pintar(input, digitos(input.value), digitosHasta(input.value, start));
    });
  }

  function boot() {
    document.querySelectorAll("[data-moneda='guarani']").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
