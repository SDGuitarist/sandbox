"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  MobileActionBar,
  ActionButton,
} from "@/components/ui/mobile-action-bar";

type LoginState = "idle" | "submitting" | "error";

export default function FacilitatorLoginPage() {
  const [password, setPassword] = useState("");
  const [state, setState] = useState<LoginState>("idle");
  const router = useRouter();

  async function handleLogin() {
    if (!password) return;

    setState("submitting");

    try {
      const response = await fetch("/api/auth/facilitator-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (response.ok) {
        router.push("/facilitator");
      } else {
        setState("error");
      }
    } catch {
      setState("error");
    }
  }

  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Facilitator Login</h1>
      <p className="text-base text-gray-600 mb-6">
        Enter the facilitator password to access workshop management.
      </p>

      <label htmlFor="password" className="block text-base font-medium mb-2">
        Password
      </label>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Enter password"
        className="w-full min-h-[2.75rem] px-4 py-3 text-base border border-gray-300 rounded-lg"
        disabled={state === "submitting"}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleLogin();
        }}
      />

      {state === "error" && (
        <p className="text-sm text-red-600 mt-2">
          Invalid password. Please try again.
        </p>
      )}

      <MobileActionBar>
        <ActionButton
          onClick={handleLogin}
          label={state === "submitting" ? "Logging in..." : "Log In"}
          disabled={!password || state === "submitting"}
        />
      </MobileActionBar>
    </div>
  );
}
