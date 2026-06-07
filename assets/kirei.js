(() => {
  const ADVANCED_KEY = "kirei.showAdvanced";
  const THEME_KEY = "kirei.theme";
  const SCROLL_KEY = "kirei.scroll";
  const THEMES = ["rich", "mono"];
  const SCROLL_MODES = ["vertical", "horizontal"];

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
        // Local file previews may block storage; the controls should still work.
      }
    },
  };

  const typeset = (node) => {
    if (window.MathJax?.typesetPromise) {
      window.MathJax.typesetPromise(node ? [node] : undefined).catch(() => {});
    }
  };

  const currentThemeFromBody = () => {
    const found = THEMES.find((theme) => document.body.classList.contains(`theme-${theme}`));
    return found || "rich";
  };

  const normalizeTheme = (theme) => {
    if (theme === "spread") {
      return "mono";
    }
    return THEMES.includes(theme) ? theme : "rich";
  };

  const releaseControlFocus = (control) => {
    window.setTimeout(() => {
      control?.blur?.();
      if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
    }, 0);
  };

  const currentScrollFromBody = () => {
    const found = SCROLL_MODES.find((mode) => document.body.classList.contains(`scroll-${mode}`));
    return found || "vertical";
  };

  const setTheme = (theme, persist = true) => {
    const nextTheme = normalizeTheme(theme);
    THEMES.forEach((name) => {
      document.body.classList.toggle(`theme-${name}`, name === nextTheme);
    });
    document.body.classList.remove("theme-spread");
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      const active = button.dataset.themeChoice === nextTheme;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (persist) {
      storage.set(THEME_KEY, nextTheme);
    }
    typeset(document.body);
  };

  const setScrollMode = (mode, persist = true) => {
    const nextMode = SCROLL_MODES.includes(mode) ? mode : "vertical";
    SCROLL_MODES.forEach((name) => {
      document.body.classList.toggle(`scroll-${name}`, name === nextMode);
    });
    document.querySelectorAll("[data-scroll-choice]").forEach((button) => {
      const active = button.dataset.scrollChoice === nextMode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (persist) {
      storage.set(SCROLL_KEY, nextMode);
    }
    typeset(document.body);
  };

  const setAdvancedVisible = (visible) => {
    document.body.classList.toggle("show-advanced", visible);
    storage.set(ADVANCED_KEY, visible ? "1" : "0");
  };

  const updateAdvancedLabel = (count) => {
    const label = document.getElementById("advanced-toggle-label");
    if (!label) {
      return;
    }
    label.textContent = `発展を表示: ${count}件`;
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
    const advancedCount = document.querySelectorAll("[data-advanced]").length;
    const shouldShowAdvanced = storage.get(ADVANCED_KEY) === "1";
    const savedTheme = storage.get(THEME_KEY);
    const savedScrollMode = storage.get(SCROLL_KEY);

    setTheme(savedTheme || currentThemeFromBody(), Boolean(savedTheme));
    setScrollMode(savedScrollMode || currentScrollFromBody(), Boolean(savedScrollMode));
    document.querySelectorAll("[data-theme-choice]").forEach((button) => {
      button.addEventListener("click", () => {
        setTheme(button.dataset.themeChoice);
        releaseControlFocus(button);
      });
    });
    document.querySelectorAll("[data-scroll-choice]").forEach((button) => {
      button.addEventListener("click", () => {
        setScrollMode(button.dataset.scrollChoice);
        releaseControlFocus(button);
      });
    });

    updateAdvancedLabel(advancedCount);

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
