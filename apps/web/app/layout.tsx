import type { Metadata } from "next";
import Link from "next/link";
import { getServerSession } from "next-auth";
import type { ReactNode } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { SignOutButton } from "@/components/sign-out-button";
import { authOptions } from "@/lib/auth-options";

import "./globals.css";

export const metadata: Metadata = {
  title: "Macro Economic Tracker",
  description: "Track-first macro intelligence workspace",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const session = await getServerSession(authOptions);
  const workspace = session?.backendUser?.workspaces?.[0];

  return (
    <html lang="en">
      <body>
        <AuthProvider session={session}>
          <div className="page-shell">
            <header className="topbar">
              <div>
                <p className="eyebrow">Macro Economic Tracker</p>
                <h1>Track-first intelligence workspace</h1>
                {workspace ? (
                  <p className="topbar__subtle">
                    {workspace.name} | {workspace.role}
                  </p>
                ) : null}
              </div>
              <nav className="topbar__nav">
                {session ? (
                  <>
                    <Link href="/">Inbox</Link>
                    <Link href="/tracks">Tracks</Link>
                    <Link href="/alerts">Alerts</Link>
                    <Link href="/settings">Settings</Link>
                    <Link href="/tracks/new">New track</Link>
                    <SignOutButton />
                  </>
                ) : (
                  <>
                    <Link href="/login">Sign in</Link>
                    <Link href="/accept-invite">Accept invite</Link>
                  </>
                )}
              </nav>
            </header>
            <main>{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
