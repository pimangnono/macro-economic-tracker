"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";

const PUBLIC_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function AcceptInviteForm() {
  const searchParams = useSearchParams();
  const [inviteToken, setInviteToken] = useState(searchParams.get("token") ?? "");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch(`${PUBLIC_API_BASE_URL}/api/v1/auth/accept-invite`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          inviteToken,
          displayName,
          password,
        }),
      });

      if (!response.ok) {
        throw new Error("Invite acceptance failed");
      }

      const payload = (await response.json()) as { user: { email: string } };
      const signInResult = await signIn("credentials", {
        email: payload.user.email,
        password,
        redirect: false,
        callbackUrl: "/",
      });
      if (!signInResult?.ok) {
        throw new Error("Sign-in failed after accepting invite");
      }
      window.location.href = signInResult.url ?? "/";
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Invite acceptance failed");
      setIsSubmitting(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <label>
        <span>Invite token</span>
        <input value={inviteToken} onChange={(event) => setInviteToken(event.target.value)} required />
      </label>
      <label>
        <span>Display name</span>
        <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
      </label>
      <label>
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="new-password"
          required
        />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Accepting..." : "Accept invite"}
      </button>
    </form>
  );
}
