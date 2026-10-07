"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { formatMs, getScan, shortSha, type ScanStatus } from "@/app/lib/api";
import { Card, ProgressBar, Spinner } from "@/app/components/ui";

const STAGES = [
  { key: "queued", label: "Queued" },
  { key: "fetching", label: "Fetching repository" },
  { key: "fingerprinting", label: "Building fingerprint" },
  { key: "analyzing", label: "Running analyzers" },
  { key: "scoring", label: "Scoring" },
  { key: "reporting", label: "Compiling report" },
] as const;

export default function ScanProgress({ scanId }: { scanId: number }) {
  const router = useRouter();
  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      if (cancelled) return;
      try {
        const status = await getScan(scanId);
        if (cancelled) return;
        if (status.status === "completed") {
          router.replace(`/scans/${scanId}/report`);
          return;
        }
        setScan(status);
        if (status.status === "failed") {
          setError(status.error_message ?? "The scan failed. Check the analyzer logs.");
          return;
        }
        timer = setTimeout(poll, 2000);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not reach the analyzer.");
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [scanId, router, attempt]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6">
        <Card className="border-red-500/30">
          <h2 className="text-lg font-semibold text-red-300">
            Scan could not be completed
          </h2>
          <p className="mt-2 text-sm text-zinc-400">{error}</p>
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => {
                setError(null);
                setScan(null);
                setAttempt((n) => n + 1);
              }}
              className="rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 transition hover:bg-zinc-700"
            >
              Try again
            </button>
            <Link
              href="/"
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm font-medium text-zinc-300 transition hover:border-zinc-500"
            >
              Back home
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  const currentStage = scan?.current_stage ?? null;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-16 sm:px-6">
      <Card>
        <div className="mb-6">
          <p className="text-xs uppercase tracking-wider text-zinc-500">Scanning</p>
          <h1 className="mt-1 flex items-center gap-3 text-2xl font-semibold tracking-tight text-zinc-100">
            <span className="truncate">{scan?.repository ?? "…"}</span>
            <Spinner />
          </h1>
          {scan?.repository_url ? (
            <a
              href={scan.repository_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block truncate text-sm text-indigo-400 hover:text-indigo-300"
            >
              {scan.repository_url.replace(/^https?:\/\//, "")}
            </a>
          ) : null}
        </div>

        <div className="flex items-end justify-between gap-4">
          <p className="text-sm text-zinc-400">
            {currentStage === "completed"
              ? "Completed"
              : currentStage
                ? STAGES.find((s) => s.key === currentStage)?.label ?? currentStage
                : "Contacting analyzer…"}
          </p>
          <p className="text-sm tabular-nums text-zinc-400">
            {scan?.progress_pct ?? 0}%
          </p>
        </div>
        <div className="mt-2">
          <ProgressBar value={scan?.progress_pct ?? 0} />
        </div>

        <ol className="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-0">
          {STAGES.map((stage, index) => {
            const stageIndex = STAGES.findIndex((s) => s.key === currentStage);
            const done = currentStage != null && index < stageIndex;
            const current = currentStage === stage.key;
            const isLast = index === STAGES.length - 1;
            return (
              <li
                key={stage.key}
                className="flex items-center gap-2 text-xs sm:flex-1"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold transition ${
                      done
                        ? "bg-emerald-500/20 text-emerald-400"
                        : current
                          ? "bg-indigo-500/25 text-indigo-300 ring-1 ring-inset ring-indigo-500/40"
                          : "bg-zinc-800 text-zinc-600"
                    }`}
                  >
                    {done ? "✓" : index + 1}
                  </span>
                  <span
                    className={
                      done || current ? "text-zinc-300" : "text-zinc-600"
                    }
                  >
                    {stage.label}
                  </span>
                </span>
                {!isLast ? (
                  <span
                    className={`mx-2 hidden h-px flex-1 sm:block ${
                      done ? "bg-emerald-500/40" : "bg-zinc-800"
                    }`}
                  />
                ) : null}
              </li>
            );
          })}
        </ol>

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-zinc-500">Target</dt>
            <dd className="mt-0.5 text-sm capitalize text-zinc-200">
              {scan?.target ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Branch</dt>
            <dd className="mt-0.5 font-mono text-sm text-zinc-200">
              {scan?.branch ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Commit</dt>
            <dd className="mt-0.5 font-mono text-sm text-zinc-200">
              {scan?.commit_sha ? shortSha(scan.commit_sha) : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">Started</dt>
            <dd className="mt-0.5 text-sm text-zinc-200">
              {scan ? new Date(scan.created_at).toLocaleString() : "—"}
            </dd>
          </div>
        </dl>
      </Card>

      {scan && scan.analyzer_runs.length > 0 ? (
        <Card className="mt-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            Analyzers
          </h2>
          <ul className="divide-y divide-zinc-800">
            {scan.analyzer_runs.map((run) => (
              <li key={run.analyzer} className="flex items-center gap-3 py-3">
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${
                    run.status === "running"
                      ? "animate-pulse bg-indigo-400"
                      : run.finding_count != null
                        ? "bg-emerald-500/70"
                        : "bg-zinc-700"
                  }`}
                />
                <span className="w-32 truncate text-sm font-medium text-zinc-300 sm:w-44">
                  {run.analyzer}
                </span>
                <span className="text-xs text-zinc-600">{run.version}</span>
                {run.status === "running" ? <Spinner /> : null}
                <span className="ml-auto text-xs text-zinc-500">
                  {run.finding_count != null
                    ? `${run.finding_count} findings · `
                    : ""}
                  {formatMs(run.duration_ms)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}