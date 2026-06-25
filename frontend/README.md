# NYC Transit Hub — Frontend

React + TypeScript (Vite) client for the live subway map. See the [root README](../README.md) for architecture, deployment, and the backend.

## Stack

- React 19 + TypeScript, built with Vite
- [react-leaflet](https://react-leaflet.js.org/) for the live map (dark CartoDB basemap, no API key required)
- [D3.js](https://d3js.org/) for the alerts-by-route bar chart, rendered directly via a `useEffect` + D3 selection (not a wrapper library)
- No external state library — polling + `useState` is enough for this app's data shape

## Development

```bash
npm install
cp .env.example .env
npm run dev
```

`VITE_API_BASE_URL` controls which backend the app talks to (defaults to `http://localhost:8000`).

## Scripts

- `npm run dev` — local dev server with HMR
- `npm run build` — type-checks (`tsc -b`) then builds to `dist/`
- `npx oxlint` — lint
