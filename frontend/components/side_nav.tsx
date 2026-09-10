"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FileText, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/chat", label: "Chat", icon: MessageSquare },
] as const;

// An allowlist rather than a denylist: the sign-in and password-recovery
// screens must never grow navigation into the app, and neither should any
// future standalone screen unless it opts in here.
const SHOWN_ON: ReadonlySet<string> = new Set(LINKS.map((l) => l.href));

export function SideNav() {
  const pathname = usePathname();

  if (!SHOWN_ON.has(pathname)) return null;

  return (
    <nav className="w-52 shrink-0 border-r bg-sidebar p-3">
      <ul className="space-y-1">
        {LINKS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded px-3 py-2 text-sm",
                  active
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
