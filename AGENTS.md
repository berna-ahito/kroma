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
- The frontend is static HTML in `static/index.html` and `static/landing.html`.
- Run locally on Windows PowerShell with:
  `.\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000`
- Visit `http://localhost:8000` for the landing page and `http://localhost:8000/app` for the app.
- Runtime/local state lives in `docs/`, `chroma_db/`, `chroma_db_next/`, and `index_stats.json`.
- Do not read or print `.env` values.
