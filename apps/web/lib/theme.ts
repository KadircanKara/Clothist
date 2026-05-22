export type Theme = "light" | "dark";
export const THEME_STORAGE_KEY = "clothist-theme";
export const DEFAULT_THEME: Theme = "dark";

/**
 * Inline-able script: runs before paint to set the theme attribute so we
 * never flash the wrong palette. Reads localStorage, falls back to system
 * preference, then to DEFAULT_THEME.
 */
export const themeBootstrapScript = `
(function() {
  try {
    var stored = localStorage.getItem("${THEME_STORAGE_KEY}");
    var theme = stored;
    if (theme !== "light" && theme !== "dark") {
      theme = "${DEFAULT_THEME}";
    }
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "${DEFAULT_THEME}");
  }
})();
`;
