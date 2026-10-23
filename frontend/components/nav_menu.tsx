"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

// On narrow screens the side nav becomes a drawer: the user bar holds the
// button that opens it, so the open state lives above both of them.
type NavMenu = { open: boolean; toggle: () => void; close: () => void };

const NavMenuContext = createContext<NavMenu | null>(null);

export function NavMenuProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <NavMenuContext.Provider
      value={{ open, toggle: () => setOpen((o) => !o), close: () => setOpen(false) }}
    >
      {children}
    </NavMenuContext.Provider>
  );
}

export function useNavMenu() {
  const menu = useContext(NavMenuContext);
  if (!menu) throw new Error("useNavMenu must be used inside NavMenuProvider");
  return menu;
}
