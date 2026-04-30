# AI Smart Saver — Budget Guardian

> A full-stack personal finance tracker built with Python + Flet, featuring AI-powered chat, scikit-learn ML forecasting and anomaly detection, multi-user profiles, recurring transactions, drag-and-drop dashboards, and both desktop and phone-accessible web modes.

---

## Screenshots
<img width="1680" height="969" alt="AI Smart Saver - Budget Guardian - Brave 4_30_2026 1_36_46 PM" src="https://github.com/user-attachments/assets/b212c2ce-3996-4718-a77d-a385067baf7e" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_22 PM" src="https://github.com/user-attachments/assets/48c2217e-9b3b-485d-beea-8433ded7e9e2" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_42 PM" src="https://github.com/user-attachments/assets/075b431e-b195-4e41-a37e-6c00cb2f1c5d" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_10_48 PM" src="https://github.com/user-attachments/assets/ea295c51-3980-4a0d-b8a1-c962fdf3673d" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_11_28 PM" src="https://github.com/user-attachments/assets/6fb6e458-6036-4fad-a21a-b26e2beb3ca3" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_11_55 PM" src="https://github.com/user-attachments/assets/9c9566bf-668d-47d2-b480-438944a46482" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_12_01 PM" src="https://github.com/user-attachments/assets/e90841ff-e3f2-4d60-b8cc-9873f72c5592" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_12_18 PM" src="https://github.com/user-attachments/assets/75d2172f-f366-4ee0-b07d-4233db4cf1ea" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_06 PM" src="https://github.com/user-attachments/assets/364f0b5a-55e5-4e84-87ed-e4d09c0119bb" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 9_54_45 PM" src="https://github.com/user-attachments/assets/fee253b3-e6bd-4558-a3b3-27068c48621f" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 9_54_58 PM" src="https://github.com/user-attachments/assets/ff94aa65-d06c-444a-8a37-910cf0fd7587" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_36 PM" src="https://github.com/user-attachments/assets/8a579961-3e4a-4eb0-99ac-4414f7174ee4" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_23_49 PM" src="https://github.com/user-attachments/assets/6ad7bd61-9c82-49db-aee8-25f591d9a0ca" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_28_2026 11_07_10 AM" src="https://github.com/user-attachments/assets/17800db5-756f-423c-8da2-deefbef73b87" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_28_2026 11_01_16 AM" src="https://github.com/user-attachments/assets/19a46c6d-20f8-483f-9ffe-fec0764cdbcf" />
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_28_2026 11_01_00 AM" src="https://github.com/user-attachments/assets/22210ce8-9653-45c7-a5d2-ccb3f3c19575" />


---

## What It Does

AI Smart Saver lets you track every peso (or any currency) that comes in and goes out — across multiple password-protected profiles, with smart automation and real machine learning built in.

- Log income and expenses with one-time or recurring schedules
- Set budget limits per category and get warned before you overspend
- Get AI-powered financial advice from a built-in chat assistant
- Let scikit-learn predict next month's spending and flag unusual transactions
- Run the whole thing offline as a desktop app, or share access over Wi-Fi as a web app

---

## Feature Overview

### Dashboard
- Balance hero card with income, spending, and savings rate at a glance
- Drag-and-drop card reordering — your layout is saved per profile
- Clickable cards that expand into a full detail view
- Upcoming bills, budget progress bars, spending charts, and ML cards all in one place
- Quick **+ Income** and **+ Expense** action buttons

### Transactions
- One-time and recurring transactions (daily, weekly, bi-weekly, monthly, yearly, or custom interval)
- Recurring entries auto-apply on app startup when they come due
- Filter by keyword, category, and date range
- Running balance shown per transaction
- Schedule future transactions — balance updates on the effective date
- Edit or delete any entry; edit and resend in AI chat

### Budgets
- Set per-category spending limits with a custom date range
- Progress bars with color-coded status (green → yellow → orange → red)
- Days-remaining counter and overdue detection

### Charts and Analytics
- Daily spending trend (last 30 days, area line chart)
- Cashflow pulse — income vs spend bar chart across the last 6 months
- Category donut breakdown
- Top categories horizontal bar chart
- Weekday spending rhythm chart
- Month-by-month cashflow table

### AI Finance Advisor
- Multi-turn chat with full conversation history saved per profile
- Works offline via [Ollama](https://ollama.com/) or online via the Anthropic API
- Three provider modes: Smart, Online First, Offline First
- AI can trigger persistent notifications for budget alerts and bill reminders using structured tags
- Chat history manager with search, rename, bulk delete, and storage usage display

### ML Engine (scikit-learn)
Two models trained on your own spending data and stored per-profile on disk:

| Model | Algorithm | What it does | Minimum data |
|-------|-----------|--------------|--------------|
| Anomaly Detector | IsolationForest | Flags transactions that look unusual compared to your normal patterns | 12 for live scan, 30 for full model |
| Spending Forecaster | LinearRegression | Predicts next month's spend per category with trend arrows (↑ ↓ →) | 3 months of history per category |

- Auto-retrain scheduler (Daily / Weekly / Monthly) — runs in a background thread on startup
- Manual **Retrain Now** button in Settings
- Reliability % badges so you know how much to trust each prediction

### Notifications
- Persistent notification inbox with unread badge on the bell icon
- Budget warning (80%+) and exceeded (100%+) alerts auto-generated on data change
- Upcoming bill alerts for overdue, today, and within 3 days
- AI-generated insight notifications
- Mark read, mark all read, delete, bulk delete, clear all

### Multi-User Profiles
- Separate password-protected profiles, each with isolated data
- Emoji or imported photo avatars
- Admin mode for profile management (edit, delete, bypass password)
- Last active user remembered for fast re-entry

### Settings
- 17-currency support with correct symbols and decimal places
- Anthropic API key storage (masked in UI)
- AI response mode toggle
- ML retrain schedule control and status dialog
- CSV export of full transaction history
- Dark / light theme toggle

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI Framework | [Flet](https://flet.dev/) — Flutter-based Python UI |
| Language | Python 3.10+ |
| Database | SQLite (local) / PostgreSQL (shared/web mode) |
| Anomaly Detection | scikit-learn `IsolationForest` |
| Spending Forecast | scikit-learn `LinearRegression` |
| Model Persistence | `joblib` |
| Data Processing | `pandas`, `numpy` |
| Charts | `matplotlib` (Agg backend, embedded as base64 PNG) |
| AI — Offline | [Ollama](https://ollama.com/) local LLM |
| AI — Online | Anthropic Claude API (`claude-haiku-4-5`) |
| Date Math | `python-dateutil` (relativedelta) |
| API Server | FastAPI + Uvicorn |
| Containerization | Docker + Docker Compose |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip

### Install and Run (Desktop)

```bash
# Clone the repo
git clone https://github.com/salipuranalgine-cmyk/ai-budget-tracker.git
cd ai-budget-tracker

# Create and activate a virtual environment (recommended)
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the desktop app
flet run main.py
```

### Run as a Web App (phone-friendly)

```powershell
# Windows — set execution policy if needed
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1

# Start the web server
.\venv\Scripts\flet.exe run --web --host 0.0.0.0 --port 8550 main.py
```

Then open on your PC: `http://127.0.0.1:8550`  
Or on your phone (same Wi-Fi): `http://192.168.x.x:8550`

---

## Docker (Web + PostgreSQL)

Starts the Flet web app and a PostgreSQL database together:

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Flet web app | `http://localhost:8550` |
| PostgreSQL | `localhost:5432` |

To also start the FastAPI backend:

```bash
docker compose --profile api up --build
```

| Service | URL |
|---------|-----|
| FastAPI | `http://localhost:8000` |
| API docs | `http://localhost:8000/docs` |

---

## PostgreSQL Mode

For shared access (multiple devices on the same network, phone-friendly):

```powershell
# Windows PowerShell
$env:DATABASE_URL="postgresql://postgres:your_password@127.0.0.1:5432/ai_budget_tracker"
flet run --web --host 0.0.0.0 --port 8550 main.py
```

To migrate existing SQLite data to PostgreSQL:

```bash
python migrate_sqlite_to_postgres.py
```

See [POSTGRES_FASTAPI_SETUP.md](POSTGRES_FASTAPI_SETUP.md) for the full guide.

---

## Setting Up AI

### Option A — Offline AI with Ollama (no internet required after setup)

1. Download and install [Ollama](https://ollama.com/download)
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. The app will detect Ollama automatically on next launch.

### Option B — Online AI with Anthropic (faster on low-end PCs)

1. Create an account at [console.anthropic.com](https://console.anthropic.com)
2. Generate an API key starting with `sk-ant-`
3. Paste it in **Settings → AI Setup → Online AI**

You can combine both — set **AI Response Mode** to **Smart** and the app picks the fastest available option automatically.

---

## Enabling ML Predictions

The ML engine starts learning from your own data automatically. No setup required.

| Feature | Activates when you have... |
|---------|--------------------------|
| Live anomaly scan | 12+ expense transactions |
| Full anomaly model | 30+ expense transactions |
| Spending forecast | 3+ months of data per category |

Retraining runs in the background on startup based on your chosen schedule (Daily / Weekly / Monthly). You can also trigger **Retrain Now** anytime from **Settings → ML Engine Status**.

---

## REST API

When running with `--profile api`, FastAPI is available at `http://localhost:8000`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/users` | List all profiles |
| POST | `/users` | Create a profile |
| GET | `/users/{id}/summary` | Balance and totals for a user |
| GET | `/users/{id}/transactions` | List transactions (filterable) |
| POST | `/users/{id}/transactions` | Add a transaction |
| PUT | `/users/{id}/transactions/{txn_id}` | Update a transaction |
| DELETE | `/users/{id}/transactions/{txn_id}` | Delete a transaction |

Interactive docs: `http://localhost:8000/docs`

---

## Admin Password

The default master admin password is `Salipuran321`. Change it immediately after setup:

```bash
python set_admin_password.py
```

Or directly in PostgreSQL:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO app_state(key, value)
VALUES (
  'master_admin_password_hash',
  encode(digest('your_new_password', 'sha256'), 'hex')
)
ON CONFLICT (key)
DO UPDATE SET value = EXCLUDED.value;
```

---

## Data Privacy

- All budget data is stored in local SQLite files on your device by default.
- ML models (scikit-learn) run 100% locally — your spending history is never sent anywhere for ML processing.
- If you use cloud AI (Anthropic), only the message you send goes over the internet.
- PostgreSQL mode keeps data on your own server.

---

## Roadmap

- [ ] Android APK via Flet mobile packaging
- [ ] Per-category spending trend graphs over time
- [ ] More ML models (clustering for auto-category tagging)
- [ ] Savings goal tracker with progress visualization
- [ ] Export to Excel in addition to CSV

---

## License

MIT — feel free to use, modify, and build on this project.
