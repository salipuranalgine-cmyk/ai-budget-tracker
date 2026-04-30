# AI Smart Saver

A multi-user budget tracker built with Python and Flet, with PostgreSQL support, Docker support, AI chat assistance, recurring transactions, budget monitoring, and a phone-friendly web mode.

## What this project does

- Tracks income and expenses by profile
- Supports password-protected user profiles
- Runs in desktop mode or web mode
- Uses SQLite locally or PostgreSQL for shared access
- Includes recurring transactions and budget limit monitoring
- Includes an AI finance chat assistant with saved history
- Supports mobile testing through the Flet web build

## Main features

### Multi-user profiles

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

### AI advisor

- Ask budget questions in a chat interface
- Save chat history per profile
- Continue conversations across sessions
- Use local Ollama or Anthropic depending on configuration

### Web and mobile access

- Run the app as a Flet web app
- Test from another device on the same network
- Share temporary external links using Cloudflare Tunnel

## Tech stack

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

## Project structure

- [main.py](/C:/Users/jinsa/ai-budget-tracker/main.py) - main Flet app entry
- [ui](/C:/Users/jinsa/ai-budget-tracker/ui) - UI screens and view helpers
- [backend](/C:/Users/jinsa/ai-budget-tracker/backend) - database and API backend modules
- [assets](/C:/Users/jinsa/ai-budget-tracker/assets) - icons and app assets
- [api_server.py](/C:/Users/jinsa/ai-budget-tracker/api_server.py) - lightweight API entry wrapper
- [set_admin_password.py](/C:/Users/jinsa/ai-budget-tracker/set_admin_password.py) - helper script for master admin password

## Run locally

Desktop mode:

```powershell
.\venv\Scripts\flet.exe run main.py
```

Web mode:

```powershell
.\venv\Scripts\flet.exe run --web --host 0.0.0.0 --port 8550 main.py
```

## PostgreSQL mode

Set `DATABASE_URL` before starting the app:

```powershell
$env:DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/ai_budget_tracker"
```

Then run the app in desktop or web mode.

More setup details are in [POSTGRES_FASTAPI_SETUP.md](/C:/Users/jinsa/ai-budget-tracker/POSTGRES_FASTAPI_SETUP.md).

## Docker

Build and run the web app with PostgreSQL:

```powershell
docker compose up --build
```

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
