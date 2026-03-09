/**
 * Accessibility Auditor — Main JavaScript
 * Handles delete confirmation dialogs via event listeners (no inline handlers).
 */

document.addEventListener("DOMContentLoaded", function () {
  // Attach confirmation dialogs to all delete forms
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      var message = form.getAttribute("data-confirm") || "Are you sure?";
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
});
