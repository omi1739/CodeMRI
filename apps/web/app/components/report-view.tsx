"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  getComparison,
  getFinding,
  getReport,
  listFindings,
  shortSha,
  type Comparison,
  type FindingDetail,
  type FindingSummary,
  type Report,
} from "@/app/lib/api";
import {
  Card,
  Chip,
  ConfidenceBadge,
  ScoreRing,
  SectionTitle,
  SeverityBadge,
  scoreBarTone,
  scoreLabelTone,
} from "@/app/components/ui";

const EFFORT_LABEL: Record<string, string> = {
  S: "Short",
  M: "Medium",
  L: "Large",
};

const TARGET_LABEL: Record<string, string> = {
  portfolio: "Portfolio",
  university: "University",
  production: "Production",
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low"] as const;

export default function ReportView({ scanId }: { scanId: number }) {
  const [report, setReport] = useState<Report | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [items, setItems] = useState<FindingSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [findingsLoading, setFindingsLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [category, setCategory] = useState<string>("all");
  const [details, setDetails] = useState<Map<string, FindingDetail>>(new Map());
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [reportData, comparisonData] = await Promise.all([
          getReport(scanId),
          getComparison(scanId).catch(() => null),
        ]);
        if (cancelled) return;
        setReport(reportData);
        setComparison(comparisonData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the report.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scanId]);

  useEffect(() => {
    let cancelled = false;
    const seq = loadSeq.current;
    (async () => {
      try {
        const page = await listFindings(scanId, {
          limit: 100,
          category: category === "all" ? undefined : category,
        });
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.total);
        setOffset(page.offset);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load findings.");
        }
      } finally {
        if (!cancelled && seq === loadSeq.current) setFindingsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scanId, category]);

  const toggleExpand = useCallback(
    async (item: FindingSummary) => {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(item.id)) next.delete(item.id);
        else next.add(item.id);
        return next;
      });
      if (details.has(item.id) || failed.has(item.id)) return;
      setLoadingId(item.id);
      try {
        const detail = await getFinding(item.id);
        setDetails((prev) => new Map(prev).set(item.id, detail));
      } catch {
        setFailed((prev) => new Set(prev).add(item.id));
      } finally {
        setLoadingId(null);
      }
    },
    [details, failed]
  );

  const selectCategory = (value: string) => {
    loadSeq.current += 1;
    setFindingsLoading(true);
    setCategory(value);
  };

  const loadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await listFindings(scanId, {
        limit: 100,
        offset,
        category: category === "all" ? undefined : category,
      });
      setItems((prev) => [...prev, ...page.items]);
      setTotal(page.total);
      setOffset(page.offset);
    } catch {
      setError("Could not load more findings.");
    } finally {
      setLoadingMore(false);
    }
  }, [scanId, offset, category, loadingMore]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-16">
        <Card className="border-red-500/30">
          <h2 className="text-lg font-semibold text-red-300">Report unavailable</h2>
          <p className="mt-2 text-sm text-zinc-400">{error}</p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:text-zinc-100"
          >
            Back home
          </Link>
        </Card>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-3 px-6 py-24">
        <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-zinc-500 border-t-transparent" />
        <p className="text-sm text-zinc-500">Loading report…</p>
      </div>
    );
  }

  const fingerprint = report.fingerprint;
  const counts = report.counts ?? {};
  const categoryOptions = Object.keys(counts).sort();
  const remaining = total - items.length;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <header className="mb-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wider text-zinc-500">
              Scan #{report.scan_id} · {TARGET_LABEL[report.target] ?? report.target} target
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">
                <a
                  href={report.repository_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-indigo-300"
                >
                  {report.repository}
                </a>
              </h1>
              {report.label ? (
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${scoreLabelTone(report.label)}`}
                >
                  {report.label}
                </span>
              ) : null}
            </div>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-500">
              <span>{report.branch}</span>
              {report.commit_sha ? (
                <span className="font-mono text-xs">{shortSha(report.commit_sha)}</span>
              ) : null}
              {report.finished_at ? (
                <span>{new Date(report.finished_at).toLocaleString()}</span>
              ) : null}
              <span className="text-zinc-700">· 9 analyzers</span>
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Link
              href="/history"
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
            >
              History
            </Link>
            <Link
              href="/"
              className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/25 transition hover:bg-indigo-400"
            >
              New scan
            </Link>
          </div>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="flex flex-col gap-6">
          <Card className="flex flex-col items-center gap-3">
            <ScoreRing score={report.overall_score ?? 0} />
            <div className="flex flex-wrap items-center justify-center gap-2">
              {SEVERITY_ORDER.map((level) => {
                const count = report.severity_counts[level];
                if (!count) return null;
                return (
                  <span
                    key={level}
                    className="flex items-center gap-1.5 rounded-full bg-zinc-800/70 py-1 pl-1 pr-2.5"
                  >
                    <SeverityBadge severity={level} />
                    <span className="text-xs tabular-nums text-zinc-300">{count}</span>
                  </span>
                );
              })}
            </div>
            {SEVERITY_ORDER.every((level) => !report.severity_counts[level]) ? (
              <span className="text-sm text-emerald-400">No findings — clean scan</span>
            ) : null}
          </Card>

          {comparison && comparison.comparisons.length > 0 ? (
            <Card>
              <SectionTitle>Score by target mode</SectionTitle>
              <p className="mt-1 text-xs text-zinc-500">
                Re-weighting the same findings for other audiences.
              </p>
              <ul className="mt-3 flex flex-col gap-2">
                {comparison.comparisons.map((mode) => {
                  const active = mode.target === report.target;
                  const delta =
                    report.overall_score != null
                      ? mode.overall_score - report.overall_score
                      : 0;
                  return (
                    <li
                      key={mode.target}
                      className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 ${
                        active
                          ? "border-indigo-500/50 bg-indigo-500/10"
                          : "border-zinc-800 bg-zinc-950/50"
                      }`}
                    >
                      <div>
                        <p className="text-sm font-medium text-zinc-200">
                          {TARGET_LABEL[mode.target] ?? mode.target}
                        </p>
                        {!active && delta !== 0 ? (
                          <p
                            className={`text-xs ${
                              delta > 0 ? "text-emerald-400" : "text-red-400"
                            }`}
                          >
                            {delta > 0 ? "+" : ""}
                            {delta} vs portfolio
                          </p>
                        ) : null}
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-semibold tabular-nums text-zinc-100">
                          {mode.overall_score}
                        </p>
                        <p className="text-xs text-zinc-500">{mode.label}</p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ) : null}

          {fingerprint ? (
            <Card>
              <SectionTitle>Fingerprint</SectionTitle>
              <dl className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-xs text-zinc-500">Files</dt>
                  <dd className="mt-0.5 tabular-nums text-zinc-200">
                    {fingerprint.file_count?.toLocaleString() ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-zinc-500">Lines of code</dt>
                  <dd className="mt-0.5 tabular-nums text-zinc-200">
                    {fingerprint.total_loc?.toLocaleString() ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-zinc-500">Test files</dt>
                  <dd className="mt-0.5 tabular-nums text-zinc-200">
                    {fingerprint.test_file_count?.toLocaleString() ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-zinc-500">Package manager</dt>
                  <dd className="mt-0.5 text-zinc-200">
                    {fingerprint.package_manager ?? "—"}
                  </dd>
                </div>
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {fingerprint.languages?.slice(0, 6).map((lang) => (
                  <Chip key={lang}>{lang}</Chip>
                ))}
                {fingerprint.frameworks?.slice(0, 4).map((fw) => (
                  <Chip key={`fw-${fw}`} title={`Framework: ${fw}`}>
                    {fw}
                  </Chip>
                ))}
                {fingerprint.typescript ? <Chip>TypeScript</Chip> : null}
                {fingerprint.ci ? <Chip title="CI detected">CI</Chip> : null}
                {fingerprint.docker ? <Chip title="Dockerfile detected">Docker</Chip> : null}
                {fingerprint.readme ? <Chip>README</Chip> : null}
                {fingerprint.license ? <Chip>License</Chip> : null}
                {fingerprint.env_example ? <Chip>.env.example</Chip> : null}
              </div>
            </Card>
          ) : null}
        </aside>

        <div className="flex flex-col gap-6">
          {report.scores.length > 0 ? (
            <Card>
              <SectionTitle>Category scores</SectionTitle>
              <ul className="mt-4 flex flex-col gap-4">
                {report.scores.map((score) => (
                  <li key={score.category}>
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-sm font-medium capitalize text-zinc-200">
                        {score.category}
                      </span>
                      <span className="text-sm tabular-nums text-zinc-400">
                        {score.score}
                        <span className="text-zinc-600">
                          {" "}
                          · {(score.weight * 100).toFixed(0)}% weight
                        </span>
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${scoreBarTone(score.score)}`}
                        style={{ width: `${score.score}%` }}
                      />
                    </div>
                    {score.penalty > 0 ? (
                      <p className="mt-1 text-xs text-zinc-500">
                        −{score.penalty} pts from {score.items.length}{" "}
                        {score.items.length === 1 ? "finding" : "findings"}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {report.recommendations.length > 0 ? (
            <Card>
              <SectionTitle>Top recommendations</SectionTitle>
              <ol className="mt-4 flex flex-col gap-4">
                {report.recommendations.map((rec) => (
                  <li
                    key={rec.rank}
                    className="rounded-lg bg-zinc-900/80 p-4 ring-1 ring-inset ring-zinc-800"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-semibold text-zinc-100">
                        <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/15 text-xs font-semibold text-indigo-300">
                          {rec.rank}
                        </span>
                        {rec.title}
                      </h3>
                      <span className="shrink-0 rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
                        {EFFORT_LABEL[rec.effort] ?? rec.effort} effort
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      {rec.explanation}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-emerald-400">
                        {rec.expected_impact}
                      </span>
                      {rec.finding_ids.slice(0, 5).map((id) => (
                        <a
                          key={id}
                          href={`#${id}`}
                          className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-indigo-300 hover:bg-zinc-700"
                        >
                          {id}
                        </a>
                      ))}
                    </div>
                  </li>
                ))}
              </ol>
            </Card>
          ) : null}

          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <SectionTitle>
                Findings{" "}
                <span className="text-zinc-600">
                  · {total} {total === 1 ? "finding" : "findings"}
                </span>
              </SectionTitle>
              <div className="flex flex-wrap items-center gap-1.5">
                <FilterPill
                  active={category === "all"}
                  onClick={() => selectCategory("all")}
                  label="All"
                />
                {categoryOptions.map((cat) => (
                  <FilterPill
                    key={cat}
                    active={category === cat}
                    onClick={() => selectCategory(cat)}
                    label={cat.replaceAll("_", " ")}
                    count={counts[cat]}
                  />
                ))}
              </div>
            </div>

            {findingsLoading ? (
              <ul className="mt-4 flex flex-col gap-4">
                {[0, 1, 2, 3].map((i) => (
                  <li
                    key={i}
                    className="rounded-lg bg-zinc-900/80 p-4 ring-1 ring-inset ring-zinc-800"
                  >
                    <div className="h-3 w-2/5 animate-pulse rounded bg-zinc-800" />
                    <div className="mt-3 h-3 w-4/5 animate-pulse rounded bg-zinc-800/70" />
                    <div className="mt-2 h-3 w-3/5 animate-pulse rounded bg-zinc-800/70" />
                  </li>
                ))}
              </ul>
            ) : items.length === 0 ? (
              <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-6 text-center">
                <p className="text-sm font-medium text-emerald-400">
                  No findings {category !== "all" ? "in this category" : "for this target"}
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Nothing matched the analyzer rules at this weight and confidence.
                </p>
              </div>
            ) : (
              <ul className="mt-4 flex flex-col gap-3">
                {items.map((item) => {
                  const isOpen = expanded.has(item.id);
                  const detail = details.get(item.id);
                  const isLoading = loadingId === item.id;
                  const showFailure = failed.has(item.id) && !detail;
                  return (
                    <li
                      key={item.id}
                      id={item.id}
                      className="scroll-mt-6 rounded-lg bg-zinc-900/80 ring-1 ring-inset ring-zinc-800 transition hover:ring-zinc-700"
                    >
                      <button
                        type="button"
                        onClick={() => toggleExpand(item)}
                        className="flex w-full items-start gap-3 p-4 text-left"
                        aria-expanded={isOpen}
                      >
                        <span
                          className="mt-0.5 shrink-0 select-none text-zinc-600 transition-transform duration-200"
                          style={{ transform: isOpen ? "rotate(90deg)" : "none" }}
                        >
                          ▸
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <SeverityBadge severity={item.severity} />
                            <span className="font-mono text-xs text-zinc-500">
                              {item.rule_id}
                            </span>
                            <span className="ml-auto font-mono text-xs text-zinc-600">
                              ×{item.occurrence_count}
                            </span>
                          </span>
                          <span className="mt-1.5 block text-sm font-semibold text-zinc-100">
                            {item.title}
                          </span>
                        </span>
                      </button>

                      {isOpen ? (
                        <div className="space-y-2 border-t border-zinc-800/80 px-4 py-3 pl-9">
                          {isLoading ? (
                            <div className="flex items-center gap-2 text-sm text-zinc-500">
                              <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-500 border-t-transparent" />
                              Loading evidence…
                            </div>
                          ) : showFailure ? (
                            <p className="text-sm text-red-400">
                              Could not load evidence for this finding.
                            </p>
                          ) : detail ? (
                            <>
                              {detail.description ? (
                                <p className="text-sm leading-6 text-zinc-400">
                                  {detail.description}
                                </p>
                              ) : null}
                              {detail.evidence.length > 0 ? (
                                <div className="flex flex-col gap-2">
                                  {detail.evidence.map((ev, index) => (
                                    <div
                                      key={index}
                                      className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3"
                                    >
                                      <div className="flex flex-wrap items-center gap-2">
                                        <span className="font-mono text-xs text-zinc-300">
                                          {ev.file_path}
                                        </span>
                                        {ev.line_start ? (
                                          <span className="font-mono text-xs text-zinc-600">
                                            L{ev.line_start}
                                            {ev.line_end && ev.line_end !== ev.line_start
                                              ? `–L${ev.line_end}`
                                              : ""}
                                          </span>
                                        ) : null}
                                        {ev.symbol ? (
                                          <span className="text-xs text-zinc-500">
                                            {ev.symbol}
                                          </span>
                                        ) : null}
                                        {ev.metric_name ? (
                                          <span className="text-xs text-zinc-500">
                                            {ev.metric_name}: {ev.metric_value}
                                          </span>
                                        ) : null}
                                        {ev.permalink ? (
                                          <a
                                            href={ev.permalink}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="ml-auto text-xs font-medium text-indigo-400 hover:text-indigo-300"
                                          >
                                            View on GitHub ↗
                                          </a>
                                        ) : null}
                                      </div>
                                      {ev.snippet ? (
                                        <pre className="mt-2 max-h-40 overflow-auto rounded bg-zinc-900 p-2 font-mono text-xs leading-5 text-zinc-300">
                                          {ev.snippet}
                                        </pre>
                                      ) : null}
                                      {ev.reason ? (
                                        <p className="mt-2 text-xs italic text-zinc-500">
                                          {ev.reason}
                                        </p>
                                      ) : null}
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {detail.recommendation ? (
                                <p className="text-xs leading-5 text-zinc-500">
                                  <span className="font-medium text-zinc-400">
                                    Fix:{" "}
                                  </span>
                                  {detail.recommendation}
                                </p>
                              ) : null}
                              <div className="flex items-center gap-2 pt-1">
                                <ConfidenceBadge confidence={item.confidence} />
                                <span className="text-xs capitalize text-zinc-600">
                                  {item.category} · {item.id}
                                </span>
                              </div>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}

            {remaining > 0 ? (
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="mt-4 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-zinc-100 disabled:opacity-60"
              >
                {loadingMore ? "Loading…" : `Load more (${remaining} remaining)`}
              </button>
            ) : null}
          </Card>
        </div>
      </div>
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition ${
        active
          ? "bg-indigo-500/15 text-indigo-200 ring-1 ring-inset ring-indigo-500/40"
          : "bg-zinc-900 text-zinc-400 ring-1 ring-inset ring-zinc-800 hover:text-zinc-200"
      }`}
    >
      {label.replaceAll("_", " ")}
      {count != null ? <span className="ml-1 text-zinc-500">{count}</span> : null}
    </button>
  );
}