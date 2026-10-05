// Site-wide behaviour. Most interactivity is HTMX attributes in the templates; this file
// only covers what HTMX can't do alone: dismissing messages, the modal, and drag and drop.

// ---- Dark mode ------------------------------------------------------------------------
// base.html sets the starting theme before paint; this flips it and remembers the choice.

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-theme-toggle]")) return;
  const dark = document.documentElement.classList.toggle("dark");
  try {
    localStorage.setItem("theme", dark ? "dark" : "light");
  } catch (e) {
    // Private browsing can block storage; the toggle still works for this page.
  }
});

// ---- Dismissible messages and the modal -----------------------------------------------

function closeModal() {
  const modal = document.getElementById("modal");
  if (modal) modal.innerHTML = "";
  // Belt and braces: remove any dialog that ended up outside #modal.
  document.querySelectorAll("[data-modal-backdrop]").forEach((el) => el.remove());
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
  if (event.key !== "Escape") return;
  closeModal();
  closeDropdowns();
  clearSearchResults();
});

// ---- Top bar dropdowns (<details data-dropdown>) and search results --------------------

function closeDropdowns(except) {
  document.querySelectorAll("details[data-dropdown][open]").forEach((menu) => {
    if (menu !== except) menu.removeAttribute("open");
  });
}

function clearSearchResults() {
  const results = document.getElementById("search-results");
  if (results) results.innerHTML = "";
}

document.addEventListener("click", (event) => {
  // Only one dropdown open at a time; clicking anywhere else closes them.
  closeDropdowns(event.target.closest("details[data-dropdown]"));
  if (!event.target.closest("[data-search]")) clearSearchResults();
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

// ---- Image drop zones (cover images) ---------------------------------------------------
// The zone is a <label> for a real file input, so clicking it opens the system file picker.
// This adds an instant preview and lets you drop an image onto it.

function showPreview(input) {
  const zone = input.closest("[data-dropzone]");
  const file = input.files && input.files[0];
  if (!zone || !file) return;
  zone.querySelector("[data-dropzone-preview]").src = URL.createObjectURL(file);
  zone.querySelector("[data-dropzone-name]").textContent = file.name;
  zone.querySelector("label").dataset.hasFile = "";
}

document.addEventListener("change", (event) => {
  if (event.target.matches("[data-cover-input]")) showPreview(event.target);
});

["dragenter", "dragover"].forEach((type) =>
  document.addEventListener(type, (event) => {
    const label = event.target.closest("[data-dropzone] label");
    if (!label) return;
    event.preventDefault(); // allow dropping
    label.dataset.dragging = "";
  }),
);

["dragleave", "drop"].forEach((type) =>
  document.addEventListener(type, (event) => {
    const label = event.target.closest("[data-dropzone] label");
    if (!label) return;
    delete label.dataset.dragging;
    if (type !== "drop") return;
    event.preventDefault();
    const input = label.closest("[data-dropzone]").querySelector("[data-cover-input]");
    if (event.dataTransfer.files.length) {
      input.files = event.dataTransfer.files;
      showPreview(input);
    }
  }),
);

// ---- Auth pages: show/hide password and a password strength meter ------------------------

document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-password-toggle]");
  if (!toggle) return;
  const input = toggle.parentElement.querySelector("input");
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  toggle.setAttribute("aria-pressed", String(show));
  toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
  toggle.querySelector("[data-eye]").classList.toggle("hidden", show);
  toggle.querySelector("[data-eye-off]").classList.toggle("hidden", !show);
});

const STRENGTH = [
  ["", "Use 8 or more characters with a mix of letters, numbers and symbols."],
  ["bg-red-500", "Weak: add more characters."],
  ["bg-amber-400", "Fair: try adding numbers or symbols."],
  ["bg-lime-500", "Good password."],
  ["bg-emerald-500", "Strong password."],
];

function passwordScore(value) {
  if (!value) return 0;
  let score = value.length >= 8 ? 1 : 0;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value) && /[^A-Za-z0-9]/.test(value)) score += 1;
  return Math.max(1, Math.min(score, 4));
}

document.addEventListener("input", (event) => {
  const meter = document.querySelector(`[data-strength-for="${event.target.id}"]`);
  if (!meter) return;
  const score = passwordScore(event.target.value);
  const [colour, label] = STRENGTH[score];
  meter.querySelectorAll("span").forEach((bar, index) => {
    bar.className = `h-1 rounded-full transition ${index < score ? colour : "bg-line dark:bg-line-dark"}`;
  });
  meter.querySelector("[data-strength-label]").textContent = label;
});

// ---- Toasts (Django messages) --------------------------------------------------------
// Each toast fades and slides out after 2 seconds; × closes it straight away.

const TOAST_MS = 2000;

function scheduleToasts(root) {
  root.querySelectorAll("[data-toast]:not([data-toast-scheduled])").forEach((toast) => {
    toast.dataset.toastScheduled = "";
    setTimeout(() => {
      toast.classList.add("opacity-0", "translate-x-4");
      setTimeout(() => toast.remove(), 300);
    }, TOAST_MS);
  });
}

htmx.onLoad(scheduleToasts);

// Demo panel: clicking the email or password fills the login form; on pages without one
// (sign-up), it copies the value instead.
document.addEventListener("click", async (event) => {
  const item = event.target.closest("[data-demo-fill]");
  if (!item) return;
  const hint = item.closest("section")?.querySelector("[data-demo-hint]");
  const target = document.getElementById(item.dataset.demoFill === "login" ? "id_login" : "id_password");
  if (target) {
    target.value = item.dataset.value;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    if (hint) hint.textContent = "Filled in. Press Log in, or use the demo button.";
    return;
  }
  try {
    await navigator.clipboard.writeText(item.dataset.value);
    if (hint) hint.textContent = "Copied to the clipboard.";
  } catch (e) {
    if (hint) hint.textContent = "Select the text to copy it.";
  }
});
