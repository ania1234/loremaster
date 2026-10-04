import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { UserBar } from "@/components/user_bar";
import { SideNav } from "@/components/side_nav";

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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* The window itself never scrolls: each page scrolls inside its own
          column, so the bars around it stay put. */}
      <body className="flex h-full flex-col">
        <UserBar />
        <div className="flex min-h-0 flex-1">
          <SideNav />
          <div className="min-w-0 flex-1 overflow-y-auto">{children}</div>
        </div>
      </body>
    </html>
  );
}
