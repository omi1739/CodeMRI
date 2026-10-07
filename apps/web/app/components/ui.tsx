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

export function ScoreRing({ score, size = 180 }: { score: number; size?: number }) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference - (clamped / 100) * circumference;
  const color = clamped >= 80 ? "#34d399" : clamped >= 60 ? "#fbbf24" : "#f87171";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
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