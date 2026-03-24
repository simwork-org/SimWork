"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { claimInvite, getMe, getMySessions, setMyRole } from "@/lib/api";
import { useAuthToken } from "@/lib/useAuthToken";
import {
  clearPendingAuthState,
  findAssignedSession,
  readPendingAuthState,
  resolveAuthenticatedDestination,
  setCookie,
} from "@/lib/auth-routing";

export default function AuthRedirectPage() {
  const ready = useAuthToken();
  const router = useRouter();
  const [status, setStatus] = useState("Signing you in...");

  useEffect(() => {
    if (!ready) return;

    async function redirect() {
      try {
        const { role, invite, next } = readPendingAuthState();
        clearPendingAuthState();

        if (role === "company") {
          setStatus("Setting up your account...");
          await setMyRole("company");
        }

        if (invite) {
          setStatus("Preparing your assessment...");
          try {
            const result = await claimInvite(invite);
            if (result.company_name) {
              setCookie("simwork_company", result.company_name);
            }
            router.replace(`/briefing/${result.session_id}`);
            return;
          } catch {
          }
        }

        const me = await getMe();

        if (me.role === "company") {
          if (!role && !invite) {
            router.replace("/dashboard?notice=candidate-access-company");
            return;
          }
          router.replace(resolveAuthenticatedDestination(me.role, [], next));
        } else {
          const { sessions } = await getMySessions();
          const assignedSession = findAssignedSession(sessions);
          if (assignedSession?.company_name) {
            setCookie("simwork_company", assignedSession.company_name);
          }
          router.replace(resolveAuthenticatedDestination(me.role, sessions, next));
        }
      } catch {
        router.replace("/?auth=candidate");
      }
    }

    redirect();
  }, [ready, router]);

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: "#101122" }}
    >
      <div className="text-center">
        <div className="flex items-center justify-center size-14 bg-[#10B981] rounded-2xl text-white mx-auto mb-4 animate-pulse">
          <span className="material-symbols-outlined text-3xl">strategy</span>
        </div>
        <p className="text-slate-400 text-sm">{status}</p>
      </div>
    </div>
  );
}
