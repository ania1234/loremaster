"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

type Status =
  | { kind: "error"; message: string }
  | { kind: "info"; message: string }
  | { kind: "exists"; message: string }
  | null;

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function handleLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatus(null);
    setBusy(true);
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    setBusy(false);
    if (error) setStatus({ kind: "error", message: error.message });
    else router.push("/home");
  }

  async function handleSignUp() {
    setStatus(null);

    if (!email || !password) {
      setStatus({
        kind: "error",
        message: "Enter an email and password to create an account.",
      });
      return;
    }

    setBusy(true);
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/home` },
    });
    setBusy(false);

    // Supabase returns "User already registered" only when email confirmation
    // is off. With confirmation on it returns a placeholder user with an empty
    // identities array instead, so the address is not leaked outright.
    const alreadyRegistered =
      error?.code === "user_already_exists" ||
      (!error && data.user?.identities?.length === 0);

    if (alreadyRegistered) {
      setStatus({
        kind: "exists",
        message: `An account for ${email} already exists.`,
      });
      return;
    }

    if (error) {
      setStatus({ kind: "error", message: error.message });
      return;
    }

    if (data.session) {
      // Email confirmation is disabled on the project: signed in already.
      router.push("/home");
      return;
    }

    setStatus({
      kind: "info",
      message: `Account created. Check ${email} for the activation link.`,
    });
  }

  async function handleResetPassword() {
    setBusy(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setBusy(false);
    if (error) setStatus({ kind: "error", message: error.message });
    else
      setStatus({
        kind: "info",
        message: `Password reset link sent to ${email}.`,
      });
  }

  return (
    <form onSubmit={handleLogin} className="mx-auto mt-24 max-w-sm space-y-4">
      <h1 className="text-2xl font-semibold">Sign in to Loremaster</h1>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="w-full rounded border px-3 py-2"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="password"
        className="w-full rounded border px-3 py-2"
      />
      {status && (
        <div className="space-y-2">
          <p
            className={
              status.kind === "error"
                ? "text-sm text-red-600"
                : "text-sm text-gray-700"
            }
          >
            {status.message}
          </p>
          {status.kind === "exists" && (
            <button
              type="button"
              onClick={handleResetPassword}
              disabled={busy}
              className="w-full rounded border px-3 py-2 disabled:opacity-50"
            >
              Send password reset link
            </button>
          )}
        </div>
      )}
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
      >
        Sign in
      </button>
      <button
        type="button"
        onClick={handleSignUp}
        disabled={busy}
        className="w-full rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-50"
      >
        Create account
      </button>
    </form>
  );
}
