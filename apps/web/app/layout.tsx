import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import SiteNav from "./components/site-nav";
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

export const viewport: Viewport = {
  themeColor: "#09090b",
};

export default function RootLayout({ children }: { children: ReactNode }) {
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
            <SiteNav />
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-zinc-800/80">
          <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-zinc-600 sm:flex-row">
            <span>
              CodeMRI <span className="text-zinc-500">V1</span>
            </span>
            <span>Findings link to pinned commit evidence</span>
            <span className="text-zinc-700">
              health reports for JavaScript repositories
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}