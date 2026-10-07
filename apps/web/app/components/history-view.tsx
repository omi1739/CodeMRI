"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { listScans, shortSha, type ScanHistoryEntry } from "@/app/lib/api";
import { Card, Skeleton, scoreTextTone } from "@/app/components/ui";

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  failed: "bg-red-500/15 text-red-400 ring-red-500/30",
  queued: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30",
  fetching: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  fingerprinting: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  analyzing: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  scoring: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
  reporting: "bg-sky-500/15 text-sky-400 ring-sky-500/30",
};

const ACTIVE_STATUSES = [
  "queued",
  "fetching",
  "fingerprinting",
  "analyzing",
  "scoring",
  "reporting",
] as const;

type StatusFilter = "all" | "completed" | "in-progress" | "failed";

export default function HistoryView() {
  const [scans, setScans] = useState<ScanHistoryEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await listScans(50);
        if (!cancelled) setScans(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load scan history.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    if (!scans) return null;
    return scans.filter((scan) => {
      if (filter === "all") return true;
      if (filter === "completed") return scan.status === "completed";
      if (filter === "failed") return scan.status === "failed";
      return (ACTIVE_STATUSES as readonly string[]).includes(scan.status);
    });
  }, [scans, filter]);

  const counts = useMemo(() => {
    if (!scans) return { all: 0, completed: 0, failed: 0, "in-progress": 0 };
    return {
      all: scans.length,
      completed: scans.filter((s) => s.status === "completed").length,
      failed: scans.filter((s) => s.status === "failed").length,
      "in-progress": scans.filter((s) =>
        (ACTIVE_STATUSES as readonly string[]).includes(s.status)
      ).length,
    };
  }, [scans]);

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-12">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            Recent activity
          </p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-50">
            Scan history
          </h1>
        </div>
        <Link
          href="/"
          className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400"
        >
          New scan
        </Link>
      </header>

      {error ? (
        <Card className="border-red-500/30">
          <h2 className="text-lg font-semibold text-red-300">History unavailable</h2>
          <p className="mt-2 text-sm text-zinc-400">{error}</p>
          <p className="mt-3 text-xs text-zinc-500">
            Start a scan to create the first entry.
          </p>
        </Card>
      ) : scans === null ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4"
            >
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="mt-2 h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : scans.length === 0 ? (
        <Card>
          <div className="py-8 text-center">
            <p className="text-sm font-medium text-zinc-300">No scans yet</p>
            <p className="mt-1 text-xs text-zinc-500">
              Paste a repository URL on the home page to get started.
            </p>
          </div>
        </Card>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            {(
              [
                ["all", "All"],
                ["completed", "Completed"],
                ["in-progress", "In progress"],
                ["failed", "Failed"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  filter === key
                    ? "bg-indigo-500/15 text-indigo-200 ring-1 ring-inset ring-indigo-500/40"
                    : "bg-zinc-900 text-zinc-400 ring-1 ring-inset ring-zinc-800 hover:text-zinc-200"
                }`}
              >
                {label}
                <span className={`ml-1.5 ${filter === key ? "text-indigo-300" : "text-zinc-600"}`}>
                  {counts[key]}
                </span>
              </button>
            ))}
          </div>

          {filtered && filtered.length === 0 ? (
            <Card>
              <div className="py-8 text-center text-sm text-zinc-500">
                No scans match this filter.
              </div>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {filtered?.map((scan) => {
                const inProgress = scan.status !== "completed" && scan.status !== "failed";
                const href =
                  scan.status === "completed"
                    ? `/scans/${scan.scan_id}/report`
                    : `/scans/${scan.scan_id}`;
                return (
                  <Link
                    key={scan.scan_id}
                    href={href}
                    className="group rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:border-zinc-600 hover:bg-zinc-900"
                  >
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">
                          {scan.repository}
                        </p>
                        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-zinc-500">
                          <span>Scan #{scan.scan_id}</span>
                          <span>·</span>
                          <span className="capitalize">{scan.target}</span>
                          <span>·</span>
                          <span>{new Date(scan.created_at).toLocaleString()}</span>
                          {scan.commit_sha ? (
                            <>
                              <span>·</span>
                              <span className="font-mono">{shortSha(scan.commit_sha)}</span>
                            </>
                          ) : null}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        {scan.overall_score != null ? (
                          <div className="text-right">
                            <p
                              className={`text-lg font-semibold tabular-nums ${scoreTextTone(scan.overall_score)}`}
                            >
                              {scan.overall_score}
                            </p>
                            <p className="text-xs text-zinc-500">{scan.label}</p>
                          </div>
                        ) : null}
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium capitalize ring-1 ring-inset ${
                            STATUS_STYLE[scan.status] ?? STATUS_STYLE.queued
                          }`}
                        >
                          {inProgress ? (
                            <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                          ) : null}
                          {scan.status}
                        </span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}