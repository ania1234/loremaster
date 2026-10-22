"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

type Status =
  | { kind: "error"; message: string }
  | { kind: "info"; message: string }
  | { kind: "exists"; message: string }
  | null;

// Google's branding rules ask for the multicolour "G" next to the wording.
function GoogleLogo() {
  return (
    <svg viewBox="0 0 48 48" className="h-4 w-4" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  async function handleLogin(e: React.SubmitEvent<HTMLFormElement>) {
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

  async function handleGoogleSignIn() {
    setStatus(null);
    setBusy(true);
    // Lands on /home like the sign-up link; the client picks the session up
    // from the URL hash there.
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/home` },
    });
    // On success the browser is already on its way to Google.
    if (error) {
      setBusy(false);
      setStatus({ kind: "error", message: error.message });
    }
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
      <h1 className="engraver-title text-2xl">Sign in to Loremaster</h1>
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
        className="w-full rounded bg-[#385A55] px-3 py-2 text-white disabled:opacity-50"
      >
        Create account
      </button>
      <div className="flex items-center gap-3 text-xs text-gray-500">
        <span className="h-px flex-1 bg-gray-200" />
        or
        <span className="h-px flex-1 bg-gray-200" />
      </div>
      <button
        type="button"
        onClick={handleGoogleSignIn}
        disabled={busy}
        className="flex w-full items-center justify-center gap-2 rounded border px-3 py-2 disabled:opacity-50"
      >
        <GoogleLogo />
        Sign in with Google
      </button>
    </form>
  );
}
