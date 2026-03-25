import type { Metadata } from "next";
import { Roboto } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "../components/UI/Toast";

const roboto = Roboto({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700", "900"],
  variable: "--font-roboto",
});

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
      <body className={`${roboto.variable} font-sans antialiased`}>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  );
}
