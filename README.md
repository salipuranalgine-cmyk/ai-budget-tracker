# AI Smart Saver - Budget Guardian

AI Smart Saver is a multi-profile budgeting app built with Python and Flet. It supports local or PostgreSQL-backed storage, web access for phone testing, AI-assisted finance chat, recurring transactions, dashboard analytics, scikit-learn insights, and a lightweight RAG pipeline backed by PostgreSQL and `pgvector`.

## Screenshots

<img width="1680" height="969" alt="AI Smart Saver - Budget Guardian - Brave 4_30_2026 1_36_46 PM" src="https://github.com/user-attachments/assets/b212c2ce-3996-4718-a77d-a385067baf7e" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_22 PM" src="https://github.com/user-attachments/assets/48c2217e-9b3b-485d-beea-8433ded7e9e2" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_42 PM" src="https://github.com/user-attachments/assets/075b431e-b195-4e41-a37e-6c00cb2f1c5d" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_48 PM" src="https://github.com/user-attachments/assets/ea295c51-3980-4a0d-b8a1-c962fdf3673d" />

## Features

- Multi-profile budgeting with user passwords and admin mode
- Responsive dashboard with draggable, expandable cards
- Income and expense tracking with filters, edit/delete, and CSV export
- Recurring transaction automation with upcoming bill visibility
- AI finance assistant with per-profile chat history
- Retrieval-augmented answers over financial history
- scikit-learn anomaly detection and spending forecast cards
- Notifications for budgets, bills, and AI insights
- Docker setup for app + PostgreSQL + `pgvector`
- Responsive Flet web UI for desktop and mobile browsers

## Feature Overview

### Dashboard

- Balance overview with income, spending, and savings rate
- Drag-and-drop card reordering saved per profile
- Expandable analytics and summary cards
- Budget, recurring, ML, and AI cards in one place
- Quick `+ Income` and `+ Expense` actions

### Transactions

- One-time and recurring income/expense entries
- Filters by keyword, category, and date range
- Edit/delete flows and scheduled future transactions
- Case-insensitive search

### Budgets

- Category-based limits with custom date ranges
- Progress tracking with warning and exceeded states
- Remaining-days and expired-period visibility

### AI Finance Advisor

- Multi-turn chat with saved history per profile
- Local Ollama or online Anthropic support
- Smart / Online First / Offline First response modes
- AI-generated notifications and insights
- Retrieval-backed answers for historical financial context

### ML Engine

- `IsolationForest` anomaly detection for flagged transactions
- `LinearRegression` spending forecasts per category
- Reliability indicators and retrain scheduling
- Manual retrain control from Settings

### Multi-User Profiles

- Separate profiles with isolated data
- Emoji or imported photo avatars
- Admin mode for edit/delete/support access

## Tech Stack

- Python 3.10+
- Flet
- PostgreSQL / SQLite
- `pgvector`
- scikit-learn
- pandas / numpy
- matplotlib
- FastAPI
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

Set the master admin password immediately after setup:

```powershell
py set_admin_password.py
```

## Notes

- SQLite is still useful for solo local usage
- PostgreSQL is the better fit for shared/browser access
- Exported CSV files are meant to be user downloads, not committed artifacts
