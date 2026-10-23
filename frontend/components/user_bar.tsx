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
    // INITIAL_SESSION fills in the account details after mount; the header
    // already reserves its height while the session is being restored.
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user.email ?? null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/");
  }

  if (HIDDEN_ON.has(pathname)) return null;

  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b px-8 text-sm">
      {email && (
        <>
          <span className="min-w-0 truncate text-gray-600">Logged in as {email}</span>
          <button
            type="button"
            onClick={handleSignOut}
            className="shrink-0 rounded border px-3 py-1 hover:bg-gray-50"
          >
            Log out
          </button>
        </>
      )}
    </header>
  );
}
