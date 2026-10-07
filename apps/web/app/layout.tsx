import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CodeMRI",
  description:
    "Evidence-backed code health reports for JavaScript repositories.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-zinc-950 text-zinc-100">
        <header className="sticky top-0 z-20 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-6 py-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-lg font-semibold tracking-tight text-zinc-50"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-500/15 ring-1 ring-inset ring-indigo-500/40">
                <span className="text-xs font-bold text-indigo-400">M</span>
              </span>
              Code<span className="text-indigo-400">MRI</span>
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                href="/"
                className="text-sm font-medium text-zinc-400 transition hover:text-zinc-100"
              >
                Scan
              </Link>
              <Link
                href="/history"
                className="text-sm font-medium text-zinc-400 transition hover:text-zinc-100"
              >
                History
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-zinc-800/80">
          <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4 text-xs text-zinc-600">
            <span>CodeMRI V1</span>
            <span>Findings link to pinned commit evidence</span>
          </div>
        </footer>
      </body>
    </html>
  );
}