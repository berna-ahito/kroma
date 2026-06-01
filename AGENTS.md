# Agent Instructions

## Default behavior

- Final answer only for normal questions.
- No progress narration.
- No tool narration.
- Keep answers concise.
- If graphify-out/GRAPH_REPORT.md exists, read it directly before scanning files.
- Do not run graphify detect commands unless the user asks to rebuild the graph.
- Do not use Python for graphify checks on Windows.
- Choose relevant skills automatically.
- Use Caveman-style compression by default.

## Current app state

- Kroma is a FastAPI app served from `api.py`.
- The active frontend is the React/Vite dashboard in `frontend/src`, built to `frontend/dist`.
- Final routes:
  - `/` serves the landing page.
  - `/dashboard` serves the React app.
  - `/app` redirects to `/dashboard`.
  - `/next` redirects to `/dashboard`.
  - `/api/*` serves backend endpoints.
  - `/assets/*` serves built React assets.
- Old static app files under `static/` are legacy/unrouted and are not the active app.
- Backend dev command on Windows PowerShell:
  `.\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000`
- Frontend dev command:
  `cd frontend; npm run dev`
- Production-like local route test:
  `cd frontend; npm run build; cd ..; .\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000`
- Visit `http://localhost:8000` for the landing page and `http://localhost:8000/dashboard` for the app.
- Docker builds `frontend/dist` automatically. `frontend/dist` is generated at build time and ignored by git.
- Production deployments should run Uvicorn without `--reload`.
- Environment variables:
  - `GROQ_API_KEY` is required for LLM-backed features.
  - `KROMA_DEMO_KEY` is optional for protected demo/custom document actions.
  - `APP_ENV=production` disables `/docs`, `/redoc`, and `/openapi.json`.
  - `KROMA_RATE_LIMIT_REQUESTS` and `KROMA_RATE_LIMIT_WINDOW_SECONDS` optionally tune Groq-backed endpoint rate limits.
- Runtime/local state lives in `docs/`, `chroma_db/`, `chroma_db_next/`, and `index_stats.json`; deployed real-use environments need a persistent disk/volume for these paths.
- Do not read or print `.env` values.
