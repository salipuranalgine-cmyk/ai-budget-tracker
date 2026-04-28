# PostgreSQL + FastAPI Setup

This project now supports two storage modes:

- `SQLite` as the default local desktop mode
- `PostgreSQL` when `DATABASE_URL` is set, which is the mode you want for phone access

## 1. Install server dependencies

```bash
pip install -r requirements-server.txt
```

## 2. Point the app to PostgreSQL

Windows PowerShell:

```powershell
$env:DATABASE_URL="postgresql://postgres:your_password@localhost:5432/ai_budget_tracker"
```

Windows CMD:

```cmd
set DATABASE_URL=postgresql://postgres:your_password@localhost:5432/ai_budget_tracker
```

There is also an example in [.env.example](/C:/Users/jinsa/ai-budget-tracker/.env.example).

## 3. Migrate your existing SQLite data

```bash
python migrate_sqlite_to_postgres.py
```

What gets migrated:

- shared users and app state from `users.db`
- each per-user budget database in `user_data/`
- transactions, budgets, recurring items, notifications, chat history, and app metadata

## 4. Run the FastAPI server

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /users`
- `POST /users`
- `GET /users/{user_id}/summary`
- `GET /users/{user_id}/transactions`
- `POST /users/{user_id}/transactions`
- `PUT /users/{user_id}/transactions/{txn_id}`
- `DELETE /users/{user_id}/transactions/{txn_id}`

## 5. Connect from your phone

- If your phone is on the same Wi-Fi, use your PC's LAN IP like `http://192.168.x.x:8000`
- If you want access outside your home network, the safer next step is deploying the API to a cloud host instead of exposing your PC directly

## Notes

- The desktop Flet app still works. If `DATABASE_URL` is set, it uses PostgreSQL instead of SQLite.
- In PostgreSQL mode, each app profile gets its own schema such as `budget_user_1`, which lets the current desktop code keep working while the backend becomes shared.
- FastAPI is the backend/API layer only. A true phone app or mobile web UI would still be the next step after this server layer.
