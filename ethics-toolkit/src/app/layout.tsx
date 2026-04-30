import type { Metadata } from "next";
import { LEGAL_DISCLAIMER, APP_NAME } from "@/lib/constants";
import "./globals.css";

export const metadata: Metadata = {
  title: APP_NAME,
  description: "AI Filmmaking Ethics Toolkit",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col bg-white text-gray-900">
        <main className="flex-1">{children}</main>
        <footer className="p-4 text-center text-sm text-gray-500 border-t border-gray-200">
          {LEGAL_DISCLAIMER}
        </footer>
      </body>
    </html>
  );
}
