# Expense Tracker Assignment

## Submission Links

- Repository: [https://github.com/abhi1202803/expense_tracker](https://github.com/abhi1202803/expense_tracker)
- Live application: [https://expense-tracker-sf2a.onrender.com](https://expense-tracker-sf2a.onrender.com)

## Overview

This is a minimal full-stack Expense Tracker built for the assignment brief.

It supports:

- creating a new expense with amount, category, optional description, and date
- viewing a list of expenses
- filtering expenses by category
- sorting expenses by newest date first
- showing the total of the currently visible expenses
- safely handling retries and refreshes to avoid duplicate expense creation

## Tech Stack

- Backend: Python standard library HTTP server
- Frontend: HTML, CSS, vanilla JavaScript
- Persistence: JSON file (`expenses.json`)
- Deployment: Render

## How It Meets The Assignment

### Backend

Implemented API endpoints:

- `POST /api/expenses`
- `GET /api/expenses`

Supported behavior:

- `POST /api/expenses` creates an expense with `amount`, `category`, `description`, and `date`
- `GET /api/expenses` supports:
  - `category=<value>`
  - `sort=date_desc`

Data model includes:

- `id`
- `amount`
- `category`
- `description`
- `date`
- `created_at`

### Frontend

Implemented UI:

- expense form
- expense list/table
- category filter
- date sort control
- visible total
- category summary view
- loading and error states

## Key Design Decisions

- **Money is stored as integer cents**  
  This avoids floating-point rounding issues and keeps money handling predictable.

- **Idempotency is handled explicitly with an idempotency key**  
  This is the most important correctness feature for the assignment because users may retry requests after slow responses, failed requests, or refreshes.

- **The frontend stores pending submissions in local storage**  
  This allows the app to recover from refreshes and safely retry the same request using the same idempotency key.

- **The backend and frontend are served from one small Python app**  
  This keeps the submission easy to run, review, and deploy.

- **Dates are stored in ISO format**  
  This makes validation straightforward and keeps sorting behavior predictable.

## Correctness Under Realistic Conditions

The assignment emphasized unreliable networks, retries, multiple clicks, and refreshes. The implementation addresses that by:

- disabling duplicate submission during an active request
- generating a unique idempotency key per submission
- reusing the same key when retrying a pending submission
- returning the original expense when the same request is retried
- rejecting reuse of the same idempotency key with a different payload

## Validation

Implemented validation:

- amount is required
- amount must be greater than zero
- amount must have at most two decimal places
- category is required
- date is required
- date must be in `YYYY-MM-DD` format
- description is optional

## Automated Tests

Included backend tests cover:

- idempotent replay for the same request
- conflict when the same idempotency key is reused with different data
- filtering and sorting behavior
- negative amount validation
- optional description handling
- missing date validation
- default listing order behavior

Run locally:

```bash
python -m unittest discover -s tests
```

## Trade-offs Made Because Of The Timebox

- I used a JSON file for persistence instead of a relational database.
  This kept the app dependency-free and quick to review, while still being durable enough for the assignment.

- I kept the stack intentionally small instead of introducing a backend framework or frontend framework.
  That reduced setup overhead and kept the core correctness logic easy to inspect.

- I focused more on request correctness and money handling than on broad feature scope.
  The assignment specifically emphasized realistic behavior and judgment, so correctness was prioritized over adding many extra features.

## What I Intentionally Did Not Do

- authentication or multi-user support
- editing or deleting expenses
- pagination
- advanced analytics/dashboarding
- a production database integration
- full production-grade persistence strategy for multi-instance hosting

## Persistence Note

The current deployed app stores data in `expenses.json`.

For an assignment demo, this keeps the project simple and easy to run.

For a more production-like deployment, I would replace this with a proper database or persistent disk-backed storage, especially on serverless or horizontally scaled platforms.

## Local Run

```bash
python server.py
```

Then open:

- [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Project Structure

- `server.py` - backend API and static file server
- `static/` - frontend files
- `tests/` - automated tests
- `render.yaml` - Render deployment configuration
- `DEPLOYMENT.md` - deployment notes

## AI Usage Note

AI-assisted tooling was used during development, as allowed by the assignment. Final implementation decisions, prioritization, and validation were guided toward the assignment's focus on correctness, money handling, retries, and maintainability.
