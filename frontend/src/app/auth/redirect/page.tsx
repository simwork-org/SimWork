"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { claimInvite, getMe, getMySessions, setMyRole } from "@/lib/api";
import { useAuthToken } from "@/lib/useAuthToken";

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
}

function clearCookie(name: string) {
  document.cookie = `${name}=;path=/;max-age=0`;
}

export default function AuthRedirectPage() {
  const ready = useAuthToken();
  const router = useRouter();
  const [status, setStatus] = useState("Signing you in...");

  useEffect(() => {
    if (!ready) return;

    async function redirect() {
      try {
        const pendingRole = getCookie("simwork_role");
        const pendingInvite = getCookie("simwork_invite");
        clearCookie("simwork_role");
        clearCookie("simwork_invite");

        if (pendingRole === "company") {
          setStatus("Setting up your account...");
          await setMyRole("company");
        }

        if (pendingInvite) {
          setStatus("Preparing your assessment...");
          try {
            const result = await claimInvite(pendingInvite);
            if (result.company_name) {
              document.cookie = `simwork_company=${encodeURIComponent(result.company_name)};path=/;max-age=600`;
            }
            router.replace(`/briefing/${result.session_id}`);
            return;
          } catch {
          }
        }

        const me = await getMe();

        if (me.role === "company") {
          router.replace("/dashboard");
        } else {
          const { sessions } = await getMySessions();
          const assignedSession = sessions.find((item) => item.assessment_id || item.invite_token);
          if (assignedSession?.company_name) {
            document.cookie = `simwork_company=${encodeURIComponent(assignedSession.company_name)};path=/;max-age=600`;
          }
          if (assignedSession) {
            router.replace(`/briefing/${assignedSession.session_id}`);
            return;
          }
          router.replace("/");
        }
      } catch {
        router.replace("/");
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
