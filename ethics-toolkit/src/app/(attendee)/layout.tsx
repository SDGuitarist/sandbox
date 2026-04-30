"use client";

import { useEffect } from "react";
import { AttendeeNav } from "@/components/ui/nav";
import { getOrCreateAnonymousSessionId } from "@/lib/auth/anonymous-session";
import { registerServiceWorker } from "@/lib/sw-register";

export default function AttendeeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    getOrCreateAnonymousSessionId();
    registerServiceWorker();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <AttendeeNav />
      <main className="flex-1 pb-20">{children}</main>
      <footer className="px-4 py-3 text-xs text-gray-400 text-center border-t border-gray-100">
        Guidance, not legal advice. Consult an entertainment attorney for legal
        counsel.
      </footer>
    </div>
  );
}
