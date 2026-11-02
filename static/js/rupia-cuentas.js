(function () {
  function sync(banco, extras) {
    var on = banco.checked;
    extras.forEach(function (input) {
      var field = input.closest(".field");
      if (field) field.hidden = !on;
      if (!on) {
        if (input.type === "checkbox") input.checked = false;
        else input.value = "";
      }
    });
  }

  function init(root) {
    var banco = root.querySelector("[data-cuenta-banco]");
    if (!banco) return;
    var extras = Array.prototype.slice.call(root.querySelectorAll("[data-cuenta-si-banco]"));
    banco.addEventListener("change", function () {
      sync(banco, extras);
    });
    sync(banco, extras);
  }

  document.querySelectorAll("[data-rupia='ficha']").forEach(init);
})();
