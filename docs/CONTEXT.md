# CodeMRI - CONTEXT

Source of truth: the full product spec lives in `docs/CodeMRI_Free_Build_Guide.pdf` (24 pages).
This file is the working digest for AI coding sessions. Start a session with: "Read CONTEXT.md
sections X, Y. Do only task Z."

## 1. What CodeMRI is

CodeMRI is a software health and diagnosis platform. A developer pastes a public GitHub repository
URL. CodeMRI downloads it at an exact commit, runs static analyzers, converts all results into a
common evidence format, calculates transparent scores, and shows a report that tells the developer
what to fix first.

`Repository -> Evidence -> Understanding -> Diagnosis -> Risk -> Recommendation -> Fix -> Verification`
V1 only covers up to Recommendation. Fixing and verification are V3.

### 1.1 Core principles (never break these)

1. **Evidence first**: every finding points to files, line ranges, metrics or tool output.
2. **Confidence aware**: every finding is High / Medium / Low confidence. Heuristics are never presented as facts.
3. **Prioritized, not noisy**: show the top 5 actions, not 500 warnings. Group related findings.
4. **Context matters**: target modes (Portfolio / University / Production) change weights and thresholds.
5. **AI explains, analyzers prove**: the LLM may never create a finding without evidence IDs from analyzers.
6. **Safe by design**: scanned repositories are untrusted input. V1 never installs or runs their code.

### 1.2 V1 promise

Paste a public JavaScript/TypeScript GitHub URL, choose a target, and receive a credible,
evidence-backed health report with at least 10 useful, explainable findings and very few obviously
false claims.

### 1.3 First milestone (REACHED)

Boring but powerful: paste URL -> scan -> receive real evidence-backed findings from one analyzer
end to end. Do not build the dashboard, the graph or the AI layer before this works.

## 2. Scope

**Build in V1:** public GitHub repos, JavaScript/TypeScript only, React/Next.js/Node/Express
detection, file inventory, dependency analysis + known advisories, basic secrets/security patterns,
README/docs checks, test detection, git hygiene, basic architecture graph, evidence-backed findings
+ health score + top 5 actions, AI explanation last and optional.

**Do NOT build in V1:** private repos/OAuth, other languages, runtime execution (npm install/build/
test), automatic fixes or PR creation, team/org features, scheduled scans, big AI chat interface,
social layer, enterprise policies, historical trends.

### 2.1 What CodeMRI must explicitly refuse to claim

- Not "vulnerable" unless an OSV/GHSA advisory matches the exact resolved version.
- Not "insecure" from a heuristic alone; low-confidence results are labelled as such.
- Never claims code "works" or "does not work" (no runtime execution in V1).
- Never claims coverage percentages unless a coverage artifact exists in the repo.
- Never judges developers by commit-message style (low-weight hygiene signal only).
- Never claims a README feature is "missing" unless high-confidence and the search was thorough;
  otherwise: "no evidence found".

## 3. Stack (as implemented in this repository)

| Layer | Choice | Status |
|---|---|---|
| Web app | Next.js 16 (App Router) + TypeScript + Tailwind 4, in `apps/web` | working |
| API | FastAPI + Python + Pydantic, in `services/analyzer` | working |
| ORM | SQLAlchemy 2 (typed `Mapped` models) + Alembic | working |
| Database | SQLite now (`data/codemri.db`), Postgres (Neon/Supabase) later | working |
| Job queue | FastAPI BackgroundTasks + status machine; Redis/Arq later | working |
| Repo fetch | GitHub REST API + tarball download, one PAT in `.env` | working |
| Dependency data | npm registry API + OSV.dev querybatch (both free, no key) | working |
| Lint/quality | ESLint with OUR OWN config, jscpd (Phase 5) — heuristic QUA rules in use | fallback in use |
| Secrets | Gitleaks (Phase 4) — regex SEC rules in use | fallback in use |
| Parsing | tree-sitter where wheels allow; regex/pathlib fallback (Python 3.14) | fallback in use |
| Scoring | `app/scoring/weights.yaml` + deterministic engine | working |
| AI (last) | LiteLLM wrapper over free tiers (Gemini/Groq/Ollama) | not started |

Local-first: run everything on the laptop (`data/` is git-ignored); deploy only after V1 works.

## 4. Architecture and scan lifecycle

```
Browser -> Next.js (apps/web) -> FastAPI (services/analyzer)
   -> SQLite/Postgres (repositories, scans, findings, evidence, scores ...)
   -> worker (BackgroundTasks; same codebase)
        -> GitHub API / tarball download -> ./data/scans/<id>/
        -> Analyzers (fingerprint, dependencies, ... ) one by one
        -> Evidence normalizer (common Finding format, dedupe, redaction)
        -> Health engine (weighted, configurable scoring)
```

Status machine (stored on `scans.status` / `current_stage` / `progress_pct`):

```
queued -> fetching -> fingerprinting -> analyzing -> scoring -> reporting -> completed
                    \______________ any step can fail -> failed (with error message) ______/
```

Progress map lives in `app/worker.py::STAGE_PROGRESS`. The UI polls `GET /api/scans/{id}` every
2 seconds.

## 5. Monorepo layout (this repository)

```
codemri/
  apps/web/                    # Next.js dashboard
  services/analyzer/           # FastAPI app + worker
    app/
      main.py                  # FastAPI entry, CORS, lifespan init_db
      api/                     # scans.py routes, schemas.py, limits.py (rate limit)
      core/                    # config.py, logging.py, cache.py
      db/                      # models.py, session.py, alembic/
      github/                  # url.py (strict parsing), client.py (API), fetch.py (tarball+safe extract)
      analyzers/
        base.py                # Analyzer protocol + Finding/Evidence models  <-- THE CONTRACT
        _shared.py             # shared regex/pathlib helpers (imports, complexity, duplication)
        fingerprint/           # inventory.py, analyzer.py
        dependencies/          # lockfile.py, net.py, analyzer.py
        security/ quality/ testing/ documentation/ architecture/ git_hygiene/ deployment/
                               # V1 heuristics (regex/pathlib), registered in worker.py
      evidence/normalize.py    # dedupe + grouping + fingerprint_hash + redaction
      scoring/                 # weights.yaml + engine.py
      worker.py                # scan pipeline
    tests/                     # pytest + fixtures
    alembic/                   # migrations
  docs/                        # CONTEXT.md, taxonomy.md, decisions.md, this guide's PDF
  benchmarks/                  # repos.yaml (SHA-pinned) + expected/
  data/                        # git-ignored: sqlite db, caches, scan artifacts
```

### 5.1 The Analyzer interface (the heart of the system)

Every analyzer is a plugin with the same shape (`app/analyzers/base.py`):

- `Evidence`: `file_path, line_start, line_end, symbol, metric_name, metric_value, snippet (REDACTED), reason, permalink`
- `Finding`: `category, rule_id, title, severity, confidence, description, recommendation, analyzer, evidence[], group_key, occurrence_count`
- `ScanContext`: `scan_id, source_dir (read-only), commit_sha, repository_url, fingerprint, target, inventory`
- `Analyzer` Protocol: `name: str, version: str, run(ctx) -> list[Finding]`

Rules for writing one: never execute scanned-repo code; use rule IDs from `docs/taxonomy.md`;
evidence needs file_path + reason; redact secrets; group noisy results; add pytest fixtures
(clean repo, one positive per rule, one edge case).

## 6. Data model

Tables (see `app/db/models.py`): `repositories`, `scans`, `analyzer_runs`, `findings`, `evidence`,
`scores`, `recommendations`, `file_inventory`, `graph_edges`. Key fields: `scans.status`,
`commit_sha`, `target_mode`, `overall_score`, `label`, `fingerprint_json`;
`findings.fingerprint_hash` (stable across scans), `group_key`, `occurrence_count`;
`evidence.snippet` (redacted). Finding IDs are exposed as `F-<id>`.

Raw analyzer output stays on disk (`data/scans/<id>/artifacts/<analyzer>.json`); only normalized
evidence goes to the database.

## 7. Finding taxonomy

Full rule list with per-rule specs: `docs/taxonomy.md`. Summary:

- **Severity**: critical (fix first) / high / medium / low / info (no penalty).
- **Confidence**: high (deterministic) / medium (strong heuristic) / low (weak heuristic).
- **IDs**: `CATEGORY-NNN`, stable forever, never reused for a different meaning.
- Starter set: SEC-001..005, DEP-001..005, QUA-001..004, TST-001..004, DOC-001..004,
  ARC-001..003, GIT-001..004, DEP-LY-001, MNT-001. Plus FP-001/FP-002 (fingerprint, info only).

## 8. Health engine (deterministic, explainable)

All numbers live in `app/scoring/weights.yaml`. Formula:

```
penalty(finding)  = severity_points[severity] * confidence_multiplier[confidence]
severity_points   = { critical: 25, high: 12, medium: 5, low: 2, info: 0 }
confidence_mult   = { high: 1.0, medium: 0.6, low: 0.3 }
# Diminishing returns per rule_id: 1st-3rd full, 4th-10th half, beyond 10th: 0.1
category_score    = max(0, 100 - sum(penalties in that category))
overall_score     = sum(category_score * effective_weight) / sum(effective_weights)
```

Base weights: security 20, dependencies 10, code_quality 15, documentation 10, testing 15,
architecture 15, deployment 5, git_hygiene 5, maintainability 5 (fingerprint 0, informational).
Target modes multiply category weights (portfolio: docs/tests/deployment up; university: tests/docs/
quality up, architecture/deployment down; production: security/testing/deployment/deps up plus
x1.25 severity multiplier on security + dependency findings).

Labels: 90-100 Excellent | 75-89 Good | 60-74 Fair | 40-59 Needs work | 0-39 At risk.

Explainability: every score stores `explanation_json` (which findings reduced it, by how much).
Recommendation ranking: `priority = (severity_points * confidence_mult * category_weight) / effort`
with effort S=1, M=2, L=4; group by root cause; report top 5.

## 9. API contract

| Method + path | Purpose |
|---|---|
| `POST /api/scans` | Body `{url, target}`; validates URL, resolves commit; returns `{scan_id}`; 422 invalid URL, 429 rate limit |
| `GET /api/scans/{id}` | status, stage, progress_pct, analyzer_runs[] |
| `GET /api/scans/{id}/report` | scores, labels, recommendations, counts, fingerprint, metadata |
| `GET /api/scans/{id}/findings` | filters: category, severity, confidence; pagination |
| `GET /api/findings/{id}` | finding + evidence with GitHub permalinks at the pinned SHA |
| `GET /api/repositories/{id}/scans` | scan history for one repository, newest first |
| `GET /api/scans` | recent scans across all repositories (`limit`), for the History page |
| `GET /api/scans/{id}/comparison` | overall score + label recomputed for every target mode |

## 10. Safety rules (V1 golden rule: NEVER execute scanned repository code)

- Safe extraction: reject absolute paths and `..`, skip symlinks/special files, cap files/bytes
  (zip-bomb defence), cap single-file size (`app/github/fetch.py`).
- Limits: repo 150 MB, 20,000 files, 1 MB per file, analyzer timeout 120 s, scan timeout 600 s.
- Never load the scanned repo's ESLint config or plugins (configs are executable JS).
- Secrets: token only in `.env` (git-ignored); redact anything secret-looking before DB/logs/AI
  (`app/evidence/normalize.py::redact`).
- Abuse: allow-list github.com only, per-IP one active scan, global active cap (429).
- Prompt injection: repo text is data, never instructions.
- Output safety: escape repo-derived strings in the UI.

## 11. Workflow rules (AI-assisted development)

- One task per prompt: "Write the Gitleaks analyzer", not "build the security module".
- Contract first: give the Analyzer interface + Finding schema, ask for conforming code.
- Tests with code: pytest + fixtures in `tests/fixtures/`; run them before accepting.
- Small commits; review generated code for subprocess/path/regex/secrets issues.
- Keep `docs/decisions.md` updated and paste it into later sessions.
- Because free AI tiers are rate-limited: keep context short, ask for diffs.

## 12. Phase plan (from the guide)

0 spec/taxonomy/benchmarks -> 1 intake -> 2 fingerprinting -> 3 dependencies -> 4 security
(Gitleaks/Semgrep) -> 5 quality (ESLint/jscpd) -> 6 testing -> 7 docs -> 8 git hygiene ->
9 architecture graph -> 10 evidence normalization -> 11 health engine -> 12 report UI ->
13 AI explanation -> 14 benchmarking/quality gate.

**This repo's status:** Phases 0-3 done; Phases 4-9 shipped as regex/pathlib heuristics
(fingerprint, dependencies, security, quality, testing, documentation, git hygiene, architecture,
deployment, maintainability-derived) -> Phases 10-11 done -> Phase 12 done. Phase 13 (AI) not
started. Full pytest suite 97 passing; live E2E scans run against real GitHub repos.

### 12.1 UI (Phase 12, as built)

- Routes in `apps/web/app/`: `/` (URL + target mode form), `/history` (recent scans via
  `GET /api/scans`), `/scans/[id]` (poll `GET /api/scans/{id}` every 2 s, auto-advance on
  completion), `/scans/[id]/report` (score ring, target-mode comparison via
  `GET /api/scans/{id}/comparison`, category bars, top-5 recommendations, findings with
  evidence + GitHub permalinks at the pinned SHA).
- All three pages are Client Components that talk to FastAPI directly
  (`NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:8000`); no BFF/proxy layer in V1.
- `next.config.ts` has `cacheComponents: true` (PPR); the two dynamic routes export
  `export const instant = false` because async `params` can't be prerendered. Effects that
  self-reschedule must be declared as `function` (not `const` arrow) to avoid TDZ lint errors.
- Linting is the plain `eslint` CLI (`next lint` was removed in Next.js 16).
