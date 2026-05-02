# AI Smart Saver

<<<<<<< HEAD
A multi-user budget tracker built with Python and Flet, with PostgreSQL support, Docker support, AI chat assistance, recurring transactions, budget monitoring, and a phone-friendly web mode.
=======
A personal budget tracking desktop app built with **Python + Flet**, featuring AI-powered multi-turn chat, a scikit-learn ML engine for anomaly detection and spending forecasts, drag-and-drop dashboard cards, a full notification hub, recurring transaction automation, multi-currency support, and a clean dark/light UI.
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

## What this project does

- Tracks income and expenses by profile
- Supports password-protected user profiles
- Runs in desktop mode or web mode
- Uses SQLite locally or PostgreSQL for shared access
- Includes recurring transactions and budget limit monitoring
- Includes an AI finance chat assistant with saved history
- Supports mobile testing through the Flet web build

## Main features

<<<<<<< HEAD
### Multi-user profiles
=======
### 🏠 Dashboard
- At-a-glance overview of balance, total income, and total expenses
- Starting balance support — set your initial cash before tracking begins
- Upcoming recurring bills widget (due within the next few days)
- Quick **+ Income** and **+ Expense** action buttons
- **Drag-and-drop card reordering** — rearrange every dashboard module to match your workflow; the order is saved per user and restored on next launch
- **Clickable / expandable cards** — tap any card header to expand it for a deeper view
- Smooth animated card swaps (ease-out cubic transitions)
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

- Create separate profiles for different people
- Add emoji or imported image avatars
- Protect profiles with user passwords
- Switch into admin mode for profile management
- Open a user profile directly as admin when support is needed

### Budget tracking

- Add income and expenses
- Filter and edit transactions
- Export data to CSV
- Track category limits and warnings
- View summaries and charts on the dashboard

### Recurring transactions

- Add recurring income or expenses
- Auto-apply due recurring entries
- See upcoming recurring items on the dashboard

<<<<<<< HEAD
### AI advisor
=======
### 🧠 ML Engine (scikit-learn)
Budget Guardian includes a lightweight but real machine learning layer powered by scikit-learn. Models are trained on your own spending data and stored per-user on disk using joblib.

#### Anomaly Detector (IsolationForest)
- Learns what a "normal" transaction looks like for you based on amount, day of week, and day of month
- Flags unusual transactions as **High / Medium / Low** suspicion
- Results appear as the **Flagged Transactions** card on the dashboard
- Minimum threshold: 12 transactions for live detection, 30 for a full trained model
- Includes a **Reliability %** badge so you know how much to trust the results

#### Spending Forecaster (Linear Regression)
- Fits a trend line through your monthly per-category spending history
- Predicts what you're likely to spend next month in each category
- Trends shown as **↑ Up / ↓ Down / → Stable** with color-coded bars (red/green/blue)
- Results appear as the **Next Month Forecast** bar chart on the dashboard
- Minimum threshold: 3 months of history per category

#### Auto-Retrain Scheduler
- Automatically retrains both models in a background thread on app startup when the schedule is due
- Schedule options: **Daily / Weekly (default) / Monthly**
- Configurable from **Settings → ML Engine**
- Last retrain date and next retrain date shown in the ML status dialog
- Manual **Retrain Now** button available anytime

### 🌍 Multi-Currency Support
Supports 17 currencies with correct symbols and decimal places:
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

- Ask budget questions in a chat interface
- Save chat history per profile
- Continue conversations across sessions
- Use local Ollama or Anthropic depending on configuration

<<<<<<< HEAD
### Web and mobile access
=======
### ⚙️ Settings
- Switch currency at any time
- Save / update your Anthropic API key (stored locally, masked in the UI)
- Choose AI provider mode (Smart / Online First / Offline First)
- View and clear AI chat storage usage
- **ML Engine panel** — view model status, last/next retrain dates, transaction count, months of data, and retrain schedule; trigger a manual retrain from here
- Dark / Light theme toggle (available from any screen)
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

- Run the app as a Flet web app
- Test from another device on the same network
- Share temporary external links using Cloudflare Tunnel

## Tech stack

<<<<<<< HEAD
- Python 3.10
- Flet
- PostgreSQL
- SQLite
- FastAPI
- Docker
- Docker Compose
- scikit-learn
- pandas
- matplotlib
=======
| Layer | Technology |
|-------|------------|
| UI Framework | [Flet](https://flet.dev/) (Flutter-based Python UI) |
| Language | Python 3.10+ |
| Database | SQLite via custom `database.py` (per-user DBs + shared `users.db`) |
| ML — Anomaly Detection | scikit-learn `IsolationForest` |
| ML — Forecasting | scikit-learn `LinearRegression` |
| ML — Model Persistence | `joblib` (ships with scikit-learn) |
| Data Processing | `pandas`, `numpy` |
| Charts | `matplotlib` (Agg backend, embedded as base64 PNG) |
| AI — Offline | [Ollama](https://ollama.com/) local LLM (llama3.2, qwen2.5, phi3, etc.) |
| AI — Online | Anthropic Claude API (`claude-haiku-4-5`) |
| Date Math | `python-dateutil` (relativedelta for monthly/yearly recurrence) |
| Data Export | CSV via `exports/` folder |
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

## Project structure

- [main.py](/C:/Users/jinsa/ai-budget-tracker/main.py) - main Flet app entry
- [ui](/C:/Users/jinsa/ai-budget-tracker/ui) - UI screens and view helpers
- [backend](/C:/Users/jinsa/ai-budget-tracker/backend) - database and API backend modules
- [assets](/C:/Users/jinsa/ai-budget-tracker/assets) - icons and app assets
- [api_server.py](/C:/Users/jinsa/ai-budget-tracker/api_server.py) - lightweight API entry wrapper
- [set_admin_password.py](/C:/Users/jinsa/ai-budget-tracker/set_admin_password.py) - helper script for master admin password

## Run locally

<<<<<<< HEAD
Desktop mode:

```powershell
.\venv\Scripts\flet.exe run main.py
=======
- `transactions` — all income and expense records
- `budget_limits` — per-category limits with duration and date range
- `recurring_transactions` — repeating transactions with frequency and next-due tracking
- `notifications` — persistent notification inbox
- `chat_sessions` + `chat_messages` — full AI conversation history
- `app_meta` — user preferences (currency, API key, AI mode, starting balance, dashboard card order, ML retrain schedule and last-run date)

Trained ML models are stored separately in:

```
user_data/ml_models/budget_user_<id>/
    anomaly_detector.pkl   ← IsolationForest
    forecasters.pkl        ← dict of { category: LinearRegression }
```

---

## 🚀 Getting Started

**Prerequisites**
- Python 3.10 or higher
- pip

**Installation**

```bash
# Clone the repository
git clone https://github.com/salipuranalgine-cmyk/ai-budget-tracker.git
cd ai-budget-tracker

# Install dependencies
pip install flet python-dateutil scikit-learn pandas matplotlib numpy joblib

# Run the app
python main.py
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91
```

Web mode:

```powershell
.\venv\Scripts\flet.exe run --web --host 0.0.0.0 --port 8550 main.py
```

## PostgreSQL mode

<<<<<<< HEAD
Set `DATABASE_URL` before starting the app:
=======
**Enabling ML Predictions**

The ML engine activates automatically once you have enough transaction history:
- Anomaly detection: starts scanning from 12 transactions; full model trains at 30
- Spending forecast: activates after 3+ months of data per category

No extra setup needed — the app trains in the background on launch.

---
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

```powershell
$env:DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/ai_budget_tracker"
```

<<<<<<< HEAD
Then run the app in desktop or web mode.

More setup details are in [POSTGRES_FASTAPI_SETUP.md](/C:/Users/jinsa/ai-budget-tracker/POSTGRES_FASTAPI_SETUP.md).
=======
<img width="1680" height="1027" alt="AI Smart Saver - Budget Guardian 4_22_2026 8_09_58 PM" src="https://github.com/user-attachments/assets/8797b0fa-8ddb-43ac-962a-69694fed207a" />
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
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

## Docker

Build and run the web app with PostgreSQL:

<<<<<<< HEAD
```powershell
docker compose up --build
```
=======
- [ ] Android APK packaging via Flet mobile
- [ ] More ML models (clustering for category auto-tagging, etc.)
- [ ] Spending trend graphs per category over time
>>>>>>> d5528afc8c0769acbc8bb61be7444da151c30b91

This should expose:

- `http://localhost:8550` for the Flet web app
- `localhost:5432` for PostgreSQL

If you also want the API container:

```powershell
docker compose --profile api up --build
```

That also exposes:

- `http://localhost:8000` for FastAPI

More details are in [DOCKER_SETUP.md](/C:/Users/jinsa/ai-budget-tracker/DOCKER_SETUP.md).

## Temporary remote testing

For temporary friend testing, you can expose the local web app using Cloudflare Tunnel:

```powershell
& "C:\Users\jinsa\Downloads\cloudflared-windows-amd64.exe" tunnel --url http://localhost:8550
```

Then share the generated `trycloudflare.com` link.

## Notes

- SQLite is still useful for single-device local mode
- PostgreSQL is the better choice for shared or phone-access workflows
- The app currently mixes local desktop and web concerns in one codebase, but the structure is now separated enough to maintain cleanly

## Portfolio readiness

This is strong enough for a portfolio if you present it as:

- a full-stack personal finance app
- a multi-user profile system
- a mobile-testable Flet web experience
- a project that supports PostgreSQL, FastAPI, and Docker

To make it even stronger, add:

- screenshots or a short demo GIF
- a short architecture section
- one section describing the hardest engineering problems you solved
