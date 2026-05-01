# Deployment Guide

This project is intentionally lightweight and does not need external packages.

## Recommended host

Any basic Python host will work. Good low-friction options:

- Render
- Railway
- Fly.io

## Start command

```bash
python server.py --host 0.0.0.0 --port $PORT
```

## Suggested deployment steps

1. Create a GitHub repository and push this project.
2. Create a new web service on your host.
3. Point it at the repository.
4. Use the start command above.
5. After deploy, open the public URL and verify:
   - creating an expense works
   - retrying a submission does not duplicate it
   - filtering and sorting still work
   - total and category summary update correctly

## Notes

- Data persistence is file-based in `expenses.json`.
- For a true multi-instance production setup, move persistence to a managed database.
- For this assignment, the current setup keeps the app easy to run and easy to review.
