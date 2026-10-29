(function () {
  function boot() {
    var list = document.querySelector("[data-rupia='list']");
    if (list) initList(list);
    var ficha = document.querySelector("[data-rupia='ficha']");
    if (ficha) initFicha(ficha);
  }

  function rows(root) {
    return Array.prototype.slice.call(root.querySelectorAll("tbody tr[data-href]"));
  }

  function initList(root) {
    initActionMenus(root);

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

  function initFicha(root) {
    var input = root.querySelector("[name='descripcion']");
    var navError = document.getElementById("marca-nav-error");
    var actions = document.getElementById("marca-actions");
    var confirmBox = document.getElementById("marca-confirm");
    var deleteBtn = document.getElementById("marca-delete");
    var cancelBtn = document.getElementById("marca-delete-cancel");

    function dirty() {
      return input.value.trim() !== input.defaultValue.trim();
    }

    function showNavError(on) {
      if (!navError) return;
      navError.hidden = !on;
      navError.textContent = on
        ? "Guardá o volvé al listado antes de pasar a otra marca."
        : "";
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

    input.addEventListener("input", function () {
      showNavError(false);
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
      var typing = event.target === input;
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
