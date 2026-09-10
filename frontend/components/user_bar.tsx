"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

// The sign-in page is its own landing screen and carries no bar. A recovery
// link creates a real session, so the bar would otherwise show up mid-reset
// and offer to log the user out of the flow they are still completing.
const HIDDEN_ON = new Set(["/", "/reset-password"]);

export function UserBar() {
  const [email, setEmail] = useState<string | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    // INITIAL_SESSION fires on mount, so this covers the first paint as well
    // as later sign-in/sign-out events.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user.email ?? null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/");
  }

  if (HIDDEN_ON.has(pathname) || !email) return null;

  return (
    <header className="flex items-center justify-end gap-3 border-b px-8 py-3 text-sm">
      <span className="text-gray-600">Logged in as {email}</span>
      <button
        type="button"
        onClick={handleSignOut}
        className="rounded border px-3 py-1 hover:bg-gray-50"
      >
        Log out
      </button>
    </header>
  );
}
