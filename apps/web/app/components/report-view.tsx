"use client";

import { useEffect, useState } from "react";
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

export default function ReportView({ scanId }: { scanId: number }) {
  const [report, setReport] = useState<Report | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [summaries, setSummaries] = useState<FindingSummary[]>([]);
  const [details, setDetails] = useState<Map<string, FindingDetail>>(new Map());
  const [failedDetails, setFailedDetails] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [reportData, findings, comparisonData] = await Promise.all([
          getReport(scanId),
          listFindings(scanId, 100),
          getComparison(scanId).catch(() => null),
        ]);
        if (cancelled) return;
        setReport(reportData);
        setSummaries(findings.items);
        setTotal(findings.total);
        setComparison(comparisonData);

        const detailMap = new Map<string, FindingDetail>();
        const failed: string[] = [];
        await Promise.all(
          findings.items.map(async (item) => {
            try {
              const detail = await getFinding(item.id);
              detailMap.set(item.id, detail);
            } catch {
              failed.push(item.id);
            }
          })
        );
        if (cancelled) return;
        setDetails(detailMap);
        setFailedDetails(failed);
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

  if (error) {
    return (
      <div className="mx-auto w-full max-w-5xl px-6 py-16">
        <Card className="border-red-500/30">
          <h2 className="text-lg font-semibold text-red-300">Report unavailable</h2>
          <p className="mt-2 text-sm text-zinc-400">{error}</p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700"
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
  const severityTotal =
    Object.values(report.severity_counts).reduce((sum, n) => sum + n, 0) || 0;

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-zinc-500">
              Scan #{report.scan_id} · {report.target}
            </p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-50">
              <a
                href={report.repository_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-indigo-300"
              >
                {report.repository}
              </a>
            </h1>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-500">
              <span>{report.branch}</span>
              {report.commit_sha ? <span className="font-mono">{shortSha(report.commit_sha)}</span> : null}
              {report.finished_at ? <span>{new Date(report.finished_at).toLocaleString()}</span> : null}
            </p>
          </div>
          <Link
            href="/"
            className="shrink-0 rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100"
          >
            New scan
          </Link>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="flex flex-col gap-6">
          <Card className="flex flex-col items-center gap-4">
            <ScoreRing score={report.overall_score ?? 0} />
            <span className="rounded-full bg-zinc-800 px-3 py-1 text-sm font-medium text-zinc-200">
              {report.label ?? "No label"}
            </span>
            <div className="flex flex-wrap justify-center gap-2">
              {(["critical", "high", "medium", "low"] as const).map((level) => {
                const count = report.severity_counts[level];
                if (!count) return null;
                return <SeverityBadge key={level} severity={level} />;
              })}
              {severityTotal === 0 ? (
                <span className="text-sm text-emerald-400">
                  No findings — clean scan
                </span>
              ) : null}
            </div>
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
                        className="h-full rounded-full bg-emerald-500"
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
                  <li key={rec.rank} className="rounded-lg bg-zinc-900/80 p-4 ring-1 ring-inset ring-zinc-800">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-sm font-semibold text-zinc-100">
                        <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-indigo-500/15 text-xs font-semibold text-indigo-300">
                          {rec.rank}
                        </span>
                        {rec.title}
                      </h3>
                      <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs font-medium text-zinc-400">
                        {EFFORT_LABEL[rec.effort] ?? rec.effort} effort
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">
                      {rec.explanation}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-emerald-400">{rec.expected_impact}</span>
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
            <SectionTitle>
              Findings{" "}
              <span className="text-zinc-600">
                · {total} total, {summaries.length} shown
              </span>
            </SectionTitle>
            {summaries.length === 0 ? (
              <div className="mt-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-4 py-6 text-center">
                <p className="text-sm font-medium text-emerald-400">
                  No findings for this target
                </p>
                <p className="mt-1 text-xs text-zinc-500">
                  Nothing matched the analyzer rules at this weight and confidence.
                </p>
              </div>
            ) : (
              <>
                <ul className="mt-4 flex flex-col gap-4">
                  {summaries.map((item) => {
                    const detail = details.get(item.id);
                    const showSkeleton = !detail && !failedDetails.includes(item.id);
                    return (
                      <li
                        key={item.id}
                        id={item.id}
                        className="scroll-mt-6 rounded-lg bg-zinc-900/80 p-4 ring-1 ring-inset ring-zinc-800"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <SeverityBadge severity={item.severity} />
                          <span className="font-mono text-xs text-zinc-500">
                            {item.rule_id}
                          </span>
                          <span className="ml-auto font-mono text-xs text-zinc-500">
                            {item.id} · ×{item.occurrence_count}
                          </span>
                        </div>
                        <h3 className="mt-2 text-sm font-semibold text-zinc-100">
                          {item.title}
                        </h3>
                        <p className="mt-2 text-sm leading-6 text-zinc-400">
                          {showSkeleton ? (
                            <span className="text-zinc-600">Loading evidence…</span>
                          ) : (
                            detail?.description
                          )}
                        </p>

                        {detail && detail.evidence.length > 0 ? (
                          <div className="mt-3 flex flex-col gap-2">
                            {detail.evidence.slice(0, 3).map((ev, index) => (
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
                                    <span className="text-xs text-zinc-500">{ev.symbol}</span>
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
                            {detail.evidence.length > 3 ? (
                              <p className="text-xs text-zinc-600">
                                + {detail.evidence.length - 3} more occurrences
                              </p>
                            ) : null}
                          </div>
                        ) : null}

                        {detail && detail.recommendation ? (
                          <p className="mt-3 text-xs leading-5 text-zinc-500">
                            <span className="font-medium text-zinc-400">Fix: </span>
                            {detail.recommendation}
                          </p>
                        ) : null}

                        <div className="mt-3 flex items-center gap-2">
                          <ConfidenceBadge confidence={item.confidence} />
                          <span className="text-xs capitalize text-zinc-600">
                            {detail?.category ?? item.category}
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                {total > summaries.length ? (
                  <p className="mt-4 text-xs text-zinc-600">
                    Showing {summaries.length} of {total} findings — expand the list
                    via the API to see the rest.
                  </p>
                ) : null}
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}