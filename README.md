# AI Smart Saver

AI Smart Saver is a multi-profile budgeting app built with Python and Flet. It supports local or PostgreSQL-backed storage, web access for phone testing, AI-assisted finance chat, recurring transactions, dashboard analytics, and a lightweight RAG pipeline backed by PostgreSQL and `pgvector`.

## Features

- Multi-profile budgeting with user passwords and admin mode
- Dashboard cards for balance, budgets, recurring items, charts, ML insights, and AI chat
- Income and expense tracking with filters, edit/delete, and CSV export
- Recurring transaction automation with upcoming bill visibility
- AI finance assistant with per-profile chat history
- Retrieval-augmented answers over financial history
- scikit-learn anomaly detection and spending forecast cards
- Docker setup for app + PostgreSQL + `pgvector`
- Responsive Flet web UI for desktop and mobile browsers

## Stack

- Python 3.10+
- Flet
- PostgreSQL / SQLite
- `pgvector`
- scikit-learn
- pandas / numpy
- matplotlib
- Docker / Docker Compose
- Ollama and Anthropic integration

## Project Structure

- [main.py](/C:/Users/jinsa/ai-budget-tracker/main.py) - app entrypoint
- [backend](/C:/Users/jinsa/ai-budget-tracker/backend) - database, chat, RAG, and backend helpers
- [ui](/C:/Users/jinsa/ai-budget-tracker/ui) - Flet screens and shared UI helpers
- [assets](/C:/Users/jinsa/ai-budget-tracker/assets) - app icons and web assets
- [ai_insights.py](/C:/Users/jinsa/ai-budget-tracker/ai_insights.py) - AI response orchestration
- [ml_engine.py](/C:/Users/jinsa/ai-budget-tracker/ml_engine.py) - local ML models
- [set_admin_password.py](/C:/Users/jinsa/ai-budget-tracker/set_admin_password.py) - helper for updating the master admin password in PostgreSQL

## Local Run

Desktop mode:

```powershell
.\venv\Scripts\flet.exe run main.py
```

Web mode:

```powershell
.\venv\Scripts\flet.exe run --web --host 0.0.0.0 --port 8550 main.py
```

## PostgreSQL Mode

Set `DATABASE_URL` before starting the app:

```powershell
$env:DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/ai_budget_tracker"
```

Optional for Docker-hosted Ollama access:

```powershell
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
```

Then run the app in desktop or web mode.

More database notes are in [POSTGRES_FASTAPI_SETUP.md](/C:/Users/jinsa/ai-budget-tracker/POSTGRES_FASTAPI_SETUP.md).

## Docker

Build and run the web app with PostgreSQL:

```powershell
docker compose up --build
```

This exposes:

- `http://localhost:8550` for the Flet web app
- `localhost:5432` for PostgreSQL

If you also want the API container:

```powershell
docker compose --profile api up --build
```

That also exposes:

- `http://localhost:8000` for FastAPI

More details are in [DOCKER_SETUP.md](/C:/Users/jinsa/ai-budget-tracker/DOCKER_SETUP.md).

## AI and RAG Notes

- AI chat history is stored per profile
- Exact values like balances and monthly totals still come from app logic and DB queries
- Retrieval is used for historical context and semantic finance questions
- PostgreSQL can use `pgvector` for the vector search path
- If `pgvector` is unavailable, the app falls back to a non-vector retrieval path

## Admin Password

The app supports a master admin password stored in PostgreSQL.

Update it with:

```powershell
py set_admin_password.py
```

If you publish or share this project, change your local credentials and passwords first.

## Notes

- SQLite is still useful for solo local usage
- PostgreSQL is the better fit for shared/browser access
- Exported CSV files are meant to be user downloads, not committed artifacts
