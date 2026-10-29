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
    function select(id, focusRow) {
      rows(root).forEach(function (row) {
        var on = row.getAttribute("data-id") === String(id);
        row.setAttribute("aria-selected", on ? "true" : "false");
        row.tabIndex = on ? 0 : -1;
        if (on && focusRow) row.focus();
      });
    }

    root.addEventListener("click", function (event) {
      var row = event.target.closest("tr[data-href]");
      if (!row || !root.contains(row)) return;
      window.location.href = row.getAttribute("data-href");
    });

    document.addEventListener("keydown", function (event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
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
