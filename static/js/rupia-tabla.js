(function () {
  function boot() {
    var list = document.querySelector("[data-rupia='list']");
    if (list) initList(list);
    var ficha = document.querySelector("[data-rupia='ficha']");
    if (ficha) initFicha(ficha);
  }

  function visorImagen() {
    var node = document.querySelector("[data-imagen-visor]");
    if (node) return node;
    node = document.createElement("div");
    node.className = "imagen-visor";
    node.hidden = true;
    node.setAttribute("data-imagen-visor", "");
    node.innerHTML =
      '<button type="button" class="imagen-visor-cerrar" data-imagen-cerrar aria-label="Cerrar">×</button>' +
      '<img alt="Imagen del ítem" data-imagen-visor-img>';
    document.body.appendChild(node);
    node.addEventListener("click", function (event) {
      if (event.target === node || event.target.closest("[data-imagen-cerrar]")) {
        cerrarVisor();
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape" || node.hidden) return;
      event.preventDefault();
      event.stopPropagation();
      cerrarVisor();
    }, true);
    return node;
  }

  function abrirVisor(src, alt, volver) {
    var node = visorImagen();
    var foto = node.querySelector("[data-imagen-visor-img]");
    foto.src = src;
    foto.alt = alt || "Imagen del ítem";
    node.hidden = false;
    document.body.classList.add("is-visor");
    node.dataset.returnFocus = "";
    node._volver = volver || null;
    var cerrar = node.querySelector("[data-imagen-cerrar]");
    if (cerrar) cerrar.focus();
  }

  function cerrarVisor() {
    var node = document.querySelector("[data-imagen-visor]");
    if (!node || node.hidden) return;
    node.hidden = true;
    document.body.classList.remove("is-visor");
    var foto = node.querySelector("[data-imagen-visor-img]");
    if (foto) foto.removeAttribute("src");
    if (node._volver) node._volver.focus();
  }

  function initImagen(root) {
    var card = root.querySelector("[data-imagen]");
    if (!card) return;
    var input = card.querySelector("[data-imagen-input]");
    var preview = card.querySelector("[data-imagen-preview]");
    var vacio = card.querySelector("[data-imagen-vacio]");
    var barra = card.querySelector("[data-imagen-barra]");
    var marco = card.querySelector(".imagen-marco");
    var ver = card.querySelector("[data-imagen-ver]");
    var cambiar = card.querySelector("[data-imagen-cambiar]");
    var quitar = card.querySelector("[data-imagen-quitar]");
    var check = root.querySelector("[name='quitar_imagen']");
    if (!input || !preview) return;

    function tieneFoto() {
      return !preview.hidden && !!preview.getAttribute("src");
    }

    function mostrar(src, alt) {
      preview.src = src;
      preview.alt = alt || "Imagen seleccionada";
      preview.hidden = false;
      if (vacio) vacio.hidden = true;
      if (barra) barra.hidden = false;
      if (marco) marco.classList.add("tiene-foto");
      if (quitar) quitar.hidden = false;
    }

    function vaciar() {
      preview.hidden = true;
      preview.removeAttribute("src");
      if (vacio) vacio.hidden = false;
      if (barra) barra.hidden = true;
      if (marco) marco.classList.remove("tiene-foto");
    }

    if (check) quitar.hidden = !tieneFoto();
    if (check && check.checked) vaciar();

    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) return;
      if (preview.dataset.objectUrl) URL.revokeObjectURL(preview.dataset.objectUrl);
      var url = URL.createObjectURL(file);
      preview.dataset.objectUrl = url;
      if (check) check.checked = false;
      mostrar(url, "Imagen seleccionada");
    });

    function verFoto() {
      if (!tieneFoto()) return;
      abrirVisor(preview.src, preview.alt, ver);
    }

    if (ver) ver.addEventListener("click", verFoto);
    if (cambiar) cambiar.addEventListener("click", function () { input.click(); });
    preview.addEventListener("click", verFoto);

    if (quitar) {
      quitar.addEventListener("click", function () {
        if (preview.dataset.objectUrl) {
          URL.revokeObjectURL(preview.dataset.objectUrl);
          delete preview.dataset.objectUrl;
        }
        input.value = "";
        if (check) check.checked = true;
        vaciar();
      });
    }
  }

  function rows(root) {
    return Array.prototype.slice.call(root.querySelectorAll("tbody tr[data-href]"));
  }

  function initList(root) {
    initActionMenus(root);

    root.querySelectorAll("[data-filters-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        var panel = root.querySelector("[data-filters-panel]");
        if (!panel) return;
        var open = panel.hidden;
        panel.hidden = !open;
        button.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });

    function select(id, focusRow) {
      rows(root).forEach(function (row) {
        var on = row.getAttribute("data-id") === String(id);
        row.setAttribute("aria-selected", on ? "true" : "false");
        row.tabIndex = on ? 0 : -1;
        if (on && focusRow) row.focus();
      });
    }

    root.addEventListener("click", function (event) {
      if (event.target.closest("[data-rupia='action-menu']")) return;
      var row = event.target.closest("tr[data-href]");
      if (!row || !root.contains(row)) return;
      window.location.href = row.getAttribute("data-href");
    });

    document.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target.closest("input, textarea, select")) return;
      var list = rows(root);
      if (!list.length) return;
      var index = list.findIndex(function (row) {
        return row.getAttribute("aria-selected") === "true";
      });
      if (index < 0) index = 0;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        var next = event.key === "ArrowDown"
          ? Math.min(list.length - 1, index + 1)
          : Math.max(0, index - 1);
        select(list[next].getAttribute("data-id"), true);
      } else if (event.key === "Enter") {
        if (event.target.closest("a, button")) return;
        event.preventDefault();
        window.location.href = list[index].getAttribute("data-href");
      }
    });
  }

  function placeActionMenu(menu) {
    var trigger = menu.querySelector(".action-menu-trigger");
    var panel = menu.querySelector(".action-menu-panel");
    if (!trigger || !panel) return;
    var rect = trigger.getBoundingClientRect();
    var width = panel.offsetWidth || 168;
    var height = panel.offsetHeight || 88;
    var left = rect.left + rect.width / 2 - width / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    var top = rect.bottom + 6;
    if (top + height > window.innerHeight - 8) {
      top = Math.max(8, rect.top - height - 6);
    }
    panel.style.left = left + "px";
    panel.style.top = top + "px";
  }

  function finishCloseActionMenu(menu) {
    var panel = menu.querySelector(".action-menu-panel");
    var trigger = menu.querySelector(".action-menu-trigger");
    if (!panel || !trigger) return;
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    resetActionMenuConfirm(menu);
  }

  function closeActionMenu(menu) {
    var panel = menu.querySelector(".action-menu-panel");
    if (!panel) return;
    if (!menu.classList.contains("is-open")) {
      finishCloseActionMenu(menu);
      return;
    }
    menu.classList.remove("is-open");
    var closed = false;
    function onEnd(event) {
      if (closed || (event && event.propertyName !== "opacity")) return;
      closed = true;
      panel.removeEventListener("transitionend", onEnd);
      finishCloseActionMenu(menu);
    }
    panel.addEventListener("transitionend", onEnd);
    window.setTimeout(onEnd, 220);
  }

  function openActionMenu(menu) {
    var panel = menu.querySelector(".action-menu-panel");
    var trigger = menu.querySelector(".action-menu-trigger");
    if (!panel || !trigger) return;
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    placeActionMenu(menu);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        menu.classList.add("is-open");
      });
    });
  }

  function resetActionMenuConfirm(menu) {
    var menuPanel = menu.querySelector("[data-action-panel='menu']");
    var confirmPanel = menu.querySelector("[data-action-panel='confirm']");
    if (menuPanel) menuPanel.hidden = false;
    if (confirmPanel) confirmPanel.hidden = true;
  }

  function initActionMenus(root) {
    var openMenu = null;

    function closeOpenMenu() {
      if (openMenu) {
        closeActionMenu(openMenu);
        openMenu = null;
      }
    }

    root.querySelectorAll("[data-rupia='action-menu']").forEach(function (menu) {
      var trigger = menu.querySelector(".action-menu-trigger");
      var panel = menu.querySelector(".action-menu-panel");
      var confirmPanel = menu.querySelector("[data-action-panel='confirm']");
      var confirmText = menu.querySelector("[data-confirm-text]");
      var deleteForm = menu.querySelector("[data-delete-form]");
      var deleteTrigger = menu.querySelector("[data-delete-trigger]");
      var cancelBtn = menu.querySelector("[data-delete-cancel]");

      if (!trigger || !panel) return;

      trigger.addEventListener("click", function (event) {
        event.stopPropagation();
        if (openMenu === menu && menu.classList.contains("is-open")) {
          closeOpenMenu();
          return;
        }
        closeOpenMenu();
        openActionMenu(menu);
        openMenu = menu;
      });

      if (deleteTrigger && confirmPanel && deleteForm) {
        deleteTrigger.addEventListener("click", function (event) {
          event.stopPropagation();
          var message = deleteTrigger.getAttribute("data-confirm") || "";
          var action = deleteTrigger.getAttribute("data-action") || "";
          if (confirmText) confirmText.textContent = message;
          deleteForm.action = action;
          menu.querySelector("[data-action-panel='menu']").hidden = true;
          confirmPanel.hidden = false;
          placeActionMenu(menu);
        });
      }

      if (cancelBtn) {
        cancelBtn.addEventListener("click", function (event) {
          event.stopPropagation();
          resetActionMenuConfirm(menu);
        });
      }

      panel.addEventListener("click", function (event) {
        event.stopPropagation();
      });
    });

    document.addEventListener("click", function () {
      closeOpenMenu();
    });

    window.addEventListener("resize", function () {
      if (openMenu) placeActionMenu(openMenu);
    });
    document.addEventListener("scroll", function () {
      if (openMenu) placeActionMenu(openMenu);
    }, true);

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        if (!openMenu) return;
        var confirmPanel = openMenu.querySelector("[data-action-panel='confirm']");
        if (confirmPanel && !confirmPanel.hidden) {
          event.preventDefault();
          resetActionMenuConfirm(openMenu);
          return;
        }
        closeOpenMenu();
      }
    });
  }

  function fichaFields(root) {
    return Array.prototype.slice.call(root.querySelectorAll("input, textarea, select")).filter(function (field) {
      return field.type !== "hidden" && field.type !== "submit" && field.type !== "button";
    });
  }

  function fieldDirty(field) {
    if (field.type === "checkbox" || field.type === "radio") {
      return field.checked !== field.defaultChecked;
    }
    return field.value.trim() !== String(field.defaultValue || "").trim();
  }

  function initFicha(root) {
    var fields = fichaFields(root);
    var navError = root.querySelector("[data-nav-error]");
    var barcode = root.querySelector("[name='codigo_barra']");

    if (barcode) {
      barcode.addEventListener("keydown", function (event) {
        if (event.key !== "Enter" || event.altKey || event.ctrlKey || event.metaKey) return;
        event.preventDefault();
        var descripcion = root.querySelector("[name='descripcion']");
        if (descripcion) descripcion.focus();
      });
    }

    initImagen(root);
    var actions = root.querySelector("[data-ficha-actions]");
    var confirmBox = root.querySelector("[data-ficha-confirm]");
    var deleteBtn = root.querySelector("[data-delete-open]");
    var cancelBtn = root.querySelector("[data-delete-cancel]");

    function dirty() {
      return fields.some(fieldDirty);
    }

    function showNavError(on) {
      if (!navError) return;
      navError.hidden = !on;
      navError.textContent = on ? navError.getAttribute("data-nav-message") || "" : "";
    }

    function go(url) {
      if (!url) return false;
      if (dirty()) {
        showNavError(true);
        return true;
      }
      window.location.href = url;
      return true;
    }

    fields.forEach(function (field) {
      field.addEventListener("input", function () {
        showNavError(false);
      });
    });

    root.querySelectorAll("[data-record-nav]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (!dirty()) return;
        event.preventDefault();
        showNavError(true);
      });
    });

    if (deleteBtn && confirmBox && actions) {
      deleteBtn.addEventListener("click", function () {
        actions.hidden = true;
        confirmBox.hidden = false;
        var submit = confirmBox.querySelector("button[type='submit']");
        if (submit) submit.focus();
      });
      cancelBtn.addEventListener("click", function () {
        confirmBox.hidden = true;
        actions.hidden = false;
        deleteBtn.focus();
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        if (document.querySelector("[data-rupia='action-menu'].is-open")) return;
        if (confirmBox && !confirmBox.hidden) {
          event.preventDefault();
          cancelBtn.click();
          return;
        }
        window.location.href = root.getAttribute("data-list");
        return;
      }
      var sideways = event.key === "ArrowLeft" || event.key === "ArrowRight";
      if (!sideways) return;
      var typing = fields.indexOf(event.target) !== -1;
      if (typing && !event.altKey) return;
      var url = event.key === "ArrowLeft"
        ? root.getAttribute("data-prev")
        : root.getAttribute("data-next");
      if (go(url)) event.preventDefault();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
