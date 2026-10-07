# CodeMRI

Evidence-backed code health reports for JavaScript repositories.

Paste a public GitHub URL and CodeMRI produces a 0–100 health score pinned to a
specific commit, broken down across security, testing, documentation,
architecture, dependencies, code quality, git hygiene, and deployment.

## Getting Started

### Prerequisites

- Python 3.11+ for the analyzer service
- Node.js 20+ for the Next.js web app

### Install

```bash
# analyzer service
cd services/analyzer
pip install -r requirements.txt

# web app
cd apps/web
npm install
```

### Run

Start the API on port 8000:

```bash
python -m uvicorn app.main:app --port 8000
```

Start the web app on port 3000:

```bash
npm run dev
```

Open http://127.0.0.1:3000, paste a repository URL, pick a target audience, and
scan.

## Repository layout

- `services/analyzer` — FastAPI scan pipeline (fetch, inventory, analyzers,
  scoring, evidence normalization)
- `apps/web` — Next.js report UI (scan form, live progress, report, history)
- `docs` — product decisions, rule taxonomy, and conventions
- `benchmarks` — pinned, SHA-pinned repos used for regression runs

## API

The main endpoints live under `/api`: `POST /api/scans` starts a scan and
returns an ID for polling; `GET /api/scans/{id}` returns status and progress;
`GET /api/scans/{id}/report`, `/api/scans/{id}/findings`, and
`/api/scans/{id}/comparison` expose the finished report; `GET /api/scans`
lists history.

## Tests

```bash
cd services/analyzer && python -m pytest
cd apps/web && npm run test && npm run lint
```

## License

MIT — see the LICENSE file at the repository root.