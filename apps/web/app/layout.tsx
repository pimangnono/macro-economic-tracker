import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Macro Economic Tracker",
  description: "Track-first macro intelligence workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="page-shell">
          <header className="topbar">
            <div>
              <p className="eyebrow">Macro Economic Tracker</p>
              <h1>Track-first intelligence workspace</h1>
            </div>
            <nav className="topbar__nav">
              <Link href="/">Inbox</Link>
              <Link href="/tracks/new">New track</Link>
              <a href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/docs`}>
                API docs
              </a>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
