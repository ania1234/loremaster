import type { Metadata } from "next";
import { Geist, Geist_Mono, IM_Fell_English, Noto_Serif_JP } from "next/font/google";
import "./globals.css";
import { UserBar } from "@/components/user_bar";
import { SideNav } from "@/components/side_nav";
import { NavMenuProvider } from "@/components/nav_menu";

import { InteractiveBackground } from "@/components/interactive_background";

const rippleEngraving = IM_Fell_English({
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-ripple-engraving",
});

const rippleCjk = Noto_Serif_JP({
  weight: "500",
  preload: false,
  variable: "--font-ripple-cjk",
});

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Loremaster",
  description: "RAG Application for RPG rules and sessions.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${rippleEngraving.variable} ${rippleCjk.variable} h-full antialiased`}
    >
      {/* The window itself never scrolls: each page scrolls inside its own
          column, so the bars around it stay put. */}
      <body className="flex h-full flex-col">
        <InteractiveBackground />
        <NavMenuProvider>
          <UserBar />
          <div className="flex min-h-0 flex-1">
            <SideNav />
            <div className="page-content min-w-0 flex-1 overflow-y-auto">{children}</div>
          </div>
        </NavMenuProvider>
      </body>
    </html>
  );
}
