# TaskForge code tour

A guided walk through the code, so you can explain and change any part of it. Each section
follows one feature from the URL to the database and points at the files involved.

## Map of the project

| Folder | What lives there |
| --- | --- |
| `config/` | Settings (`base`, `dev`, `test`, `prod`), the root URL list, WSGI |
| `accounts/` | Custom `User` (email login, no username), sign-up form, demo login |
| `projects/` | Projects, memberships, **permissions**, dashboard data, covers, search, `seed_demo` |
| `tasks/` | Tasks, comments, the Kanban board, filters, CSV export, My tasks |
| `activity/` | The activity feed and the notifications bell |
| `templates/` | `base.html`, shared components, allauth (login/sign-up) overrides |
| `assets/tailwind.css` | Design tokens and shared CSS classes (compiled by the Tailwind CLI) |
| `static/js/app.js` | The only hand-written JavaScript (~200 lines): modal, drag and drop, toasts |
| `tests/` | 300 pytest tests and `factories.py` |

**Rule of thumb:** views stay thin. They check permissions, read the form, call a function
in `services.py`, and choose a template. Business rules live in `services.py`.

## 1. One request, start to finish: dragging a card

1. **Browser.** SortableJS fires `onEnd` (`static/js/app.js`, `initBoard`). It sends
   `htmx.ajax("POST", card.dataset.moveUrl, {status, position})`. The CSRF token comes from
   `hx-headers` on `<body>` in `templates/base.html`.
2. **URL.** `config/urls.py` includes `tasks/urls.py`, so `projects/<project_pk>/tasks/<pk>/move/`
   resolves to `tasks.views.task_move`.
3. **Permissions.** `task_move` calls `get_task()`, which calls
   `projects.permissions.get_membership()`. A non-member gets a 404 before any data is touched.
4. **Validation.** Bad `status` or `position` values return 400.
5. **Business logic.** `tasks.services.move_task()`:
   - locks the project's tasks with `select_for_update()`, so two people dragging at once can't
     produce duplicate positions
   - inserts the task at its new index and renumbers the column 0, 1, 2…
   - closes the gap in the old column
   - logs a "moved" entry with `activity.services.log()`
6. **Response.** An empty `204` with `HX-Trigger: boardChanged`. The board `<div>` in
   `tasks/templates/tasks/partials/board.html` listens with
   `hx-trigger="boardChanged from:body"` and reloads itself from the server.

Why re-render instead of trusting the browser? The database stays the single source of truth:
what you see is always what was saved.

## 2. Permissions (`projects/permissions.py`)

- `get_membership(user, project_id, owner_only=False)` is the **only** place access is decided.
- Not a member: **404**. A 403 would leak that the project exists.
- A member, but not the owner, on an owner action (edit, delete, invite, cover): **403**.
- `ProjectMemberMixin` / `ProjectOwnerMixin` wrap it for class-based views; function views call
  it directly.
- Tasks are always fetched *inside* the user's project (`get_task`), so a valid task id can't
  be reached through another project's URL.
- `tests/test_projects_permissions.py` and `tests/test_tasks_permissions.py` list every URL in a
  table and check logged out, non-member and non-owner for each.

## 3. HTMX patterns used everywhere

| Pattern | Example |
| --- | --- |
| Return a partial instead of a page | `BoardView.get_template_names()` checks `is_htmx(request)` |
| Swap a part of the page | Invite form: `hx-target="#members" hx-swap="outerHTML"` |
| Modal | Load into `#modal` with `hx-swap="innerHTML"`; `app.js` closes it |
| Tell the page something changed | `HX-Trigger: {"boardChanged": null, "closeModal": null}` |
| Update a second area | Out-of-band swap: the Export CSV link, the notification badge |
| Work without JavaScript | Every form has a normal `action`; views redirect when not HTMX |

**A bug worth knowing about:** htmx attributes are *inherited*. `#board` uses
`hx-swap="outerHTML"`, so the cards inside it inherited it, and opening a task replaced
`#modal` instead of filling it, which broke the × button. The fix was `hx-disinherit="*"` plus
an explicit `hx-swap` on each modal opener, with a regression test in `tests/test_tasks_views.py`.

## 4. Avoiding N+1 queries

- The board loads all tasks in one query (`select_related("assignee")`,
  `annotate(Count("comments"))`) and groups them into columns in Python (`board_columns`).
- `projects/dashboard.py` gathers the whole dashboard in a fixed set of queries.
  `Count(..., filter=Q(...), distinct=True)` avoids double counting when two joins multiply rows.
- Tests use `django_assert_num_queries` to prove the counts stay fixed as data grows: board 7,
  filtered board 4, dashboard 8.

## 5. Accounts

- `accounts/models.py`: `USERNAME_FIELD = "email"`, `username = None`, and a custom
  `UserManager`, because the default manager needs a username.
- Login and sign-up are django-allauth views with custom templates:
  `templates/account/login.html`, `templates/account/signup.html` and the full-page layout in
  `templates/allauth/layouts/entrance.html`.
- `accounts/forms.SignupForm` adds a full name. "Remember me" is allauth's `remember` field,
  drawn as a switch.
- **Demo login:** `accounts/demo.py` finds the demo user, `accounts/views.demo_login` logs in
  with one POST, and `seed_demo --if-missing` creates the account on first start.
- **Google:** shown only when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set
  (`accounts/context_processors.py`).

## 6. Settings and running it

- `config/settings/base.py` reads everything secret from the environment (django-environ).
- `docker-compose.yml` has safe development defaults, so `docker compose up` needs no `.env`.
- `scripts/dev-entrypoint.sh`: builds the CSS, migrates, seeds the demo once, then runs
  `runserver`.
- `prod.py` adds HTTPS/HSTS and secure cookies, and **refuses to start** with the placeholder
  `SECRET_KEY`. CI runs `manage.py check --deploy` on every push.

## Practice questions (and where to look)

1. *How do you stop a user seeing another team's project?* `projects/permissions.py`, section 2.
2. *Why 404 instead of 403?* Section 2.
3. *What happens when two people drag the same card at once?* `move_task`, `select_for_update`.
4. *How does the board update without a page reload?* Section 1, `HX-Trigger`.
5. *How did you find and fix an N+1 problem?* Section 4 and `test_board_query_count_*`.
6. *Why HTMX and not React?* README → Architecture and decisions.
7. *Where does business logic live, and why?* `services.py` in each app.
8. *How are uploads validated?* `projects/models.py`: `ImageField`, `FileExtensionValidator`,
   `validate_cover_size`. Tests in `tests/test_covers.py`.
9. *How do you keep secrets out of git?* `.env` is git-ignored, `.env.example` is committed, and
   `prod.py` guards the key.
10. *How is coverage measured and shown?* `pyproject.toml` (`[tool.coverage]`), CI fails under
    70%, and the badge is published from CI to the `badges` branch.

**A good exercise:** pick one question, delete the code it points at, and rebuild it from memory.
