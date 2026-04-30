"use client";

import { useState } from "react";
import { createBrowserClient } from "@/lib/supabase/client";
import {
  MobileActionBar,
  ActionButton,
} from "@/components/ui/mobile-action-bar";

type SaveState = "prompt" | "sending" | "sent" | "error";

export default function SavePage() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<SaveState>("prompt");

  async function handleSave() {
    if (!email) return;

    setState("sending");

    try {
      const supabase = createBrowserClient();
      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: `${window.location.origin}/results`,
        },
      });

      if (error) {
        setState("error");
        return;
      }

      setState("sent");
    } catch {
      setState("error");
    }
  }

  if (state === "sent") {
    return (
      <div className="px-4 py-6 max-w-lg mx-auto text-center">
        <h1 className="text-2xl font-bold mb-2">Check Your Email</h1>
        <p className="text-base text-gray-600">
          We sent a magic link to <strong>{email}</strong>. Click it to save
          your results and start your 14-day premium trial.
        </p>
      </div>
    );
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Want to keep your results?</h1>
      <p className="text-base text-gray-600 mb-6">
        Enter your email to save your work and unlock a 14-day premium trial.
      </p>

      <label htmlFor="email" className="block text-base font-medium mb-2">
        Email address
      </label>
      <input
        id="email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="w-full min-h-[2.75rem] px-4 py-3 text-base border border-gray-300 rounded-lg"
        disabled={state === "sending"}
      />

      {state === "error" && (
        <p className="text-sm text-red-600 mt-2">
          Something went wrong. Please try again.
        </p>
      )}

      <MobileActionBar>
        <ActionButton
          onClick={handleSave}
          label={state === "sending" ? "Sending..." : "Save My Results"}
          disabled={!email || state === "sending"}
        />
      </MobileActionBar>
    </div>
  );
}
