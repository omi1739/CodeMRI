"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Scan", match: (p: string) => p === "/" },
  { href: "/history", label: "History", match: (p: string) => p.startsWith("/history") },
];

export default function SiteNav() {
  const pathname = usePathname();
  return (
    <nav className="flex items-center gap-1 rounded-full bg-zinc-900/70 p-1 ring-1 ring-inset ring-zinc-800">
      {LINKS.map((link) => {
        const active = link.match(pathname);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
              active
                ? "bg-indigo-500/15 text-indigo-200 ring-1 ring-inset ring-indigo-500/40"
                : "text-zinc-400 hover:text-zinc-100"
            }`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}