"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleLogin(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) setError(error.message);
    else router.push("/home");
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
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button className="w-full rounded bg-black px-3 py-2 text-white">
        Sign in
      </button>
      <button
        type="button"
        onClick={() => supabase.auth.signInWithOAuth({ provider: "google" })}
        className="w-full rounded border px-3 py-2"
      >
        Continue with Google
      </button>
    </form>
  );
}