// Site-wide behaviour. Most interactivity is HTMX attributes in the templates; this file
// only covers what HTMX can't do alone: dismissing messages, the modal, and drag and drop.

// ---- Dismissible messages and the modal -----------------------------------------------

function closeModal() {
  const modal = document.getElementById("modal");
  if (modal) modal.innerHTML = "";
}

document.addEventListener("click", (event) => {
  const dismiss = event.target.closest("[data-dismiss]");
  if (dismiss) dismiss.closest("[data-dismissible]")?.remove();

  // Close on the X/Cancel buttons, or a click on the dark backdrop around the dialog.
  if (event.target.closest("[data-close-modal]") || event.target.matches("[data-modal-backdrop]")) {
    closeModal();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});

// The server asks for this with the response header `HX-Trigger: closeModal`.
document.addEventListener("closeModal", closeModal);

// ---- Kanban drag and drop -------------------------------------------------------------

function initBoard(root) {
  if (!window.Sortable) return;
  root.querySelectorAll("[data-sortable]").forEach((list) => {
    Sortable.create(list, {
      group: "board", // cards can move between the three columns
      animation: 150,
      ghostClass: "opacity-40",
      // On touch screens, a short press starts a drag so normal scrolling still works.
      delay: 150,
      delayOnTouchOnly: true,
      onEnd(event) {
        if (event.from === event.to && event.oldIndex === event.newIndex) return;
        // POST the new column and index. The server replies 204 with
        // HX-Trigger: boardChanged, so the board re-renders from the database.
        htmx.ajax("POST", event.item.dataset.moveUrl, {
          source: event.item, // so the CSRF header set on <body> is included
          swap: "none",
          values: { status: event.to.dataset.status, position: event.newIndex },
        });
      },
    });
  });
}

// Runs on first page load and again for every piece of HTML that HTMX swaps in,
// so the board is re-initialised each time it reloads.
htmx.onLoad(initBoard);
