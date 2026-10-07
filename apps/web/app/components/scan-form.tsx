"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { createScan, type TargetMode } from "@/app/lib/api";

const TARGETS: { id: TargetMode; label: string; blurb: string }[] = [
  {
    id: "portfolio",
    label: "Portfolio",
    blurb: "Weighted for hiring review: structure, tests, and docs.",
  },
  {
    id: "university",
    label: "University",
    blurb: "Coursework lens: clarity and completeness of implementation.",
  },
  {
    id: "production",
    label: "Production",
    blurb: "Security and dependency hygiene take priority.",
  },
];

const PLACEHOLDER = "https://github.com/owner/repository";

export default function ScanForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [target, setTarget] = useState<TargetMode>("portfolio");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Enter a GitHub repository URL to scan.");
      return;
    }
    setSubmitting(true);
    try {
      const scan = await createScan(trimmed, target);
      router.push(`/scans/${scan.scan_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the scan.");
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <div>
        <label
          htmlFor="repo-url"
          className="mb-2 block text-sm font-medium text-zinc-300"
        >
          Repository URL
        </label>
        <input
          id="repo-url"
          type="text"
          inputMode="url"
          autoComplete="url"
          spellCheck={false}
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder={PLACEHOLDER}
          disabled={submitting}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-60"
        />
      </div>

      <div>
        <span className="mb-2 block text-sm font-medium text-zinc-300">Target context</span>
        <div className="grid gap-2 sm:grid-cols-3">
          {TARGETS.map((option) => {
            const active = target === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => setTarget(option.id)}
                disabled={submitting}
                aria-pressed={active}
                className={`rounded-lg border px-4 py-3 text-left transition disabled:opacity-60 ${
                  active
                    ? "border-indigo-500 bg-indigo-500/10 ring-1 ring-indigo-500/40"
                    : "border-zinc-700 bg-zinc-900 hover:border-zinc-500"
                }`}
              >
                <span
                  className={`block text-sm font-semibold ${
                    active ? "text-indigo-300" : "text-zinc-200"
                  }`}
                >
                  {option.label}
                </span>
                <span className="mt-0.5 block text-xs text-zinc-500">
                  {option.blurb}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {error ? (
        <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-indigo-500 px-6 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? (
          <>
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
            Starting scan…
          </>
        ) : (
          "Start scan"
        )}
      </button>
    </form>
  );
}