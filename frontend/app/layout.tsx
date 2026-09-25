import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solana Explorer AI",
  description: "AI-powered debugging assistant for Solana transactions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
