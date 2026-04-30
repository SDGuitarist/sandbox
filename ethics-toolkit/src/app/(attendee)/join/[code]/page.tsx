"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createBrowserClient } from "@/lib/supabase/client";
import { getOrCreateAnonymousSessionId } from "@/lib/auth/anonymous-session";

type JoinState = "loading" | "valid" | "invalid" | "error";

export default function JoinPage() {
  const params = useParams<{ code: string }>();
  const router = useRouter();
  const [state, setState] = useState<JoinState>("loading");

  useEffect(() => {
    async function validateAndJoin() {
      try {
        const supabase = createBrowserClient();
        const { data, error } = await supabase
          .from("workshop_sessions")
          .select("id, status")
          .eq("session_code", params.code)
          .single();

        if (error || !data) {
          setState("invalid");
          return;
        }

        if (data.status !== "active") {
          setState("invalid");
          return;
        }

        getOrCreateAnonymousSessionId();
        localStorage.setItem("workshopSessionId", data.id);
        setState("valid");
        router.push("/");
      } catch {
        setState("error");
      }
    }

    validateAndJoin();
  }, [params.code, router]);

  return (
    <div className="px-4 py-6 max-w-lg mx-auto text-center">
      {state === "loading" && (
        <p className="text-base text-gray-600">Joining workshop...</p>
      )}
      {state === "valid" && (
        <p className="text-base text-gray-600">
          Joined! Redirecting to tools...
        </p>
      )}
      {state === "invalid" && (
        <div>
          <h1 className="text-2xl font-bold mb-2">Invalid Session</h1>
          <p className="text-base text-gray-600">
            This workshop session code is not valid or the session has ended.
          </p>
        </div>
      )}
      {state === "error" && (
        <div>
          <h1 className="text-2xl font-bold mb-2">Something Went Wrong</h1>
          <p className="text-base text-gray-600">
            Unable to join the workshop. Please try again.
          </p>
        </div>
      )}
    </div>
  );
}
