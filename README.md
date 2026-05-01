# Expense Tracker

A minimal full-stack expense tracker built for the assignment brief. It includes:

- An idempotent `POST /api/expenses` API
- A `GET /api/expenses` API with category filtering and `date_desc` sorting
- A simple browser UI for creating, viewing, filtering, sorting, and totaling expenses
- Small automated tests around correctness-sensitive behavior

## Tech choices

- **Python standard library + JSON file persistence**: keeps the stack lightweight, easy to run locally, and durable across refreshes and restarts without extra services.
- **Integer cents for money**: avoids floating-point rounding problems while still supporting real currency values.
- **Vanilla HTML/CSS/JS frontend**: small enough for the scope, with no install step required.

## Idempotency strategy

The main correctness risk in this assignment is duplicate expense creation when a client retries after a timeout, refresh, or repeated clicks.

To handle that:

- `POST /api/expenses` accepts an `Idempotency-Key` header.
- The backend stores that key with the created expense.
- A retry with the same key and the same payload returns the original expense instead of creating a duplicate.
- A retry with the same key but a different payload is rejected with `409 Conflict`.
- The frontend stores an in-flight submission in `localStorage`, so a refresh can safely retry with the same key.

## API

### `POST /api/expenses`

Create a new expense.

Headers:

- `Content-Type: application/json`
- `Idempotency-Key: <unique-client-key>`

Body:

```json
{
  "amount": "125.50",
  "category": "Food",
  "description": "Lunch",
  "date": "2026-04-30"
}
```

Example success response:

```json
{
  "expense": {
    "id": "uuid",
    "amount": "125.50",
    "category": "Food",
    "description": "Lunch",
    "date": "2026-04-30",
    "created_at": "2026-05-01T10:00:00Z"
  },
  "idempotency_replay": false
}
```

### `GET /api/expenses`

Optional query parameters:

- `category=Food`
- `sort=date_desc`

## Validation

Implemented:

- amount must be greater than zero
- amount must have at most two decimal places
- category is required
- description is optional
- date is required and must be `YYYY-MM-DD`

## Running locally

```bash
python server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If you want to use the bundled runtime that is already available in this environment:

```bash
C:\Users\abhis\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe server.py
```

## Running tests

```bash
python -m unittest discover -s tests
```

## Repository-ready structure

This folder is ready to be used as the assignment repository root:

- `server.py` contains the backend API and static file server
- `static/` contains the frontend
- `tests/` contains automated backend tests
- `README.md` documents design decisions, trade-offs, and run instructions

## Deployment note

Because the app uses only the Python standard library, it can be deployed on simple Python hosts with a start command such as:

```bash
python server.py --host 0.0.0.0 --port $PORT
```

If the host injects `PORT` as an environment variable, the small code change below is the only thing you may want before deploying:

- pass the platform port into `server.py`
- commit the project to GitHub
- connect the repo to a host such as Render, Railway, or Fly.io

This local environment does not have external deployment access, so the live public link still has to be created outside this session.

## Design decisions

- I used one small server that serves both the API and static frontend to keep the submission easy to run and review.
- Expense dates are stored as ISO strings, which makes them easy to validate and sort consistently.
- Money is stored as integer cents in the persistence layer and formatted back to a string for API responses.
- The frontend always requests `sort=date_desc` so the UI matches the acceptance criteria.

## Trade-offs

- I kept authentication and multi-user support out of scope.
- The backend uses the idempotency-key pattern explicitly rather than trying to infer duplicates from expense fields, because inferring duplicates can incorrectly collapse legitimate repeated expenses.
- In this environment I used a simple JSON-file store instead of a relational database so the app stays dependency-free and easy to run.

## Intentionally not done

- No external component library or frontend framework
- No live deployment from this local environment
- No pagination, editing, or deletion of expenses

## Submission notes

The assignment asks for both a repository link and a live deployment link. This project is ready to be committed to a repository, but it has not been deployed from this environment.
