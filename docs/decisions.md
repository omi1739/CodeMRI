# Decisions log

Format: date - decision - reason. Paste this file into later AI sessions for consistency.

## 2026-10-06

- **SQLite instead of PostgreSQL for V1 dev.** No Docker on this machine; the guide explicitly
  allows SQLite for weeks 1-2. SQLAlchemy models are dialect-agnostic; switching to Postgres is a
  `DATABASE_URL` change + `alembic upgrade`. Migration uses `render_as_batch=True` for SQLite.
- **Monorepo layout per guide Section 5**: `apps/web` (moved the existing `client/`), 
  `services/analyzer`, `docs/`, `benchmarks/`. The old `client/` nested git repo was folded into
  the root repo (its only commit was "Initial commit from Create Next App").
- **Python 3.14.3 is the local interpreter.** Verified installs: fastapi 0.142, sqlalchemy 2.1,
  pydantic 2.13, alembic 1.20, httpx 0.28, pytest 9.1, pyyaml 6.0. tree-sitter wheels were NOT
  verified for 3.14 - until confirmed, parsing uses pathlib/regex (inventory, import scan).
- **BackgroundTasks instead of a separate worker process.** Guide's simplification rule: keep it
  synchronous-ish until scans are slow. The status machine is identical when we later move to a
  DB-polling worker or Redis/Arq, so no API change will be needed.
- **Grouping happens at the analyzer layer.** Analyzers emit grouped findings
  (one row per rule + group_key, with `occurrence_count`); the scoring engine applies the
  diminishing-returns formula across occurrences (1-3 full, 4-10 half, beyond 10th 0.1x).
- **npm cache TTL 24h, OSV cache TTL 7d** in `data/cache/` (git-ignored) to stay inside free-tier
  rate limits and keep benchmarks reproducible.
- **Analyzer failure does not fail the scan.** `worker.py` records the failure in
  `analyzer_runs.error_message` and continues; the report reflects only what actually ran.
  Rationale: a broken tool must not destroy an otherwise useful scan.
- **Unused-import detection (DEP-005) stays LOW confidence** with a tooling denylist; CLIs and
  plugins are legitimately never imported.
- **No users/auth in V1** (anonymous scans), per guide. Rate limiting is in-memory:
  1 active scan per IP, 20 active scans total, IP stored in `scans.config_json`.

## 2026-10-07

- **Phase 12 UI shipped as plain Client Components, no BFF.** Next.js 16.4 App Router;
  three routes (`/`, `/scans/[id]`, `/scans/[id]/report`) `fetch()` FastAPI directly via
  `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`). Progress polls every 2 s and
  auto-redirects to the report. Rationale: V1 milestone is a single-report tool; a proxy
  layer adds latency and a second contract to keep in sync.
- **`export const instant = false` on the two dynamic routes.** `next.config.ts` keeps
  `cacheComponents: true` (PPR). Async `params` access cannot be prerendered, so the build
  fails without the opt-out; this intentionally makes navigation to those routes block on
  the server. Home page stays instant.
- **No `Math.random()` in component init.** During prerender the placeholder-picker
  (`Math.random()` in a `useState` initializer) abort the build
  (`blocking-prerender-random-client`); a fixed placeholder removed the instability.
- **Self-rescheduling effects use `function` declarations, not `const` arrows.** The Next.js
  `react-hooks/immutability` lint flags TDZ when a `setTimeout(tick)` references the
  const arrow before it is initialized; a hoisted inner `function poll()` inside the effect
  avoided it.
- **Resolved: plain Tailwind, not shadcn/ui, for the report page.** shadcn adds a copy-paste
  component layer we don't need for 3 pages; revisit if the dashboard (V2) wants its table
  primitives.
- **Remaining V1 analyzers (security/quality/testing/docs/architecture/git/deployment +
  MNT-001) shipped as regex/pathlib heuristics, not Phase 4/5 binaries.** Gitleaks, Semgrep,
  ESLint and jscpd are not installed, and a repo's ESLint config/plugins are untrusted
  executable code (V1 golden rule). Rules keep the taxonomy severity/confidence contracts and
  never present heuristics as facts (e.g. SEC-005 and ARC-003 capped at low confidence).
  Tools can replace the rule bodies later without changing rule IDs or API.
- **GIT-004 (stale repo) deliberately not implemented.** Git history is not in a GitHub
  tarball; claiming low activity would be a guess. Spec-only until the API fetches commit
  history.
- **Scan history + target-mode comparison added to the API.** `GET /api/scans` lists recent
  scans across repositories (drives the new `/history` page); `GET /api/scans/{id}/comparison`
  re-runs `compute_scores` for all three target modes without storing anything, so the report
  can show "score under each audience" without re-scanning.
- **UI polished toward the V1 dashboard.** Header nav (Scan / History) with sticky blur,
  radial-gradient background, feature grid on home, report header gets a "New scan" action and
  a "Score by target mode" card in the sidebar. Still plain Client Components talking straight
  to FastAPI; no BFF in V1.

## Not decided yet

- Fire-and-forget worker process / Redis queue for scans beyond the current BackgroundTasks +
  status-machine approach (revisit when scans get slow or scans-per-Ip concurrency is real).
- Whether production deploys re-run heavy dependabot-dist rolodex data: OSV caching (7d) is
  already in place.
