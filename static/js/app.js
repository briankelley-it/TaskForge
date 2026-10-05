// Small site-wide behaviour. Interactive features use HTMX attributes in the templates.
document.addEventListener("DOMContentLoaded", () => {
  // Let flash messages be dismissed.
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("[data-dismiss]");
    if (button) button.closest("[data-dismissible]")?.remove();
  });
});
