"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";
import { signIn } from "next-auth/react";

export function SignInForm() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("analyst@macrotracker.local");
  const [password, setPassword] = useState("macro-demo-pass");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const callbackUrl = searchParams.get("callbackUrl") || "/";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const response = await signIn("credentials", {
      email,
      password,
      redirect: false,
      callbackUrl,
    });

    if (!response?.ok) {
      setError("Sign-in failed. Check the seeded credentials or invite status.");
      setIsSubmitting(false);
      return;
    }

    window.location.href = response.url ?? "/";
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <label>
        <span>Email</span>
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="email"
          required
        />
      </label>
      <label>
        <span>Password</span>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {error ? <p className="form-error">{error}</p> : null}
      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in..." : "Sign in"}
      </button>
    </form>
  );
}
