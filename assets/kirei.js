(() => {
  const ADVANCED_KEY = "kirei.showAdvanced";

  const storage = {
    get(key) {
      try {
        return window.localStorage?.getItem(key) ?? null;
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage?.setItem(key, value);
      } catch {
        // Local file previews may block storage; the toggle should still work.
      }
    },
  };

  const typeset = (node) => {
    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetPromise([node]).catch(() => {});
    }
  };

  const setAdvancedVisible = (visible) => {
    document.body.classList.toggle("show-advanced", visible);
    storage.set(ADVANCED_KEY, visible ? "1" : "0");
  };

  const closeOtherGaps = (activeId) => {
    document.querySelectorAll(".kgap-trigger[aria-expanded='true']").forEach((button) => {
      if (button.dataset.kgapTarget === activeId) {
        return;
      }
      const popover = document.getElementById(button.dataset.kgapTarget);
      button.setAttribute("aria-expanded", "false");
      if (popover) {
        popover.hidden = true;
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    const advancedToggle = document.getElementById("advanced-toggle");
    const shouldShowAdvanced = storage.get(ADVANCED_KEY) === "1";

    if (advancedToggle) {
      advancedToggle.checked = shouldShowAdvanced;
      setAdvancedVisible(shouldShowAdvanced);
      advancedToggle.addEventListener("change", () => {
        setAdvancedVisible(advancedToggle.checked);
        if (advancedToggle.checked) {
          document.querySelectorAll("[data-advanced]").forEach(typeset);
        }
      });
    }

    document.addEventListener("click", (event) => {
      const trigger = event.target.closest(".kgap-trigger");
      if (!trigger) {
        if (!event.target.closest(".kgap-popover")) {
          closeOtherGaps(null);
        }
        return;
      }

      const targetId = trigger.dataset.kgapTarget;
      const popover = document.getElementById(targetId);
      if (!popover) {
        return;
      }

      const willOpen = trigger.getAttribute("aria-expanded") !== "true";
      closeOtherGaps(targetId);
      trigger.setAttribute("aria-expanded", willOpen ? "true" : "false");
      popover.hidden = !willOpen;
      if (willOpen) {
        typeset(popover);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeOtherGaps(null);
      }
    });
  });
})();
