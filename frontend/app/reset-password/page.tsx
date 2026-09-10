"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

// The client uses the implicit flow with detectSessionInUrl, so the recovery
// tokens arrive in the URL hash and are exchanged for a session before the
// first auth event fires. Until that happens we don't know if the link is good.
type LinkState = "checking" | "ready" | "invalid";

export default function ResetPasswordPage() {
  const [linkState, setLinkState] = useState<LinkState>("checking");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      // INITIAL_SESSION is emitted only once the hash has been processed, so a
      // null session at that point means there was no usable recovery token.
      if (session) {
        setLinkState("ready");
        return;
      }
      // An expired or already-used link comes back as an error in the hash
      // instead of tokens, and never produces a session.
      const hashError = new URLSearchParams(
        window.location.hash.replace(/^#/, ""),
      ).get("error_description");
      if (hashError) setError(hashError);
      setLinkState("invalid");
    });
    return () => data.subscription.unsubscribe();
  }, []);

  async function handleUpdatePassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (password !== confirmation) {
      setError("The two passwords do not match.");
      return;
    }

    setBusy(true);
    const { error } = await supabase.auth.updateUser({ password });
    setBusy(false);

    if (error) {
      setError(error.message);
      return;
    }

    setDone(true);
    router.push("/home");
  }

  if (linkState === "checking") {
    return (
      <main className="mx-auto mt-24 max-w-sm space-y-4">
        <p className="text-sm text-gray-500">Checking your reset link…</p>
      </main>
    );
  }

  if (linkState === "invalid") {
    return (
      <main className="mx-auto mt-24 max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold">Reset link expired</h1>
        <p className="text-sm text-gray-700">
          {error ?? "This password reset link is no longer valid."} Request a
          new one from the sign-in page.
        </p>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="w-full rounded bg-black px-3 py-2 text-white"
        >
          Back to sign in
        </button>
      </main>
    );
  }

  return (
    <form
      onSubmit={handleUpdatePassword}
      className="mx-auto mt-24 max-w-sm space-y-4"
    >
      <h1 className="text-2xl font-semibold">Choose a new password</h1>
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="new password"
        className="w-full rounded border px-3 py-2"
      />
      <input
        type="password"
        value={confirmation}
        onChange={(e) => setConfirmation(e.target.value)}
        placeholder="confirm new password"
        className="w-full rounded border px-3 py-2"
      />
      {error && <p className="text-sm text-red-600">{error}</p>}
      {done && <p className="text-sm text-gray-700">Password updated.</p>}
      <button
        type="submit"
        disabled={busy || done}
        className="w-full rounded bg-black px-3 py-2 text-white disabled:opacity-50"
      >
        Update password
      </button>
    </form>
  );
}
