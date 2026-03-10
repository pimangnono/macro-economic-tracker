"use client";

import { signOut, useSession } from "next-auth/react";

const PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function SignOutButton() {
  const { data: session } = useSession();

  async function handleSignOut() {
    if (session?.accessToken) {
      await fetch(`${PUBLIC_API_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      }).catch(() => undefined);
    }
    await signOut({ callbackUrl: "/login" });
  }

  return (
    <button className="ghost-button" type="button" onClick={handleSignOut}>
      Sign out
    </button>
  );
}
