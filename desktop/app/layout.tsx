import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "AutoFlow AI",
  description: "Turn one instruction into a verified workflow.",
  applicationName: "AutoFlow AI",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0f0f0f",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={cn(
          GeistSans.variable,
          GeistMono.variable,
          "font-sans bg-background text-foreground",
        )}
      >
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
