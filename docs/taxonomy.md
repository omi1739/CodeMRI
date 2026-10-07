# CodeMRI Rule Taxonomy

Stable IDs: `CATEGORY-NNN`. Never reuse an ID for a different meaning.
Every rule needs: what it detects, evidence required, how severity is chosen, known false
positives, recommended action text.

**Severity**: critical / high / medium / low / info. **Confidence**: high / medium / low.

**Status legend:** `implemented` (running today) | `planned` (Phase 4-9 spec, not built).

> Implementation note (2026-10-07): Phase 4/5 tooling (Gitleaks, Semgrep, ESLint, jscpd) is not
> installed on this machine and repo ESLint configs are untrusted executable code, so all rules
> below are implemented as regex/pathlib heuristics in `app/analyzers/`. Severity/confidence and
> evidence contracts match the table; where a tool is named in the notes it describes the rule's
> intent, not the runtime mechanism.

## Fingerprint (status: implemented)

| ID | Title | Severity | Confidence | Status |
|---|---|---|---|---|
| FP-001 | Detected project stack | info | high | implemented |
| FP-002 | No Node.js project detected | info | high | implemented |

- **FP-001** evidence: stack summary JSON (languages, package manager, file count, LOC) as one
  evidence entry pointing at `package.json`. Info severity, never penalizes a score.
- **FP-002** evidence: `package.json` missing at repo root. Means V1 analyzers will mostly skip;
  wording must say results are partial, not that the project is bad.

## Security (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| SEC-001 | Probable secret / credential in source | critical-high | medium-high |
| SEC-002 | Sensitive file committed (.env, id_rsa, *.pem, credentials.json) | high | high |
| SEC-003 | Insecure code pattern (eval, SQL string concat, dangerouslySetInnerHTML) | medium-high | medium |
| SEC-004 | Insecure configuration (CORS *, debug on, TLS verification off, hardcoded JWT) | medium | medium |
| SEC-005 | API routes with no visible auth check | medium | low |

- **SEC-001**: regex patterns for known cloud/token formats (`AKIA*`, `ghp_*`, `sk-*`, private-key
  headers) plus `key=value` credential assignments. Evidence: file, line, rule name, masked preview
  (first ~4 chars) only - NEVER the full secret; the redaction pass runs before storage.
  Severity by secret type (cloud/private key = critical, generic credential = medium).
  FP risk: sample/test strings - token patterns require known prefixes so entropy is implied.
- **SEC-002**: exact path match against a sensitive-file list. High confidence.
- **SEC-003**: regex over the module body (eval call, `innerHTML`/`dangerouslySetInnerHTML`,
  SQL string-concatenation signals). Evidence: file, line, snippet (capped). Confidence max medium.
- **SEC-004**: own config rules (CORS wildcard, disabled TLS verification, debug on, hardcoded
  JWT secret).
- **SEC-005**: route file (path contains routes/controllers/api/handlers) with HTTP-method
  registrations but no auth/session/token reference in the file. LOW confidence only:
  auth may live elsewhere (middleware.ts, gateway, external service).

## Dependencies (status: implemented - DEP-001/002/003/004/005)

| ID | Title | Severity | Confidence | Status |
|---|---|---|---|---|
| DEP-001 | Direct dependency with known advisory (exact version match) | by advisory severity | high | implemented |
| DEP-002 | Dependency outdated by one or more major versions | low-medium | high | implemented |
| DEP-003 | No lockfile committed | medium | high | implemented |
| DEP-004 | Multiple package managers / conflicting lockfiles | low | high | implemented |
| DEP-005 | Possibly unused dependency (declared, never imported) | low | low | implemented |

- **DEP-001**: OSV `querybatch` on `{ecosystem: npm, name, version}` with the EXACT resolved
  version (lockfile, else exact pin). Evidence: package@version, advisory IDs (GHSA/OSV),
  summary snippet, link. Severity from advisory (CVSS/severity text): >=9 critical, >=7 high,
  >=4 medium, else low. **Refuse to claim vulnerable without exact-version match.**
  On OSV/network failure: emit nothing (never guess). Grouped per package (`DEP-001|pkg`).
- **DEP-002**: registry `dist-tags.latest` vs resolved/base major. One grouped finding with the
  count + worst 5 examples as evidence (name: current -> latest). Severity: medium if >1 dep
  behind or >=2 majors, else low. FP risk: ranges like `*`/`latest`, monorepo workspace deps.
- **DEP-003**: `package.json` present, no lockfile in root. High confidence. Action: commit lockfile.
- **DEP-004**: >1 of package-lock.json / yarn.lock / pnpm-lock.yaml / bun.lockb.
- **DEP-005**: runtime (non-dev) dep never referenced by any import/require in scanned source.
  LOW confidence - CLIs, plugins and peer-provided code are legitimately never imported.
  Tooling denylist (eslint/babel/typescript/@types/...) must be excluded.

## Code quality (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| QUA-001 | Very high complexity function | medium | high |
| QUA-002 | Very large file | low | high |
| QUA-003 | Significant duplicated code blocks | low | medium |
| QUA-004 | Unused imports (grouped per file) | low | high |

- Complexity is a heuristic on function-looking blocks (branch/`&&`/`||`/`??` counts), never
  executed code; QUA-002 uses the inventory LOC; QUA-003 detects repeated 5-line blocks;
  QUA-004 is lexical import-name usage.
- **Grouping required**: one finding per rule per file with count + worst 5 examples, not hundreds
  of raw lines. Done-when: messy student project = 3-8 grouped findings.

## Testing (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| TST-001 | No tests detected | high | high |
| TST-002 | Tests exist but coverage unknown | info | high |
| TST-003 | Critical module with no obvious test | medium | medium |
| TST-004 | Test script missing in package.json | medium | high |

- Detect framework (`fingerprint.test_frameworks`) + `test` script; find test files
  (`inventory.is_test`); map critical modules (auth/payment/billing/... segments) to test files
  by path conventions.
- Ingest committed coverage artifacts only; NEVER run tests. Never claim a coverage % without one.

## Documentation (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| DOC-001 | README missing or nearly empty | medium | high |
| DOC-002 | No setup / install instructions | medium | medium |
| DOC-003 | Env variables used in code but not documented | medium | medium |
| DOC-004 | README claims a feature with no supporting code | low | low |

- README heading parse (install/usage/run/test/env/deploy/license).
- DOC-003: `process.env.X` usages vs README and `.env.example`.
- DOC-004: only ever "no evidence found", never "false". Low confidence, weigh little.

## Architecture (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| ARC-001 | Circular dependency between modules | medium | high |
| ARC-002 | God module (very high in-degree) | medium | medium |
| ARC-003 | Orphan modules never imported (possible dead code) | low | low |

- Import graph from `import`/`require` regex + relative-path resolution over the file inventory;
  cycles via DFS/SCC.
- Graph-derived findings: confidence max low/medium when aliases/monorepo paths are involved.
- **MNT-001 is derived here**: a module with importers >= 8 AND high complexity AND no matching
  test file. Must cite the inputs in evidence.

## Git hygiene (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| GIT-001 | Build artifacts / OS files committed | medium | high |
| GIT-002 | Weak or missing .gitignore | low | high |
| GIT-003 | Very large files committed | low | medium |
| GIT-004 | Stale repo / very low commit activity | — | — |

- Evidence must be concrete files. 
- **GIT-004 intentionally skipped**: git history/commit activity cannot be determined from a
  tarball; the analyzer must never guess, so the rule is spec-only until git metadata is fetched.

## Deployment (status: implemented)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| DEP-LY-001 | No Dockerfile / CI config | low | high |

## Maintainability (status: implemented - derived)

| ID | Title | Severity | Confidence |
|---|---|---|---|
| MNT-001 | High-risk module: high fan-in + no tests + high complexity | medium | medium |

- Derived finding only; combines evidence from the architecture analyzer. Must cite the inputs.

## Writing a new rule

1. Add the row here first (ID, severity, confidence, evidence contract).
2. Implement in `app/analyzers/<name>/` returning `Finding` objects with real evidence.
3. Add fixtures: clean repo, one positive per rule, one edge case (empty/huge/binary).
4. If it needs a score penalty, add effort estimate to `app/scoring/weights.yaml`.
