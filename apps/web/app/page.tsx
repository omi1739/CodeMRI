import Link from "next/link";
import ScanForm from "@/app/components/scan-form";

const FEATURES = [
  {
    title: "Health score",
    body: "A single 0–100 score broken down across security, tests, docs, structure, and dependencies.",
  },
  {
    title: "Pinned evidence",
    body: "Every finding links to the exact commit and source line, so you can verify it yourself.",
  },
  {
    title: "Security signals",
    body: "Secrets, unsafe patterns, and dependency advisories checked against OSV — plus more.",
  },
  {
    title: "Ranked fixes",
    body: "Top-five recommendations sorted by expected impact versus effort.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-16">
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

      <div className="mt-12">
        <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-zinc-600">
          What you get
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4"
            >
              <h3 className="text-sm font-semibold text-zinc-200">{feature.title}</h3>
              <p className="mt-1 text-sm leading-6 text-zinc-500">{feature.body}</p>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-sm text-zinc-500">
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