# CA Camp Finder

Monitors late cancellations at San Diego area beach campgrounds, Crystal Pier Hotel, and Crystal Cove cottages. Sends Pushover notifications to your iPhone when Friday–Sunday availability opens up.

## Monitored Locations

| Location | Type | System |
|---|---|---|
| San Elijo State Beach (RV) | Campground | ReserveCA |
| South Carlsbad State Beach (RV) | Campground | ReserveCA |
| Carlsbad State Beach (RV) | Campground | ReserveCA |
| Silver Strand State Beach (RV) | Campground | ReserveCA |
| Crystal Pier Hotel | Hotel | Playwright scraper |
| Crystal Cove Cottages | Cottages | ReserveCA |

## Architecture

```
GitHub push → GitHub Actions (multi-arch build) → ghcr.io
                                                        ↓
                               Watchtower on RPi5 pulls new images
                                        ↓
                  ┌─────────────┬──────────────┬───────────┐
                  │  frontend   │   backend    │ watchtower│
                  │  nginx:80   │  FastAPI:8k  │           │
                  └─────────────┴──────────────┴───────────┘
                                     │
                               SQLite on volume
```

**Intelligent scheduling**: Checks every 60 min by default, automatically dropping to every 15 min during peak cancellation windows (Thursday nights, 48–72 hrs before upcoming Fridays, and 6–11 PM daily).

---

## Raspberry Pi 5 Setup (one-time)

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 2. Authenticate with ghcr.io

Create a GitHub Personal Access Token (PAT) with `read:packages` scope at:
**GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**

```bash
echo YOUR_PAT | docker login ghcr.io -u brianmhardwick --password-stdin
```

### 3. Clone repo and configure

```bash
git clone https://github.com/brianmhardwick/ca-camp-finder.git
cd ca-camp-finder
cp .env.example .env
nano .env   # add your Pushover keys
```

### 4. Add Caddy reverse proxy config

Add this block to your Caddyfile (replace `camps.yourdomain.com`):

```
camps.yourdomain.com {
    # API calls go directly to the backend
    handle /api/* {
        reverse_proxy localhost:8089
    }
    # Everything else is served by the Angular nginx container
    handle {
        reverse_proxy localhost:8088
    }
}
```

Then reload Caddy: `caddy reload` (or `docker exec caddy caddy reload --config /etc/caddy/Caddyfile` if Caddy is containerized).

### 5. Start the stack

```bash
mkdir -p data
docker compose up -d
```

Visit your configured domain. The UI loads immediately; first availability check runs after the initial interval.

### 6. Verify Pushover

In the Monitor tab, tap **Test Alert** — you should receive a test notification on your iPhone within seconds.

---

## Pushover Setup

1. Create account at [pushover.net](https://pushover.net)
2. Install the Pushover app on your iPhone
3. Note your **User Key** from the dashboard
4. Create an application at pushover.net/apps — note the **API Token**
5. Add both to your `.env` file

---

## Ongoing Deployment (from your phone)

Every `git push` to `main` triggers GitHub Actions to build new images and push to `ghcr.io`. Watchtower polls every 5 minutes and automatically restarts containers with the new images — no SSH required.

You can also trigger a manual build from the GitHub mobile app:
**Actions → Build & Push to ghcr.io → Run workflow**

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PUSHOVER_USER_KEY` | — | Your Pushover user key |
| `PUSHOVER_API_TOKEN` | — | Your Pushover app token |
| `DEFAULT_CHECK_INTERVAL` | `60` | Minutes between standard checks |
| `PEAK_WINDOW_INTERVAL` | `15` | Minutes during peak cancellation windows |
| `SCAN_DAYS_AHEAD` | `90` | Days ahead to scan for Fri/Sat/Sun availability |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |

---

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
playwright install chromium
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm start   # proxies /api to localhost:8000
```

Open `http://localhost:4200`

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Status, last/next check, interval |
| `GET` | `/api/locations` | All locations with toggle state |
| `PATCH` | `/api/locations/{slug}` | Enable/disable a location |
| `GET` | `/api/logs` | Availability history (paginated) |
| `DELETE` | `/api/logs/{id}` | Remove a log entry |
| `POST` | `/api/check/now` | Trigger immediate check |
| `POST` | `/api/notify/test` | Send test Pushover notification |
| `GET` | `/api/settings` | Current interval settings |
| `PATCH` | `/api/settings` | Update interval settings |

Interactive docs available at `http://<pi-ip>:8000/docs`

---

## Troubleshooting

**No availability found for Crystal Pier** — Their booking widget may have changed. Check backend logs: `docker compose logs backend`. The Playwright scraper targets available room elements; if the widget structure changes, update the selectors in `backend/app/scrapers/crystal_pier.py`.

**ReserveCA returns empty results** — Facility IDs are pre-configured. If a park changes their ID (rare), update `database.py` seed data and restart.

**Notifications not arriving** — Use **Test Alert** in the UI. If it fails, verify `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` in `.env`. Run `docker compose restart backend` after changes.
