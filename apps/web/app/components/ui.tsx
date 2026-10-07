import type { Severity } from "@/app/lib/api";

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

const SEVERITY_BADGE: Record<Severity, string> = {
  critical: "bg-red-500/15 text-red-400 ring-1 ring-inset ring-red-500/30",
  high: "bg-orange-500/15 text-orange-400 ring-1 ring-inset ring-orange-500/30",
  medium: "bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-500/30",
  low: "bg-sky-500/15 text-sky-400 ring-1 ring-inset ring-sky-500/30",
  info: "bg-zinc-500/15 text-zinc-400 ring-1 ring-inset ring-zinc-500/30",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const style = SEVERITY_BADGE[severity as Severity] ?? SEVERITY_BADGE.info;
  const label = SEVERITY_LABEL[severity as Severity] ?? severity;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${style}`}
    >
      {label}
    </span>
  );
}

const CONFIDENCE_BADGE: Record<string, string> = {
  high: "bg-emerald-500/15 text-emerald-400 ring-1 ring-inset ring-emerald-500/30",
  medium: "bg-sky-500/15 text-sky-400 ring-1 ring-inset ring-sky-500/30",
  low: "bg-zinc-500/15 text-zinc-400 ring-1 ring-inset ring-zinc-500/30",
};

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CONFIDENCE_BADGE[confidence] ?? CONFIDENCE_BADGE.low}`}
    >
      {confidence}
    </span>
  );
}

export function Chip({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center rounded-md bg-zinc-800/80 px-2 py-1 text-xs text-zinc-300 ring-1 ring-inset ring-zinc-700/60"
    >
      {children}
    </span>
  );
}

export function ProgressBar({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
      <div
        className="h-full rounded-full bg-indigo-500 transition-[width] duration-500 ease-out"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export function ScoreRing({ score, size = 168 }: { score: number; size?: number }) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference - (clamped / 100) * circumference;
  const color = scoreColor(clamped);
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-zinc-800"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-semibold tracking-tight text-zinc-100">
          {clamped}
        </span>
        <span className="text-xs uppercase tracking-widest text-zinc-500">/ 100</span>
      </div>
    </div>
  );
}

export function scoreColor(score: number): string {
  if (score >= 90) return "#34d399"; // emerald
  if (score >= 75) return "#38bdf8"; // sky
  if (score >= 60) return "#fbbf24"; // amber
  if (score >= 40) return "#fb923c"; // orange
  return "#f87171"; // red
}

export function scoreBarTone(score: number): string {
  if (score >= 90) return "bg-emerald-400";
  if (score >= 75) return "bg-sky-400";
  if (score >= 60) return "bg-amber-400";
  if (score >= 40) return "bg-orange-400";
  return "bg-red-400";
}

export function scoreLabelTone(label: string | null | undefined): string {
  switch (label) {
    case "Excellent":
      return "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30";
    case "Good":
      return "bg-sky-500/15 text-sky-400 ring-sky-500/30";
    case "Fair":
      return "bg-amber-500/15 text-amber-300 ring-amber-500/30";
    case "Needs work":
      return "bg-orange-500/15 text-orange-400 ring-orange-500/30";
    case "At risk":
      return "bg-red-500/15 text-red-400 ring-red-500/30";
    default:
      return "bg-zinc-500/15 text-zinc-400 ring-zinc-500/30";
  }
}

export function scoreTextTone(score: number): string {
  if (score >= 90) return "text-emerald-300";
  if (score >= 75) return "text-sky-300";
  if (score >= 60) return "text-amber-300";
  if (score >= 40) return "text-orange-300";
  return "text-red-300";
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 px-4 py-3">
      <dt className="truncate text-xs text-zinc-500">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-semibold text-zinc-100" title={hint}>
        {value}
      </dd>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-zinc-800/70 ${className}`}
    />
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
      {children}
    </h2>
  );
}

export function Spinner() {
  return (
    <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-500 border-t-transparent align-middle" />
  );
}