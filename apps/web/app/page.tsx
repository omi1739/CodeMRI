import Link from "next/link";
import ScanForm from "@/app/components/scan-form";

const FEATURES = [
  {
    mark: "S",
    title: "Health score",
    body: "A single 0–100 score broken down across security, tests, docs, structure, and dependencies.",
  },
  {
    mark: "E",
    title: "Pinned evidence",
    body: "Every finding links to the exact commit and source line, so you can verify it yourself.",
  },
  {
    mark: "O",
    title: "Security signals",
    body: "Secrets, unsafe patterns, and dependency advisories checked against OSV — plus more.",
  },
  {
    mark: "F",
    title: "Ranked fixes",
    body: "Top-five recommendations sorted by expected impact versus effort.",
  },
];

const STEPS = [
  { n: "01", title: "Paste a repo", body: "A public GitHub URL — any language, any size." },
  { n: "02", title: "Pick an audience", body: "Portfolio, university, or production scoring." },
  { n: "03", title: "Read the report", body: "Score, findings, evidence, and ranked fixes." },
];

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-14 sm:px-6 sm:py-20">
      <div className="mb-12 text-center">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-indigo-400">
          CodeMRI V1
        </p>
        <h1 className="text-balance text-4xl font-semibold tracking-tight text-zinc-50 sm:text-5xl">
          Know what your code&apos;s worth,{" "}
          <span className="bg-gradient-to-r from-indigo-400 to-sky-400 bg-clip-text text-transparent">
            commit by commit
          </span>
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-pretty text-base leading-7 text-zinc-400">
          Paste a public GitHub JavaScript/TypeScript repository and CodeMRI
          produces an evidence-backed health report: structure, hygiene,
          security signals, and a score pinned to a specific commit.
        </p>
      </div>

      <ScanForm />

      <div className="mt-12 grid gap-3 sm:grid-cols-3">
        {STEPS.map((step) => (
          <div
            key={step.n}
            className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4"
          >
            <p className="font-mono text-xs text-indigo-400">{step.n}</p>
            <h3 className="mt-1 text-sm font-semibold text-zinc-200">
              {step.title}
            </h3>
            <p className="mt-1 text-xs leading-5 text-zinc-500">{step.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-10">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-zinc-600">
          What you get
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 transition hover:border-zinc-700"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-indigo-500/15 text-xs font-semibold text-indigo-300 ring-1 ring-inset ring-indigo-500/30">
                  {feature.mark}
                </span>
                <h3 className="text-sm font-semibold text-zinc-200">
                  {feature.title}
                </h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-zinc-500">
                {feature.body}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-8 text-center text-sm text-zinc-500">
          Already scanned something?{" "}
          <Link
            href="/history"
            className="font-medium text-indigo-400 transition hover:text-indigo-300"
          >
            View your scan history
          </Link>
        </p>
      </div>
    </div>
  );
}