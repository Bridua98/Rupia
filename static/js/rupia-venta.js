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
  var timer = 0;

  function csrf() {
    var field = root.querySelector("[name='csrfmiddlewaretoken']");
    return field ? field.value : "";
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
      li.textContent = item.label || item.descripcion;
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

  if (cabecera) {
    cabecera.querySelectorAll("select[name='medio'], select[name='caja'], select[name='tipo_comprobante']").forEach(function (el) {
      el.addEventListener("change", function () { cabecera.submit(); });
    });
    cabecera.querySelectorAll("input[name='medio']").forEach(function (el) {
      el.addEventListener("change", function () { cabecera.submit(); });
    });
  }

  if (clienteQ && clienteSuggest && clienteId) {
    clienteQ.addEventListener("input", function () {
      var check = clienteBox.querySelector("input[name='consumidor_final']");
      if (check) check.checked = false;
      clienteId.value = "";
      var q = clienteQ.value.trim();
      if (!q) {
        clienteSuggest.hidden = true;
        return;
      }
      fetch("/ventas/punto-de-venta/clientes/?q=" + encodeURIComponent(q))
        .then(function (res) { return res.json(); })
        .then(function (data) {
          listar(clienteSuggest, data.resultados || [], function (item) {
            clienteId.value = String(item.id);
            clienteQ.value = item.label;
            clienteSuggest.hidden = true;
            if (cabecera) cabecera.submit();
          });
        });
    });
  }
})();
