import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaveMePls - Aegis Drone Command",
  description: "Autonomous Command Agent system for rescue drone orchestration in disaster zones.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
