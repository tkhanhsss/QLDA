# Product Requirements — Task Manager (To-do) Web App

> This document is the input given to the PM agent. The PM must read it, split the work into tasks (at most 7), and assign them one by one. Every task must be small, independently testable, and have acceptance criteria that an automated test can verify.

## 1. Goal

Build a small web application for managing personal tasks. A user can create, view, update, complete, delete, filter and search tasks, through both a REST API and a simple web page.

The product is intentionally small. The priority is a working, well-tested application built step by step, not a large feature set.

## 2. Tech constraints

- Language: Python 3.11+
- Backend: FastAPI, served with uvicorn
- Database: SQLite via the standard `sqlite3` module (no ORM)
- Frontend: one static HTML file with plain CSS and vanilla JavaScript (`fetch`). No build tools, no frameworks, no CDN dependencies, so it works offline
- Tests: `pytest` with FastAPI `TestClient` (uses `httpx`)
- Lint: `ruff` must report no errors
- Allowed dependencies: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `pytest`, `ruff`. Do not add others
- No authentication, no external services, no network calls

## 3. Project layout (inside `workspace/`)

```
app/
  __init__.py
  main.py          # FastAPI app and routes
  database.py      # SQLite access
  schemas.py       # Pydantic models
static/
  index.html       # the web page (task T07)
tests/
  conftest.py      # shared fixtures (temporary database), written by the Tester
  test_T01.py ...  # one test file per task
requirements.txt
README.md
```

Run command: `uvicorn app.main:app --reload`

## 4. Testability rules (important)

These rules exist so that the Tester agent can write reliable tests and so that regression runs do not break each other.

1. The database file path must be read from the environment variable `TODO_DB_PATH` **each time a connection is opened** (default: `todo.db`). Tests set this variable to a temporary file, so every test starts with a clean database.
2. The database table must be created automatically when it does not exist: run `CREATE TABLE IF NOT EXISTS` every time a connection is opened, so a fresh temporary database always works.
3. The app object must be importable as `app.main:app` with no side effects at import time (no file creation, no database connection).
4. All error responses are JSON in FastAPI's default shape, for example `{"detail": "Task not found"}`.
5. A later task must never break the behavior of an earlier task. The full test suite is run after every task.
6. Everything under `tests/` (including `conftest.py`) is written by the Tester agent. The Coder never creates or edits tests.
7. From the product root, both `pytest tests/` and `python -m pytest tests/` must find `app` without setting `PYTHONPATH`. Include a root `pytest.ini` with `pythonpath = .` under `[pytest]` in T01.

## 5. Data model

A **Task** has:

| Field | Type | Rules |
|-------|------|-------|
| `id` | integer | Auto-increment primary key |
| `title` | string | Required. Leading and trailing spaces are trimmed. After trimming it must be 1 to 100 characters |
| `done` | boolean | Default `false` |
| `created_at` | string | ISO 8601 timestamp set by the server when the task is created |

## 6. Functional requirements

### FR-1 Health check
- `GET /health` returns HTTP 200 with body `{"status": "ok"}`.

### FR-2 Create a task
- `POST /tasks` with JSON `{"title": "Buy milk"}` returns HTTP 201 and the created task (`id`, `title`, `done`, `created_at`).
- `done` is `false` for a new task.
- Missing title, empty title, whitespace-only title, or title longer than 100 characters after trimming returns HTTP 422 and does not save anything.
- Leading and trailing spaces in the title are trimmed before saving.

### FR-3 View tasks
- `GET /tasks` returns HTTP 200 and a JSON list of all tasks, newest first (highest `id` first). An empty database returns `[]`.
- `GET /tasks/{id}` returns HTTP 200 and the task, or HTTP 404 with `{"detail": "Task not found"}` if it does not exist.

### FR-4 Update a task
- `PATCH /tasks/{id}` accepts a partial JSON body with `title` and/or `done`. Only the provided fields change.
- Returns HTTP 200 and the updated task.
- The same title rules as FR-2 apply; invalid title returns HTTP 422 and the task is unchanged.
- An empty body `{}` returns HTTP 422.
- An unknown id returns HTTP 404.
- `created_at` and `id` can never be changed.

### FR-5 Delete a task
- `DELETE /tasks/{id}` returns HTTP 204 with no body.
- After deletion, `GET /tasks/{id}` returns 404.
- Deleting the same id again returns HTTP 404.

### FR-6 Filter and search
- `GET /tasks?status=done` returns only completed tasks; `?status=todo` returns only uncompleted tasks; no `status` returns all.
- Any other `status` value returns HTTP 422.
- `GET /tasks?q=milk` returns tasks whose title contains the text, case-insensitive.
- `status` and `q` can be combined.
- Results keep the newest-first order.

### FR-7 Web page
- `GET /` returns HTTP 200 with the HTML page (`static/index.html`), content type `text/html`.
- The page language is Vietnamese. Required visible texts:
  - Page heading: `Quản lý công việc`
  - Add button: `Thêm`
  - Empty state: `Chưa có công việc nào`
- Required elements, with these exact `id` attributes (so tests can check them):
  - `task-form` (a form), `task-input` (text input, `maxlength="100"`), `task-list` (the list container)
  - `filter-all`, `filter-todo`, `filter-done` (filter buttons), `search-input` (search box)
- The page uses the API above through `fetch`. Behavior:
  - Submitting the form creates a task and shows it at the top of the list without reloading the page.
  - Each task row has a checkbox to toggle `done` and a delete button. Completed tasks show the title with a line-through style.
  - The filter buttons and the search box filter the list using the `status` and `q` query parameters.
  - If the API returns an error, show a short error message on the page.
- Layout: single centered column, readable on a phone and a desktop screen, simple clean style. A Designer agent defines the exact look before coding.

## 7. Suggested task breakdown

The PM may adjust this, but must keep tasks small, ordered by dependency, and at most 7 in total.

| ID | Task | Needs UI design |
|----|------|-----------------|
| T01 | Project skeleton, `GET /health`, `requirements.txt`, `README.md`, `pytest.ini` | No |
| T02 | Database layer and `POST /tasks` (FR-2) | No |
| T03 | `GET /tasks` and `GET /tasks/{id}` (FR-3) | No |
| T04 | `PATCH /tasks/{id}` (FR-4) | No |
| T05 | `DELETE /tasks/{id}` (FR-5) | No |
| T06 | Filter and search (FR-6) | No |
| T07 | Web page (FR-7) | Yes |

Each task description from the PM must contain: a title, a short explanation, a list of acceptance criteria copied or derived from the requirements above, and whether it needs a UI design.

## 8. Out of scope

User accounts and login, due dates, priorities, tags, pagination, drag and drop, real-time sync, deployment, Docker, database migrations, any non-Vietnamese UI language.

## 9. Definition of done (whole product)

- All tasks reach DONE with a passing test report. A task stuck after 3 revision rounds is marked BLOCKED and reported.
- `pytest tests/` passes completely, including the regression run.
- `ruff check .` reports no errors.
- `uvicorn app.main:app` starts, and the web page at `/` works: add, complete, delete, filter and search all behave as described.
- `README.md` explains how to install dependencies, run the app, and run the tests.
