"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { useNavMenu } from "@/components/nav_menu";
import { hasSideNav } from "@/components/side_nav";

// The sign-in page is its own landing screen and carries no bar. A recovery
// link creates a real session, so the bar would otherwise show up mid-reset
// and offer to log the user out of the flow they are still completing.
const HIDDEN_ON = new Set(["/", "/reset-password"]);

export function UserBar() {
  const [email, setEmail] = useState<string | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const menu = useNavMenu();

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
    <header className="flex h-14 shrink-0 items-center justify-end gap-3 border-b px-4 text-sm md:px-8">
      {hasSideNav(pathname) && (
        <button
          type="button"
          onClick={menu.toggle}
          aria-expanded={menu.open}
          aria-controls="side-nav"
          aria-label={menu.open ? "Close menu" : "Open menu"}
          className="mr-auto shrink-0 rounded p-1.5 hover:bg-gray-50 md:hidden"
        >
          <Menu className="size-5" aria-hidden />
        </button>
      )}
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
