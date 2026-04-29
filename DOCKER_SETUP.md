# Docker Setup

This project is now ready to run with Docker in a beginner-friendly way.

## What each file does

- `Dockerfile`
  Builds one image for the app code.
- `docker-compose.yml`
  Starts the app and PostgreSQL together.
- `.dockerignore`
  Keeps Docker from copying virtual environments, caches, and local databases into the image.
- `requirements.txt`
  Lists the Python packages the app needs inside the container.

## The simplest setup

From the project root:

```powershell
docker compose up --build
```

That starts:

- the Flet web app on `http://localhost:8550`
- PostgreSQL on `localhost:5432`

## Optional API container

If you also want the FastAPI backend running:

```powershell
docker compose --profile api up --build
```

That adds:

- FastAPI on `http://localhost:8000`

## Important learning notes

### 1. Why use `docker-compose.yml`?

Because this app needs more than one service:

- your app
- your PostgreSQL database

Compose lets both start together with one command.

### 2. Why use `DATABASE_URL`?

Inside Docker, containers talk to each other by service name.

So this:

```text
postgresql://postgres:postgres@postgres:5432/ai_budget_tracker
```

means:

- username: `postgres`
- password: `postgres`
- host: `postgres`  <- this is the Compose service name
- port: `5432`
- database: `ai_budget_tracker`

### 3. Why not use `127.0.0.1` inside Docker?

Because inside a container, `127.0.0.1` means "this same container", not your database container.

That is why Compose uses `postgres` as the host instead.

## Useful commands

Start:

```powershell
docker compose up --build
```

Run in background:

```powershell
docker compose up --build -d
```

Stop:

```powershell
docker compose down
```

Stop and remove database data too:

```powershell
docker compose down -v
```

## What I recommend you learn first

1. `Dockerfile` builds one app image
2. `docker-compose.yml` connects multiple services
3. `ports` expose container ports to your PC
4. `environment` passes configuration like `DATABASE_URL`
5. `volumes` keep Postgres data alive even after containers stop
