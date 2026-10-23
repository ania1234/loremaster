"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { FileText, MessageSquare, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useNavMenu } from "@/components/nav_menu";

const LINKS = [
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/chat", label: "Chat", icon: MessageSquare },
] as const;

const RECENT_CONVERSATIONS = 5;

type Conversation = { id: string; title: string | null };

// An allowlist rather than a denylist: the sign-in and password-recovery
// screens must never grow navigation into the app, and neither should any
// future standalone screen unless it opts in here.
const SHOWN_ON: ReadonlySet<string> = new Set(LINKS.map((l) => l.href));

export function hasSideNav(pathname: string) {
  return SHOWN_ON.has(pathname);
}

function linkClass(active: boolean) {
  return cn(
    "flex items-center gap-2 rounded px-3 py-2 text-sm",
    active
      ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
      : "text-sidebar-foreground hover:bg-sidebar-accent/60",
  );
}

export function SideNav() {
  const pathname = usePathname();
  const menu = useNavMenu();

  if (!hasSideNav(pathname)) return null;

  return (
    <>
      {/* Below md the nav is a drawer over the page, opened from the user bar;
          tapping beside it closes it, like the button does. */}
      {menu.open && (
        <div
          aria-hidden
          onClick={menu.close}
          className="fixed inset-x-0 top-14 bottom-0 z-30 bg-black/30 md:hidden"
        />
      )}
      <nav
        id="side-nav"
        className={cn(
          "w-52 shrink-0 overflow-y-auto border-r bg-sidebar p-3",
          menu.open
            ? "max-md:fixed max-md:top-14 max-md:bottom-0 max-md:left-0 max-md:z-40 max-md:w-64 max-md:max-w-[80vw] max-md:shadow-lg max-md:backdrop-blur-sm"
            : "max-md:hidden",
        )}
      >
        {/* useSearchParams needs a Suspense boundary, or `next build` fails. */}
        <Suspense>
          <NavLinks pathname={pathname} onNavigate={menu.close} />
        </Suspense>
      </nav>
    </>
  );
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate: () => void }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  // The conversation open in the chat; null on a new one or another page.
  const openId = pathname === "/chat" ? searchParams.get("c") : null;
  const [recent, setRecent] = useState<Conversation[]>([]);
  // Bumped after a delete, so the next-oldest conversation moves into the list.
  const [reloads, setReloads] = useState(0);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Refetched whenever the open conversation changes, which includes the
  // chat writing a brand-new conversation's id into the URL.
  useEffect(() => {
    let stale = false;
    apiFetch(`/api/conversations?limit=${RECENT_CONVERSATIONS}`)
      .then((res) => res.json())
      .then((conversations) => {
        if (!stale) setRecent(conversations);
      })
      .catch(() => {}); // the list is a shortcut; navigation works without it
    return () => {
      stale = true;
    };
  }, [openId, reloads]);

  async function handleDelete(c: Conversation) {
    if (!window.confirm(`Delete "${c.title ?? "Untitled"}"? This can't be undone.`)) {
      return;
    }
    setDeletingId(c.id);
    try {
      await apiFetch(`/api/conversations/${c.id}`, { method: "DELETE" });
      // A fresh chat replaces the deleted one; this also refetches the list.
      if (c.id === openId) router.replace("/chat");
    } catch {
      window.alert("Couldn't delete the conversation. Please try again.");
    } finally {
      setDeletingId(null);
      setReloads((n) => n + 1);
    }
  }

  return (
    <>
      <ul className="space-y-1">
        {LINKS.map(({ href, label, icon: Icon }) => {
          // "Chat" means a new conversation; an open one is marked below.
          const active = pathname === href && !openId;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                onClick={onNavigate}
                className={linkClass(active)}
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>

      {recent.length > 0 && (
        <section className="mt-6">
          <h2 className="px-3 pb-1 text-xs font-medium text-muted-foreground">
            Recent conversations
          </h2>
          <ul className="space-y-1">
            {recent.map((c) => {
              const active = c.id === openId;
              const title = c.title ?? "Untitled";
              return (
                <li key={c.id} className="group relative">
                  <Link
                    href={`/chat?c=${c.id}`}
                    aria-current={active ? "page" : undefined}
                    title={title}
                    onClick={onNavigate}
                    className={cn(linkClass(active), "pr-8")}
                  >
                    <span className="truncate">{title}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(c)}
                    disabled={deletingId === c.id}
                    aria-label={`Delete conversation "${title}"`}
                    title="Delete conversation"
                    className={cn(
                      "absolute top-1/2 right-1 -translate-y-1/2 rounded p-1 text-muted-foreground",
                      "hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100",
                      "group-hover:opacity-100 disabled:opacity-50",
                      active ? "opacity-100" : "opacity-0",
                    )}
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}
