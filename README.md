# NYC Transit Hub

A real-time web application that tracks every train currently running on the NYC subway, surfaces active MTA service alerts, and visualizes delay patterns across lines — built on an actual ETL pipeline reading directly from the MTA's GTFS-realtime feeds, not a live passthrough.

**[Live demo →](#)** _(add your deployed URL here once live — see Deployment below)_

## What it does

- Polls all 8 NYCT subway realtime feeds (1-7/S, ACE, BDFM, G, JZ, NQRW, L, SIR) on a 30-second interval and persists a normalized snapshot to Postgres
- Plots every in-service train on a live map, at its current/approaching station (the subway feed reports stop-level position, not GPS — see [Known limitations](#known-limitations))
- Draws each route's line geometry on the map, color-coded by official MTA route family — toggleable independently from stations and trains (top-right map control)
- Surfaces active service alerts in a departure-board-style panel
- Charts active alerts by route with a D3 bar chart
- Logs every ETL run (`/api/health`) so the pipeline's health is visible, not just inferred from the UI

## Where the route lines come from

There's no static `shapes.txt` in the data bundled with `nyct-gtfs` (only `stops.txt` and `trips.txt` — the actual geometric route shapes live in MTA's full static GTFS zip, which isn't fetchable without violating MTA's robots.txt). So instead of drawing pre-defined polylines, `app/etl.py` derives line geometry from real operating data: every currently-scheduled trip's ordered stop sequence is a genuine observed path along that route. Each ingest cycle extracts the consecutive-station pairs from every active trip and accumulates them into a `route_segments` table — unlike vehicles, these aren't wiped each cycle, since a route's physical shape doesn't change minute to minute.

Practical effect: right after a fresh deploy, the line layer will be sparse and fill in over the first several ingest cycles as more trips contribute their stop sequences. Within a few minutes of normal operation it converges on a complete picture of every route currently running service.

## Architecture

```
backend/                    Flask API + ETL pipeline
  app/
    etl.py                  The pipeline: seeds stations once, ingests live feeds on a schedule
    mta_alerts.py            Service-alerts feed client (pure parser is unit tested)
    models.py                SQLAlchemy models (Station, VehicleSnapshot, ServiceAlert, IngestRun)
    routes.py                REST API
    data/stops.txt           Official MTA static GTFS stop reference (lat/lon), via nyct-gtfs
  tests/                     13 tests, no network required (see Testing below)

frontend/                   React + TypeScript (Vite)
  src/
    components/TransitMap.tsx    Leaflet map
    components/DelayChart.tsx    D3 bar chart
    components/AlertsPanel.tsx   Service alerts list

docker-compose.yml          One-command local stack (Postgres + backend)
```

**Stack:** Flask, SQLAlchemy, PostgreSQL, APScheduler, [nyct-gtfs](https://github.com/Andrew-Dickinson/nyct-gtfs) · React, TypeScript, Leaflet, D3.js · Docker

## Why nyct-gtfs instead of hand-rolled protobuf parsing

The NYCT subway feed is a GTFS-realtime feed with NYC-specific protocol extensions (track assignment, train IDs). `nyct-gtfs` is a well-maintained MIT-licensed library purpose-built for this feed, and it also bundles MTA's official static `stops.txt` (lat/lon for every station), which is what makes the map possible without a separate static-GTFS download step. The service-alerts feed isn't covered by that library, so `app/mta_alerts.py` parses it directly via the same compiled protobuf classes `nyct-gtfs` already provides (kept as a pure, unit-tested function — see `tests/test_etl.py`).

## Local development

```bash
git clone https://github.com/zz2548/nyc-transit-hub.git
cd nyc-transit-hub
docker compose up --build
```

This starts Postgres and the backend together. The backend seeds the stations table on first boot and starts ingesting live data immediately (requires outbound internet access to `api-endpoint.mta.info`).

Then, in a second terminal, run the frontend:

```bash
cd frontend
cp .env.example .env   # VITE_API_BASE_URL defaults to http://localhost:8000
npm install
npm run dev
```

Open http://localhost:5173.

### Running the backend without Docker

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install .
cp .env.example .env   # falls back to a local SQLite file if DATABASE_URL is unset
python3 wsgi.py
```

## Testing

```bash
cd backend
pip install '.[dev]'
PYTHONPATH=. pytest tests/ -v
```

13 tests, all running against an in-memory SQLite DB and saved sample feed responses — no network or live MTA connection required. The ETL's pure transformation functions (`trip_to_vehicle_record`, `parse_alerts_feed_dict`) are unit tested directly; the parts that require a live network connection (the actual feed fetch) are exercised by deploying, not by the test suite.

```bash
cd frontend
npm run build   # tsc -b && vite build — type-checks and builds
npx oxlint
```

## Deployment

This is set up to deploy as two independent services — a backend on **Render** and a frontend on **Vercel** — which is a normal, free-tier-friendly split for this kind of app.

### Backend + database (Render)

1. Create a new **PostgreSQL** instance on Render (free tier is fine for a portfolio demo). Copy its internal connection string.
2. Create a new **Web Service**, pointing at this repo's `backend/` directory, with the existing `Dockerfile`.
3. Set environment variables:
   - `DATABASE_URL` → the Postgres connection string from step 1
   - `CORS_ORIGINS` → your Vercel frontend URL (set this after step 2 of the frontend deploy below)
   - `ENABLE_SCHEDULER` → `true`
   - `INGEST_INTERVAL_SECONDS` → `30`
4. Deploy. Hit `https://<your-service>.onrender.com/api/health` — `last_ingest_run.status` should read `"success"` within a minute of boot.

> **Free-tier note:** Render's free web services spin down when idle and cold-start on the next request. The in-process scheduler only runs while the dyno is awake, so the very first request after a cold start may show slightly stale data until the next ingest cycle completes. For an always-warm demo, upgrade the web service to Render's paid "Starter" tier, or add a free uptime-ping service (e.g. UptimeRobot) hitting `/api/health` every few minutes to keep it warm.

### Frontend (Vercel)

1. Import this repo into Vercel, with **Root Directory** set to `frontend/`.
2. Set the environment variable `VITE_API_BASE_URL` to your Render backend URL from above.
3. Deploy. Vercel auto-detects the Vite build (`npm run build`, output `dist/`).
4. Go back to Render and set `CORS_ORIGINS` to this Vercel URL, then redeploy the backend.

## Known limitations

- **Train markers represent "current/approaching station," not GPS position.** NYCT's subway realtime feed doesn't publish vehicle coordinates between stations (unlike the bus feeds) — only the stop a train is at, approaching, or has just left. This is the same constraint every NYC subway tracker app works within; showing trains at their station is the standard, accurate approach.
- **Route lines are derived from live trip data, not a static shapes file** (see "Where the route lines come from" above). They're real, but they're segment-by-segment straight lines between adjacent stations rather than geographically precise track curvature — fine for a schematic map (which is what the official MTA map is too), not survey-grade.
- **A few transfer complexes (e.g. Times Sq-42 St) appear as two adjacent markers** instead of one merged station. MTA's static `stops.txt` doesn't merge physically-connected stations into a single complex at the file level — that requires a separate complex-ID crosswalk this project doesn't currently ingest.
- **Single gunicorn worker by design** (see `backend/Dockerfile`) — the ETL scheduler runs in-process, so a second worker would double-ingest and race on the same writes. Fine at portfolio scale; a production version would split ingestion into its own worker process.
